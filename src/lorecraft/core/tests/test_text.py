"""Tests for shared text values."""

import pytest

from ..text import EmptyStrError, NonEmptyStr


@pytest.mark.unit
class TestNonEmptyStr:
    def test_non_empty_value_is_a_string(self) -> None:
        #: Given
        value = 'schema'

        #: When
        text = NonEmptyStr.parse(value)

        #: Then
        assert text.value == value, 'the value retains its string contents'
        assert str(text) == value, 'the value prints as its string contents'

    def test_empty_value_raises_shared_error(self) -> None:
        #: When
        with pytest.raises(EmptyStrError) as exc_info:
            NonEmptyStr.parse('')

        #: Then
        assert exc_info.value.value == '', 'the error retains the rejected value'
