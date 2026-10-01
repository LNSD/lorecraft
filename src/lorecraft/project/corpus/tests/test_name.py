"""Corpus name parsing."""

import pytest

from lorecraft.core.error import Error

from ..name import CorpusName, EmptyCorpusNameError, InvalidCorpusNameCharacterError


@pytest.mark.unit
class TestCorpusName:
    def test_parse_with_a_lowercase_word_returns_value_object(self) -> None:
        #: Given
        valid_name = 'code'

        #: When
        corpus = CorpusName.parse(valid_name)

        #: Then
        assert corpus.value == valid_name, 'a lowercase word is kept as the corpus name'
        assert str(corpus) == valid_name, 'the lowercase name is usable in paths and reports'

    def test_parse_with_a_leading_underscore_returns_value_object(self) -> None:
        #: Given
        valid_name = '_internal'

        #: When
        corpus = CorpusName.parse(valid_name)

        #: Then
        assert corpus.value == valid_name, 'a corpus name may start with an underscore'
        assert str(corpus) == valid_name, 'the underscore-led name is usable in paths and reports'

    def test_parse_with_underscores_and_a_digit_returns_value_object(self) -> None:
        #: Given
        valid_name = 'my_corpus_2'

        #: When
        corpus = CorpusName.parse(valid_name)

        #: Then
        assert corpus.value == valid_name, 'underscores and a trailing digit are kept in the corpus name'
        assert str(corpus) == valid_name, 'the snake-case name with a digit is usable in paths and reports'

    def test_parse_with_empty_name_raises_empty_corpus_name_error(self) -> None:
        #: Given
        invalid_name = ''

        #: When
        with pytest.raises(EmptyCorpusNameError) as exc_info:
            CorpusName.parse(invalid_name)

        #: Then
        assert type(exc_info.value).__bases__ == (Error,), 'the variant derives from Error directly, not a family'
        assert str(exc_info.value) == 'corpus name cannot be empty', 'the error explains the empty-name case'

    def test_parse_with_a_single_dot_raises_character_error_at_position_zero(self) -> None:
        #: Given
        invalid_name = '.'
        position = 0

        #: When
        with pytest.raises(InvalidCorpusNameCharacterError) as exc_info:
            CorpusName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for a lone dot'
        assert exc_info.value.position == position, 'the error locates the dot at position 0'
        assert exc_info.value.character == invalid_name[position], (
            'the error identifies the dot as the invalid character'
        )
        assert repr(invalid_name) in str(exc_info.value), 'the message safely displays the name with a lone dot'

    def test_parse_with_a_double_dot_raises_character_error_at_position_zero(self) -> None:
        #: Given
        invalid_name = '..'
        position = 0

        #: When
        with pytest.raises(InvalidCorpusNameCharacterError) as exc_info:
            CorpusName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for a double dot'
        assert exc_info.value.position == position, 'the error locates the first dot at position 0'
        assert exc_info.value.character == invalid_name[position], (
            'the error identifies the first dot as the invalid character'
        )
        assert repr(invalid_name) in str(exc_info.value), 'the message safely displays the name with a double dot'

    def test_parse_with_a_hyphen_raises_character_error_at_the_hyphen(self) -> None:
        #: Given
        invalid_name = 'my-corpus'
        position = 2

        #: When
        with pytest.raises(InvalidCorpusNameCharacterError) as exc_info:
            CorpusName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for a hyphen'
        assert exc_info.value.position == position, 'the error locates the hyphen at position 2'
        assert exc_info.value.character == invalid_name[position], (
            'the error identifies the hyphen as the invalid character'
        )
        assert repr(invalid_name) in str(exc_info.value), 'the message safely displays the name with a hyphen'

    def test_parse_with_a_leading_uppercase_letter_raises_character_error_at_position_zero(self) -> None:
        #: Given
        invalid_name = 'Code'
        position = 0

        #: When
        with pytest.raises(InvalidCorpusNameCharacterError) as exc_info:
            CorpusName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for an uppercase letter'
        assert exc_info.value.position == position, 'the error locates the uppercase letter at position 0'
        assert exc_info.value.character == invalid_name[position], (
            'the error identifies the uppercase letter as the invalid character'
        )
        assert repr(invalid_name) in str(exc_info.value), (
            'the message safely displays the name with an uppercase letter'
        )

    def test_parse_with_a_leading_digit_raises_character_error_at_position_zero(self) -> None:
        #: Given
        invalid_name = '2code'
        position = 0

        #: When
        with pytest.raises(InvalidCorpusNameCharacterError) as exc_info:
            CorpusName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for a leading digit'
        assert exc_info.value.position == position, 'the error locates the digit at position 0'
        assert exc_info.value.character == invalid_name[position], (
            'the error identifies the digit as the invalid character'
        )
        assert repr(invalid_name) in str(exc_info.value), 'the message safely displays the name with a leading digit'

    def test_parse_with_a_space_raises_character_error_at_the_space(self) -> None:
        #: Given
        invalid_name = 'code feat'
        position = 4

        #: When
        with pytest.raises(InvalidCorpusNameCharacterError) as exc_info:
            CorpusName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for a space'
        assert exc_info.value.position == position, 'the error locates the space at position 4'
        assert exc_info.value.character == invalid_name[position], (
            'the error identifies the space as the invalid character'
        )
        assert repr(invalid_name) in str(exc_info.value), 'the message safely displays the name with a space'

    def test_parse_with_a_slash_raises_character_error_at_the_slash(self) -> None:
        #: Given
        invalid_name = 'code/feat'
        position = 4

        #: When
        with pytest.raises(InvalidCorpusNameCharacterError) as exc_info:
            CorpusName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for a slash'
        assert exc_info.value.position == position, 'the error locates the slash at position 4'
        assert exc_info.value.character == invalid_name[position], (
            'the error identifies the slash as the invalid character'
        )
        assert repr(invalid_name) in str(exc_info.value), 'the message safely displays the name with a slash'

    def test_parse_with_a_backslash_raises_character_error_at_the_backslash(self) -> None:
        #: Given
        invalid_name = 'code\\feat'
        position = 4

        #: When
        with pytest.raises(InvalidCorpusNameCharacterError) as exc_info:
            CorpusName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for a backslash'
        assert exc_info.value.position == position, 'the error locates the backslash at position 4'
        assert exc_info.value.character == invalid_name[position], (
            'the error identifies the backslash as the invalid character'
        )
        assert repr(invalid_name) in str(exc_info.value), 'the message safely displays the name with a backslash'

    def test_parse_with_a_nul_character_raises_character_error_at_the_nul_character(self) -> None:
        #: Given
        invalid_name = 'co\0de'
        position = 2

        #: When
        with pytest.raises(InvalidCorpusNameCharacterError) as exc_info:
            CorpusName.parse(invalid_name)

        #: Then
        assert exc_info.value.name == invalid_name, 'the error retains the name rejected for a NUL character'
        assert exc_info.value.position == position, 'the error locates the NUL character at position 2'
        assert exc_info.value.character == invalid_name[position], (
            'the error identifies the NUL character as the invalid character'
        )
        assert repr(invalid_name) in str(exc_info.value), 'the message safely displays the name with a NUL character'

    def test_direct_construction_with_empty_name_raises_empty_corpus_name_error(self) -> None:
        #: Given
        invalid_name = ''

        #: When
        with pytest.raises(EmptyCorpusNameError) as exc_info:
            CorpusName(invalid_name)

        #: Then
        assert str(exc_info.value) == 'corpus name cannot be empty', 'direct construction checks the same invariant'
