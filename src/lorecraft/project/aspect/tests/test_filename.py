"""Aspect filename parsing."""

import pytest

from ..filename import AspectFilename
from ..name import InvalidAspectNameCharacterError


@pytest.mark.unit
class TestAspectFilename:
    def test_parse_with_a_single_word_preserves_entire_name(self) -> None:
        #: Given
        filename = 'logging'

        #: When
        parsed = AspectFilename.parse(filename)

        #: Then
        assert str(parsed.name) == filename, 'a single-word stem is the whole name'
        assert str(parsed) == filename, 'formatting round trips the single-word filename'

    def test_parse_with_hyphenated_words_preserves_entire_name(self) -> None:
        #: Given
        filename = 'python-errors-handling'

        #: When
        parsed = AspectFilename.parse(filename)

        #: Then
        assert str(parsed.name) == filename, 'a hyphenated stem is one name, not split at its hyphens'
        assert str(parsed) == filename, 'formatting round trips the hyphenated filename'

    def test_parse_with_an_underscore_preserves_entire_name(self) -> None:
        #: Given
        filename = 'my_name'

        #: When
        parsed = AspectFilename.parse(filename)

        #: Then
        assert str(parsed.name) == filename, 'a stem with an underscore is the whole name'
        assert str(parsed) == filename, 'formatting round trips the underscored filename'

    def test_parse_with_trailing_separator_raises_invalid_name_error(self) -> None:
        #: Given
        filename = 'python-'

        #: When
        with pytest.raises(InvalidAspectNameCharacterError) as exc_info:
            AspectFilename.parse(filename)

        #: Then
        assert exc_info.value.name == filename, 'the name error passes through, retaining the whole stem'
        assert exc_info.value.position == len(filename) - 1, 'the trailing separator is the invalid character'
