"""Name parsing: schema stems, aspect names, aspect filenames and corpus names."""

import pytest

from lorecraft_core.error import Error
from lorecraft_project.aspect import (
    AspectFilename,
    AspectName,
    AspectNamespace,
    AspectNamespaceError,
    InvalidAspectFilenameError,
    InvalidAspectNameCharacterError,
)
from lorecraft_project.corpus import CorpusName, CorpusNameError, EmptyCorpusNameError, InvalidCorpusNameCharacterError

from ..name import SchemaName, parse_schema_name, schema_name_stem


@pytest.mark.unit
class TestSchemaName:
    def test_corpus_tuple_has_corpus_stem(self) -> None:
        #: Given
        name: SchemaName = (CorpusName.parse('code'),)

        #: When
        stem = schema_name_stem(name)

        #: Then
        assert stem == 'code', 'a corpus schema has no namespace segment'

    def test_parse_treats_everything_after_corpus_as_namespace(self) -> None:
        #: Given
        stem = 'code-python-errors'

        #: When
        name = parse_schema_name(stem)

        #: Then
        assert name == (CorpusName.parse('code'), AspectNamespace.parse('python-errors')), (
            'the full suffix is one namespace'
        )

    def test_namespace_tuple_joins_kebab_namespace(self) -> None:
        #: Given
        name: SchemaName = (
            CorpusName.parse('code'),
            AspectNamespace.parse('python-errors-handling'),
        )

        #: When
        stem = schema_name_stem(name)

        #: Then
        assert stem == 'code-python-errors-handling', 'the namespace follows the corpus'

    def test_parse_with_underscore_in_namespace_raises_namespace_error(self) -> None:
        #: Given
        stem = 'code-python_errors_handling'

        #: When
        with pytest.raises(AspectNamespaceError) as exc_info:
            parse_schema_name(stem)

        #: Then
        assert exc_info.value.namespace == 'python_errors_handling', 'the error retains the rejected namespace'


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
        with pytest.raises(InvalidAspectFilenameError) as exc_info:
            AspectFilename.parse(filename)

        #: Then
        assert exc_info.value.filename == filename, 'the error retains the rejected filename'
        assert isinstance(exc_info.value.__cause__, InvalidAspectNameCharacterError), (
            'the cause identifies the invalid character'
        )


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
        assert isinstance(exc_info.value, CorpusNameError), 'the error belongs to the corpus-name hierarchy'
        assert isinstance(exc_info.value, Error), 'the error belongs to the package hierarchy'
        assert exc_info.value.name == invalid_name, 'the rejected value is available without parsing the message'
        assert exc_info.value.character is None, 'an empty name has no invalid character'
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
