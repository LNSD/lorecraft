"""The frontmatter schema a structure specification states.

`parse` checks a schema the specification may hold, and `validate` reports a document's frontmatter against it.
"""

import pytest

from lorecraft.core.mapping import FrozenMapping, Plain

from ..structure import FrontmatterSchema
from ..structure_failure import (
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
