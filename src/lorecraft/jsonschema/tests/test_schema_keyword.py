"""The keyword a `jsonschema` error reports, read as a typed variant."""

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError

from lorecraft.core.mapping import Plain
from lorecraft.core.num import UnsignedInt

from ..json_type import JsonType
from ..schema_keyword import (
    AdditionalPropertiesKeyword,
    ConstKeyword,
    Dependency,
    DependentRequiredKeyword,
    EnumKeyword,
    Keyword,
    MaxPropertiesKeyword,
    MinPropertiesKeyword,
    OtherKeyword,
    PatternKeyword,
    RequiredKeyword,
    TypeKeyword,
    UnevaluatedPropertiesKeyword,
    keyword_of,
)


def _first_error(schema: dict[str, Plain], instance: Plain) -> SchemaValidationError:
    for error in Draft202012Validator(schema).iter_errors(instance):
        return error
    raise AssertionError('the instance was expected to break the schema')


def _keyword(schema: dict[str, Plain], instance: Plain) -> Keyword:
    return keyword_of(_first_error(schema, instance))


@pytest.mark.unit
class TestKeywordOf:
    def test_keyword_of_with_a_type_name_returns_that_name(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'string'}
        instance: Plain = 1

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == TypeKeyword((JsonType.STRING,)), 'a type written as a name holds that name'

    def test_keyword_of_with_an_array_of_type_names_returns_every_name(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': ['string', 'null']}
        instance: Plain = 1

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == TypeKeyword((JsonType.STRING, JsonType.NULL)), 'a type written as an array holds every name'

    def test_keyword_of_with_required_returns_the_fields_it_names(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'required': ['a', 'b']}
        instance: Plain = {}

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == RequiredKeyword(('a', 'b')), 'required names its fields in order'

    def test_keyword_of_with_dependent_required_returns_each_field_and_its_dependencies(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'dependentRequired': {'a': ['b', 'c']}}
        instance: Plain = {'a': 1}

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == DependentRequiredKeyword((Dependency('a', ('b', 'c')),)), (
            'each field maps to its dependencies'
        )

    def test_keyword_of_with_additional_properties_returns_its_variant(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'additionalProperties': False}
        instance: Plain = {'a': 1}

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == AdditionalPropertiesKeyword(), 'additionalProperties is its own variant'

    def test_keyword_of_with_unevaluated_properties_returns_its_variant(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'unevaluatedProperties': False}
        instance: Plain = {'a': 1}

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == UnevaluatedPropertiesKeyword(), 'unevaluatedProperties is its own variant'

    def test_keyword_of_with_enum_returns_the_allowed_values(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'enum': ['a', 1]}
        instance: Plain = 'z'

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == EnumKeyword(('a', 1)), 'enum holds the values it allows'

    def test_keyword_of_with_const_returns_the_allowed_value(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'const': 'a'}
        instance: Plain = 'z'

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == ConstKeyword('a'), 'const holds the one value it allows'

    def test_keyword_of_with_pattern_returns_the_expression(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'pattern': '^a'}
        instance: Plain = 'z'

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == PatternKeyword('^a'), 'pattern holds its expression'

    def test_keyword_of_with_min_properties_returns_the_limit(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'minProperties': 2}
        instance: Plain = {}

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == MinPropertiesKeyword(UnsignedInt(2)), 'minProperties holds its limit'

    def test_keyword_of_with_max_properties_returns_the_limit(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'maxProperties': 0}
        instance: Plain = {'a': 1}

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == MaxPropertiesKeyword(UnsignedInt(0)), 'maxProperties holds its limit'

    def test_keyword_of_with_any_other_keyword_returns_other(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'minLength': 3}
        instance: Plain = 'a'

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == OtherKeyword(), 'a keyword the package does not read is other'

    def test_keyword_of_with_a_required_that_names_a_non_string_returns_other(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'required': [1]}
        instance: Plain = {}

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == OtherKeyword(), 'a required that is not an array of strings is not read as one'

    def test_keyword_of_with_a_dependent_required_that_names_a_non_string_returns_other(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'dependentRequired': {'a': [1]}}
        instance: Plain = {'a': 1}

        #: When
        keyword = _keyword(schema, instance)

        #: Then
        assert keyword == OtherKeyword(), 'a dependentRequired entry that is not an array of strings is not read'
