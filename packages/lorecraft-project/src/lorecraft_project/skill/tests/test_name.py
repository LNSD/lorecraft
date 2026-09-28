"""Skill name parsing against the Agent Skills specification's name rule."""

import pytest

from lorecraft_core.error import Error

from ..name import (
    EmptySkillNameError,
    InvalidSkillNameCharacterError,
    SkillName,
    SkillNameError,
    SkillNameTooLongError,
)


@pytest.mark.unit
class TestSkillName:
    def test_parse_with_a_single_letter_preserves_the_spelling(self) -> None:
        #: Given
        valid_name = 'a'

        #: When
        parsed = SkillName.parse(valid_name)

        #: Then
        assert parsed.value == valid_name, 'a one-letter name is kept exactly as supplied'

    def test_parse_with_a_kebab_case_name_preserves_the_spelling(self) -> None:
        #: Given
        valid_name = 'code-check'

        #: When
        parsed = SkillName.parse(valid_name)

        #: Then
        assert parsed.value == valid_name, 'a kebab-case name is kept exactly as supplied'

    def test_parse_with_digits_in_its_segments_preserves_the_spelling(self) -> None:
        #: Given
        valid_name = 'k8s-1'

        #: When
        parsed = SkillName.parse(valid_name)

        #: Then
        assert parsed.value == valid_name, 'digits are allowed inside and as a whole segment'

    def test_parse_with_sixty_four_characters_preserves_the_spelling(self) -> None:
        #: Given
        valid_name = 'a' * 64

        #: When
        parsed = SkillName.parse(valid_name)

        #: Then
        assert parsed.value == valid_name, 'sixty-four characters is the longest name the rule allows'

    def test_str_with_valid_name_returns_the_spelling(self) -> None:
        #: Given
        name = SkillName.parse('code-check')

        #: When
        text = str(name)

        #: Then
        assert text == 'code-check', f'str should round-trip the name, got {text!r}'

    def test_parse_with_empty_name_raises_empty_skill_name_error(self) -> None:
        #: Given
        invalid_name = ''

        #: When
        with pytest.raises(EmptySkillNameError) as exc_info:
            SkillName.parse(invalid_name)

        #: Then
        assert isinstance(exc_info.value, SkillNameError), 'the error belongs to the skill-name hierarchy'
        assert isinstance(exc_info.value, Error), 'the error belongs to the package hierarchy'
        assert exc_info.value.name == invalid_name, 'the error retains the rejected name'

    def test_parse_with_sixty_five_characters_raises_too_long_error_with_length(self) -> None:
        #: Given
        invalid_name = 'a' * 65

        #: When
        with pytest.raises(SkillNameTooLongError) as exc_info:
            SkillName.parse(invalid_name)

        #: Then
        assert isinstance(exc_info.value, SkillNameError), 'the error belongs to the skill-name hierarchy'
        assert exc_info.value.name == invalid_name, 'the error retains the rejected name'
        assert exc_info.value.length == 65, f'the error reports the length, got {exc_info.value.length}'

    def test_parse_with_an_uppercase_letter_raises_character_error_at_position_zero(self) -> None:
        #: Given
        invalid_name = 'Code'
        position = 0

        #: When
        with pytest.raises(InvalidSkillNameCharacterError) as exc_info:
            SkillName.parse(invalid_name)

        #: Then
        assert isinstance(exc_info.value, SkillNameError), 'the error belongs to the skill-name hierarchy'
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for the uppercase C'
        assert exc_info.value.position == position, (
            f'the error locates the uppercase C at position 0, got position {exc_info.value.position}'
        )
        assert exc_info.value.character == invalid_name[position], 'the error identifies the uppercase C as invalid'

    def test_parse_with_a_leading_hyphen_raises_character_error_at_position_zero(self) -> None:
        #: Given
        invalid_name = '-a'
        position = 0

        #: When
        with pytest.raises(InvalidSkillNameCharacterError) as exc_info:
            SkillName.parse(invalid_name)

        #: Then
        assert isinstance(exc_info.value, SkillNameError), 'the error belongs to the skill-name hierarchy'
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for the leading hyphen'
        assert exc_info.value.position == position, (
            f'the error locates the leading hyphen at position 0, got position {exc_info.value.position}'
        )
        assert exc_info.value.character == invalid_name[position], 'the error identifies the leading hyphen as invalid'

    def test_parse_with_a_trailing_hyphen_raises_character_error_at_the_last_position(self) -> None:
        #: Given
        invalid_name = 'a-'
        position = 1

        #: When
        with pytest.raises(InvalidSkillNameCharacterError) as exc_info:
            SkillName.parse(invalid_name)

        #: Then
        assert isinstance(exc_info.value, SkillNameError), 'the error belongs to the skill-name hierarchy'
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for the trailing hyphen'
        assert exc_info.value.position == position, (
            f'the error locates the trailing hyphen at position 1, got position {exc_info.value.position}'
        )
        assert exc_info.value.character == invalid_name[position], 'the error identifies the trailing hyphen as invalid'

    def test_parse_with_a_double_hyphen_raises_character_error_at_the_second_hyphen(self) -> None:
        #: Given
        invalid_name = 'a--b'
        position = 2

        #: When
        with pytest.raises(InvalidSkillNameCharacterError) as exc_info:
            SkillName.parse(invalid_name)

        #: Then
        assert isinstance(exc_info.value, SkillNameError), 'the error belongs to the skill-name hierarchy'
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for the second hyphen'
        assert exc_info.value.position == position, (
            f'the error locates the second hyphen at position 2, got position {exc_info.value.position}'
        )
        assert exc_info.value.character == invalid_name[position], 'the error identifies the second hyphen as invalid'

    def test_parse_with_an_underscore_raises_character_error_at_the_underscore(self) -> None:
        #: Given
        invalid_name = 'a_b'
        position = 1

        #: When
        with pytest.raises(InvalidSkillNameCharacterError) as exc_info:
            SkillName.parse(invalid_name)

        #: Then
        assert isinstance(exc_info.value, SkillNameError), 'the error belongs to the skill-name hierarchy'
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for the underscore'
        assert exc_info.value.position == position, (
            f'the error locates the underscore at position 1, got position {exc_info.value.position}'
        )
        assert exc_info.value.character == invalid_name[position], 'the error identifies the underscore as invalid'

    def test_parse_with_a_space_raises_character_error_at_the_space(self) -> None:
        #: Given
        invalid_name = 'a b'
        position = 1

        #: When
        with pytest.raises(InvalidSkillNameCharacterError) as exc_info:
            SkillName.parse(invalid_name)

        #: Then
        assert isinstance(exc_info.value, SkillNameError), 'the error belongs to the skill-name hierarchy'
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for the space'
        assert exc_info.value.position == position, (
            f'the error locates the space at position 1, got position {exc_info.value.position}'
        )
        assert exc_info.value.character == invalid_name[position], 'the error identifies the space as invalid'

    def test_parse_with_a_non_ascii_letter_raises_character_error_at_the_non_ascii_letter(self) -> None:
        #: Given
        invalid_name = 'ré'
        position = 1

        #: When
        with pytest.raises(InvalidSkillNameCharacterError) as exc_info:
            SkillName.parse(invalid_name)

        #: Then
        assert isinstance(exc_info.value, SkillNameError), 'the error belongs to the skill-name hierarchy'
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for the accented letter'
        assert exc_info.value.position == position, (
            f'the error locates the accented letter at position 1, got position {exc_info.value.position}'
        )
        assert exc_info.value.character == invalid_name[position], 'the error identifies the accented letter as invalid'

    def test_direct_construction_with_invalid_name_raises_character_error(self) -> None:
        #: Given
        invalid_name = 'Bad'

        #: When
        with pytest.raises(InvalidSkillNameCharacterError) as exc_info:
            SkillName(invalid_name)

        #: Then
        assert exc_info.value.position == 0, 'direct construction checks the same invariant as parse'
