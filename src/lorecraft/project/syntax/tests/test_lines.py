"""Counting the lines of a text, as the budget on a skill's `SKILL.md` counts them."""

import pytest

from ..lines import count_lines, split_lines


@pytest.mark.unit
class TestCountLines:
    def test_count_lines_with_empty_text_returns_zero(self) -> None:
        #: Given
        text = ''

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == 0, f'empty text holds no line, got {lines}'

    def test_count_lines_with_a_final_newline_adds_no_line(self) -> None:
        #: Given
        text = 'one\ntwo\n'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == 2, f'the newline ending the last line opens no new one, got {lines}'

    def test_count_lines_without_a_final_newline_counts_the_last_line(self) -> None:
        #: Given
        text = 'one\ntwo'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == 2, f'a last line with no newline is still a line, got {lines}'

    def test_count_lines_with_frontmatter_counts_its_lines_too(self) -> None:
        #: Given
        # three lines of frontmatter block, its delimiters included, and two of body
        text = '---\nname: review\n---\n# Review\nBody.\n'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == 5, f'the frontmatter block counts like any other line, got {lines}'

    def test_count_lines_with_blank_lines_counts_each(self) -> None:
        #: Given
        text = '# Review\n\n\nBody.\n'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == 4, f'a blank line is a line, got {lines}'

    def test_count_lines_with_crlf_endings_counts_each_once(self) -> None:
        #: Given
        text = 'one\r\ntwo\r\n'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == 2, f'a `\\r\\n` ending ends one line, not two, got {lines}'

    def test_count_lines_with_a_form_feed_inside_a_line_does_not_break_it(self) -> None:
        #: Given
        text = 'one\x0ctwo\n'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == 1, f'only a `\\n` ends a line, as the findings number lines, got {lines}'

    def test_count_lines_with_a_unicode_line_separator_does_not_break_the_line(self) -> None:
        #: Given
        text = 'one\u2028two\n'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == 1, f'U+2028 is not a `\\n`, so it ends no line, got {lines}'

    def test_count_lines_with_a_lone_carriage_return_does_not_break_the_line(self) -> None:
        #: Given
        text = 'one\rtwo\n'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == 1, f'a `\\r` without a `\\n` after it ends no line, got {lines}'


@pytest.mark.unit
class TestSplitLines:
    def test_split_lines_with_a_final_newline_opens_no_line(self) -> None:
        #: Given
        text = 'one\ntwo\n'

        #: When
        lines = split_lines(text)

        #: Then
        assert lines == ('one', 'two'), f'the newline ending the last line opens no new one, got {lines}'

    def test_split_lines_with_crlf_breaks_leaves_no_carriage_return(self) -> None:
        #: Given
        text = 'one\r\ntwo'

        #: When
        lines = split_lines(text)

        #: Then
        assert lines == ('one', 'two'), f'a CRLF break ends one line without its carriage return, got {lines}'

    def test_split_lines_with_a_form_feed_inside_a_line_does_not_break_it(self) -> None:
        #: Given
        text = 'one\x0ctwo\u2028three\nfour'

        #: When
        lines = split_lines(text)

        #: Then
        assert lines == ('one\x0ctwo\u2028three', 'four'), f'only a newline ends a line, got {lines}'

    def test_split_lines_with_empty_text_holds_no_line(self) -> None:
        #: Given
        text = ''

        #: When
        lines = split_lines(text)

        #: Then
        assert lines == (), f'empty text holds no line, got {lines}'
