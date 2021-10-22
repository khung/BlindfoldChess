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
