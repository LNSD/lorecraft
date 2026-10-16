"""Validation facts returned across the JSON Schema package boundary."""

from collections.abc import Callable, Mapping

import pytest
from jsonschema import Draft202012Validator

from lorecraft.core.mapping import FrozenMapping, Plain

from .. import (
    CheckedSchema,
    JsonType,
    RequiredKeyword,
    SchemaHasUnresolvableReference,
    SchemaMetaError,
    TypeKeyword,
    UnevaluatedPropertiesKeyword,
    Violation,
    additional_message,
    best_violation,
    dependency_message,
    required_message,
    unevaluated_message,
    validate,
)

Validation = Callable[[Mapping[str, Plain], Plain], tuple[Violation, ...] | Violation | None]


def _checked(schema: Mapping[str, Plain]) -> CheckedSchema:
    """Return the schema ready to validate, narrowing the refusal away for a schema the test knows is sound."""
    checked = CheckedSchema.check(schema)
    assert isinstance(checked, CheckedSchema), 'the test schema passes the schema check'
    return checked


def _library_message(schema: Mapping[str, Plain], instance: Plain) -> str:
    """Return the first message the installed validator library reports for the instance."""
    return tuple(Draft202012Validator(schema).iter_errors(instance))[0].message


def _paths(violations: tuple[Violation, ...]) -> tuple[tuple[str | int, ...], ...]:
    """Return each violation's instance path, the part of the order the test is about."""
    return tuple(violation.path for violation in violations)


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


@pytest.mark.unit
class TestCheckedSchema:
    def test_check_with_a_wrong_keyword_type_returns_a_meta_schema_refusal(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 5}

        #: When
        refusal = CheckedSchema.check(schema)

        #: Then
        assert isinstance(refusal, SchemaMetaError), 'a schema the library would raise on is refused before validate'

    def test_check_with_a_dangling_reference_returns_an_unresolvable_reference_refusal(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'$ref': '#/$defs/missing'}

        #: When
        refusal = CheckedSchema.check(schema)

        #: Then
        assert refusal == SchemaHasUnresolvableReference('#/$defs/missing'), 'the dangling reference is named'

    def test_check_with_an_invalid_pattern_returns_a_meta_schema_refusal(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'pattern': '('}

        #: When
        refusal = CheckedSchema.check(schema)

        #: Then
        assert isinstance(refusal, SchemaMetaError), 'a schema the library would raise on is refused before validate'

    def test_init_called_directly_raises_type_error(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'string'}

        #: When
        with pytest.raises(TypeError):
            CheckedSchema(schema)

    def test_validate_with_twelve_array_items_orders_the_paths_as_text(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'items': {'type': 'string'}}
        instance: Plain = list(range(12))
        checked = _checked(schema)

        #: When
        violations = checked.validate(instance)

        #: Then
        assert _paths(violations) == (
            (0,),
            (1,),
            (10,),
            (11,),
            (2,),
            (3,),
            (4,),
            (5,),
            (6,),
            (7,),
            (8,),
            (9,),
        ), 'index 10 sorts before index 2 because each path segment compares as text'

    def test_validate_with_two_failing_properties_returns_them_in_path_order(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'properties': {'b': {'type': 'string'}, 'a': {'type': 'string'}}}
        instance: Plain = {'b': 1, 'a': 2}
        checked = _checked(schema)

        #: When
        violations = checked.validate(instance)

        #: Then
        assert _paths(violations) == (('a',), ('b',)), 'violations are ordered by instance path, not schema order'

    def test_validate_with_a_type_mismatch_returns_the_library_wording(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'string'}
        instance: Plain = 1
        expected = "1 is not of type 'string'"
        checked = _checked(schema)
        library_message = _library_message(schema, instance)

        #: When
        violations = checked.validate(instance)

        #: Then
        assert library_message == expected, "the pinned wording is the installed library's"
        assert len(violations) == 1, f'one failure is reported, got {violations}'
        assert violations[0].message == expected, 'the violation keeps the library wording verbatim'

    def test_validate_with_a_missing_required_property_returns_the_library_wording(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'required': ['x']}
        instance: Plain = {}
        expected = "'x' is a required property"
        checked = _checked(schema)
        library_message = _library_message(schema, instance)

        #: When
        violations = checked.validate(instance)

        #: Then
        assert library_message == expected, "the pinned wording is the installed library's"
        assert len(violations) == 1, f'one failure is reported, got {violations}'
        assert violations[0].message == expected, 'the violation keeps the library wording verbatim'

    def test_validate_with_a_missing_dependency_returns_the_library_wording(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'dependentRequired': {'x': ['y']}}
        instance: Plain = {'x': 1}
        expected = "'y' is a dependency of 'x'"
        checked = _checked(schema)
        library_message = _library_message(schema, instance)

        #: When
        violations = checked.validate(instance)

        #: Then
        assert library_message == expected, "the pinned wording is the installed library's"
        assert len(violations) == 1, f'one failure is reported, got {violations}'
        assert violations[0].message == expected, 'the violation keeps the library wording verbatim'

    def test_validate_with_an_additional_property_returns_the_library_wording(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'additionalProperties': False}
        instance: Plain = {'x': 1}
        expected = "Additional properties are not allowed ('x' was unexpected)"
        checked = _checked(schema)
        library_message = _library_message(schema, instance)

        #: When
        violations = checked.validate(instance)

        #: Then
        assert library_message == expected, "the pinned wording is the installed library's"
        assert len(violations) == 1, f'one failure is reported, got {violations}'
        assert violations[0].message == expected, 'the violation keeps the library wording verbatim'

    def test_validate_with_an_unevaluated_property_returns_the_library_wording(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'unevaluatedProperties': False}
        instance: Plain = {'x': 1}
        expected = "Unevaluated properties are not allowed ('x' was unexpected)"
        checked = _checked(schema)
        library_message = _library_message(schema, instance)

        #: When
        violations = checked.validate(instance)

        #: Then
        assert library_message == expected, "the pinned wording is the installed library's"
        assert len(violations) == 1, f'one failure is reported, got {violations}'
        assert violations[0].message == expected, 'the violation keeps the library wording verbatim'


@pytest.mark.unit
class TestMessages:
    def test_required_message_with_a_field_name_matches_the_library_wording(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'required': ['x']}
        instance: Plain = {}
        expected = _library_message(schema, instance)

        #: When
        message = required_message('x')

        #: Then
        assert message == expected, 'the function reproduces the library text'

    def test_dependency_message_with_a_field_name_matches_the_library_wording(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'dependentRequired': {'x': ['y']}}
        instance: Plain = {'x': 1}
        expected = _library_message(schema, instance)

        #: When
        message = dependency_message('x', 'y')

        #: Then
        assert message == expected, 'the function reproduces the library text'

    def test_additional_message_with_a_field_name_matches_the_library_wording(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'additionalProperties': False}
        instance: Plain = {'x': 1}
        expected = _library_message(schema, instance)

        #: When
        message = additional_message('x')

        #: Then
        assert message == expected, 'the function reproduces the library text'

    def test_unevaluated_message_with_a_field_name_matches_the_library_wording(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'unevaluatedProperties': False}
        instance: Plain = {'x': 1}
        expected = _library_message(schema, instance)

        #: When
        message = unevaluated_message('x')

        #: Then
        assert message == expected, 'the function reproduces the library text'
