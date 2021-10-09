import sys
from typing import Callable

from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQml import QQmlApplicationEngine
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable, QThreadPool
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

    Instance variables
    ------------------
    player_side
    engine_time_limit
    """

    # Qt signal to indicate that the board has changed
    boardChanged = pyqtSignal(str)
    # Qt signals to indicate whose turn it is
    playerTurn = pyqtSignal()
    engineTurn = pyqtSignal()
    gameOver = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        # Connect signals
        self.engineTurn.connect(self.engine_play)
        self.player_side = chess.WHITE
        self._board = chess.Board()
        engine_path = r"C:\Users\Kevin Hung\Documents\stockfish_13_win_x64_bmi2.exe"
        # Use the synchronous wrapper instead of the coroutines to avoid having to deal with an asyncio event loop in
        # Qt.
        self._engine = chess.engine.SimpleEngine.popen_uci(engine_path)
        self.engine_time_limit = 10.0
        self._thread_pool = QThreadPool()

    @pyqtSlot()
    def engine_play(self) -> None:
        """Have the engine think about and make its move."""
        worker = Worker(self._get_engine_move)
        worker.signals.result.connect(self._push_engine_move)
        self._thread_pool.start(worker)

    @pyqtSlot(str)
    def push_player_move(self, move: str) -> None:
        """
        Play the indicated player's move and update the UI.

        :param move: The chess move in Standard Algebraic Notation.
        """
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
        result = self._engine.play(self._board, chess.engine.Limit(time=self.engine_time_limit))
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
            print("outcome: " + outcome.termination.name)
            self.gameOver.emit(outcome.termination.name)
        elif self._board.is_check():
            print("in check")

    @pyqtSlot()
    def handle_exit(self) -> None:
        """Clean up by stopping the engine. Connect to QGuiApplication.aboutToQuit signal to handle exits correctly."""
        self._engine.quit()


if __name__ == '__main__':
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    # Allow access to signals/slots in Main class to QML.
    backend = Backend()
    engine.rootContext().setContextProperty('backend', backend)
    engine.load('main.qml')
    # We need to draw this outside the initialization so the signals can be connected to the slots first.
    backend.draw_current_board()
    engine.quit.connect(app.quit)
    # Need to connect to app instead of to engine for the slot to work
    app.aboutToQuit.connect(backend.handle_exit)
    sys.exit(app.exec())
