"""The committed structure schema is a JSON Schema every specification this repository carries passes.

`docs/schemas/structure.spec.json` is rendered by `just gen` from `StructureFile`, the pydantic model
`StructureSpec.parse` deserializes each file with, so the schema and the validation cannot disagree about a
shape; CI's `gen-check` job keeps the committed file current. What is left to hold is the file an editor reads:
that it is a well-formed schema, that it accepts every specification this repository writes, and that it holds the
`frontmatter` key, whose JSON Schema is written out rather than rendered, to a schema describing an object.
"""

import json
from collections.abc import Mapping, Sized
from pathlib import Path
from typing import Final

import pytest
from jsonschema import Draft202012Validator, ValidationError

REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SCHEMA_FILE: Final[Path] = REPOSITORY_ROOT / 'docs' / 'schemas' / 'structure.spec.json'
SPECS_DIR: Final[Path] = REPOSITORY_ROOT / 'docs' / '__meta__'


@pytest.fixture(scope='module')
def validator() -> Draft202012Validator:
    """A validator for the committed structure schema."""
    return Draft202012Validator(json.loads(SCHEMA_FILE.read_text(encoding='utf-8')))


def _every_empty(found: Mapping[str, Sized]) -> bool:
    """Whether no name carries anything, such as an error or a problem.

    Args:
        found: What was found per name, one collection each.
    """
    return all(not items for items in found.values())


def _errors(validator: Draft202012Validator, spec: dict[str, object]) -> list[ValidationError]:
    """Every error the validator finds in the specification, in the order it finds them.

    Args:
        validator: Validator of the structure specification schema.
        spec: The specification to validate.
    """
    return list(validator.iter_errors(spec))


def _messages_by_file(validator: Draft202012Validator, spec_files: list[Path]) -> dict[str, list[str]]:
    """The messages of the errors the validator finds in each specification file, by file name.

    Args:
        validator: Validator of the structure specification schema.
        spec_files: Specification files to read as JSON and validate.
    """
    return {
        spec_file.name: [error.message for error in validator.iter_errors(json.loads(spec_file.read_text()))]
        for spec_file in spec_files
    }


@pytest.mark.it
class TestStructureSpecSchema:
    def test_structure_schema_when_checked_against_the_metaschema_is_well_formed(self) -> None:
        #: Given
        schema = json.loads(SCHEMA_FILE.read_text(encoding='utf-8'))

        #: When
        Draft202012Validator.check_schema(schema)

        #: Then
        assert schema['$schema'] == 'https://json-schema.org/draft/2020-12/schema', 'the schema names its dialect'

    def test_structure_schema_with_every_repository_structure_spec_accepts_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec_files = sorted([*SPECS_DIR.glob('*.spec.json'), *SPECS_DIR.glob('*.structure.json')])

        #: When
        schema_errors = _messages_by_file(validator, spec_files)

        #: Then
        assert spec_files, 'the repository carries structure specifications, so the comparison is not vacuous'
        assert _every_empty(schema_errors), (
            f'the parser reads every one of them (`just check-docs`), so the schema must accept them: {schema_errors}'
        )

    def test_structure_schema_with_a_frontmatter_schema_describing_an_object_accepts_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'type': 'object', 'required': ['name'], 'properties': {'name': {'type': 'string'}}}}

        #: When
        errors = _errors(validator, spec)

        #: Then
        assert errors == [], 'an editor accepts a frontmatter schema stating an object type'

    def test_structure_schema_with_a_frontmatter_schema_without_a_type_refuses_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'required': ['name']}}

        #: When
        errors = _errors(validator, spec)

        #: Then
        assert errors, 'an editor refuses a frontmatter schema that leaves the object type implied'

    def test_structure_schema_with_a_malformed_frontmatter_schema_refuses_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'type': 'object', 'required': 'name'}}

        #: When
        errors = _errors(validator, spec)

        #: Then
        assert errors, 'an editor checks the frontmatter schema against the Draft 2020-12 meta-schema'

    def test_structure_schema_with_a_frontmatter_schema_of_another_type_refuses_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'type': 'array'}}

        #: When
        errors = _errors(validator, spec)

        #: Then
        assert errors, 'an editor refuses a frontmatter schema describing anything but an object'

    def test_structure_schema_with_a_frontmatter_schema_whose_type_is_a_list_refuses_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'type': ['object', 'null']}}

        #: When
        errors = _errors(validator, spec)

        #: Then
        assert errors, 'an editor refuses a type list, even one naming object: the type is exactly "object"'

    def test_structure_schema_with_a_null_frontmatter_refuses_it(self, validator: Draft202012Validator) -> None:
        #: Given
        spec = {'tokens': 100, 'frontmatter': None}

        #: When
        errors = _errors(validator, spec)

        #: Then
        assert errors, 'an editor refuses null, as the load does: no rule is written by leaving the key out'

    def test_structure_schema_with_a_frontmatter_schema_carrying_an_id_accepts_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'$id': 'https://example.com/code', 'type': 'object'}}

        #: When
        errors = _errors(validator, spec)

        #: Then
        assert errors == [], 'no schema can refuse $id here, so the editor lets it through and the load refuses it'

    def test_structure_schema_with_a_frontmatter_schema_in_a_foreign_dialect_accepts_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'frontmatter': {'$schema': 'http://json-schema.org/draft-07/schema#', 'type': 'object'}}

        #: When
        errors = _errors(validator, spec)

        #: Then
        assert errors == [], 'the editor lets a foreign $schema through and the load refuses it'

    def test_structure_schema_with_a_padded_section_name_refuses_it(self, validator: Draft202012Validator) -> None:
        #: Given
        spec = {'outline': [{'section': ' Checklist'}]}

        #: When
        errors = _errors(validator, spec)

        #: Then
        assert errors, 'an editor refuses a section name with whitespace at either end, as the load does'

    def test_structure_schema_with_an_empty_forbidden_entry_refuses_it(self, validator: Draft202012Validator) -> None:
        #: Given
        spec = {'forbidden': ['']}

        #: When
        errors = _errors(validator, spec)

        #: Then
        assert errors, 'an editor refuses an empty section name, as the load does'

    def test_structure_schema_with_a_section_name_holding_inner_spaces_accepts_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'outline': [{'section': 'Code References'}], 'forbidden': ['Table of Contents']}

        #: When
        errors = _errors(validator, spec)

        #: Then
        assert errors == [], 'whitespace inside a name is heading text, so the editor accepts it'

    def test_structure_schema_with_a_forbidden_entry_given_twice_refuses_it(
        self, validator: Draft202012Validator
    ) -> None:
        #: Given
        spec = {'forbidden': ['Changelog', 'Changelog']}

        #: When
        errors = _errors(validator, spec)

        #: Then
        assert errors, 'an editor refuses a repeated forbidden entry, which the load refuses too'
