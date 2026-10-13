"""The source text a diagnostic is excerpted from, read by one-based line number."""

import pytest

from lorecraft.project.syntax import LineNumber

from ..diagnostic_text import SourceText


def _line(number: int) -> LineNumber:
    return LineNumber.from_int(number)


@pytest.mark.unit
class TestSourceText:
    def test_line_with_the_first_line_returns_the_first_text(self) -> None:
        #: Given
        source = SourceText(('---', 'name: a'))

        #: When
        text = source.line(_line(1))

        #: Then
        assert text == '---', 'line 1 is the first line, not the second'

    def test_line_with_the_last_line_returns_the_last_text(self) -> None:
        #: Given
        source = SourceText(('---', 'name: a'))

        #: When
        text = source.line(_line(2))

        #: Then
        assert text == 'name: a', 'the last line is read by its own number'

    def test_has_line_with_the_last_line_returns_true(self) -> None:
        #: Given
        source = SourceText(('---', 'name: a'))

        #: When
        has_line = source.has_line(_line(2))

        #: Then
        assert has_line is True, 'the file runs to its last line'

    def test_has_line_with_a_line_past_the_end_returns_false(self) -> None:
        #: Given
        source = SourceText(('---', 'name: a'))

        #: When
        has_line = source.has_line(_line(3))

        #: Then
        assert has_line is False, 'a line the file does not run to cannot be excerpted'
