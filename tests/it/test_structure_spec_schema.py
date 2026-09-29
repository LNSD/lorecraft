"""The committed structure schema is a JSON Schema every specification this repository carries passes.

``docs/schemas/structure.spec.json`` is rendered by ``just gen`` from ``StructureFile``, the pydantic model
``StructureAspect.parse`` deserializes each file with, so the schema and the validation cannot disagree about a
shape; CI's ``gen-check`` job keeps the committed file current. What is left to hold is the file an editor reads:
that it is a well-formed schema, that it accepts every specification this repository writes, and that it holds the
``frontmatter`` key, whose JSON Schema is written out rather than rendered, to a schema describing an object.
"""

import json
from pathlib import Path
from typing import Final

import pytest
from jsonschema import Draft202012Validator

REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SCHEMA_FILE: Final[Path] = REPOSITORY_ROOT / 'docs' / 'schemas' / 'structure.spec.json'
SPECS_DIR: Final[Path] = REPOSITORY_ROOT / 'docs' / '__meta__'


@pytest.fixture(scope='module')
def validator() -> Draft202012Validator:
    """A validator for the committed structure schema."""
    return Draft202012Validator(json.loads(SCHEMA_FILE.read_text(encoding='utf-8')))


@pytest.mark.it
class TestStructureSpecSchema:
    def test_structure_schema_is_a_well_formed_json_schema(self) -> None:
        #: Given
        schema = json.loads(SCHEMA_FILE.read_text(encoding='utf-8'))

        #: When
        Draft202012Validator.check_schema(schema)

        #: Then
        assert schema['$schema'] == 'https://json-schema.org/draft/2020-12/schema', 'the schema names its dialect'

    def test_every_repository_structure_spec_passes_the_schema(self, validator: Draft202012Validator) -> None:
        #: Given
        spec_files = sorted(SPECS_DIR.glob('*.structure.json'))

        #: When
        schema_errors = {
            spec_file.name: [error.message for error in validator.iter_errors(json.loads(spec_file.read_text()))]
            for spec_file in spec_files
        }

        #: Then
        assert spec_files, 'the repository carries structure specifications, so the comparison is not vacuous'
        assert all(not errors for errors in schema_errors.values()), (
            f'the parser reads every one of them (`just check-docs`), so the schema must accept them: {schema_errors}'
        )

    def test_structure_schema_with_a_frontmatter_schema_describing_an_object_accepts_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'type': 'object', 'required': ['name'], 'properties': {'name': {'type': 'string'}}}}

        #: When
        errors = list(validator.iter_errors(spec))

        #: Then
        assert errors == [], 'an editor accepts a frontmatter schema stating an object type'

    def test_structure_schema_with_a_frontmatter_schema_without_a_type_refuses_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'required': ['name']}}

        #: When
        errors = list(validator.iter_errors(spec))

        #: Then
        assert errors, 'an editor refuses a frontmatter schema that leaves the object type implied'

    def test_structure_schema_with_a_malformed_frontmatter_schema_refuses_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'type': 'object', 'required': 'name'}}

        #: When
        errors = list(validator.iter_errors(spec))

        #: Then
        assert errors, 'an editor checks the frontmatter schema against the Draft 2020-12 meta-schema'

    def test_structure_schema_with_a_frontmatter_schema_of_another_type_refuses_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'type': 'array'}}

        #: When
        errors = list(validator.iter_errors(spec))

        #: Then
        assert errors, 'an editor refuses a frontmatter schema describing anything but an object'

    def test_structure_schema_with_a_frontmatter_schema_whose_type_is_a_list_refuses_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'type': ['object', 'null']}}

        #: When
        errors = list(validator.iter_errors(spec))

        #: Then
        assert errors, 'an editor refuses a type list, even one naming object: the type is exactly "object"'

    def test_structure_schema_with_a_null_frontmatter_refuses_it(self, validator: Draft202012Validator) -> None:
        #: Given
        spec = {'tokens': 100, 'frontmatter': None}

        #: When
        errors = list(validator.iter_errors(spec))

        #: Then
        assert errors, 'an editor refuses null, as the load does: no rule is written by leaving the key out'

    def test_structure_schema_with_a_frontmatter_schema_carrying_an_id_accepts_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'$id': 'https://example.com/code', 'type': 'object'}}

        #: When
        errors = list(validator.iter_errors(spec))

        #: Then
        assert errors == [], 'no schema can refuse $id here, so the editor lets it through and the load refuses it'

    def test_structure_schema_with_a_frontmatter_schema_in_a_foreign_dialect_accepts_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'$schema': 'http://json-schema.org/draft-07/schema#', 'type': 'object'}}

        #: When
        errors = list(validator.iter_errors(spec))

        #: Then
        assert errors == [], 'the editor lets a foreign $schema through and the load refuses it'
