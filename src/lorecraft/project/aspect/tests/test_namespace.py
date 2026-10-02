"""Aspect namespace parsing and prefix matching."""

import pytest

from lorecraft.core.error import Error

from ..filename import AspectFilename
from ..namespace import AspectNamespace, EmptyAspectNamespaceError, InvalidAspectNamespaceCharacterError


@pytest.mark.unit
class TestAspectNamespace:
    def test_parse_with_a_single_letter_preserves_namespace(self) -> None:
        #: Given
        valid_namespace = 'a'

        #: When
        parsed = AspectNamespace.parse(valid_namespace)

        #: Then
        assert str(parsed) == valid_namespace, 'a single lowercase letter is a whole namespace'

    def test_parse_with_a_hyphen_between_single_letters_preserves_namespace(self) -> None:
        #: Given
        valid_namespace = 'a-b'

        #: When
        parsed = AspectNamespace.parse(valid_namespace)

        #: Then
        assert str(parsed) == valid_namespace, 'a hyphen between two one-letter words is a valid separator'

    def test_parse_with_nested_words_and_digits_preserves_namespace(self) -> None:
        #: Given
        valid_namespace = 'python-errors2-v3'

        #: When
        parsed = AspectNamespace.parse(valid_namespace)

        #: Then
        assert str(parsed) == valid_namespace, 'hyphen-separated lowercase words with digits are kept as supplied'

    def test_parse_with_an_empty_string_raises_empty_namespace_error(self) -> None:
        #: Given
        empty_namespace = ''

        #: When
        with pytest.raises(EmptyAspectNamespaceError) as exc_info:
            AspectNamespace.parse(empty_namespace)

        #: Then
        assert type(exc_info.value).__bases__ == (Error,), 'the variant derives from Error directly, not a family'

    def test_parse_with_a_single_invalid_character_raises_character_error_at_zero(self) -> None:
        #: Given
        invalid_namespace = 'X'

        #: When
        with pytest.raises(InvalidAspectNamespaceCharacterError) as exc_info:
            AspectNamespace.parse(invalid_namespace)

        #: Then
        assert exc_info.value.namespace == invalid_namespace, 'the error keeps the rejected namespace'
        assert exc_info.value.position == 0, f'the first character is the invalid one, got {exc_info.value.position}'
        assert exc_info.value.character == 'X', f'the uppercase letter is reported, got {exc_info.value.character!r}'
        assert repr(invalid_namespace) in str(exc_info.value), 'the message names the rejected namespace'

    def test_parse_with_a_mid_string_invalid_character_raises_character_error_at_it(self) -> None:
        #: Given
        invalid_namespace = 'pyThon'

        #: When
        with pytest.raises(InvalidAspectNamespaceCharacterError) as exc_info:
            AspectNamespace.parse(invalid_namespace)

        #: Then
        assert exc_info.value.namespace == invalid_namespace, 'the error keeps the rejected namespace'
        assert exc_info.value.position == 2, f'the uppercase letter is at position 2, got {exc_info.value.position}'
        assert exc_info.value.character == 'T', f'the uppercase letter is reported, got {exc_info.value.character!r}'
        assert repr(invalid_namespace) in str(exc_info.value), 'the message names the rejected namespace'

    def test_parse_with_a_double_hyphen_raises_character_error_at_the_second_hyphen(self) -> None:
        #: Given
        invalid_namespace = 'a--b'

        #: When
        with pytest.raises(InvalidAspectNamespaceCharacterError) as exc_info:
            AspectNamespace.parse(invalid_namespace)

        #: Then
        assert exc_info.value.namespace == invalid_namespace, 'the error keeps the rejected namespace'
        assert exc_info.value.position == 2, f'the second hyphen is the invalid one, got {exc_info.value.position}'
        assert exc_info.value.character == '-', f'the hyphen is reported, got {exc_info.value.character!r}'
        assert repr(invalid_namespace) in str(exc_info.value), 'the message names the rejected namespace'

    def test_parse_with_a_trailing_hyphen_raises_character_error_at_the_hyphen(self) -> None:
        #: Given
        invalid_namespace = 'a-'

        #: When
        with pytest.raises(InvalidAspectNamespaceCharacterError) as exc_info:
            AspectNamespace.parse(invalid_namespace)

        #: Then
        assert exc_info.value.namespace == invalid_namespace, 'the error keeps the rejected namespace'
        assert exc_info.value.position == 1, f'the trailing hyphen is the invalid one, got {exc_info.value.position}'
        assert exc_info.value.character == '-', f'the hyphen is reported, got {exc_info.value.character!r}'
        assert repr(invalid_namespace) in str(exc_info.value), 'the message names the rejected namespace'

    def test_is_prefix_of_with_the_namespace_itself_returns_true(self) -> None:
        #: Given
        namespace = AspectNamespace.parse('python')
        filename = AspectFilename.parse('python')

        #: When
        is_prefix = namespace.is_prefix_of(filename)

        #: Then
        assert is_prefix, 'a filename equal to the namespace is governed by it'

    def test_is_prefix_of_with_a_hyphen_continuation_returns_true(self) -> None:
        #: Given
        namespace = AspectNamespace.parse('python')
        filename = AspectFilename.parse('python-errors')

        #: When
        is_prefix = namespace.is_prefix_of(filename)

        #: Then
        assert is_prefix, 'a filename continuing the namespace after a hyphen is governed by it'

    def test_is_prefix_of_with_a_name_merely_starting_with_the_namespace_returns_false(self) -> None:
        #: Given
        namespace = AspectNamespace.parse('python')
        filename = AspectFilename.parse('pythonic')

        #: When
        is_prefix = namespace.is_prefix_of(filename)

        #: Then
        assert not is_prefix, 'a filename sharing the letters but not the hyphen is outside the namespace'
