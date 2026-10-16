"""The position of an index into a YAML text."""

import time

import pytest

from lorecraft.core.num import NonZeroUnsignedInt

from ..position import LineIndex
from ..reader import read_yaml
from ..tree import YamlMapping, YamlPosition


def _at(line: int, column: int) -> YamlPosition:
    return YamlPosition(NonZeroUnsignedInt(line), NonZeroUnsignedInt(column))


@pytest.mark.unit
class TestPositionAt:
    def test_position_at_with_the_start_of_the_text_returns_the_first_line_and_column(self) -> None:
        #: When
        position = LineIndex('a: b\n').position_at(0)

        #: Then
        assert position == _at(1, 1), f'the first character is at 1:1, got {position!r}'

    def test_position_at_with_an_index_after_line_feeds_counts_from_the_line_start(self) -> None:
        #: When
        position = LineIndex('a: b\nc: d\n').position_at(8)

        #: Then
        assert position == _at(2, 4), f'the column restarts after a line feed, got {position!r}'

    @pytest.mark.parametrize(('text', 'index'), [('a\r\nbc', 4), ('a\rbc', 3), ('a\nbc', 3)])
    def test_position_at_with_each_line_break_counts_it_once(self, text: str, index: int) -> None:
        #: When
        position = LineIndex(text).position_at(index)

        #: Then
        assert position == _at(2, 2), f'{text!r} breaks one line before its second character, got {position!r}'

    def test_position_at_with_byte_order_marks_counts_them_as_characters(self) -> None:
        #: When
        position = LineIndex('a: ﻿﻿b').position_at(6)

        #: Then
        assert position == _at(1, 7), f'a U+FEFF takes a column, got {position!r}'

    @pytest.mark.parametrize('separator', ['\x85', '\u2028', '\u2029'])
    def test_position_at_with_a_line_separator_stays_on_the_line(self, separator: str) -> None:
        #: When
        position = LineIndex(f'a{separator}bc').position_at(3)

        #: Then
        assert position == _at(1, 4), f'U+{ord(separator):04X} ends no line, got {position!r}'

    def test_position_at_with_a_long_text_locates_every_key_in_linear_time(self) -> None:
        #: Given
        count = 20_000
        text = ''.join(f'k{i}: x\n' for i in range(count))

        #: When
        started = time.perf_counter()
        problem = read_yaml(text)
        elapsed = time.perf_counter() - started

        #: Then
        assert isinstance(problem, YamlMapping), f'the text is a mapping, got {problem!r}'
        last = problem.entries[-1][0]
        assert last.position == _at(count, 1), f'the last key is on the last line, got {last.position!r}'
        assert elapsed < 5, f'{count} entries read in {elapsed:.1f}s, which a quadratic scan of the breaks would exceed'

    def test_read_yaml_with_two_texts_that_differ_only_after_the_first_locates_each_in_its_own_text(self) -> None:
        #: Given
        first = 'a: b\n'
        second = 'a: b\n\n\nc: d\n'

        #: When
        read_yaml(first)
        problem = read_yaml(second)

        #: Then
        assert isinstance(problem, YamlMapping), f'the text is a mapping, got {problem!r}'
        assert problem.entries[1][0].position == _at(4, 1), 'no line index survives the read of another text'
