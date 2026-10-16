"""Validation facts returned across the JSON Schema package boundary."""

from collections.abc import Callable, Mapping

import pytest

from lorecraft.core.mapping import FrozenMapping, Plain

from .. import (
    JsonType,
    RequiredKeyword,
    TypeKeyword,
    UnevaluatedPropertiesKeyword,
    Violation,
    best_violation,
    validate,
)

Validation = Callable[[Mapping[str, Plain], Plain], tuple[Violation, ...] | Violation | None]


@pytest.mark.unit
class TestValidate:
    @pytest.mark.parametrize('instance', ['oops', []])
    def test_validate_with_a_non_object_instance_returns_a_type_violation(self, instance: Plain) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'x': {'type': 'string'}}}

        #: When
        violations = validate(schema, instance)

        #: Then
        assert len(violations) == 1, 'a value with the wrong type produces one violation'
        assert violations[0].keyword == TypeKeyword((JsonType.OBJECT,)), 'the violation retains the expected type'

    @pytest.mark.parametrize('instance', ['oops', []])
    def test_best_violation_with_a_non_object_instance_returns_a_type_violation(self, instance: Plain) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'x': {'type': 'string'}}}

        #: When
        violation = best_violation(schema, instance)

        #: Then
        assert violation is not None, 'a value with the wrong type has a best violation'
        assert violation.keyword == TypeKeyword((JsonType.OBJECT,)), 'the violation retains the expected type'

    @pytest.mark.parametrize('validate_one', [validate, best_violation])
    def test_validation_with_a_nested_unevaluated_property_keeps_evaluated_keys(self, validate_one: Validation) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'properties': {'x': {'type': 'object', 'properties': {'ok': {}}, 'unevaluatedProperties': False}}
        }
        instance: Plain = {'x': {'ok': 1, 'extra': 2}}

        #: When
        result = validate_one(schema, instance)
        violation = result[0] if isinstance(result, tuple) else result

        #: Then
        assert violation is not None, 'the nested extra property produces a violation'
        assert violation.evaluated_properties == frozenset({'ok'}), 'facts come from the failing nested object'

    def test_validate_with_mutated_inputs_keeps_owned_violation_values(self) -> None:
        #: Given
        required = ['name']
        prefs_schema: dict[str, Plain] = {'x': 1}
        properties: dict[str, Plain] = {'prefs': prefs_schema}
        schema: dict[str, Plain] = {'type': 'object', 'required': required, 'properties': properties}
        prefs_instance: dict[str, Plain] = {'theme': 'dark'}
        instance: dict[str, Plain] = {'prefs': prefs_instance}

        #: When
        violation = validate(schema, instance)[0]
        required.append('email')
        prefs_schema['x'] = 2
        prefs_instance['theme'] = 'light'

        #: Then
        assert violation.instance == FrozenMapping.from_plain({'prefs': {'theme': 'dark'}}), (
            'the violation owns a frozen copy of its instance'
        )
        assert violation.schema == FrozenMapping.from_plain(
            {'type': 'object', 'required': ['name'], 'properties': {'prefs': {'x': 1}}}
        ), 'the violation owns a frozen copy of its schema'

    def test_validate_with_a_missing_required_property_returns_its_owned_facts(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'required': ['name']}
        instance: Plain = {}

        #: When
        violations = validate(schema, instance)

        #: Then
        assert len(violations) == 1, 'one missing property produces one violation'
        assert violations[0].message == "'name' is a required property", 'the validator message stays verbatim'
        assert violations[0].keyword == RequiredKeyword(('name',)), 'the keyword fact is typed'
        assert violations[0].path == (), 'the missing property has no instance path'

    def test_validate_with_unevaluated_properties_returns_evaluated_keys(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'known': {'type': 'string'}},
            'unevaluatedProperties': False,
        }
        instance: Plain = {'known': 'value', 'extra': 'value'}

        #: When
        violations = validate(schema, instance)

        #: Then
        assert len(violations) == 1, 'one rejected extra property produces one violation'
        assert violations[0].keyword == UnevaluatedPropertiesKeyword(), 'the failed keyword is retained'
        assert violations[0].evaluated_properties == frozenset({'known'}), (
            'evaluated keys let project code identify the rejected property'
        )

    def test_best_violation_with_multiple_failures_returns_one_best_match(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'anyOf': [{'type': 'string'}, {'type': 'integer'}]}
        instance: Plain = []

        #: When
        violation = best_violation(schema, instance)

        #: Then
        assert violation is not None, 'a value rejected by every alternative has a best violation'
        assert violation.message == '[] is not valid under any of the given schemas', (
            'the validator best-match selection is retained'
        )

    def test_best_violation_with_a_subschema_uses_its_root_reference_context(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'$ref': '#/$defs/text'}
        root_schema: dict[str, Plain] = {
            'type': 'object',
            '$defs': {'text': {'type': 'string'}},
            'unevaluatedProperties': schema,
        }

        #: When
        violation = best_violation(schema, 1, root_schema=root_schema)

        #: Then
        assert violation is not None, 'the reference resolves in the containing schema'
        assert violation.message == "1 is not of type 'string'", 'the referenced constraint supplies the failure'
