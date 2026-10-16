"""Schema inspection facts exposed across the JSON Schema package boundary."""

import pytest

from lorecraft.core.mapping import Plain

from .. import SchemaMetaError, check_schema


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
