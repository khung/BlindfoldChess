import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.11

ApplicationWindow {
    id: appWindow
    visible: true
    minimumWidth: 640
    minimumHeight: 480
    title: "Blindfold Chess"

    menuBar: MenuBar {
        Menu {
            title: "&File"
            Action { text: "&New Game" }
            Action { text: "&Open Game..." }
            Action { text: "&Import FEN" }
            MenuSeparator { }
            Action { text: "&Save" }
            MenuSeparator { }
            Action { text: "E&xit" }
        }
        Menu {
            title: "&Edit"
            Action { text: "&Undo Move" }
        }
        Menu {
            title: "&Settings"
            Action { text: "&Options" }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20

        Image {
            id: boardImage
            Layout.alignment: Qt.AlignHCenter
            source: "assets/chessboard.png"
            state: "hidden"

            states: [
                State {
                    name: "hidden"
                    PropertyChanges { target: boardImage; opacity: 0 }
                },
                State {
                    name: "visible"
                    PropertyChanges { target: boardImage; opacity: 100 }
                }
            ]
        }

        Button {
            id: peekButton
            Layout.alignment: Qt.AlignHCenter
            text: "Peek at Board"
            onClicked: {
                if (boardImage.state == "hidden")
                    boardImage.state = "visible"
                else
                    boardImage.state = "hidden"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "Enter move:"
            }

            TextField {
                id: moveTextField
            }
        }
    }
}
