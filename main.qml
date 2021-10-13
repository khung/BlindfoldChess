import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.11
import QtQuick.Dialogs 1.3

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
            Action {
                text: "&Options"
                onTriggered: optionsDialog.open()
            }
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

    Dialog {
        id: optionsDialog
        title: "Options"
        GridLayout {
            columns: 2
            Label { text: "Engine Path" }
            TextField {
                id: enginePathField;
                Layout.fillWidth: true;
            }
        }
        standardButtons: Dialog.Save | Dialog.Cancel
        onAccepted: {
            var options = {
                'enginePath': enginePathField.text
            };
            backend.save_options(options);
        }
    }

    MessageDialog {
        id: errorMessageDialog
        title: "Error"
        icon: StandardIcon.Critical
    }

    // Connect to signal for updating the board.
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
    Connections {
        target: backend
        function onError(message) {
            errorMessageDialog.text = message;
            errorMessageDialog.open();
        }
    }
    // Connect to signal that indicates the options have changed.
    Connections {
        target: backend
        function onOptionsChanged(options) {
            enginePathField.text = options['enginePath']
        }
    }
}
