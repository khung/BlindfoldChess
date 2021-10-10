import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.11

ApplicationWindow {
    id: appWindow
    visible: true
    minimumWidth: 800
    minimumHeight: 600
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
            state: "visible"

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

            BusyIndicator {
                id: busyIndicator
                anchors.centerIn: parent
                running: false
            }
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
                onAccepted: {
                    backend.push_player_move(moveTextField.text);
                    moveTextField.clear();
                }
            }
        }
    }

    // Connect to signal for updating the board
    Connections {
        target: backend
        function onBoardChanged(board) {
            boardImage.source = board;
        }
    }
    Connections {
        target: backend
        function onPlayerTurn() {
            moveTextField.enabled = true;
            busyIndicator.running = false;
        }
    }
    Connections {
        target: backend
        function onEngineTurn() {
            moveTextField.enabled = false;
            busyIndicator.running = true;
        }
    }
}
