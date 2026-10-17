"""Classifying the parser's error into adr-019's syntax error kinds, with the block's text at its marks.

Every case reads a real text, so the kind is pinned for the error the parser reports for it; the cases the parser
does not produce build the error by hand.
"""

import logging
from textwrap import dedent

import pytest

from lorecraft.core.num import NegativeIntError, NonZeroUnsignedInt
from lorecraft.yaml.problem import SyntaxErrorProblem
from lorecraft.yaml.reader import read_yaml
from lorecraft.yaml.tree import YamlPosition

from ..syntax_error import (
    ClosesNothing,
    ColonInValue,
    IndentedUnderText,
    MatchesNoLevel,
    NotKeyOrItem,
    ParserError,
    TabIndent,
    TabInLine,
    TextAfterCollection,
    TextAfterQuote,
    UnclosedQuote,
    UnknownEscape,
    UnreadableBlock,
    UnstartableCharacter,
    YamlSyntaxError,
    classify_syntax_error,
)


def _kind(text: str) -> YamlSyntaxError:
    """The kind of syntax error the reader reports for a text that holds one.

    Args:
        text: The YAML text.
    """
    problem = read_yaml(text)
    assert isinstance(problem, SyntaxErrorProblem), f'{text!r} is a syntax error, got {problem!r}'
    return problem.error


@pytest.mark.unit
class TestClassifySyntaxError:
    def test_classify_syntax_error_with_a_second_colon_in_a_value_returns_the_value_kind(self) -> None:
        #: When
        problem = _kind('a: b: c\n')

        #: Then
        assert problem == ColonInValue('a', 'b: c', 0), (
            'a `: ` inside a plain value is the value kind, with the value quoted in the help'
        )

    def test_classify_syntax_error_with_a_key_under_a_text_value_returns_the_indented_kind(self) -> None:
        #: Given
        block = dedent("""\
            name: a
              description: b
            """)

        #: When
        problem = _kind(block)

        #: Then
        assert problem == IndentedUnderText('description', 'name', 1), (
            'a key indented under a key whose value is text names both'
        )

    def test_classify_syntax_error_with_a_colon_ending_a_list_item_value_returns_the_indentation_kind(self) -> None:
        #: Given
        block = dedent("""\
            l:
            - a
              more
              k: v
            """)

        #: When
        problem = _kind(block)

        #: Then
        assert problem == MatchesNoLevel(3), (
            'the value of a list item is text, so the key that ends it matches no level, on its own line'
        )

    def test_classify_syntax_error_with_a_colon_that_ends_plain_words_below_returns_the_line_of_the_words(self) -> None:
        #: Given
        block = dedent("""\
            just words
            name: a
            """)

        #: When
        problem = _kind(block)

        #: Then
        assert problem == NotKeyOrItem(0), 'the plain words are the line to fix, not the key that ends them'

    def test_classify_syntax_error_with_a_line_that_matches_no_level_returns_the_indentation_kind(self) -> None:
        #: Given
        block = dedent("""\
            a:
              b: 1
             c: 2
            """)

        #: When
        problem = _kind(block)

        #: Then
        assert problem == MatchesNoLevel(2), 'a line indented to no level is the indentation kind'

    def test_classify_syntax_error_with_a_dash_after_a_mapping_returns_the_indentation_kind(self) -> None:
        #: Given
        block = dedent("""\
            a: 1
            - b
            """)

        #: When
        problem = _kind(block)

        #: Then
        assert problem == MatchesNoLevel(1), 'an item among keys lines up with none of them'

    def test_classify_syntax_error_with_a_key_after_a_sequence_returns_the_indentation_kind(self) -> None:
        #: Given
        block = dedent("""\
            - a
            b: c
            """)

        #: When
        problem = _kind(block)

        #: Then
        assert problem == MatchesNoLevel(1), 'a key among items lines up with none of them'

    def test_classify_syntax_error_with_a_line_that_is_no_key_returns_the_key_or_item_kind(self) -> None:
        #: Given
        block = dedent("""\
            name: a
            just words
            b: c
            """)

        #: When
        problem = _kind(block)

        #: Then
        assert problem == NotKeyOrItem(1), 'the line is where the key began, not the next'

    def test_classify_syntax_error_with_a_sequence_entry_after_a_key_returns_the_key_or_item_kind(self) -> None:
        #: When
        problem = _kind('a: - b\n')

        #: Then
        assert problem == NotKeyOrItem(0), 'an item written after a key is not what a line holds'

    def test_classify_syntax_error_with_an_unclosed_quote_returns_the_line_it_opens_on(self) -> None:
        #: Given
        block = dedent("""\
            name: "abc
            b: c
            """)

        #: When
        problem = _kind(block)

        #: Then
        assert problem == UnclosedQuote(0), 'the quote is reported where it opens, not where the block ends'

    def test_classify_syntax_error_with_text_after_a_closing_quote_returns_the_quote_kind(self) -> None:
        #: When
        problem = _kind('name: "a" b\n')

        #: Then
        assert problem == TextAfterQuote(0), 'text after a closing quote is named by the quote'

    def test_classify_syntax_error_with_text_after_a_flow_sequence_returns_the_bracket_kind(self) -> None:
        #: Given
        block = 'a: [b, c] d\n'

        #: When
        problem = _kind(block)

        #: Then
        assert problem == TextAfterCollection(']', 0), (
            'text after a flow collection is named by the bracket that closed it'
        )

    def test_classify_syntax_error_with_text_after_a_flow_mapping_returns_the_bracket_kind(self) -> None:
        #: Given
        block = 'a: {b: c} d\n'

        #: When
        problem = _kind(block)

        #: Then
        assert problem == TextAfterCollection('}', 0), (
            'text after a flow collection is named by the bracket that closed it'
        )

    def test_classify_syntax_error_with_an_extra_sequence_end_returns_the_bracket_kind(self) -> None:
        #: Given
        block = 'a: [b, c]]\n'

        #: When
        problem = _kind(block)

        #: Then
        assert problem == ClosesNothing(']', 0), 'a closing bracket with no opening bracket is named, on its line'

    def test_classify_syntax_error_with_an_extra_mapping_end_returns_the_bracket_kind(self) -> None:
        #: Given
        block = 'a: {b: c}}\n'

        #: When
        problem = _kind(block)

        #: Then
        assert problem == ClosesNothing('}', 0), 'a closing bracket with no opening bracket is named, on its line'

    def test_classify_syntax_error_with_a_lone_sequence_end_returns_the_bracket_kind(self) -> None:
        #: Given
        block = 'a: ]\n'

        #: When
        problem = _kind(block)

        #: Then
        assert problem == ClosesNothing(']', 0), 'a closing bracket with no opening bracket is named, on its line'

    def test_classify_syntax_error_with_a_lone_mapping_end_returns_the_bracket_kind(self) -> None:
        #: Given
        block = 'a: }\n'

        #: When
        problem = _kind(block)

        #: Then
        assert problem == ClosesNothing('}', 0), 'a closing bracket with no opening bracket is named, on its line'

    def test_classify_syntax_error_with_a_line_below_a_block_scalar_returns_the_indentation_kind(self) -> None:
        #: Given
        block = dedent("""\
            a: |
              x
             y
            """)

        #: When
        problem = _kind(block)

        #: Then
        assert problem == MatchesNoLevel(2), 'a line less indented than the scalar text matches no level'

    def test_classify_syntax_error_with_a_tab_that_starts_a_line_returns_the_tab_kind(self) -> None:
        #: When
        problem = _kind('a:\n\tb: 1\n')

        #: Then
        assert problem == TabIndent(1), 'a tab that starts a line is the indentation kind'

    def test_classify_syntax_error_with_a_tab_inside_a_line_returns_the_tab_not_whitespace_kind(self) -> None:
        #: When
        problem = _kind('a: [b,\tc]\n')

        #: Then
        assert problem == TabInLine(0), 'a tab that does not start the line is not whitespace in a flow collection'

    def test_classify_syntax_error_with_a_character_no_value_starts_with_returns_the_value_start_kind(self) -> None:
        #: When
        problem = _kind('a: @b\n')

        #: Then
        assert problem == UnstartableCharacter('@', 0), (
            'a character no plain value starts with names itself in the label'
        )

    def test_classify_syntax_error_with_a_backtick_that_starts_a_value_names_it_in_words(self) -> None:
        #: When
        problem = _kind('a: `b`\n')

        #: Then
        assert problem == UnstartableCharacter('`', 0), 'a backtick is not written between backticks in the label'

    def test_classify_syntax_error_with_an_unknown_escape_returns_the_escape_kind(self) -> None:
        #: When
        problem = _kind('a: "\\q"\n')

        #: Then
        assert problem == UnknownEscape('\\q', 0), 'the escape is named as the block writes it'

    def test_classify_syntax_error_with_an_escape_that_lacks_its_digits_returns_the_escape_with_the_digits_given(
        self,
    ) -> None:
        #: When
        problem = _kind('a: "\\xZZ"\n')

        #: Then
        assert problem == UnknownEscape('\\x', 0), (
            'a hexadecimal escape is named with the digits it was given, none here'
        )

    def test_classify_syntax_error_with_an_escape_cut_short_by_the_closing_quote_returns_the_escape_without_it(
        self,
    ) -> None:
        #: When
        problem = _kind('a: "\\u12"\n')

        #: Then
        assert problem == UnknownEscape('\\u12', 0), 'the closing quote is not taken as a digit of the escape'

    def test_classify_syntax_error_with_a_colon_that_starts_a_value_returns_the_value_start_kind(self) -> None:
        #: When
        problem = _kind('a: :\n')

        #: Then
        assert problem == UnstartableCharacter(':', 0), 'a `:` where a value starts cannot start it'

    def test_classify_syntax_error_with_a_key_marker_where_a_key_is_not_allowed_returns_the_value_start_kind(
        self,
    ) -> None:
        #: When
        problem = _kind('a: ? b\n')

        #: Then
        assert problem == UnstartableCharacter('?', 0), 'a `?` where a value starts cannot start it'

    @pytest.mark.parametrize('mark', ['', '\ufeff\ufeff'])
    def test_classify_syntax_error_with_byte_order_marks_in_the_text_returns_the_kind_it_has_without(
        self, mark: str
    ) -> None:
        #: Given
        quoted = f'a: "{mark}\\q"\n'
        flow = f'a: [{mark}b] c\n'

        #: When
        escape = _kind(quoted)
        trailing = _kind(flow)

        #: Then
        assert escape == UnknownEscape('\\q', 0), f'a U+FEFF does not move the escape, got {escape!r}'
        assert trailing == TextAfterCollection(']', 0), f'a U+FEFF does not move the text, got {trailing!r}'


@pytest.mark.unit
class TestSyntaxErrorKinds:
    def test_a_kind_with_a_negative_line_is_refused(self) -> None:
        #: When / Then
        with pytest.raises(NegativeIntError):
            NotKeyOrItem(-1)

    def test_a_kind_with_no_line_is_accepted(self) -> None:
        #: When
        kind = UnreadableBlock(None)

        #: Then
        assert kind.line is None, 'a parser that marks no line gives a kind with none'


def _mark(line: int, column: int) -> YamlPosition:
    """A position of the block, from its line and column counted from 0.

    Args:
        line: The line.
        column: The column.
    """
    return YamlPosition(NonZeroUnsignedInt(line + 1), NonZeroUnsignedInt(column + 1))


def _error(
    problem: str,
    mark: YamlPosition | None,
    *,
    context: str | None = None,
    context_mark: YamlPosition | None = None,
) -> ParserError:
    """An error the way the parser reports it, with its problem, context and positions.

    Args:
        problem: What the parser found wrong.
        mark: Where it found it.
        context: What it was reading, where it names one.
        context_mark: Where that began.
    """
    return ParserError(problem, context or '', mark, context_mark)


@pytest.mark.unit
class TestClassifySyntaxErrorOfHandBuiltError:
    def test_classify_syntax_error_with_a_colon_ending_a_scalar_with_nothing_above_returns_the_line_kind(self) -> None:
        #: Given
        error = _error('mapping values are not allowed here', _mark(0, 4))

        block = dedent("""\
            ab c: d
            x
            """)

        #: When
        problem = classify_syntax_error(error, block)

        #: Then
        assert problem == NotKeyOrItem(0), (
            'with no key line above, the scalar starts on its own line, which is the one to fix'
        )

    def test_classify_syntax_error_with_a_colon_and_no_mark_returns_the_fallback_with_no_line(self) -> None:
        #: Given
        error = _error('mapping values are not allowed here', None)

        #: When
        problem = classify_syntax_error(error, 'a: b: c\n')

        #: Then
        assert problem == UnreadableBlock(None), (
            'with no mark there is no line to name, so the error stays the fallback'
        )

    def test_classify_syntax_error_with_a_top_level_scalar_returns_the_key_or_item_kind(self) -> None:
        #: Given
        error = _error("expected '<document start>', but found '<scalar>'", _mark(1, 0))

        block = dedent("""\
            >
            text
            """)

        #: When
        problem = classify_syntax_error(error, block)

        #: Then
        assert problem == NotKeyOrItem(1), 'text under a top-level scalar is no key or item'

    def test_classify_syntax_error_with_text_and_no_mark_returns_the_fallback_with_no_line(self) -> None:
        #: Given
        error = _error("expected <block end>, but found '<scalar>'", None)

        #: When
        problem = classify_syntax_error(error, 'name: "a" b\n')

        #: Then
        assert problem == UnreadableBlock(None), 'with no mark there is no line to name'

    def test_classify_syntax_error_with_an_error_no_kind_matches_returns_the_fallback_on_its_line(self) -> None:
        #: Given
        error = _error(
            "expected the node content, but found '<alias>'", _mark(0, 3), context='while parsing a block node'
        )

        #: When
        problem = classify_syntax_error(error, 'a: *b\n')

        #: Then
        assert problem == UnreadableBlock(0), (
            'an error no kind matches is reported on the parser line, with no parser text'
        )

    def test_classify_syntax_error_with_a_character_the_problem_does_not_quote_returns_the_fallback(self) -> None:
        #: Given
        error = _error('found character that cannot start any token', _mark(0, 3))

        #: When
        problem = classify_syntax_error(error, 'a: @b\n')

        #: Then
        assert problem == UnreadableBlock(0), (
            'a character the problem does not name is left as the fallback, not a made-up one'
        )

    def test_classify_syntax_error_with_an_escape_and_no_backslash_before_it_returns_the_fallback(self) -> None:
        #: Given
        error = _error(
            "found unknown escape character 'q'",
            _mark(0, 2),
            context='while scanning a double-quoted scalar',
            context_mark=_mark(0, 0),
        )

        #: When
        problem = classify_syntax_error(error, 'aq\n')

        #: Then
        assert problem == UnreadableBlock(0), 'an escape the text does not show is left as the fallback, on its line'


@pytest.mark.unit
class TestClassifySyntaxErrorLogging:
    def test_classify_syntax_error_with_a_matching_kind_logs_the_kind_and_line(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        #: Given
        caplog.set_level(logging.DEBUG, logger='lorecraft.yaml')

        #: When
        classify_syntax_error(_error("could not find expected ':'", None), 'a: b\n')

        #: Then
        record = caplog.records[-1]
        assert record.getMessage() == 'yaml syntax error classified'
        assert record.__dict__['fields'] == {'kind': 'NotKeyOrItem', 'line': None}

    def test_classify_syntax_error_with_no_matching_kind_logs_the_parser_problem_and_line(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        #: Given
        caplog.set_level(logging.DEBUG, logger='lorecraft.yaml')

        #: When
        classify_syntax_error(_error('mapping values are not allowed here', None), 'a: b: c\n')

        #: Then
        record = caplog.records[-1]
        assert record.getMessage() == 'yaml syntax error unclassified'
        assert record.__dict__['fields'] == {'problem': 'mapping values are not allowed here', 'line': None}

    def test_classify_syntax_error_with_a_problem_outside_the_templates_logs_a_constant(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        #: Given
        caplog.set_level(logging.DEBUG, logger='lorecraft.yaml')

        #: When
        classify_syntax_error(_error('found something "SENTINEL" new', None), 'a: b\n')

        #: Then
        assert caplog.records[-1].__dict__['fields'] == {'problem': 'unrecognized', 'line': None}
