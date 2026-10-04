"""The one-based line number every node of a parse tree is positioned by."""

import pytest

from lorecraft.core.num import NonPositiveIntError

from ..position import LineNumber


@pytest.mark.unit
class TestLineNumber:
    def test_from_int_zero_raises_non_positive_int(self) -> None:
        #: Given
        rejected = 0

        #: When
        with pytest.raises(NonPositiveIntError) as exc_info:
            LineNumber.from_int(rejected)

        #: Then
        assert exc_info.value.value == rejected, 'the error carries the rejected number'
        assert str(rejected) in str(exc_info.value), 'the message names the rejected number'

    def test_from_int_negative_raises_non_positive_int(self) -> None:
        #: Given
        rejected = -1

        #: When
        with pytest.raises(NonPositiveIntError) as exc_info:
            LineNumber.from_int(rejected)

        #: Then
        assert exc_info.value.value == rejected, 'the error carries the rejected number'
        assert str(rejected) in str(exc_info.value), 'the message names the rejected number'

    def test_number_of_a_line_from_an_integer_is_that_integer(self) -> None:
        #: Given
        line = LineNumber.from_int(7)

        #: When
        number = line.number

        #: Then
        assert number == 7, f'a line number reads back as the integer it was built from, got {number!r}'

    def test_line_number_of_the_first_line_prints_as_its_number(self) -> None:
        #: Given
        line = LineNumber.from_int(1)

        #: When
        text = str(line)

        #: Then
        assert text == '1', f'a line number prints as the bare number, got {text!r}'
