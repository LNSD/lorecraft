"""The frontmatter schema a structure specification states.

`parse` checks a schema the specification may hold, and `validate` reports a document's frontmatter against it.
"""

import pytest

from lorecraft.core.mapping import FrozenMapping, Plain

from ..frontmatter_problem import (
    FieldGuidance,
    InvalidValueProblem,
    JsonType,
    MissingFieldProblem,
    OneOfValues,
    OtherValueConstraint,
    PatternMismatch,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from ..structure import FrontmatterSchema
from ..structure_failure import (
    ForeignFrontmatterDialect,
    FrontmatterSchemaId,
    InvalidFrontmatterSchema,
    UnresolvableFrontmatterSchemaRef,
    UntypedFrontmatterSchema,
)


@pytest.mark.unit
class TestFrontmatterSchema:
    def test_parse_with_an_object_schema_keeps_it(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'required': ['name'], 'description': 'read by people'}

        #: When
        frontmatter = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert isinstance(frontmatter, FrontmatterSchema), f'the schema is held, got {frontmatter!r}'
        assert frontmatter.schema == FrozenMapping.from_plain(schema), 'a well-formed object schema is held unchanged'

    def test_parse_with_the_draft_2020_12_dialect_in_schema_keeps_it(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object'}

        #: When
        frontmatter = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

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

        #: When
        frontmatter = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert isinstance(frontmatter, FrontmatterSchema), f'the schema is held, got {frontmatter!r}'
        assert frontmatter.schema == FrozenMapping.from_plain(schema), (
            'a combinator at the root is allowed next to the object type'
        )

    def test_parse_with_an_id_inside_an_enum_value_keeps_it(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'ref': {'enum': [{'$id': 'data'}]}}}

        #: When
        frontmatter = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert isinstance(frontmatter, FrontmatterSchema), f'the schema is held, got {frontmatter!r}'
        assert frontmatter.schema == FrozenMapping.from_plain(schema), (
            'a value under enum is data, not a schema, so its $id is no resource'
        )

    def test_parse_with_a_malformed_schema_returns_invalid_frontmatter_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'required': 'name'}

        #: When
        failure = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert failure == InvalidFrontmatterSchema("'name' is not of type 'array'"), (
            f'a malformed schema is refused with what the meta-schema rejected, got {failure!r}'
        )

    def test_parse_without_a_type_returns_untyped_frontmatter_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'required': ['name']}

        #: When
        failure = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert failure == UntypedFrontmatterSchema(), 'an implied object type is refused'

    def test_parse_with_a_non_object_type_returns_untyped_frontmatter_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'array'}

        #: When
        failure = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert failure == UntypedFrontmatterSchema(), 'a frontmatter is always a mapping'

    def test_parse_with_a_type_list_returns_untyped_frontmatter_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': ['object', 'null']}

        #: When
        failure = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert failure == UntypedFrontmatterSchema(), 'the type is exactly "object"'

    def test_parse_with_a_dangling_local_ref_returns_unresolvable_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'name': {'$ref': '#/$defs/missing'}}}

        #: When
        failure = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert failure == UnresolvableFrontmatterSchemaRef('#/$defs/missing'), (
            'a reference to a location the schema lacks is refused at load, not when a document is validated'
        )

    def test_parse_with_a_ref_to_another_resource_returns_unresolvable_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'name': {'$ref': 'https://example.com/name.json'}},
        }

        #: When
        failure = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert failure == UnresolvableFrontmatterSchemaRef('https://example.com/name.json'), (
            'a remote reference is refused, never fetched'
        )

    def test_parse_with_a_local_ref_to_a_definition_returns_the_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'name': {'$ref': '#/$defs/name'}},
            '$defs': {'name': {'type': 'string'}},
        }

        #: When
        parsed = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert isinstance(parsed, FrontmatterSchema), 'a reference that resolves inside the schema is accepted'

    def test_parse_with_a_ref_to_an_anchor_returns_the_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'name': {'$ref': '#label'}},
            '$defs': {'name': {'$anchor': 'label', 'type': 'string'}},
        }

        #: When
        parsed = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert isinstance(parsed, FrontmatterSchema), 'a reference to an `$anchor` of the schema is accepted'

    def test_parse_with_an_empty_ref_returns_the_schema(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'child': {'$ref': ''}}}

        #: When
        parsed = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert isinstance(parsed, FrontmatterSchema), 'the empty reference is the schema itself, as `#` is'

    def test_parse_with_a_ref_to_a_non_schema_returns_unresolvable_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'required': ['name'],
            'properties': {'name': {'$ref': '#/required/0'}},
        }

        #: When
        failure = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert failure == UnresolvableFrontmatterSchemaRef('#/required/0'), (
            'a reference that finds a value that is not a schema is refused'
        )

    def test_parse_with_a_dangling_dynamic_ref_returns_unresolvable_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'name': {'$dynamicRef': '#/$defs/missing'}}}

        #: When
        failure = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert failure == UnresolvableFrontmatterSchemaRef('#/$defs/missing'), 'a dynamic reference is held to the same'

    def test_parse_with_a_remote_dynamic_ref_returns_unresolvable_frontmatter_schema_ref(self) -> None:
        #: Given
        schema: dict[str, Plain] = {
            'type': 'object',
            'properties': {'name': {'$dynamicRef': 'https://example.com/name.json'}},
        }

        #: When
        failure = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert failure == UnresolvableFrontmatterSchemaRef('https://example.com/name.json'), (
            'a remote dynamic reference is refused, never fetched'
        )

    def test_parse_with_an_id_returns_frontmatter_schema_id(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'$id': 'https://example.com/code', 'type': 'object'}

        #: When
        failure = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert failure == FrontmatterSchemaId(), 'an $id would change how relative $refs resolve'

    def test_parse_with_an_id_in_a_nested_schema_returns_frontmatter_schema_id(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'name': {'$id': 'https://example.com/name'}}}

        #: When
        failure = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert failure == FrontmatterSchemaId(), 'an $id at any depth makes a resource of its own'

    def test_parse_with_a_foreign_dialect_returns_foreign_frontmatter_dialect(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'$schema': 'http://json-schema.org/draft-07/schema#', 'type': 'object'}

        #: When
        failure = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

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

        #: When
        failure = FrontmatterSchema.parse(FrozenMapping.from_plain(schema))

        #: Then
        assert failure == ForeignFrontmatterDialect('http://json-schema.org/draft-07/schema#'), (
            'a nested schema may not switch dialect either'
        )

    def test_validate_with_a_conforming_frontmatter_returns_no_problems(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain({'type': 'object', 'required': ['name']}))
        data: dict[str, Plain] = {'name': 'guide'}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (), 'a frontmatter the schema accepts has no problems'

    def test_validate_without_two_required_fields_returns_one_missing_problem_each(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(
            schema=FrozenMapping.from_plain({'type': 'object', 'required': ['name', 'type']})
        )
        data: dict[str, Plain] = {}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

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

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

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

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

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

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            UnknownFieldProblem(
                'model',
                "Additional properties are not allowed ('model' was unexpected)",
                ('name',),
            ),
            UnknownFieldProblem(
                'tier',
                "Additional properties are not allowed ('tier' was unexpected)",
                ('name',),
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

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            UnknownFieldProblem('desc', "Unevaluated properties are not allowed ('desc' was unexpected)", ('status',)),
            UnknownFieldProblem('tier', "Unevaluated properties are not allowed ('tier' was unexpected)", ('status',)),
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

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (InvalidValueProblem('tier', "1 is not of type 'string'", OtherValueConstraint()),), (
            'an unevaluated field is held to the rule schema, and only one breaking it is a problem, on that field'
        )

    def test_validate_with_a_value_of_the_wrong_type_returns_a_wrong_type_problem(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'name': {'type': 'string'}}}
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'name': 3}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            WrongTypeProblem('name', "3 is not of type 'string'", (JsonType.STRING,), JsonType.INTEGER),
        ), "the message is the validator's, and the types are the schema's and the value's"

    def test_validate_with_a_value_outside_an_enum_returns_an_invalid_value_problem(self) -> None:
        #: Given
        schema: dict[str, Plain] = {'type': 'object', 'properties': {'type': {'enum': ['rule', 'pattern']}}}
        frontmatter = FrontmatterSchema(schema=FrozenMapping.from_plain(schema))
        data: dict[str, Plain] = {'type': 'guide'}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

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

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

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

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            InvalidValueProblem(
                'description',
                "'Load when x.' should not be valid under {'pattern': '\\\\.\\\\s*$'}",
                OtherValueConstraint(),
                reason='No trailing period.',
            ),
        ), "the failing subschema's `$comment` is the reason, and `not` has no typed constraint"
