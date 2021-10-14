import sys
from typing import Callable
import configparser

from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQml import QQmlApplicationEngine
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable, QThreadPool, QVariant
import chess
import chess.engine
import chess.svg


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

    Instance variables
    ------------------
    player_side
    config
    """

    # Qt signals
    # Indicate that the board has changed
    boardChanged = pyqtSignal(str)
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

    config_file = "options.cfg"
    save_file = "save.fen"

    def __init__(self) -> None:
        super().__init__()
        # Connect signals
        self.engineTurn.connect(self.engine_play)
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
            print("not a valid move")
            return
        self.draw_current_board()
        self._update_board_status()
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
        self._board.push(move)
        self.draw_current_board()
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

    def _update_board_status(self) -> None:
        outcome = self._board.outcome()
        if outcome is not None:
            self.gameOver.emit(self._get_outcome_message(outcome))
        elif self._board.is_check():
            print("in check")

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
        """Clean up by stopping the engine. Connect to QGuiApplication.aboutToQuit signal to handle exits correctly."""
        if self._engine:
            self._engine.quit()

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
        with open(self.config_file, 'w') as f:
            self.config.write(f)
        self.initialize_engine()

    def set_option_values(self) -> None:
        """Populate the initial dialog values for the options."""
        options_dict = {
            'enginePath': self.config['OPTIONS'].get('EnginePath'),
            'engineSearchDepth': int(self.config['OPTIONS'].get('EngineSearchDepth')),
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
