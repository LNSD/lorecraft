"""Schema inspection facts exposed across the JSON Schema package boundary."""

import pytest

from lorecraft.core.mapping import Plain

from .. import (
    SchemaHasIdentifier,
    SchemaHasSameInstanceReferenceCycle,
    SchemaHasUnresolvableReference,
    SchemaMetaError,
    SchemaUsesForeignDialect,
    check_schema,
)


@pytest.mark.unit
class TestCheckSchema:
    def test_check_schema_with_an_invalid_schema_returns_an_owned_message(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'required': 'name'}

        #: When
        failure = check_schema(schema)

        #: Then
        assert failure == SchemaMetaError("'name' is not of type 'array'"), (
            'the validator message crosses as an owned fact'
        )

    def test_check_schema_with_a_valid_schema_returns_no_failure(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'name': {'type': 'string'}}}

        #: When
        failure = check_schema(schema)

        #: Then
        assert failure is None, 'a valid schema has no inspection failure'

    def test_check_schema_with_an_identifier_returns_identifier_refusal(self) -> None:
        #: Given
        root: dict[str, Plain] = {'$id': 'https://example.test/schema'}
        expected = SchemaHasIdentifier()

        #: When
        failure = check_schema(root)

        #: Then
        assert failure == expected, 'an identifier is returned as an owned refusal'

    def test_check_schema_with_a_foreign_dialect_returns_dialect_refusal(self) -> None:
        #: Given
        root: dict[str, Plain] = {'$schema': 'https://json-schema.org/draft/2019-09/schema'}
        expected = SchemaUsesForeignDialect('https://json-schema.org/draft/2019-09/schema')

        #: When
        failure = check_schema(root)

        #: Then
        assert failure == expected, 'a foreign dialect is returned as an owned refusal'

    def test_check_schema_with_an_unresolvable_reference_returns_reference_refusal(self) -> None:
        #: Given
        root: dict[str, Plain] = {'$ref': 'outside.json'}
        expected = SchemaHasUnresolvableReference('outside.json')

        #: When
        failure = check_schema(root)

        #: Then
        assert failure == expected, 'an unresolvable reference is returned as an owned refusal'

    def test_check_schema_with_a_same_instance_reference_cycle_returns_cycle_refusal(self) -> None:
        #: Given
        root: dict[str, Plain] = {'$ref': '#'}
        expected = SchemaHasSameInstanceReferenceCycle('#')

        #: When
        failure = check_schema(root)

        #: Then
        assert failure == expected, 'a same-instance reference cycle is returned as an owned refusal'
