import sys
from typing import Callable
import configparser
from tempfile import gettempdir
import os.path
import wave
import json
import queue

from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQml import QQmlApplicationEngine
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable, QThreadPool, QVariant, QUrl
from PyQt5.QtMultimedia import QAudioRecorder, QAudioEncoderSettings, QVideoEncoderSettings, QSound
import chess
import chess.engine
import chess.svg
from vosk import Model, KaldiRecognizer, SetLogLevel
import pyttsx3

from text_processing import create_grammar_structs, text_to_move, move_to_text


class WorkerSignals(QObject):
    """
    Define signals available for worker thread.
    """
    result = pyqtSignal(object)


class Worker(QRunnable):
    """
    Worker thread for doing multi-threading in Qt.

    Public methods
    --------------
    run
    """

    def __init__(self, fn: Callable, *args, **kwargs) -> None:
        """
        :param fn: Function to run.
        :param args: Arguments for the function.
        :param kwargs: Keyword arguments for the function.
        """
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self) -> None:
        """Run the specified function and return the result as a Qt signal."""
        result = self.fn(*self.args, **self.kwargs)
        # If the result is None, we assume that the program is exiting so we don't try to emit any signals in case
        # the signal C++ class has already been deleted by Qt. If this is not done, a RuntimeError exception may be
        # raised: "wrapped C/C++ object of type WorkerSignals has been deleted".
        if result is not None:
            self.signals.result.emit(result)


class Backend(QObject):
    """
    Backend for handling application logic.

    Public methods
    --------------
    engine_play
    push_player_move
    draw_current_board
    handle_exit
    is_engine_initialized
    initialize_engine
    save_options
    set_option_values
    reset_game
    undo_move
    can_undo_move
    save_game
    load_game
    start_recording
    stop_recording
    is_speech_recognizer_initialized
    say_text

    Instance variables
    ------------------
    player_side
    config
    """

    # Qt signals
    # Indicate that the board has changed
    boardChanged = pyqtSignal(str)
    # The move and whether to automatically play it
    playerMove = pyqtSignal(str, bool)
    engineMove = pyqtSignal(str)
    # Indicate that the options have changed
    optionsChanged = pyqtSignal(QVariant)
    # Indicate whose turn it is
    playerTurn = pyqtSignal()
    engineTurn = pyqtSignal()
    # Indicate whether the game is over
    gameOver = pyqtSignal(str)
    # Indicate that an error has occurred
    error = pyqtSignal(str)
    # Indicate whether moves can be undone
    undoEnabled = pyqtSignal(bool)
    # Indicate that the microphone input widget should be enabled
    micAvailable = pyqtSignal()
    # Indicate that a sound effect should be played
    playSoundEffect = pyqtSignal()

    config_file = "options.cfg"
    save_file = "save.fen"
    temp_file = os.path.join(gettempdir(), "user_move.wav")
    audio_sample_rate = 44100
    grammars = create_grammar_structs()

    def __init__(self) -> None:
        super().__init__()
        # Connect signals
        self.engineTurn.connect(self.engine_play)
        self.playSoundEffect.connect(self._play_sound)
        self.player_side = chess.WHITE
        self._board = chess.Board()
        self.config = configparser.ConfigParser()
        # ConfigParser instance will be empty if the file doesn't exist
        self.config.read([self.config_file])
        self._set_config_defaults()
        self._engine = None
        self.initialize_engine()
        self._thread_pool = QThreadPool()
        # Keep track of the current game's ID so that the engine will know whether it's the same game as before.
        self._game_id = 1
        self._audio_recorder = QAudioRecorder()
        self._audio_recorder.setAudioInput(self._audio_recorder.audioInput())
        self._audio_recorder.setOutputLocation(QUrl.fromLocalFile(self.temp_file))
        # Need to set audio recording to use 16khz 16-bit mono PCM
        audio_settings = QAudioEncoderSettings()
        supported_codecs = self._audio_recorder.supportedAudioCodecs()
        if 'audio/pcm' in supported_codecs:
            # Windows
            codec = 'audio/pcm'
        elif 'audio/x-raw' in supported_codecs:
            # Linux (GStreamer backend)
            codec = 'audio/x-raw'
        else:
            codec = None
        audio_settings.setCodec(codec)
        audio_settings.setChannelCount(1)
        audio_settings.setSampleRate(self.audio_sample_rate)
        self._audio_recorder.setEncodingSettings(audio_settings, QVideoEncoderSettings(), 'audio/x-wav')
        self._speech_recognizer = None
        # Initialize speech recognizer in a separate thread to prevent blocking of the GUI.
        worker = Worker(self._init_speech_recognizer)
        worker.signals.result.connect(self._assign_speech_recognizer)
        self._thread_pool.start(worker)
        # Use producer/consumer model to run a separate event loop for TTS
        self._tts_queue = queue.SimpleQueue()
        self._tts_engine = None
        self._start_tts_engine()
        self._stop_work = False
        # Create sound effect to play
        self._chess_move_sound = QSound("assets/chessmove.wav")

    @pyqtSlot()
    def engine_play(self) -> None:
        """Have the engine think about and make its move."""
        if not self.is_engine_initialized():
            return
        worker = Worker(self._get_engine_move)
        worker.signals.result.connect(self._push_engine_move)
        self._thread_pool.start(worker)

    @pyqtSlot(str)
    def push_player_move(self, move: str) -> None:
        """
        Play the indicated player's move and update the UI.

        :param move: The chess move in Standard Algebraic Notation.
        """
        if not self.is_engine_initialized():
            return
        try:
            self._board.push_san(move)
        except ValueError:
            self.error.emit("That is not a valid move.")
            return
        self.draw_current_board()
        self.playSoundEffect.emit()
        self._update_board_status(
            check_called=self._move_includes_check(move),
            checkmate_called=self._move_includes_checkmate(move)
        )
        # Only continue game if it is not terminated
        if self._board.outcome() is None:
            self.engineTurn.emit()

    def _get_engine_move(self) -> chess.Move:
        result = self._engine.play(
            self._board,
            chess.engine.Limit(depth=self.config['OPTIONS'].getint('EngineSearchDepth')),
            game=self._game_id
        )
        return result.move

    @pyqtSlot(object)
    def _push_engine_move(self, move: chess.Move) -> None:
        """
        Play the indicated engine's move and update the UI. No need to check legality of the move as the engine should
        always return a legal move given a correctly-defined board.

        :param move: The chess move given by chess.engine.PlayResult.move.
        """
        # Get the SAN move first as it relies on the board before the move
        san_move = self._board.san(move)
        self.engineMove.emit(san_move)
        try:
            text = move_to_text(self.grammars, san_move)
        except ValueError as err:
            text = ""
            self.error.emit(f"TTS error: {err}")
        self._board.push(move)
        self.draw_current_board()
        # Make sure that sound effect is played before TTS, otherwise the audio will overlap.
        self.playSoundEffect.emit()
        self.say_text(text)
        self._update_board_status()
        self.undoEnabled.emit(self.can_undo_move())
        # Only continue game if it is not terminated
        if self._board.outcome() is None:
            self.playerTurn.emit()

    def draw_current_board(self):
        """Draw the current board."""
        self.boardChanged.emit(self._create_svg_uri(chess.svg.board(self._board)))

    @staticmethod
    def _create_svg_uri(svg_data: str):
        return "data:image/svg+xml;utf8," + svg_data

    def _update_board_status(self, check_called: bool = False, checkmate_called: bool = False) -> None:
        outcome = self._board.outcome()
        if outcome is not None:
            try:
                outcome_message = self._get_outcome_message(outcome)
            except ValueError as err:
                outcome_message = "Error: " + str(err)
            self.gameOver.emit(outcome_message)
        # Say something when check state is different from what's passed in. Only need to check on player's move since
        # the engine's move will always include the appropriate state.
        if self._board.turn != self.player_side:
            if check_called and not self._board.is_check():
                self.say_text("My king is not in check.")
            if not check_called and self._board.is_check():
                self.say_text("My king is in check.")
            if checkmate_called and not self._board.is_checkmate():
                self.say_text("My king is not checkmated.")
            if not checkmate_called and self._board.is_checkmate():
                self.say_text("My king is checkmated.")

    @staticmethod
    def _get_outcome_message(outcome: chess.Outcome) -> str:
        if outcome is None:
            outcome_message = "Game in progress."
        else:
            if outcome.termination is chess.Termination.CHECKMATE:
                if outcome.winner:
                    outcome_message = "White has won by "
                else:
                    outcome_message = "Black has won by "
                outcome_message += "checkmate."
            elif outcome.termination is chess.Termination.STALEMATE:
                outcome_message = "The game has ended in a draw due to a stalemate."
            elif outcome.termination is chess.Termination.INSUFFICIENT_MATERIAL:
                outcome_message = "The game has ended in a draw due to insufficient material."
            elif outcome.termination is chess.Termination.SEVENTYFIVE_MOVES:
                outcome_message = "The game has ended in a draw due to the seventy-five-move rule."
            elif outcome.termination is chess.Termination.FIVEFOLD_REPETITION:
                outcome_message = "The game has ended in a draw due to the fivefold repetition rule."
            elif outcome.termination is chess.Termination.FIFTY_MOVES:
                # Not required to draw
                outcome_message = "The game has ended in a draw due to the fifty-move rule."
            elif outcome.termination is chess.Termination.THREEFOLD_REPETITION:
                # Not required to draw
                outcome_message = "The game has ended in a draw due to the threefold repetition rule."
            else:
                raise ValueError(f"{outcome.termination.name} case not handled!")
        return outcome_message

    @pyqtSlot()
    def handle_exit(self) -> None:
        """Clean up before exiting. Connect to QGuiApplication.aboutToQuit signal to handle exits correctly."""
        # Stop the chess engine
        if self._engine:
            self._engine.quit()
        # Delete temporary file
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)
        # Stop worker threads
        self._stop_work = True

    def is_engine_initialized(self) -> bool:
        """Check whether the engine has been initialized."""
        if self._engine is None:
            self.error.emit("Engine path is not valid. Please check the value in the options.")
            return False
        return True

    def initialize_engine(self) -> None:
        """Initialize the chess engine. If an instance already exists, stop it first."""
        if self._engine:
            self._engine.quit()
        self._engine = None
        if self.config.get('OPTIONS', 'EnginePath') != "":
            try:
                # Use the synchronous wrapper instead of the coroutines to avoid having to deal with an asyncio event
                # loop in Qt.
                self._engine = chess.engine.SimpleEngine.popen_uci(self.config['OPTIONS'].get('EnginePath'))
            except FileNotFoundError:
                # Silently fail
                pass

    @pyqtSlot(QVariant)
    def save_options(self, options: QVariant) -> None:
        """
        Save current options to the configuration file.

        :param options: A dictionary of the options.
        """
        # Convert to Python dict
        options_dict = options.toVariant()
        self.config.set('OPTIONS', 'EnginePath', options_dict['enginePath'])
        self.config.set('OPTIONS', 'EngineSearchDepth', options_dict['engineSearchDepth'])
        self.config.set('OPTIONS', 'PlaySpokenMove', options_dict['playSpokenMove'])
        with open(self.config_file, 'w') as f:
            self.config.write(f)
        self.initialize_engine()

    @pyqtSlot()
    def set_option_values(self) -> None:
        """Populate the initial dialog values for the options."""
        options_dict = {
            'enginePath': self.config['OPTIONS'].get('EnginePath'),
            'engineSearchDepth': int(self.config['OPTIONS'].get('EngineSearchDepth')),
            'playSpokenMove': self.config['OPTIONS'].get('PlaySpokenMove') == 'true'
        }
        self.optionsChanged.emit(options_dict)

    @pyqtSlot(str)
    def reset_game(self, player_side: str) -> None:
        """Reset the game. Assumes that it is the player's turn as there is no well-define way to stop a running
        engine."""
        self._board.reset()
        self.draw_current_board()
        # Reset undo
        self.undoEnabled.emit(False)
        # Use a new game ID
        self._game_id += 1
        if player_side == 'White':
            # Set to player's turn
            self.player_side = chess.WHITE
            self.playerTurn.emit()
        else:
            # Set to engine's turn
            self.player_side = chess.BLACK
            self.engineTurn.emit()

    @pyqtSlot()
    def undo_move(self) -> None:
        """Undo the player's last move."""
        if self._board.turn == self.player_side:
            # Remove engine's move
            self._board.pop()
        # Remove player's move
        self._board.pop()
        # Update board display
        self.draw_current_board()
        # Check if we can still undo
        self.undoEnabled.emit(self.can_undo_move())
        # Ensure that it's the player's turn
        self.playerTurn.emit()

    def can_undo_move(self) -> bool:
        """Checks whether the player can undo moves."""
        # Can only undo if there a player move to undo. Don't use fullmove_number as that can be changed when a FEN
        # is loaded.
        if self._board.turn == self.player_side:
            # 2 or more half-moves on stack
            can_undo = len(self._board.move_stack) > 1
        else:
            # 3 or more half-moves on stack
            can_undo = len(self._board.move_stack) > 2
        return can_undo

    @pyqtSlot()
    def save_game(self) -> None:
        """Save the game as a FEN to a file."""
        with open(self.save_file, 'w') as f:
            f.write(self._board.fen())

    @pyqtSlot()
    def load_game(self) -> None:
        """Load the game from a file containing a FEN."""
        board_set = False
        try:
            with open(self.save_file) as f:
                self._board.set_fen(f.readline())
            board_set = True
        except FileNotFoundError:
            self.error.emit("No save file found.")
        if board_set:
            # Use a new game ID
            self._game_id += 1
            self.draw_current_board()
            # Check if we can still undo
            self.undoEnabled.emit(self.can_undo_move())
            # Set the player to be the correct color
            self.player_side = self._board.turn
            # Change to player's turn
            self.playerTurn.emit()

    def _set_config_defaults(self) -> None:
        """Set defaults in one place so that they don't have to be defined in every get call."""
        if not self.config.has_section('OPTIONS'):
            self.config.add_section('OPTIONS')
        if not self.config.has_option('OPTIONS', 'EnginePath'):
            self.config.set('OPTIONS', 'EnginePath', '')
        if not self.config.has_option('OPTIONS', 'EngineSearchDepth'):
            self.config.set('OPTIONS', 'EngineSearchDepth', '20')
        if not self.config.has_option('OPTIONS', 'PlaySpokenMove'):
            self.config.set('OPTIONS', 'PlaySpokenMove', 'True')

    @pyqtSlot()
    def start_recording(self) -> None:
        """Start recording microphone input for player's move."""
        if not self.is_speech_recognizer_initialized():
            return
        self._audio_recorder.record()

    @pyqtSlot()
    def stop_recording(self) -> None:
        """Stop recording the microphone input and parse recorded move."""
        self._audio_recorder.stop()
        # Stop is synchronous so media is finalized already
        waveform = wave.open(self.temp_file, 'rb')
        # Parse every X frames for words
        while True:
            data = waveform.readframes(4000)
            if len(data) == 0:
                break
            self._speech_recognizer.AcceptWaveform(data)
        # FinalResult is returned as a string even though it's a JSON dictionary
        result = json.loads(self._speech_recognizer.FinalResult())
        try:
            move = text_to_move(self.grammars, result['text'])
        except ValueError as err:
            move = "ERROR"
        self.playerMove.emit(move, self.config['OPTIONS'].getboolean('PlaySpokenMove'))

    def _init_speech_recognizer(self) -> KaldiRecognizer:
        # Default log level 0 shows info messages
        SetLogLevel(-1)
        model = Model("model")
        # Limit the possible vocabulary to chess terms and the UNK token. May not be the best way to do this, but we
        # can use the provided model as-is.
        grammar = '["' \
                  + 'pawn bishop knight rook queen king ' \
                  + 'a b c d e f g h ' \
                  + 'one two three four five six seven eight ' \
                  + 'to promote check checkmate castle side ' \
                  + '", "[unk]"]'
        speech_recognizer = KaldiRecognizer(model, self.audio_sample_rate, grammar)
        # Show result metadata when returning results for debugging purposes
        speech_recognizer.SetWords(True)
        return speech_recognizer

    @pyqtSlot(object)
    def _assign_speech_recognizer(self, recognizer: KaldiRecognizer) -> None:
        self._speech_recognizer = recognizer
        # Microphone input is now usable
        self.micAvailable.emit()

    def is_speech_recognizer_initialized(self) -> bool:
        """Check whether the speech recognizer has been initialized."""
        if self._speech_recognizer is None:
            self.error.emit("Speech recognizer has not finished initializing.")
            return False
        return True

    def say_text(self, text: str) -> None:
        """
        Use the TTS engine to say a block of text.

        :param text: The text to convert to speech.
        """
        self._tts_queue.put(text)

    def _start_tts_engine(self) -> None:
        self._tts_engine = pyttsx3.init()
        # Set word rate to 150 words/sec (on the slower end of normal)
        self._tts_engine.setProperty('rate', 150)
        # Launch TTS event loop in a new thread
        worker = Worker(self._tts_event_loop)
        self._thread_pool.start(worker)

    def _tts_event_loop(self) -> None:
        while not self._stop_work:
            # Blocks for 100 ms waiting for an available item
            try:
                text = self._tts_queue.get(timeout=.1)
            except queue.Empty:
                text = ""
            if text != "":
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()

    @staticmethod
    def _move_includes_check(move: str) -> bool:
        return move.endswith('+')

    @staticmethod
    def _move_includes_checkmate(move: str) -> bool:
        return move.endswith('#')

    @pyqtSlot()
    def _play_sound(self) -> None:
        # Ideally, this would be part of the QML code, but QML on PyQt seems to have issues importing QtMultimedia.
        self._chess_move_sound.play()


if __name__ == '__main__':
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    # Allow access to signals/slots in Main class to QML.
    backend = Backend()
    engine.rootContext().setContextProperty('backend', backend)
    engine.load('main.qml')
    # We need to draw this outside the initialization so the signals can be connected to the slots first.
    backend.draw_current_board()
    backend.set_option_values()
    engine.quit.connect(app.quit)
    # Need to connect to app instead of to engine for the slot to work
    app.aboutToQuit.connect(backend.handle_exit)
    sys.exit(app.exec())
