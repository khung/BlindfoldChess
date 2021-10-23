import pytest
import text_processing as tp


class TestTextProcessing:
    @pytest.fixture(scope="module")
    def grammars(self):
        return tp.create_grammar_structs()

    @pytest.mark.parametrize(
        "test_input_position,expected",
        [("a one", "a1"), ("b two", "b2"), ("c three", "c3"), ("d four", "d4"),
         ("e five", "e5"), ("f six", "f6"), ("g seven", "g7"), ("h eight", "h8")]
    )
    def test_text_to_move_basic(self, grammars, test_input_position, expected):
        test_input = "pawn to " + test_input_position
        assert tp.text_to_move(grammars, test_input) == expected

    @pytest.mark.parametrize(
        "test_input_piece,expected_notation",
        [("pawn", ""), ("bishop", "B"), ("knight", "N"), ("rook", "R"), ("queen", "Q"), ("king", "K")]
    )
    def test_text_to_move_pieces(self, grammars, test_input_piece, expected_notation):
        test_input = test_input_piece + " to a one"
        expected = expected_notation + "a1"
        assert tp.text_to_move(grammars, test_input) == expected

    def test_text_to_move_ra1_misspelling(self, grammars):
        text = "rook two a one"
        reference_output = "Ra1"
        assert tp.text_to_move(grammars, text) == reference_output

    def test_text_to_move_check(self, grammars):
        text = "bishop to f seven check"
        reference_output = "Bf7+"
        assert tp.text_to_move(grammars, text) == reference_output

    def test_text_to_move_checkmate(self, grammars):
        text = "bishop to f seven checkmate"
        reference_output = "Bf7#"
        assert tp.text_to_move(grammars, text) == reference_output

    def test_text_to_move_en_passant(self, grammars):
        text = "pawn a six to b seven"
        reference_output = "a6b7"
        assert tp.text_to_move(grammars, text) == reference_output

    def test_text_to_move_promotion(self, grammars):
        text = "pawn a seven to a eight promote to queen"
        reference_output = "a7a8=Q"
        assert tp.text_to_move(grammars, text) == reference_output

    def test_text_to_move_promotion_misspelling(self, grammars):
        text = "pawn a seven to a eight promote two queen"
        reference_output = "a7a8=Q"
        assert tp.text_to_move(grammars, text) == reference_output

    def test_text_to_move_complex(self, grammars):
        text = "pawn a seven to a eight promote to queen checkmate"
        reference_output = "a7a8=Q#"
        assert tp.text_to_move(grammars, text) == reference_output

    def test_text_to_move_castle_kingside(self, grammars):
        text = "castle king side"
        reference_output = "O-O"
        assert tp.text_to_move(grammars, text) == reference_output

    def test_text_to_move_castle_queenside(self, grammars):
        text = "castle queen side"
        reference_output = "O-O-O"
        assert tp.text_to_move(grammars, text) == reference_output

    def test_text_to_move_non_move(self, grammars):
        text = "i am bobby fischer"
        with pytest.raises(ValueError):
            tp.text_to_move(grammars, text)

    def test_text_to_move_repeated_words(self, grammars):
        text = "pawn pawn to c three"
        reference_output = "c3"
        assert tp.text_to_move(grammars, text) == reference_output

    @pytest.mark.parametrize(
        "test_input,expected_position",
        [("a1", "A one"), ("b2", "b two"), ("c3", "c three"), ("d4", "d four"),
         ("e5", "e five"), ("f6", "f six"), ("g7", "g seven"), ("h8", "h eight")]
    )
    def test_move_to_text_basic(self, grammars, test_input, expected_position):
        expected = "pawn to " + expected_position
        assert tp.move_to_text(grammars, test_input) == expected

    def test_move_to_text_row(self, grammars):
        text = "R1b2"
        reference_output = "rook one to b two"
        assert tp.move_to_text(grammars, text) == reference_output

    def test_move_to_text_column(self, grammars):
        text = "Rab2"
        reference_output = "rook A to b two"
        assert tp.move_to_text(grammars, text) == reference_output

    @pytest.mark.parametrize(
        "test_input_piece,expected_text",
        [("", "pawn"), ("B", "bishop"), ("N", "knight"), ("R", "rook"), ("Q", "queen"), ("K", "king")]
    )
    def test_move_to_text_pieces(self, grammars, test_input_piece, expected_text):
        test_input = test_input_piece + "a1"
        expected = expected_text + " to A one"
        assert tp.move_to_text(grammars, test_input) == expected

    def test_move_to_text_check(self, grammars):
        text = "Bf7+"
        reference_output = "bishop to f seven, check"
        assert tp.move_to_text(grammars, text) == reference_output

    def test_move_to_text_checkmate(self, grammars):
        text = "Bf7#"
        reference_output = "bishop to f seven, checkmate"
        assert tp.move_to_text(grammars, text) == reference_output

    def test_move_to_text_en_passant(self, grammars):
        text = "a6b7"
        reference_output = "pawn A six to b seven"
        assert tp.move_to_text(grammars, text) == reference_output

    def test_move_to_text_promotion(self, grammars):
        text = "a7a8=Q"
        reference_output = "pawn A seven to A eight, promote to queen"
        assert tp.move_to_text(grammars, text) == reference_output

    def test_move_to_text_complex(self, grammars):
        text = "a7a8=Q#"
        reference_output = "pawn A seven to A eight, promote to queen, checkmate"
        assert tp.move_to_text(grammars, text) == reference_output

    def test_move_to_text_castle_kingside(self, grammars):
        text = "O-O"
        reference_output = "castle king side"
        assert tp.move_to_text(grammars, text) == reference_output

    def test_move_to_text_castle_queenside(self, grammars):
        text = "O-O-O"
        reference_output = "castle queen side"
        assert tp.move_to_text(grammars, text) == reference_output

    def test_move_to_text_capture(self, grammars):
        text = "Rxd1"
        reference_output = "rook to d one"
        assert tp.move_to_text(grammars, text) == reference_output

    def test_move_to_text_non_move(self, grammars):
        text = "aaa"
        with pytest.raises(ValueError):
            tp.move_to_text(grammars, text)
