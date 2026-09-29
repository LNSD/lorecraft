"""The one-based line number every node of a parse tree is positioned by."""

import pytest

from ..position import InvalidLineNumberError, LineNumber


@pytest.mark.unit
class TestLineNumber:
    def test_line_number_zero_raises_invalid_line_number(self) -> None:
        #: Given
        rejected = 0

        #: When
        with pytest.raises(InvalidLineNumberError) as exc_info:
            LineNumber(rejected)

        #: Then
        assert exc_info.value.value == rejected, 'the error carries the rejected number'

    def test_line_number_negative_raises_invalid_line_number(self) -> None:
        #: Given
        rejected = -1

        #: When
        with pytest.raises(InvalidLineNumberError) as exc_info:
            LineNumber(rejected)

        #: Then
        assert exc_info.value.value == rejected, 'the error carries the rejected number'

    def test_line_number_of_the_first_line_prints_as_its_number(self) -> None:
        #: Given
        line = LineNumber(1)

        #: When
        text = str(line)

        #: Then
        assert text == '1', f'a line number prints as the bare number, got {text!r}'
