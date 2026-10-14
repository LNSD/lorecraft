"""Classifying the parser's error into adr-019's syntax error kinds, with the block's text at its marks.

Every case builds the scanner's or parser's error by hand, with the marks the parser gave it for the block, so each
kind and the fallback are pinned without going through the decoder.
"""

from textwrap import dedent
from typing import Final

import pytest
from ruamel.yaml.error import MarkedYAMLError, StreamMark
from ruamel.yaml.reader import ReaderError

from ..syntax_error import SyntaxProblem, describe_control_character, describe_error


def _mark(line: int, column: int) -> StreamMark:
    """A mark of the block, from its line and column counted from 0.

    Args:
        line: The line.
        column: The column.
    """
    return StreamMark('<unicode string>', 0, line, column)


def _error(
    problem: str,
    mark: StreamMark | None,
    *,
    context: str | None = None,
    context_mark: StreamMark | None = None,
) -> MarkedYAMLError:
    """An error the way the parser raises it, with its problem, context and marks.

    Args:
        problem: What the parser found wrong.
        mark: Where it found it.
        context: What it was reading, where it names one.
        context_mark: Where that began.
    """
    return MarkedYAMLError(context, context_mark, problem, mark)


_NOT_KEY_OR_ITEM: Final[tuple[str, str]] = (
    'this line is not `key: value` or `- item`',
    'Add `: ` after the key, or quote a value that runs on',
)
_NO_MATCH: Final[tuple[str, str]] = (
    "this line's indentation matches no key or item above it",
    'Indent it like the keys or items it belongs with',
)


@pytest.mark.unit
class TestDescribeError:
    def test_describe_error_with_a_second_colon_in_a_value_returns_the_value_kind(self) -> None:
        #: Given
        error = _error('mapping values are not allowed here', _mark(0, 4))

        #: When
        problem = describe_error(error, 'a: b: c\n')

        #: Then
        assert problem == SyntaxProblem('this value holds `: `', 'Quote the value: `a: "b: c"`', 0), (
            'a `: ` inside a plain value is the value kind, with the value quoted in the help'
        )

    def test_describe_error_with_a_key_under_a_text_value_returns_the_indented_kind(self) -> None:
        #: Given
        error = _error('mapping values are not allowed here', _mark(1, 13))

        block = dedent("""\
            name: a
              description: b
            """)

        #: When
        problem = describe_error(error, block)

        #: Then
        assert problem == SyntaxProblem(
            '`description` is indented under `name`, whose value is text',
            'Align it with the key it belongs beside',
            1,
        ), 'a key indented under a key whose value is text names both'

    def test_describe_error_with_a_colon_ending_a_scalar_with_nothing_above_returns_the_line_kind(self) -> None:
        #: Given
        error = _error('mapping values are not allowed here', _mark(0, 4))

        block = dedent("""\
            ab c: d
            x
            """)

        #: When
        problem = describe_error(error, block)

        #: Then
        assert problem == SyntaxProblem(*_NOT_KEY_OR_ITEM, 0), (
            'with no key line above, the scalar starts on its own line, which is the one to fix'
        )

    def test_describe_error_with_a_colon_ending_a_list_item_value_returns_the_indentation_kind(self) -> None:
        #: Given
        error = _error('mapping values are not allowed here', _mark(3, 3))
        block = dedent("""\
            l:
            - a
              more
              k: v
            """)

        #: When
        problem = describe_error(error, block)

        #: Then
        assert problem == SyntaxProblem(*_NO_MATCH, 3), (
            'the value of a list item is text, so the key that ends it matches no level, on its own line'
        )

    def test_describe_error_with_a_colon_that_ends_plain_words_below_returns_the_line_of_the_words(self) -> None:
        #: Given
        error = _error('mapping values are not allowed here', _mark(1, 4))

        block = dedent("""\
            just words
            name: a
            """)

        #: When
        problem = describe_error(error, block)

        #: Then
        assert problem == SyntaxProblem(*_NOT_KEY_OR_ITEM, 0), (
            'the plain words are the line to fix, not the key that ends them'
        )

    def test_describe_error_with_a_colon_and_no_mark_returns_the_fallback_with_no_line(self) -> None:
        #: Given
        error = _error('mapping values are not allowed here', None)

        #: When
        problem = describe_error(error, 'a: b: c\n')

        #: Then
        assert problem == SyntaxProblem('the block cannot be read from this line on', None, None), (
            'with no mark there is no line to name, so the error stays the fallback'
        )

    def test_describe_error_with_a_line_that_matches_no_level_returns_the_indentation_kind(self) -> None:
        #: Given
        error = _error("expected <block end>, but found '<block mapping start>'", _mark(2, 1))

        block = dedent("""\
            a:
              b: 1
             c: 2
            """)

        #: When
        problem = describe_error(error, block)

        #: Then
        assert problem == SyntaxProblem(*_NO_MATCH, 2), 'a line indented to no level is the indentation kind'

    def test_describe_error_with_a_dash_after_a_mapping_returns_the_indentation_kind(self) -> None:
        #: Given
        error = _error("expected <block end>, but found '-'", _mark(1, 0))

        block = dedent("""\
            a: 1
            - b
            """)

        #: When
        problem = describe_error(error, block)

        #: Then
        assert problem == SyntaxProblem(*_NO_MATCH, 1), 'an item among keys lines up with none of them'

    def test_describe_error_with_a_key_after_a_sequence_returns_the_indentation_kind(self) -> None:
        #: Given
        error = _error("expected <block end>, but found '?'", _mark(1, 0))

        block = dedent("""\
            - a
            b: c
            """)

        #: When
        problem = describe_error(error, block)

        #: Then
        assert problem == SyntaxProblem(*_NO_MATCH, 1), 'a key among items lines up with none of them'

    def test_describe_error_with_a_line_that_is_no_key_returns_the_key_or_item_kind(self) -> None:
        #: Given
        error = _error(
            "could not find expected ':'", _mark(2, 0), context='while scanning a simple key', context_mark=_mark(1, 0)
        )

        block = dedent("""\
            name: a
            just words
            b: c
            """)

        #: When
        problem = describe_error(error, block)

        #: Then
        assert problem == SyntaxProblem(*_NOT_KEY_OR_ITEM, 1), 'the line is where the key began, not the next'

    def test_describe_error_with_a_top_level_scalar_returns_the_key_or_item_kind(self) -> None:
        #: Given
        error = _error("expected '<document start>', but found '<scalar>'", _mark(1, 0))

        block = dedent("""\
            >
            text
            """)

        #: When
        problem = describe_error(error, block)

        #: Then
        assert problem == SyntaxProblem(*_NOT_KEY_OR_ITEM, 1), 'text under a top-level scalar is no key or item'

    def test_describe_error_with_a_sequence_entry_after_a_key_returns_the_key_or_item_kind(self) -> None:
        #: Given
        error = _error('sequence entries are not allowed here', _mark(0, 3))

        #: When
        problem = describe_error(error, 'a: - b\n')

        #: Then
        assert problem == SyntaxProblem(*_NOT_KEY_OR_ITEM, 0), 'an item written after a key is not what a line holds'

    def test_describe_error_with_an_unclosed_quote_returns_the_line_it_opens_on(self) -> None:
        #: Given
        error = _error(
            'found unexpected end of stream',
            _mark(2, 0),
            context='while scanning a quoted scalar',
            context_mark=_mark(0, 6),
        )

        block = dedent("""\
            name: "abc
            b: c
            """)

        #: When
        problem = describe_error(error, block)

        #: Then
        assert problem == SyntaxProblem(
            'this quote is never closed', 'Close it on the line it continues to, or remove it', 0
        ), 'the quote is reported where it opens, not where the block ends'

    def test_describe_error_with_text_after_a_closing_quote_returns_the_quote_kind(self) -> None:
        #: Given
        error = _error("expected <block end>, but found '<scalar>'", _mark(0, 10))

        #: When
        problem = describe_error(error, 'name: "a" b\n')

        #: Then
        assert problem == SyntaxProblem('text follows the closing quote', 'Put the whole value inside the quotes', 0), (
            'text after a closing quote is named by the quote'
        )

    def test_describe_error_with_a_line_below_a_block_scalar_returns_the_indentation_kind(self) -> None:
        #: Given
        error = _error("expected <block end>, but found '<scalar>'", _mark(2, 1))

        block = dedent("""\
            a: |
              x
             y
            """)

        #: When
        problem = describe_error(error, block)

        #: Then
        assert problem == SyntaxProblem(*_NO_MATCH, 2), 'a line less indented than the scalar text matches no level'

    def test_describe_error_with_text_after_a_flow_collection_returns_the_fallback(self) -> None:
        #: Given
        error = _error("expected <block end>, but found '<scalar>'", _mark(0, 10))

        #: When
        problem = describe_error(error, 'a: [b, c] d\n')

        #: Then
        assert problem == SyntaxProblem('the block cannot be read from this line on', None, 0), (
            'text after a flow collection is no kind of the table, so it is the fallback'
        )

    def test_describe_error_with_text_and_no_mark_returns_the_fallback_with_no_line(self) -> None:
        #: Given
        error = _error("expected <block end>, but found '<scalar>'", None)

        #: When
        problem = describe_error(error, 'name: "a" b\n')

        #: Then
        assert problem == SyntaxProblem('the block cannot be read from this line on', None, None), (
            'with no mark there is no line to name'
        )

    def test_describe_error_with_an_error_no_kind_matches_returns_the_fallback_on_its_line(self) -> None:
        #: Given
        error = _error("expected the node content, but found ']'", _mark(0, 3), context='while parsing a block node')

        #: When
        problem = describe_error(error, 'a: ]\n')

        #: Then
        assert problem == SyntaxProblem('the block cannot be read from this line on', None, 0), (
            'an error no kind matches is reported on the parser line, with no parser text'
        )

    def test_describe_error_with_a_tab_that_starts_a_line_returns_the_tab_kind(self) -> None:
        #: Given
        error = _error(
            "found character '\\t' that cannot start any token",
            _mark(1, 0),
            context='while scanning for the next token',
        )

        #: When
        problem = describe_error(error, 'a:\n\tb: 1\n')

        #: Then
        assert problem == SyntaxProblem('a tab indents this line', 'Indent with spaces', 1), (
            'a tab that starts a line is the indentation kind'
        )

    def test_describe_error_with_a_tab_inside_a_line_returns_the_tab_not_whitespace_kind(self) -> None:
        #: Given
        error = _error(
            "found character '\\t' that cannot start any token",
            _mark(0, 6),
            context='while scanning for the next token',
        )

        #: When
        problem = describe_error(error, 'a: [b,\tc]\n')

        #: Then
        assert problem == SyntaxProblem('a tab is not whitespace here', 'Use spaces', 0), (
            'a tab that does not start the line is not whitespace in a flow collection'
        )

    def test_describe_error_with_a_character_no_value_starts_with_returns_the_value_start_kind(self) -> None:
        #: Given
        error = _error(
            "found character '@' that cannot start any token", _mark(0, 3), context='while scanning for the next token'
        )

        #: When
        problem = describe_error(error, 'a: @b\n')

        #: Then
        assert problem == SyntaxProblem('a plain value cannot start with `@`', 'Quote the value', 0), (
            'a character no plain value starts with names itself in the label'
        )

    def test_describe_error_with_a_backtick_that_starts_a_value_names_it_in_words(self) -> None:
        #: Given
        error = _error(
            "found character '`' that cannot start any token", _mark(0, 3), context='while scanning for the next token'
        )

        #: When
        problem = describe_error(error, 'a: `b`\n')

        #: Then
        assert problem == SyntaxProblem('a plain value cannot start with a backtick', 'Quote the value', 0), (
            'a backtick is not written between backticks in the label'
        )

    def test_describe_error_with_a_character_the_problem_does_not_quote_returns_the_fallback(self) -> None:
        #: Given
        error = _error('found character that cannot start any token', _mark(0, 3))

        #: When
        problem = describe_error(error, 'a: @b\n')

        #: Then
        assert problem == SyntaxProblem('the block cannot be read from this line on', None, 0), (
            'a character the problem does not name is left as the fallback, not a made-up one'
        )

    def test_describe_error_with_an_unknown_escape_returns_the_escape_kind(self) -> None:
        #: Given
        error = _error(
            "found unknown escape character 'q'",
            _mark(0, 5),
            context='while scanning a double-quoted scalar',
            context_mark=_mark(0, 3),
        )

        #: When
        problem = describe_error(error, 'a: "\\q"\n')

        #: Then
        assert problem == SyntaxProblem(
            '`\\q` is not an escape', 'Write `\\\\` for a backslash, or use single quotes', 0
        ), 'the escape is named as the block writes it'

    def test_describe_error_with_an_escape_that_lacks_its_digits_returns_the_escape_with_the_digits_given(self) -> None:
        #: Given
        error = _error(
            "expected escape sequence of 2 hexdecimal numbers, but found 'Z'",
            _mark(0, 6),
            context='while scanning a double-quoted scalar',
            context_mark=_mark(0, 3),
        )

        #: When
        problem = describe_error(error, 'a: "\\xZZ"\n')

        #: Then
        assert problem == SyntaxProblem(
            '`\\x` is not an escape', 'Write `\\\\` for a backslash, or use single quotes', 0
        ), 'a hexadecimal escape is named with the digits it was given, none here'

    def test_describe_error_with_an_escape_cut_short_by_the_closing_quote_returns_the_escape_without_it(self) -> None:
        #: Given
        error = _error(
            "expected escape sequence of 4 hexdecimal numbers, but found '\"'",
            _mark(0, 8),
            context='while scanning a double-quoted scalar',
            context_mark=_mark(0, 3),
        )

        #: When
        problem = describe_error(error, 'a: "\\u12"\n')

        #: Then
        assert problem == SyntaxProblem(
            '`\\u12` is not an escape', 'Write `\\\\` for a backslash, or use single quotes', 0
        ), 'the closing quote is not taken as a digit of the escape'

    def test_describe_error_with_an_escape_and_no_backslash_before_it_returns_the_fallback(self) -> None:
        #: Given
        error = _error(
            "found unknown escape character 'q'",
            _mark(0, 2),
            context='while scanning a double-quoted scalar',
            context_mark=_mark(0, 0),
        )

        #: When
        problem = describe_error(error, 'aq\n')

        #: Then
        assert problem == SyntaxProblem('the block cannot be read from this line on', None, 0), (
            'an escape the text does not show is left as the fallback, on its line'
        )

    def test_describe_error_with_a_colon_that_starts_a_value_returns_the_value_start_kind(self) -> None:
        #: Given
        error = _error('mapping values are not allowed here', _mark(0, 3))

        #: When
        problem = describe_error(error, 'a: :\n')

        #: Then
        assert problem == SyntaxProblem('a plain value cannot start with `:`', 'Quote the value', 0), (
            'a `:` where a value starts cannot start it'
        )

    def test_describe_error_with_a_key_marker_where_a_key_is_not_allowed_returns_the_value_start_kind(self) -> None:
        #: Given
        error = _error('mapping keys are not allowed here', _mark(0, 3))

        #: When
        problem = describe_error(error, 'a: ? b\n')

        #: Then
        assert problem == SyntaxProblem('a plain value cannot start with `?`', 'Quote the value', 0), (
            'a `?` where a value starts cannot start it'
        )

    def test_describe_control_character_with_a_bell_after_a_line_returns_its_code_point_and_line(self) -> None:
        #: Given
        error = ReaderError('<unicode string>', 9, ord('\x07'), 'utf-8', 'special characters are not allowed')

        #: When
        problem = describe_control_character(error, 'a: b\nc: d\x07\n')

        #: Then
        assert problem == SyntaxProblem('the block holds the control character U+0007', 'Remove it', 1), (
            'a control character is named by its code point, on the line it is on'
        )
