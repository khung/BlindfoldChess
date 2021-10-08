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
    push_move
    draw_current_board

    Instance variables
    ------------------
    boardChanged
    """

    # Qt signal to indicate that the board has changed
    boardChanged = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.board = chess.Board()

    @pyqtSlot(str)
    def push_move(self, move: str) -> None:
        """
        Play the indicated move and update the UI.

        :param move: The chess move in Standard Algebraic Notation.
        """
        try:
            self.board.push_san(move)
        except ValueError:
            print("not a valid move")
            return
        self.draw_current_board()

    def draw_current_board(self):
        """Draw the current board."""
        self.boardChanged.emit(self._create_svg_uri(chess.svg.board(self.board)))

    @staticmethod
    def _create_svg_uri(svg_data: str):
        return "data:image/svg+xml;utf8," + svg_data


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
    sys.exit(app.exec())
