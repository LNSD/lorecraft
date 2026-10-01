"""Aspect name parsing."""

import pytest

from lorecraft.core.error import Error

from ..name import AspectName, EmptyAspectNameError, InvalidAspectNameCharacterError


@pytest.mark.unit
class TestAspectName:
    def test_parse_with_a_single_letter_preserves_name(self) -> None:
        #: Given
        valid_name = 'a'

        #: When
        parsed = AspectName.parse(valid_name)

        #: Then
        assert str(parsed) == valid_name, 'a single lowercase letter is a whole name'

    def test_parse_with_a_hyphen_between_single_letters_preserves_name(self) -> None:
        #: Given
        valid_name = 'a-b'

        #: When
        parsed = AspectName.parse(valid_name)

        #: Then
        assert str(parsed) == valid_name, 'a hyphen between two one-letter words is a valid separator'

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
        assert exc_info.value.position == 7, f'the second underscore is the invalid one, got {exc_info.value.position}'
        assert exc_info.value.character == '_', f'the underscore is reported, got {exc_info.value.character!r}'
        assert repr(invalid_name) in str(exc_info.value), 'the message names the rejected name'

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
        assert exc_info.value.position == 0, (
            f'the leading uppercase letter is the invalid one, got {exc_info.value.position}'
        )
        assert exc_info.value.character == 'H', f'the uppercase letter is reported, got {exc_info.value.character!r}'
        assert repr(invalid_name) in str(exc_info.value), 'the message names the rejected name'

    def test_parse_with_a_mid_name_uppercase_letter_raises_character_error_at_it(self) -> None:
        #: Given
        invalid_name = 'heXder'

        #: When
        with pytest.raises(InvalidAspectNameCharacterError) as exc_info:
            AspectName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'the error keeps the rejected name'
        assert exc_info.value.position == 2, f'the uppercase letter is at position 2, got {exc_info.value.position}'
        assert exc_info.value.character == 'X', f'the uppercase letter is reported, got {exc_info.value.character!r}'
        assert repr(invalid_name) in str(exc_info.value), 'the message names the rejected name'

    def test_parse_with_an_empty_string_raises_empty_name_error(self) -> None:
        #: Given
        empty_name = ''

        #: When
        with pytest.raises(EmptyAspectNameError) as exc_info:
            AspectName.parse(empty_name)

        #: Then
        assert type(exc_info.value).__bases__ == (Error,), 'the variant derives from Error directly, not a family'
