"""Counting the lines of a text, as the budget on a skill's `SKILL.md` counts them."""

import pytest

from ..lines import count_lines, line_at, newline_offsets, split_lines
from ..num import UnsignedInt


@pytest.mark.unit
class TestCountLines:
    def test_count_lines_with_empty_text_returns_zero(self) -> None:
        #: Given
        text = ''

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == UnsignedInt(0), f'empty text holds no line, got {lines}'

    def test_count_lines_with_a_final_newline_adds_no_line(self) -> None:
        #: Given
        text = 'one\ntwo\n'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == UnsignedInt(2), f'the newline ending the last line opens no new one, got {lines}'

    def test_count_lines_without_a_final_newline_counts_the_last_line(self) -> None:
        #: Given
        text = 'one\ntwo'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == UnsignedInt(2), f'a last line with no newline is still a line, got {lines}'

    def test_count_lines_with_frontmatter_counts_its_lines_too(self) -> None:
        #: Given
        # three lines of frontmatter block, its delimiters included, and two of body
        text = '---\nname: review\n---\n# Review\nBody.\n'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == UnsignedInt(5), f'the frontmatter block counts like any other line, got {lines}'

    def test_count_lines_with_blank_lines_counts_each(self) -> None:
        #: Given
        text = '# Review\n\n\nBody.\n'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == UnsignedInt(4), f'a blank line is a line, got {lines}'

    def test_count_lines_with_crlf_endings_counts_each_once(self) -> None:
        #: Given
        text = 'one\r\ntwo\r\n'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == UnsignedInt(2), f'a `\\r\\n` ending ends one line, not two, got {lines}'

    def test_count_lines_with_a_form_feed_inside_a_line_does_not_break_it(self) -> None:
        #: Given
        text = 'one\x0ctwo\n'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == UnsignedInt(1), f'a form feed ends no line, as CommonMark has it, got {lines}'

    def test_count_lines_with_a_unicode_line_separator_does_not_break_the_line(self) -> None:
        #: Given
        text = 'one\u2028two\n'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == UnsignedInt(1), f'U+2028 ends no line, as CommonMark has it, got {lines}'

    def test_count_lines_with_lone_carriage_returns_counts_each_as_a_line_end(self) -> None:
        #: Given
        text = 'one\rtwo\rthree'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == UnsignedInt(3), f'a lone `\\r` ends a line, as CommonMark has it, got {lines}'

    def test_count_lines_with_a_final_carriage_return_adds_no_line(self) -> None:
        #: Given
        text = 'one\rtwo\r'

        #: When
        lines = count_lines(text)

        #: Then
        assert lines == UnsignedInt(2), f'the `\\r` ending the last line opens no new one, got {lines}'


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
        assert lines == ('one\x0ctwo\u2028three', 'four'), f'CommonMark ends a line at no other character, got {lines}'

    def test_split_lines_with_empty_text_holds_no_line(self) -> None:
        #: Given
        text = ''

        #: When
        lines = split_lines(text)

        #: Then
        assert lines == (), f'empty text holds no line, got {lines}'


@pytest.mark.unit
class TestNewlineOffsets:
    def test_newline_offsets_with_empty_text_returns_no_offset(self) -> None:
        #: Given
        text = ''

        #: When
        offsets = newline_offsets(text)

        #: Then
        assert offsets == (), f'empty text holds no line break, got {offsets}'

    def test_newline_offsets_with_a_crlf_break_returns_one_offset_for_the_pair(self) -> None:
        #: Given
        text = 'one\r\ntwo\n'

        #: When
        offsets = newline_offsets(text)

        #: Then
        assert offsets == (3, 8), f'a CRLF break is one break, at its `\\r`, got {offsets}'

    def test_newline_offsets_with_a_lone_carriage_return_returns_its_offset(self) -> None:
        #: Given
        text = 'one\rtwo\n'

        #: When
        offsets = newline_offsets(text)

        #: Then
        assert offsets == (3, 7), f'a lone `\\r` is a line break, got {offsets}'

    def test_newline_offsets_with_a_vertical_tab_returns_no_offset_for_it(self) -> None:
        #: Given
        separator = '\x0b'
        text = f'one{separator}two\nthree'

        #: When
        offsets = newline_offsets(text)

        #: Then
        assert offsets == (7,), f'{separator!r} is no line break, as CommonMark has it, got {offsets}'

    def test_newline_offsets_with_a_form_feed_returns_no_offset_for_it(self) -> None:
        #: Given
        separator = '\x0c'
        text = f'one{separator}two\nthree'

        #: When
        offsets = newline_offsets(text)

        #: Then
        assert offsets == (7,), f'{separator!r} is no line break, as CommonMark has it, got {offsets}'

    def test_newline_offsets_with_a_next_line_returns_no_offset_for_it(self) -> None:
        #: Given
        separator = '\x85'
        text = f'one{separator}two\nthree'

        #: When
        offsets = newline_offsets(text)

        #: Then
        assert offsets == (7,), f'{separator!r} is no line break, as CommonMark has it, got {offsets}'

    def test_newline_offsets_with_a_line_separator_returns_no_offset_for_it(self) -> None:
        #: Given
        separator = '\u2028'
        text = f'one{separator}two\nthree'

        #: When
        offsets = newline_offsets(text)

        #: Then
        assert offsets == (7,), f'{separator!r} is no line break, as CommonMark has it, got {offsets}'

    def test_newline_offsets_with_a_paragraph_separator_returns_no_offset_for_it(self) -> None:
        #: Given
        separator = '\u2029'
        text = f'one{separator}two\nthree'

        #: When
        offsets = newline_offsets(text)

        #: Then
        assert offsets == (7,), f'{separator!r} is no line break, as CommonMark has it, got {offsets}'


@pytest.mark.unit
class TestLineAt:
    def test_line_at_with_text_after_each_kind_of_break_returns_the_line_it_is_on(self) -> None:
        #: Given
        text = 'a\nb\r\nc\rd'

        #: When
        lines = [line_at(text, offset) for offset in (0, 2, 5, 7)]

        #: Then
        assert lines == [1, 2, 3, 4], f'a line feed, a CRLF pair and a lone `\\r` each end one line, got {lines}'

    def test_line_at_with_bytes_counts_lines_as_the_text_they_decode_to(self) -> None:
        #: Given
        data = b'a\nb\r\nc\rd\xff'
        offset = data.index(b'\xff')

        #: When
        line = line_at(data, offset)

        #: Then
        assert line == 4, f'bytes break lines at the same bytes as text does, got {line}'

    def test_line_at_with_an_offset_between_the_halves_of_a_crlf_pair_returns_the_line_the_pair_ends(self) -> None:
        #: Given
        text = 'a\r\nb'

        #: When
        lines = [line_at(text, offset) for offset in (1, 2, 3)]

        #: Then
        assert lines == [1, 1, 2], f'a CRLF pair ends one line, and its two halves are on it, got {lines}'

    def test_line_at_with_bytes_and_an_offset_between_the_halves_of_a_crlf_pair_returns_the_line_the_pair_ends(
        self,
    ) -> None:
        #: Given
        data = b'a\r\nb'

        #: When
        lines = [line_at(data, offset) for offset in (1, 2, 3)]

        #: Then
        assert lines == [1, 1, 2], f'bytes are located as text is, got {lines}'
