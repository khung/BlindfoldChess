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
            Action {
                id: newAction
                text: "&New Game"
                onTriggered: newDialog.open()
            }
            Action {
                id: loadAction
                text: "&Open Game"
                onTriggered: backend.load_game()
            }
            MenuSeparator { }
            Action {
                id: saveAction
                text: "&Save"
                enabled: false
                onTriggered: backend.save_game()
            }
            MenuSeparator { }
            Action {
                text: "E&xit"
                onTriggered: Qt.quit()
            }
        }
        Menu {
            title: "&Edit"
            Action {
                id: undoAction
                text: "&Undo Move"
                enabled: false
                onTriggered: backend.undo_move()
            }
        }
        Menu {
            title: "&Settings"
            Action {
                text: "&Options"
                onTriggered: {
                    // Reset the options to the saved values to clear any unsaved changes
                    backend.set_option_values();
                    optionsDialog.open();
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20

        Image {
            id: boardImage
            Layout.alignment: Qt.AlignHCenter
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
            spacing: 20
            // Player input
            RowLayout {
                Label {
                    text: "Your move:"
                }
                Button {
                    id: micButton
                    // Make it square
                    Layout.preferredWidth: parent.height
                    // Wait for speech recognizer to be initialized first
                    enabled: false
                    property bool available: false
                    state: "off"
                    states: [
                        State {
                            name: "on"
                            PropertyChanges { target: micButton; icon.source: "assets/mic_on.png" }
                        },
                        State {
                            name: "off"
                            PropertyChanges { target: micButton; icon.source: "assets/mic_off.png" }
                        }
                    ]
                    onClicked: {
                        if (micButton.state == "off") {
                            micButton.state = "on";
                            backend.start_recording();
                        }
                        else {
                            micButton.state = "off";
                            backend.stop_recording();
                        }
                    }
                }
                TextField {
                    id: moveTextField
                    implicitWidth: 100
                    enabled: false
                    onAccepted: {
                        backend.push_player_move(moveTextField.text);
                        playerMoveTimer.running = true;
                    }
                }
            }
            BusyIndicator {
                id: busyIndicator
                running: false
            }
            // Engine output
            RowLayout {
                Label {
                    text: "Computer move:"
                }
                Label {
                    id: engineMove
                    text: ""
                }
            }
        }
    }

    // Display player move for only a certain time
    Timer {
        id: playerMoveTimer
        interval: 5000
        onTriggered: moveTextField.clear()
    }

    // Display engine move for only a certain time
    Timer {
        id: engineMoveTimer
        interval: 5000
        onTriggered: engineMove.text = ""
    }

    Dialog {
        id: newDialog
        title: "New Game"
        // Show on application start (don't set immediately as it will not position correctly)
        Component.onCompleted: newDialog.visible = true

        ButtonGroup {
            id: playerSideButtonGroup
            buttons: playerSideRow.children
        }

        GridLayout {
            columns: 2
            Label { text: "Player side:" }
            RowLayout {
                id: playerSideRow

                RadioButton { text: "White";  }
                RadioButton { text: "Black" }
            }
        }
        standardButtons: Dialog.Ok | Dialog.Cancel
        onActionChosen: {
            if (action.button === Dialog.Ok) {
                // If no side was chosen, don't accept.
                if (playerSideButtonGroup.checkedButton === null) {
                    action.accepted = false;
                }
            }
        }
        onAccepted: {
            backend.reset_game(playerSideButtonGroup.checkedButton.text);
            playerSideButtonGroup.checkState = Qt.Unchecked;
        }
        onRejected: {
            // Make sure the state is cleared for the next time
            playerSideButtonGroup.checkState = Qt.Unchecked;
        }
    }

    Dialog {
        id: optionsDialog
        title: "Options"
        GridLayout {
            columns: 2
            // EnginePath
            Label { text: "Engine path" }
            TextField {
                id: enginePathField
                Layout.fillWidth: true
            }
            // EngineSearchDepth
            Label { text: "Engine search depth" }
            SpinBox {
                id: engineSearchDepthSpinBox
                Layout.fillWidth: true
                from: 5
                to: 30
            }
            // PlaySpokenMove
            Label { text: "Automatically play spoken move" }
            CheckBox {
                id: playSpokenMoveCheckBox
                Layout.fillWidth: true
            }
        }
        standardButtons: Dialog.Save | Dialog.Cancel
        onAccepted: {
            var options = {
                'enginePath': enginePathField.text,
                'engineSearchDepth': String(engineSearchDepthSpinBox.value),
                'playSpokenMove': String(playSpokenMoveCheckBox.checked),
            };
            backend.save_options(options);
        }
    }

    MessageDialog {
        id: errorMessageDialog
        title: "Error"
        icon: StandardIcon.Critical
    }

    MessageDialog {
        id: outcomeMessageDialog
        title: "Outcome"
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
            // Enable menu items
            newAction.enabled = true;
            loadAction.enabled = true;
            saveAction.enabled = true;

            moveTextField.clear();
            moveTextField.enabled = true;
            if (micButton.available)
                micButton.enabled = true;
            busyIndicator.running = false;
        }
    }
    Connections {
        target: backend
        function onEngineTurn() {
            // Disable menu items
            newAction.enabled = false;
            loadAction.enabled = false;
            saveAction.enabled = false;

            moveTextField.enabled = false;
            engineMove.text = "";
            micButton.enabled = false;
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
            enginePathField.text = options['enginePath'];
            engineSearchDepthSpinBox.value = options['engineSearchDepth'];
            playSpokenMoveCheckBox.checked = options['playSpokenMove'];
        }
    }
    Connections {
        target: backend
        function onUndoEnabled(enabled) {
            undoAction.enabled = enabled
        }
    }
    Connections {
        target: backend
        function onGameOver(message) {
            // Set widget states for a terminated game
            newAction.enabled = true;
            loadAction.enabled = true;
            // Don't save finished games
            saveAction.enabled = false;
            moveTextField.enabled = false;
            busyIndicator.running = false;

            outcomeMessageDialog.text = message;
            outcomeMessageDialog.open();
        }
    }
    Connections {
        target: backend
        function onPlayerMove(move, playMove) {
            moveTextField.text = move;
            moveTextField.focus = true;
            if (playMove) {
                moveTextField.accepted();
            }
        }
    }
    Connections {
        target: backend
        function onEngineMove(move) {
            engineMove.text = move;
            engineMoveTimer.running = true;
        }
    }
    Connections {
        target: backend
        function onMicAvailable() {
            micButton.available = true;
            if (moveTextField.enabled)
                micButton.enabled = true;
        }
    }
}
