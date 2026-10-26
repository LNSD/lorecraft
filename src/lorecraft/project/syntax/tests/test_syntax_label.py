"""Wording the syntax error kinds of `lorecraft.yaml` with the label and help `LC202` reports."""

import pytest

from lorecraft.core.lines import LineOffset
from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.yaml.problem import ControlCharacterProblem
from lorecraft.yaml.syntax_error import (
    ClosesNothing,
    ColonInValue,
    IndentedUnderText,
    MatchesNoLevel,
    NotKeyOrItem,
    SeparatorEscape,
    TabIndent,
    TabInLine,
    TextAfterCollection,
    TextAfterQuote,
    UnclosedQuote,
    UnknownEscape,
    UnreadableBlock,
    UnstartableCharacter,
)
from lorecraft.yaml.tree import YamlPosition

from ..syntax_label import SyntaxProblem, describe_control_character, describe_syntax_error

_ESCAPE_HELP = 'Write `\\\\` for a backslash, or use single quotes'


@pytest.mark.unit
class TestDescribeSyntaxError:
    def test_describe_syntax_error_with_a_line_that_is_no_key_or_item_returns_the_key_or_item_wording(self) -> None:
        #: Given
        kind = NotKeyOrItem(LineOffset(UnsignedInt(2)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem(
            'this line is not `key: value` or `- item`', 'Add `: ` after the key, or quote a value that runs on', 2
        ), f'{kind!r} is worded as its label, help and line'

    def test_describe_syntax_error_with_an_unclosed_quote_returns_the_quote_wording(self) -> None:
        #: Given
        kind = UnclosedQuote(LineOffset(UnsignedInt(1)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem(
            'this quote is never closed', 'Close it on the line it continues to, or remove it', 1
        ), f'{kind!r} is worded as its label, help and line'

    def test_describe_syntax_error_with_a_backslash_before_a_separator_returns_its_code_point(self) -> None:
        #: Given
        kind = SeparatorEscape('\x85', LineOffset(UnsignedInt(0)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem('`\\` before U+0085 is not an escape', _ESCAPE_HELP, 0), (
            f'{kind!r} is worded as its label, help and line'
        )

    def test_describe_syntax_error_with_an_unknown_escape_returns_the_escape_as_written(self) -> None:
        #: Given
        kind = UnknownEscape('\\u12', LineOffset(UnsignedInt(0)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem('`\\u12` is not an escape', _ESCAPE_HELP, 0), (
            f'{kind!r} is worded as its label, help and line'
        )

    def test_describe_syntax_error_with_a_character_no_value_starts_with_returns_it_between_backticks(self) -> None:
        #: Given
        kind = UnstartableCharacter('@', LineOffset(UnsignedInt(0)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem('a plain value cannot start with `@`', 'Quote the value', 0), (
            f'{kind!r} is worded as its label, help and line'
        )

    def test_describe_syntax_error_with_a_backtick_that_starts_a_value_returns_it_in_words(self) -> None:
        #: Given
        kind = UnstartableCharacter('`', LineOffset(UnsignedInt(0)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem('a plain value cannot start with a backtick', 'Quote the value', 0), (
            f'{kind!r} is worded as its label, help and line'
        )

    def test_describe_syntax_error_with_a_colon_in_a_value_returns_the_value_quoted(self) -> None:
        #: Given
        kind = ColonInValue('a', 'b: c', LineOffset(UnsignedInt(0)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem('this value holds `: `', 'Quote the value: `a: "b: c"`', 0), (
            f'{kind!r} is worded as its label, help and line'
        )

    def test_describe_syntax_error_with_a_colon_in_a_value_with_a_quote_returns_no_quoted_value(self) -> None:
        #: Given
        kind = ColonInValue('a', 'say "b: c"', LineOffset(UnsignedInt(0)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem('this value holds `: `', 'Quote the value: it', 0), (
            f'{kind!r} is worded as its label, help and line'
        )

    def test_describe_syntax_error_with_a_key_under_a_text_value_returns_both_keys(self) -> None:
        #: Given
        kind = IndentedUnderText('description', 'name', LineOffset(UnsignedInt(1)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem(
            '`description` is indented under `name`, whose value is text', 'Align it with the key it belongs beside', 1
        ), f'{kind!r} is worded as its label, help and line'

    def test_describe_syntax_error_with_a_line_that_matches_no_level_returns_the_indentation_wording(self) -> None:
        #: Given
        kind = MatchesNoLevel(LineOffset(UnsignedInt(3)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem(
            "this line's indentation matches no key or item above it",
            'Indent it like the keys or items it belongs with',
            3,
        ), f'{kind!r} is worded as its label, help and line'

    def test_describe_syntax_error_with_a_bracket_that_closes_nothing_returns_the_bracket(self) -> None:
        #: Given
        kind = ClosesNothing(']', LineOffset(UnsignedInt(0)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem('this `]` closes nothing', 'Remove it, or quote the value', 0), (
            f'{kind!r} is worded as its label, help and line'
        )

    def test_describe_syntax_error_with_text_after_a_closing_quote_returns_the_quote_wording(self) -> None:
        #: Given
        kind = TextAfterQuote(LineOffset(UnsignedInt(0)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem('text follows the closing quote', 'Put the whole value inside the quotes', 0), (
            f'{kind!r} is worded as its label, help and line'
        )

    def test_describe_syntax_error_with_text_after_a_flow_collection_returns_its_closing_bracket(self) -> None:
        #: Given
        kind = TextAfterCollection('}', LineOffset(UnsignedInt(0)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem(
            'text follows the closing `}`', 'Move the text inside the brackets, or quote the whole value', 0
        ), f'{kind!r} is worded as its label, help and line'

    def test_describe_syntax_error_with_a_tab_that_indents_a_line_returns_the_indentation_wording(self) -> None:
        #: Given
        kind = TabIndent(LineOffset(UnsignedInt(1)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem('a tab indents this line', 'Indent with spaces', 1), (
            f'{kind!r} is worded as its label, help and line'
        )

    def test_describe_syntax_error_with_a_tab_inside_a_line_returns_the_whitespace_wording(self) -> None:
        #: Given
        kind = TabInLine(LineOffset(UnsignedInt(0)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem('a tab is not whitespace here', 'Use spaces', 0), (
            f'{kind!r} is worded as its label, help and line'
        )

    def test_describe_syntax_error_with_an_unreadable_block_returns_the_fallback_with_no_help(self) -> None:
        #: Given
        kind = UnreadableBlock(LineOffset(UnsignedInt(0)))

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem('the block cannot be read from this line on', None, 0), (
            f'{kind!r} is worded as its label, help and line'
        )

    def test_describe_syntax_error_with_an_unreadable_block_with_no_mark_returns_no_line(
        self,
    ) -> None:
        #: Given
        kind = UnreadableBlock(None)

        #: When
        problem = describe_syntax_error(kind)

        #: Then
        assert problem == SyntaxProblem('the block cannot be read from this line on', None, None), (
            f'{kind!r} is worded as its label, help and line'
        )

    def test_describe_control_character_with_a_bell_after_a_line_returns_its_code_point_and_line(self) -> None:
        #: Given
        error = ControlCharacterProblem(
            code=ord('\x07'), position=YamlPosition(NonZeroUnsignedInt(2), NonZeroUnsignedInt(5))
        )

        #: When
        problem = describe_control_character(error)

        #: Then
        assert problem == SyntaxProblem('the block holds the control character U+0007', 'Remove it', 1), (
            'a control character is named by its code point, on the line it is on'
        )
