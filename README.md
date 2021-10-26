# Blindfold Chess

Blindfold Chess is a chess game that allows the user to play without being
able to see the board. Chess moves can be made through speaking or typing.

## Prerequisites
* Python 3.7+
* Windows, Linux, macOS
* Python packages:
  * chess
  * PyQt5
  * pyttsx3
  * vosk

## Usage

### Playing

Launch the program through the command line:

`> python BlindfoldChess.py`

On the New Game screen, choose whether to play as black or white.

![Player side selection](/doc/new_game.png)

Enter your move under *Your move*. To speak your move instead, press the
microphone button to start recording and press it again to stop. Press Enter
to play your move.

![Player move input](/doc/player_move.png)

The move must be in [Standard Algebraic Notation](https://www.chessprogramming.org/Algebraic_Chess_Notation).
Calling check or checkmate is optional, but the program will tell the user if
they are incorrect in their call. If speaking, the piece must be stated as
well as the origin square, if that is ambiguous. Example moves and their
spoken equivalents:

* e4: pawn to e four
* Kxg1: king to g one
* R1h6: rook h one to h six
* gxf7 (en passant): pawn g six to f seven
* f8=Q: pawn f eight promote to queen
* Nc2+: knight c two check
* Qh4#: queen h four checkmate
* O-O: castle kingside

The player's move will be displayed for 5 seconds before disappearing.
Similarly, the engine's move will show for only 5 seconds.

To look at the board, click on the **Peek at board** button. Click on it again
to hide the board.

![Peeking](/doc/peek.png)

### Saving and loading

To save a game in progress, go to *File* > *Save*. To load a saved game, go
to *File* > *Open Game*. Only one game can be saved at any time.

### Undo

To undo your move, go to *Edit* > *Undo Move*. This is only be available
during the player's turn and will undo the player's last move.

### Options

* Engine path: The path to the chess engine to use. Any chess engine using
the UCI protocol should be supported.
* Engine search depth: How deep the chess engine should look when considering
its move.
* Automatically play spoken move: If checked, a spoken move will be
played automatically without the user having to press Enter.

## Troubleshooting

### Speech recognition of moves does not work

The program uses the default microphone input. Check that the default input
is set correctly in your OS.

### Audio does not work

The program uses the default audio output. Check that the default output is
set correctly in your OS.