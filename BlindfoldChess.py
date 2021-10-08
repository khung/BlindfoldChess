import sys

from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQml import QQmlApplicationEngine
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
import chess
import chess.engine
import chess.svg


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
    boardChanged
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
        self.board = chess.Board()
        engine_path = r"C:\Users\Kevin Hung\Documents\stockfish_13_win_x64_bmi2.exe"
        self.engine = chess.engine.SimpleEngine.popen_uci(engine_path)

    @pyqtSlot()
    def engine_play(self) -> None:
        """Have the engine think about and make its move."""
        # This will hang the GUI as it runs in the same thread, but multithreading this is not trivial so we skip it
        # for now and just limit the engine to 1 second.
        result = self.engine.play(self.board, chess.engine.Limit(time=1.0))
        self._push_engine_move(result.move)

    @pyqtSlot(str)
    def push_player_move(self, move: str) -> None:
        """
        Play the indicated player's move and update the UI.

        :param move: The chess move in Standard Algebraic Notation.
        """
        try:
            self.board.push_san(move)
        except ValueError:
            print("not a valid move")
            return
        self.draw_current_board()
        self._update_board_status()
        # Only continue game if it is not terminated
        if self.board.outcome() is None:
            self.engineTurn.emit()

    def _push_engine_move(self, move: chess.Move) -> None:
        """
        Play the indicated engine's move and update the UI. No need to check legality of the move as the engine should
        always return a legal move given a correctly-defined board.

        :param move: The chess move given by chess.engine.PlayResult.move.
        """
        self.board.push(move)
        self.draw_current_board()
        self._update_board_status()
        # Only continue game if it is not terminated
        if self.board.outcome() is None:
            self.playerTurn.emit()

    def draw_current_board(self):
        """Draw the current board."""
        self.boardChanged.emit(self._create_svg_uri(chess.svg.board(self.board)))

    @staticmethod
    def _create_svg_uri(svg_data: str):
        return "data:image/svg+xml;utf8," + svg_data

    def _update_board_status(self) -> None:
        outcome = self.board.outcome()
        if outcome is not None:
            print("outcome: " + outcome.termination.name)
            self.gameOver.emit(outcome.termination.name)
        elif self.board.is_check():
            print("in check")

    @pyqtSlot()
    def handle_exit(self) -> None:
        """Clean up by stopping the engine. Connect to QGuiApplication.aboutToQuit signal to handle exits correctly."""
        self.engine.quit()


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
