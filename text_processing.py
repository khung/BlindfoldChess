def create_grammar_structs() -> dict:
    """
    Create a grammar structure so that natural language can be parsed.

    :return: A dictionary of all grammars.
    """
    # The formal grammar:
    # ((pawn | bishop | knight | rook | queen | king) [A1 | ... | H8] [to] (A1 | ... | H8)
    #   [promote to (bishop | rook | knight | queen)] [check | checkmate]
    # | castle (king side | queen side) [check | checkmate])
    # We ignore the taking notation, as the engine does not care. En passant is covered by the regular movement.
    positions = []
    position_notation = []
    # To and two sound very similar so a transcription can be either
    rows = ["one", "two", "to", "three", "four", "five", "six", "seven", "eight"]
    row_notation = ["1", "2", "2", "3", "4", "5", "6", "7", "8"]
    columns = ["a", "b", "c", "d", "e", "f", "g", "h"]
    for column in columns:
        for i in range(len(rows)):
            positions.append(f"{column} {rows[i]}")
            position_notation.append(f"{column}{row_notation[i]}")
    # Add a token to add the word 'to' where necessary
    positions_tts = ["[TO ]" + position for position in positions]
    #
    grammars = {
        'regular_grammar': [
            _grammar_dict_item('pieces', True, [], ["pawn", "bishop", "knight", "rook", "queen", "king"],
                                       ["", "B", "N", "R", "Q", "K"]),
            _grammar_dict_item('position_1', True, [], positions, position_notation),
            _grammar_dict_item('position_2', False, [], positions, position_notation),
            # Same to/two confusion here
            _grammar_dict_item('promotion', False, [1], ["promote to", "promote two"], ["=", "="]),
            _grammar_dict_item('promotion_piece', False, [], ["bishop", "rook", "knight", "queen"],
                                       ["B", "R", "N", "Q"]),
            _grammar_dict_item('check', False, [], ["check"], ["+"]),
            _grammar_dict_item('checkmate', False, [], ["checkmate"], ["#"]),
        ],
        'castle_grammar': [
            _grammar_dict_item('castle', True, [1], ["castle"], [""]),
            _grammar_dict_item('castle_side', False, [], ["king side", "queen side"], ["O-O", "O-O-O"]),
            _grammar_dict_item('check', False, [], ["check"], ["+"]),
            _grammar_dict_item('checkmate', False, [], ["checkmate"], ["#"]),
        ],
        'regular_grammar_tts': [
            # Go from most specific position notation to least
            _grammar_dict_item('pieces', False, [], ["bishop", "knight", "rook", "queen", "king", "pawn"],
                               ["B", "N", "R", "Q", "K", ""]),
            # We ignore capture notation
            _grammar_dict_item('capture_1', False, [], [""], ["x"]),
            _grammar_dict_item('position_1', False, [1, 2], positions_tts, position_notation),
            # Column has to be checked first, otherwise a move like R1b2 will match on position_1_column then on
            # position_1_row instead of on position_1_column + position_2.
            _grammar_dict_item('position_1_column', False, [], columns, columns),
            _grammar_dict_item('position_1_row', False, [], rows, row_notation),
            _grammar_dict_item('capture_2', False, [], [""], ["x"]),
            _grammar_dict_item('position_2', False, [], positions_tts, position_notation),
            _grammar_dict_item('promotion', False, [], ["[PAUSE]promote to"], ["="]),
            _grammar_dict_item('promotion_piece', False, [], ["bishop", "rook", "knight", "queen"],
                               ["B", "R", "N", "Q"]),
            # These will likely never be used as the caller should strip them off before calling move_to_text
            _grammar_dict_item('check', False, [], ["[PAUSE]check"], ["+"]),
            _grammar_dict_item('checkmate', False, [], ["[PAUSE]checkmate"], ["#"]),
        ],
        'castle_grammar_tts': [
            # Go from most specific position notation to least
            _grammar_dict_item('castle_side', False, [], ["castle queen side", "castle king side"], ["O-O-O", "O-O"]),
            _grammar_dict_item('check', False, [], ["[PAUSE]check"], ["+"]),
            _grammar_dict_item('checkmate', False, [], ["[PAUSE]checkmate"], ["#"]),
        ],
    }
    return grammars


def _grammar_dict_item(
        identifier: str,
        mandatory: bool,
        children: list,
        text_values: list,
        notation_values: list
) -> dict:
    """
    Create a standardized dictionary for a grammar.

    :param identifier: The name of the grammar section.
    :param mandatory: Whether the section is mandatory (only applies to top-level sections).
    :param children: A list of the relative offsets of the children of this section. For speech recognition grammars,
    this contains children to SEARCH if the parent is matched. For TTS grammars, this contains children to SKIP if the
    the parent is matched.
    children to search only if the parent is not matched.
    :param text_values: The possible values in the text form.
    :param notation_values: The possible values in the algebraic notation form.
    :return: A dictionary of the grammar.
    """
    return {
        'identifier': identifier,
        'mandatory': mandatory,
        'children': children,
        'text_values': text_values,
        'notation_values': notation_values,
    }


def text_to_move(grammars: dict, text: str) -> str:
    """
    Convert natural language text to algebraic notation. IF the natural language does not adhere to the formal
    grammar, the resulting move will not be valid. Raises a ValueError if no piece is found.

    :param grammars: The dictionary of grammars to reference.
    :param text: The natural language form of the move.
    :return: The standard algebraic notation form of the move.
    """
    text_list = text.split(" ")
    try:
        castle_index = text_list.index(grammars['castle_grammar'][0]['text_values'][0])
    except ValueError:
        castle_index = -1
    # Look for first place that a piece is mentioned
    piece_index = -1
    for i in range(len(text_list)):
        if text_list[i] in grammars['regular_grammar'][0]['text_values']:
            piece_index = i
            break
    if piece_index == -1:
        raise ValueError("Not a valid move.")
    # Matching by "sliding" the list of words across the array of possible values. Would be too convoluted and
    # error-prone to do as a regular expression.
    current_section_index = -1
    if castle_index == -1 or piece_index < castle_index:
        # Assume castle was incorrectly heard (if at all) and parse regular movement
        grammar = grammars['regular_grammar']
        current_text_index = piece_index
    else:
        # We are castling
        grammar = grammars['castle_grammar']
        current_text_index = castle_index
    move = ""
    while True:
        next_mandatory_section_index = get_next_mandatory_section(current_section_index, grammar)
        skip_counter = 0
        for grammar_index in range(current_section_index + 1, next_mandatory_section_index + 1):
            if skip_counter > 0:
                skip_counter -= 1
                continue
            children = grammar[grammar_index]['children']
            match, matched_value_index = _matches_grammar(grammar[grammar_index], text_list, current_text_index)
            if match:
                text_child_offset = 0
                for child_offset in children:
                    child_match, child_matched_value_index = _matches_grammar(
                        grammar[grammar_index + child_offset], text_list,
                        current_text_index + text_child_offset
                    )
                    if child_match:
                        text_child_offset += 1
                next_section_index = grammar_index
                current_section_index = next_section_index
                move += grammar[current_section_index]['notation_values'][matched_value_index]
                # Skip ahead in the text based on the number of children found
                current_text_index += text_child_offset
                break
            # Skip checking children in the grammar
            skip_counter += len(children)
        current_text_index += 1
        if current_text_index >= len(text_list) or current_section_index >= len(grammar):
            break
    return move


def get_next_mandatory_section(current_index: int, grammar: list) -> int:
    """
    Return the next mandatory section or the last section if there are no more mandatory sections.

    :param current_index: The current index of the grammar to start the search from.
    :param grammar: The grammar to reference for the next mandatory section.
    :return: The index of the next mandatory section.
    """
    for index in range(current_index + 1, len(grammar)):
        if grammar[index]['mandatory']:
            return index
    return len(grammar) - 1


def _matches_grammar(grammar_section: dict, text_list: list, current_text_index: int) -> (bool, int):
    values = grammar_section['text_values']
    match = False
    matched_value_index = 0
    for value_index in range(len(values)):
        # Look at all the subvalues to make sure they match
        subvalues = values[value_index].split(" ")
        range_end = current_text_index + len(subvalues)
        # We must be careful not to look past the end of the text list
        if range_end <= len(text_list) and text_list[current_text_index:range_end] == subvalues:
            match = True
            matched_value_index = value_index
            break
    return match, matched_value_index


def move_to_text(grammars: dict, move: str) -> str:
    """
    Convert algebraic notation to natural language.

    :param grammars: The dictionary of grammars to reference.
    :param move: The standard algebraic notation form of the move.
    :return: The natural language form of the move.
    """
    text_list = []
    # Matching by "sliding" the array of possible values over the list of words. Would be too convoluted and
    # error-prone to do as a regular expression.
    if move.startswith("O"):
        # We are castling
        grammar = grammars['castle_grammar_tts']
    else:
        grammar = grammars['regular_grammar_tts']
    current_text_index = 0
    current_section_index = -1
    grammar_indices_to_skip = []
    while True:
        found_match = False
        for grammar_index in range(current_section_index + 1, len(grammar)):
            if grammar_index in grammar_indices_to_skip:
                continue
            match, matched_value_index = _matches_grammar_tts(grammar[grammar_index], move, current_text_index)
            if match:
                found_match = True
                current_section_index = grammar_index
                text_list.append(grammar[current_section_index]['text_values'][matched_value_index])
                # Move ahead by the matched value
                current_text_index += len(grammar[current_section_index]['notation_values'][matched_value_index])
                # Skip children that should not be matched when the parent has been matched
                grammar_indices_to_skip.extend(
                    [current_section_index + child_offset
                     for child_offset in grammar[current_section_index]['children']]
                )
                break
        if not found_match:
            raise ValueError("Move not in algebraic notation.")
        if current_text_index >= len(move) or (current_section_index + 1) == len(grammar):
            break
    text = " ".join(text_list)
    # Make sure there is only one "to (position)" by replacing the last [TO] token
    to_split = text.split("[TO ]")
    if len(to_split) == 1:
        # Moves like castling don't have a [TO] token.
        text = to_split[0]
    else:
        # 1 or more tokens
        text = "".join(to_split[:-1]) + "to " + to_split[-1]
    # Add commas to let TTS engine know to pause
    text = text.replace(" [PAUSE]", ", ")
    # Ensure that the letter 'a' is pronounced as a letter instead of as the indefinite article.
    text = text.replace(" a ", " A ")
    # Remove any extraneous spaces for consistency
    text = text.replace("  ", " ")
    return text


def _matches_grammar_tts(grammar_section: dict, text: str, current_text_index: int) -> (bool, int):
    values = grammar_section['notation_values']
    match = False
    matched_value_index = 0
    for value_index in range(len(values)):
        value = values[value_index]
        # Assumes that values are ordered "greedily", e.g. O-O-O comes before O-O
        range_end = current_text_index + len(value)
        # We must be careful not to look past the end of the text
        if range_end <= len(text) and text[current_text_index:range_end] == value:
            match = True
            matched_value_index = value_index
            break
    return match, matched_value_index
