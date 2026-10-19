"""The frontmatter schema a structure specification states.

`parse` checks a schema the specification may hold, and `validate` reports a document's frontmatter against it.
"""

import pytest

from lorecraft.core.mapping import FrozenMapping, Plain
from lorecraft.core.num import UnsignedInt
from lorecraft.jsonschema import JsonType

from ..frontmatter_problem import (
    BlockProblem,
    FieldCount,
    FieldGuidance,
    FieldLimit,
    InvalidValueProblem,
    MaxFields,
    MinFields,
    MissingFieldProblem,
    OneOfValues,
    OtherBlockConstraint,
    OtherValueConstraint,
    PatternMismatch,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from ..frontmatter_schema import FrontmatterSchema
from ..structure_failure import (
    CyclicFrontmatterSchemaRefKeyword,
    ForeignFrontmatterDialect,
    IdentifiedFrontmatterSchema,
    InvalidFrontmatterSchema,
    UnresolvableFrontmatterSchemaRefKeyword,
    UntypedFrontmatterSchema,
)


@pytest.mark.unit
class TestFrontmatterSchema:
    def test_equal_schemas_compare_and_hash_by_schema(self) -> None:
        #: Given
        schema = FrozenMapping.from_plain({'type': 'object', 'required': ['name']})
        first = FrontmatterSchema(schema=schema)
        second = FrontmatterSchema(schema=schema)

        #: When
        #: Then
        assert first == second, 'schemas with the same contents compare equal'
        assert hash(first) == hash(second), 'schemas with the same contents hash equally'

    def test_parse_with_an_object_schema_keeps_it(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'required': ['name'], 'description': 'read by people'}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        frontmatter = FrontmatterSchema.parse(mapping)

        #: Then
        assert isinstance(frontmatter, FrontmatterSchema), f'the schema is held, got {frontmatter!r}'
        assert frontmatter.schema == FrozenMapping.from_plain(schema), 'a well-formed object schema is held unchanged'

    def test_parse_with_the_draft_2020_12_dialect_in_schema_keeps_it(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object'}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        frontmatter = FrontmatterSchema.parse(mapping)

        #: Then
        assert isinstance(frontmatter, FrontmatterSchema), f'the schema is held, got {frontmatter!r}'
        assert frontmatter.schema == FrozenMapping.from_plain(schema), 'naming the dialect the check applies is allowed'

    def test_parse_with_root_combinators_beside_the_type_keeps_it(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'if': {'properties': {'type': {'const': 'pattern'}}},
            'then': {'required': ['scope']},
        }
        mapping = FrozenMapping.from_plain(schema)

        #: When
        frontmatter = FrontmatterSchema.parse(mapping)

        #: Then
        assert isinstance(frontmatter, FrontmatterSchema), f'the schema is held, got {frontmatter!r}'
        assert frontmatter.schema == FrozenMapping.from_plain(schema), (
            'a combinator at the root is allowed next to the object type'
        )

    def test_parse_with_an_id_inside_an_enum_value_keeps_it(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'ref': {'enum': [{'$id': 'data'}]}}}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        frontmatter = FrontmatterSchema.parse(mapping)

        #: Then
        assert isinstance(frontmatter, FrontmatterSchema), f'the schema is held, got {frontmatter!r}'
        assert frontmatter.schema == FrozenMapping.from_plain(schema), (
            'a value under enum is data, not a schema, so its $id is no resource'
        )

    def test_parse_with_a_malformed_schema_returns_invalid_frontmatter_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'required': 'name'}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == InvalidFrontmatterSchema("'name' is not of type 'array'"), (
            f'a malformed schema is refused with what the meta-schema rejected, got {failure!r}'
        )

    def test_parse_without_a_type_returns_untyped_frontmatter_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'required': ['name']}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == UntypedFrontmatterSchema(), 'an implied object type is refused'

    def test_parse_with_a_non_object_type_returns_untyped_frontmatter_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'array'}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == UntypedFrontmatterSchema(), 'a frontmatter is always a mapping'

    def test_parse_with_a_type_list_returns_untyped_frontmatter_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': ['object', 'null']}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == UntypedFrontmatterSchema(), 'the type is exactly "object"'

    def test_parse_with_a_dangling_local_ref_returns_unresolvable_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'name': {'$ref': '#/$defs/missing'}}}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == UnresolvableFrontmatterSchemaRefKeyword('#/$defs/missing'), (
            'a reference to a location the schema lacks is refused at load, not when a document is validated'
        )

    def test_parse_with_a_ref_to_another_resource_returns_unresolvable_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'name': {'$ref': 'https://example.com/name.json'}},
        }
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == UnresolvableFrontmatterSchemaRefKeyword('https://example.com/name.json'), (
            'a remote reference is refused, never fetched'
        )

    def test_parse_with_a_ref_to_its_own_schema_returns_cyclic_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', '$ref': '#'}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == CyclicFrontmatterSchemaRefKeyword('#'), (
            'a reference that only leads back to itself is refused'
        )

    def test_parse_with_a_ref_cycle_through_definitions_returns_cyclic_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'allOf': [{'$ref': '#/$defs/a'}],
            '$defs': {'a': {'anyOf': [{'$ref': '#/$defs/b'}]}, 'b': {'$ref': '#/$defs/a'}},
        }
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == CyclicFrontmatterSchemaRefKeyword('#/$defs/a'), 'a cycle through applicators is refused'

    def test_parse_with_a_ref_cycle_through_dependent_schemas_returns_cyclic_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'dependentSchemas': {'a': {'$ref': '#'}}}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == CyclicFrontmatterSchemaRefKeyword('#'), 'a dependent schema applies to the same value'

    def test_parse_with_an_unused_ref_cycle_in_defs_returns_cyclic_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            '$defs': {'a': {'$ref': '#/$defs/b'}, 'b': {'$ref': '#/$defs/a'}},
        }
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert isinstance(failure, CyclicFrontmatterSchemaRefKeyword), 'a cycle nothing refers to is still refused'

    def test_parse_with_a_recursive_ref_below_properties_returns_the_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'child': {'$ref': '#'}}}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        parsed = FrontmatterSchema.parse(mapping)

        #: Then
        assert isinstance(parsed, FrontmatterSchema), 'a reference applied to a smaller value is not a cycle'

    def test_parse_with_a_local_ref_to_a_definition_returns_the_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'name': {'$ref': '#/$defs/name'}},
            '$defs': {'name': {'type': 'string'}},
        }
        mapping = FrozenMapping.from_plain(schema)

        #: When
        parsed = FrontmatterSchema.parse(mapping)

        #: Then
        assert isinstance(parsed, FrontmatterSchema), 'a reference that resolves inside the schema is accepted'

    def test_parse_with_a_ref_to_an_anchor_returns_the_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'name': {'$ref': '#label'}},
            '$defs': {'name': {'$anchor': 'label', 'type': 'string'}},
        }
        mapping = FrozenMapping.from_plain(schema)

        #: When
        parsed = FrontmatterSchema.parse(mapping)

        #: Then
        assert isinstance(parsed, FrontmatterSchema), 'a reference to an `$anchor` of the schema is accepted'

    def test_parse_with_an_empty_ref_returns_the_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'child': {'$ref': ''}}}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        parsed = FrontmatterSchema.parse(mapping)

        #: Then
        assert isinstance(parsed, FrontmatterSchema), 'the empty reference is the schema itself, as `#` is'

    def test_parse_with_a_ref_to_a_non_schema_returns_unresolvable_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'required': ['name'],
            'properties': {'name': {'$ref': '#/required/0'}},
        }
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == UnresolvableFrontmatterSchemaRefKeyword('#/required/0'), (
            'a reference that finds a value that is not a schema is refused'
        )

    def test_parse_with_a_dangling_dynamic_ref_returns_unresolvable_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'name': {'$dynamicRef': '#/$defs/missing'}}}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == UnresolvableFrontmatterSchemaRefKeyword('#/$defs/missing'), (
            'a dynamic reference is held to the same'
        )

    def test_parse_with_a_remote_dynamic_ref_returns_unresolvable_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'name': {'$dynamicRef': 'https://example.com/name.json'}},
        }
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == UnresolvableFrontmatterSchemaRefKeyword('https://example.com/name.json'), (
            'a remote dynamic reference is refused, never fetched'
        )

    def test_parse_with_an_id_returns_frontmatter_schema_id(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'$id': 'https://example.com/code', 'type': 'object'}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == IdentifiedFrontmatterSchema(), 'an $id would change how relative $refs resolve'

    def test_parse_with_an_id_in_a_nested_schema_returns_frontmatter_schema_id(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'name': {'$id': 'https://example.com/name'}}}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == IdentifiedFrontmatterSchema(), 'an $id at any depth makes a resource of its own'

    def test_parse_with_a_foreign_dialect_returns_foreign_frontmatter_dialect(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'$schema': 'http://json-schema.org/draft-07/schema#', 'type': 'object'}
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == ForeignFrontmatterDialect('http://json-schema.org/draft-07/schema#'), (
            'a schema written for another dialect is refused'
        )

    def test_parse_with_a_foreign_dialect_in_a_nested_schema_returns_foreign_frontmatter_dialect(
        self,
    ) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            '$defs': {'scope': {'$schema': 'http://json-schema.org/draft-07/schema#', 'type': 'string'}},
        }
        mapping = FrozenMapping.from_plain(schema)

        #: When
        failure = FrontmatterSchema.parse(mapping)

        #: Then
        assert failure == ForeignFrontmatterDialect('http://json-schema.org/draft-07/schema#'), (
            'a nested schema may not switch dialect either'
        )

    def test_validate_with_a_conforming_frontmatter_returns_no_problems(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain({'type': 'object', 'required': ['name']}))
        data: dict[str, Plain] = {'name': 'guide'}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (), 'a frontmatter the schema accepts has no problems'

    def test_validate_without_two_required_fields_returns_one_missing_problem_each(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(
            schema=FrozenMapping.from_plain({'type': 'object', 'required': ['name', 'type']})
        )
        data: dict[str, Plain] = {}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            MissingFieldProblem('name', "'name' is a required property"),
            MissingFieldProblem('type', "'type' is a required property"),
        ), 'jsonschema reports each absent field once, however many the schema requires'

    def test_validate_with_one_of_two_required_fields_present_returns_a_missing_problem_for_the_other(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(
            schema=FrozenMapping.from_plain({'type': 'object', 'required': ['name', 'type']})
        )
        data: dict[str, Plain] = {'name': 'guide'}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (MissingFieldProblem('type', "'type' is a required property"),), (
            'a required field the frontmatter carries is not reported missing'
        )

    def test_validate_with_two_fields_at_fault_orders_the_problems_by_field_before_message(self) -> None:
        #: Given
        # `name` sorts before `type`, while their messages sort the other way round
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'name': {'type': 'string'}, 'type': {'enum': ['rule', 'pattern']}},
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'name': 3, 'type': 'guide'}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            WrongTypeProblem('name', "3 is not of type 'string'", (JsonType.STRING,), JsonType.INTEGER),
            InvalidValueProblem(
                'type',
                "'guide' is not one of ['rule', 'pattern']",
                OneOfValues(('rule', 'pattern')),
                guidance=FieldGuidance(allowed=('rule', 'pattern')),
            ),
        ), 'problems are ordered by the field they concern first, and by their message only within a field'

    def test_validate_with_fields_the_schema_does_not_allow_returns_one_unknown_field_problem_each(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'name': {}},
            'patternProperties': {'^x-': {}},
            'additionalProperties': False,
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'name': 'guide', 'x-owner': 'me', 'model': 'opus', 'tier': 1}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            UnknownFieldProblem(
                'model',
                "Additional properties are not allowed ('model' was unexpected)",
                known_fields=('name',),
            ),
            UnknownFieldProblem(
                'tier',
                "Additional properties are not allowed ('tier' was unexpected)",
                known_fields=('name',),
            ),
        ), 'each field neither properties nor patternProperties names is its own problem, naming the properties'

    def test_validate_with_fields_no_keyword_evaluates_returns_one_unknown_field_problem_each(self) -> None:
        #: Given
        # `name` and `description` are evaluated only through `allOf`, which `additionalProperties` would not see
        schema: dict[str, Plain] = {
            'type': 'object',
            'allOf': [{'$ref': '#/$defs/base'}],
            'properties': {'status': {}},
            'unevaluatedProperties': False,
            '$defs': {'base': {'properties': {'name': {}, 'description': {}}}},
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {
            'name': 'guide',
            'description': 'A guide.',
            'status': 'draft',
            'desc': 'x',
            'tier': 1,
        }
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            UnknownFieldProblem(
                'desc', "Unevaluated properties are not allowed ('desc' was unexpected)", known_fields=('status',)
            ),
            UnknownFieldProblem(
                'tier', "Unevaluated properties are not allowed ('tier' was unexpected)", known_fields=('status',)
            ),
        ), (
            'each field no keyword of the composed schema evaluates is its own problem, on that field, and the fields '
            'named are the properties of the schema holding the keyword, not those it evaluates through `allOf`'
        )

    def test_validate_with_unevaluated_fields_breaking_the_rule_schema_returns_an_invalid_value_problem_each(
        self,
    ) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'allOf': [{'properties': {'name': {}}}],
            'unevaluatedProperties': {'type': 'string'},
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'name': 3, 'owner': 'me', 'tier': 1}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (InvalidValueProblem('tier', "1 is not of type 'string'", OtherValueConstraint()),), (
            'an unevaluated field is held to the rule schema, and only one breaking it is a problem, on that field'
        )

    def test_validate_with_a_referenced_unevaluated_rule_resolves_against_the_root_schema(self) -> None:
        #: Given
        rule: dict[str, Plain] = {'$ref': '#/$defs/s'}
        schema: dict[str, Plain] = {
            'type': 'object',
            '$defs': {'s': {'type': 'string'}},
            'unevaluatedProperties': rule,
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        mapping = FrozenMapping.from_plain({'x': 1})

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (InvalidValueProblem('x', "1 is not of type 'string'", OtherValueConstraint()),), (
            'a referenced unevaluated rule resolves in the complete frontmatter schema'
        )

    def test_validate_with_an_enum_unevaluated_rule_keeps_its_message_and_typed_constraint(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'unevaluatedProperties': {'enum': ['yes', 'no']},
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        mapping = FrozenMapping.from_plain({'x': 'bad'})

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            InvalidValueProblem(
                'x',
                "'bad' is not one of ['yes', 'no']",
                OneOfValues(('yes', 'no')),
                guidance=FieldGuidance(allowed=('yes', 'no')),
            ),
        ), 'the plain enum retains its message punctuation and typed allowed values'

    def test_validate_with_a_value_of_the_wrong_type_returns_a_wrong_type_problem(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'name': {'type': 'string'}}}
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'name': 3}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            WrongTypeProblem('name', "3 is not of type 'string'", (JsonType.STRING,), JsonType.INTEGER),
        ), "the message is the validator's, and the types are the schema's and the value's"

    def test_validate_with_a_value_outside_an_enum_returns_an_invalid_value_problem(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'type': {'enum': ['rule', 'pattern']}}}
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'type': 'guide'}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            InvalidValueProblem(
                'type',
                "'guide' is not one of ['rule', 'pattern']",
                OneOfValues(('rule', 'pattern')),
                guidance=FieldGuidance(allowed=('rule', 'pattern')),
            ),
        ), 'a value of the right type breaking another rule is invalid, and the values allowed are carried'

    def test_validate_with_a_value_breaking_a_pattern_returns_the_pattern_and_the_comment(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'name': {'type': 'string', 'description': 'Kebab-case.', 'examples': ['setup-guide']}},
            'allOf': [{'properties': {'name': {'pattern': '^[a-z-]+$'}}, '$comment': 'Lowercase words only.'}],
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'name': 'Setup'}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            InvalidValueProblem(
                'name',
                "'Setup' does not match '^[a-z-]+$'",
                PatternMismatch('^[a-z-]+$'),
                reason=None,
                guidance=FieldGuidance(description='Kebab-case.', example='setup-guide'),
            ),
        ), "the `$comment` beside `properties` is not the failing subschema's, so it is no reason"

    def test_validate_with_a_failing_subschema_that_has_a_comment_returns_it_as_the_reason(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {
                'description': {
                    'type': 'string',
                    'allOf': [{'not': {'pattern': r'\.\s*$'}, '$comment': 'No trailing period.'}],
                }
            },
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'description': 'Load when x.'}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            InvalidValueProblem(
                'description',
                "'Load when x.' should not be valid under {'pattern': '\\\\.\\\\s*$'}",
                OtherValueConstraint(),
                reason='No trailing period.',
            ),
        ), "the failing subschema's `$comment` is the reason, and `not` has no typed constraint"

    def test_validate_with_a_value_other_than_a_const_returns_the_value_allowed(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'type': {'const': 'rule'}}}
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'type': 'guide'}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            InvalidValueProblem(
                'type',
                "'rule' was expected",
                OneOfValues(('rule',)),
                guidance=FieldGuidance(example='rule', allowed=('rule',)),
            ),
        ), 'a const is the one value allowed, and the example the property gives when it lists none'

    def test_validate_with_an_item_outside_an_enum_returns_an_untyped_constraint(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'tags': {'type': 'array', 'items': {'enum': ['a', 'b']}}},
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'tags': ['c']}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (InvalidValueProblem('tags', "'c' is not one of ['a', 'b']", OtherValueConstraint()),), (
            "the enum limits the items, not the field, so the field's own value is not said to be outside it"
        )

    def test_validate_with_an_item_breaking_a_pattern_returns_an_untyped_constraint(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'tags': {'type': 'array', 'items': {'pattern': '^[a-z]+$'}}},
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'tags': ['A']}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (InvalidValueProblem('tags', "'A' does not match '^[a-z]+$'", OtherValueConstraint()),), (
            "the pattern limits the items, not the field, so the field's own value is not said to break it"
        )

    def test_validate_with_an_unknown_key_inside_a_field_returns_an_invalid_value_problem_on_the_field(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'metadata': {'type': 'object', 'properties': {'author': {}}, 'additionalProperties': False}},
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'metadata': {'owner': 'me'}}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            InvalidValueProblem(
                'metadata',
                "Additional properties are not allowed ('owner' was unexpected)",
                OtherValueConstraint(),
            ),
        ), "a key inside a field makes that field's value invalid; the field itself is known"

    def test_validate_with_a_list_value_matches_it_as_a_json_array(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'tags': {'type': 'array', 'items': {'type': 'string'}}, 'meta': {'type': 'object'}},
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'tags': ['a', 'b'], 'meta': {'owner': 'me'}}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (), 'a frozen list is still a JSON array to the schema, and a frozen mapping an object'

    def test_validate_with_a_list_where_a_string_belongs_quotes_it_as_a_list(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'name': {'type': 'string'}}}
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'name': ['a']}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            WrongTypeProblem('name', "['a'] is not of type 'string'", (JsonType.STRING,), JsonType.ARRAY),
        ), 'the message quotes the value as the YAML decoded it, not as the tuple it is frozen into'

    def test_validate_with_a_rule_over_the_whole_block_returns_a_block_problem(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain({'type': 'object', 'minProperties': 1}))
        data: dict[str, Plain] = {}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            BlockProblem('{} should be non-empty', MinFields(FieldLimit(UnsignedInt(1))), FieldCount(UnsignedInt(0))),
        ), 'a rule over the block concerns no field'

    def test_validate_with_too_many_fields_returns_a_block_problem_with_the_limit_and_the_description(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'description': 'A guide.', 'maxProperties': 1}
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'name': 'guide', 'type': 'rule'}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            BlockProblem(
                "{'name': 'guide', 'type': 'rule'} has too many properties",
                MaxFields(FieldLimit(UnsignedInt(1))),
                FieldCount(UnsignedInt(2)),
                description='A guide.',
            ),
        ), 'the limit, the number of fields written and the root description are carried'

    def test_validate_with_another_rule_over_the_block_returns_a_block_problem_without_a_typed_limit(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'not': {'required': ['name']}}
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'name': 'guide'}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            BlockProblem(
                "{'name': 'guide'} should not be valid under {'required': ['name']}",
                OtherBlockConstraint(),
                FieldCount(UnsignedInt(1)),
            ),
        ), "a keyword with no typed constraint keeps the validator's wording"

    def test_validate_with_a_key_propertynames_rejects_returns_an_invalid_value_problem_on_the_key(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'propertyNames': {'pattern': '^[a-z]+$'}}
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'name': 'guide', 'B_': 2}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            InvalidValueProblem('B_', "'B_' does not match '^[a-z]+$'", PatternMismatch('^[a-z]+$')),
        ), 'a key the names rule rejects names a field, so it is not a problem of the whole block'

    def test_validate_with_a_missing_dependency_returns_an_invalid_value_problem_on_the_field(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'dependentRequired': {'status': ['owner', 'date']}}
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'status': 'draft', 'owner': 'me'}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            InvalidValueProblem('status', "'date' is a dependency of 'status'", OtherValueConstraint()),
        ), 'the field that needs another is the one at fault, and a dependency present is not reported'

    def test_validate_with_a_missing_field_the_schema_describes_returns_its_guidance(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'required': ['type', 'name'],
            'properties': {
                'type': {'enum': ['rule', 'pattern'], 'description': 'The kind of document.'},
                'name': {'type': 'string', 'examples': ['setup', 'install']},
            },
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            MissingFieldProblem(
                'type',
                "'type' is a required property",
                guidance=FieldGuidance(description='The kind of document.', allowed=('rule', 'pattern')),
            ),
            MissingFieldProblem('name', "'name' is a required property", guidance=FieldGuidance(example='setup')),
        ), 'the description, the values allowed and the first example come from the property'

    def test_validate_with_a_missing_field_and_an_object_example_returns_guidance(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'required': ['value'],
            'properties': {'value': {'examples': [{'k': 'v'}]}},
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        mapping = FrozenMapping.from_plain({})
        expected = MissingFieldProblem(
            'value', "'value' is a required property", guidance=FieldGuidance(example='{"k": "v"}')
        )

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (expected,), 'an object example is serialized as plain JSON guidance'

    def test_validate_with_a_missing_field_and_an_object_const_returns_guidance(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'required': ['value'],
            'properties': {'value': {'const': {'k': 'v'}}},
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        mapping = FrozenMapping.from_plain({})
        expected = MissingFieldProblem(
            'value',
            "'value' is a required property",
            guidance=FieldGuidance(example='{"k": "v"}', allowed=('{"k": "v"}',)),
        )

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (expected,), 'an object constant is serialized as plain JSON guidance'

    def test_validate_with_an_unevaluated_rule_and_an_object_example_returns_guidance(self) -> None:
        #: Given
        rule: dict[str, Plain] = {'type': 'string', 'examples': [{'k': 'v'}]}
        schema: dict[str, Plain] = {'type': 'object', 'unevaluatedProperties': rule}
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        mapping = FrozenMapping.from_plain({'x': 1})
        expected = InvalidValueProblem(
            'x',
            "1 is not of type 'string'",
            OtherValueConstraint(),
            guidance=FieldGuidance(example='{"k": "v"}'),
        )

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (expected,), 'a schema-valued object example is serialized as plain JSON guidance'

    def test_validate_with_an_unevaluated_rule_and_an_object_const_returns_guidance(self) -> None:
        #: Given
        rule: dict[str, Plain] = {'const': {'k': 'v'}}
        schema: dict[str, Plain] = {'type': 'object', 'unevaluatedProperties': rule}
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        mapping = FrozenMapping.from_plain({'x': 1})
        expected = InvalidValueProblem(
            'x',
            "{'k': 'v'} was expected",
            OneOfValues(('{"k": "v"}',)),
            guidance=FieldGuidance(example='{"k": "v"}', allowed=('{"k": "v"}',)),
        )

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (expected,), 'a schema-valued object constant is serialized as plain JSON guidance'

    def test_validate_with_a_required_field_in_a_branch_returns_it_without_guidance(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'status': {'type': 'string'}, 'owner': {'description': 'Who maintains it.'}},
            'if': {'properties': {'status': {'const': 'stable'}}, 'required': ['status']},
            'then': {'required': ['owner']},
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'status': 'stable'}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (MissingFieldProblem('owner', "'owner' is a required property"),), (
            "a branch's `required` sits in a schema without `properties`, so the property is not read"
        )

    def test_validate_with_a_value_of_one_of_several_types_returns_every_type_expected(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'tags': {'type': ['string', 'null']}}}
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'tags': True}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            WrongTypeProblem(
                'tags', "True is not of type 'string', 'null'", (JsonType.STRING, JsonType.NULL), JsonType.BOOLEAN
            ),
        ), 'a boolean is not an integer, and every type the schema accepts is expected'

    def test_validate_with_a_number_found_returns_the_number_type(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'version': {'type': 'string', 'description': 'The version.'}},
        }
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'version': 1.5}
        mapping = FrozenMapping.from_plain(data)

        #: When
        problems = frontmatter.validate(mapping)

        #: Then
        assert problems == (
            WrongTypeProblem(
                'version',
                "1.5 is not of type 'string'",
                (JsonType.STRING,),
                JsonType.NUMBER,
                guidance=FieldGuidance(description='The version.'),
            ),
        ), 'a fraction is a number, and the description is carried with the type'
