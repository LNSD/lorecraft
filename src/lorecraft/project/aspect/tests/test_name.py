"""Aspect name parsing."""

import pytest

from ..name import AspectName, InvalidAspectNameCharacterError


@pytest.mark.unit
class TestAspectName:
    def test_parse_with_a_single_word_preserves_name(self) -> None:
        #: Given
        valid_name = 'header'

        #: When
        parsed = AspectName.parse(valid_name)

        #: Then
        assert str(parsed) == valid_name, 'a single lowercase word is kept as supplied'

    def test_parse_with_a_hyphen_between_words_preserves_name(self) -> None:
        #: Given
        valid_name = 'header-schema'

        #: When
        parsed = AspectName.parse(valid_name)

        #: Then
        assert str(parsed) == valid_name, 'a hyphen between two words is a valid separator'

    def test_parse_with_an_underscore_between_words_preserves_name(self) -> None:
        #: Given
        valid_name = 'header_schema'

        #: When
        parsed = AspectName.parse(valid_name)

        #: Then
        assert str(parsed) == valid_name, 'an underscore between two words is a valid separator'

    def test_parse_with_an_underscore_and_a_hyphen_preserves_name(self) -> None:
        #: Given
        valid_name = 'header_schema-v2'

        #: When
        parsed = AspectName.parse(valid_name)

        #: Then
        assert str(parsed) == valid_name, 'underscore and hyphen separators mix within one name'

    def test_parse_with_a_leading_underscore_raises_character_error(self) -> None:
        #: Given
        invalid_name = '_header'

        #: When
        with pytest.raises(InvalidAspectNameCharacterError) as exc_info:
            AspectName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'a name cannot start with an underscore, and the error keeps it'

    def test_parse_with_a_trailing_underscore_raises_character_error(self) -> None:
        #: Given
        invalid_name = 'header_'

        #: When
        with pytest.raises(InvalidAspectNameCharacterError) as exc_info:
            AspectName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'a name cannot end with an underscore, and the error keeps it'

    def test_parse_with_a_double_underscore_raises_character_error(self) -> None:
        #: Given
        invalid_name = 'header__schema'

        #: When
        with pytest.raises(InvalidAspectNameCharacterError) as exc_info:
            AspectName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, (
            'two underscores in a row are rejected, and the error keeps the name'
        )

    def test_parse_with_a_hyphen_before_an_underscore_raises_character_error(self) -> None:
        #: Given
        invalid_name = 'header-_schema'

        #: When
        with pytest.raises(InvalidAspectNameCharacterError) as exc_info:
            AspectName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'adjacent separators are rejected, and the error keeps the name'

    def test_parse_with_an_uppercase_letter_raises_character_error(self) -> None:
        #: Given
        invalid_name = 'Header'

        #: When
        with pytest.raises(InvalidAspectNameCharacterError) as exc_info:
            AspectName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'an uppercase letter is rejected, and the error keeps the name'
