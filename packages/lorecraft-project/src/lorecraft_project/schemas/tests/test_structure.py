"""The structure aspect: ``parse`` deserializes a file's text into the dialect's shape, and construction refuses
rules that are not usable."""

from textwrap import dedent
from typing import Final

import pytest

from lorecraft_vfs import RootRelativePath

from ..structure import (
    AnySections,
    InvalidStructureSchemaError,
    SectionEntry,
    StructureAspect,
    StructureSchema,
    TitleRule,
)

SPEC_PATH: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')


@pytest.mark.unit
class TestStructureAspectParse:
    def test_parse_with_every_field_returns_the_rules_it_states(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                  "description": "read by people only",
                  "title": {"count": 1, "first": true},
                  "empty_sections": "forbidden",
                  "outline": [
                    {"any": true},
                    {"section": "Checklist"},
                    {"section": "References", "optional": true}
                  ],
                  "forbidden": ["Changelog"]
                }
                """
            )
        )

        #: When
        aspect = StructureAspect.parse(SPEC_PATH, schema)

        #: Then
        assert aspect == StructureAspect(
            path=SPEC_PATH,
            title=TitleRule(count=1, first=True),
            forbid_empty_sections=True,
            outline=(
                AnySections(),
                SectionEntry(name='Checklist', optional=False),
                SectionEntry(name='References', optional=True),
            ),
            forbidden=('Changelog',),
        ), 'every field is read into its typed rule'

    def test_parse_with_a_schema_reference_returns_the_rules_without_it(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                  "$schema": "../schemas/structure.spec.json",
                  "forbidden": ["Changelog"]
                }
                """
            )
        )

        #: When
        aspect = StructureAspect.parse(SPEC_PATH, schema)

        #: Then
        assert aspect == StructureAspect(
            path=SPEC_PATH,
            title=None,
            forbid_empty_sections=False,
            outline=(),
            forbidden=('Changelog',),
        ), 'the `$schema` reference is for editors and changes no rule'

    def test_parse_with_a_schema_reference_that_is_not_a_string_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                  "$schema": 5,
                  "forbidden": ["Changelog"]
                }
                """
            )
        )

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the error names the rejected file'

    def test_parse_with_text_that_is_not_json_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                """
            )
        )

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'text that is not JSON is refused at the edge, naming the file'

    def test_parse_with_a_title_count_below_one_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                  "title": {"count": 0, "first": true}
                }
                """
            )
        )

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'no document satisfies a count of 0'

    def test_parse_with_a_string_for_a_boolean_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                  "outline": [{"section": "Checklist", "optional": "yes"}]
                }
                """
            )
        )

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the file is read strictly, so no value is coerced into another type'

    def test_parse_with_an_unknown_field_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                  "forbidden": ["Changelog"],
                  "sections": []
                }
                """
            )
        )

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the error names the rejected file'

    def test_parse_with_a_spec_field_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        schema = StructureSchema('{"spec": "code.md", "forbidden": ["Changelog"]}')

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the prose is named by the filename, so `spec` is not a field'

    def test_parse_with_an_empty_sections_value_other_than_forbidden_raises_invalid_structure_schema_error(
        self,
    ) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                  "empty_sections": "allowed"
                }
                """
            )
        )

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, '"forbidden" is the only value `empty_sections` takes'

    def test_parse_with_a_boolean_title_count_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                  "title": {"count": true, "first": true}
                }
                """
            )
        )

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a JSON boolean is not a count, though Python treats it as one'

    def test_parse_with_an_outline_entry_of_neither_shape_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                  "outline": [{"heading": "Checklist"}]
                }
                """
            )
        )

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an outline entry is a section or an `any` run, nothing else'

    def test_parse_with_a_forbidden_entry_that_is_not_a_string_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                  "forbidden": [1]
                }
                """
            )
        )

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, '`forbidden` holds section names only'


@pytest.mark.unit
class TestStructureAspectConstruction:
    def test_construction_without_any_rule_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        path = SPEC_PATH

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect(
                path=path,
                title=None,
                forbid_empty_sections=False,
                outline=(),
                forbidden=(),
            )

        #: Then
        assert exc_info.value.path == path, 'a specification stating no rule would check nothing'

    def test_construction_with_a_title_count_of_zero_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        title = TitleRule(count=0, first=False)

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect(
                path=SPEC_PATH,
                title=title,
                forbid_empty_sections=False,
                outline=(),
                forbidden=(),
            )

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a title rule asks for at least one title'

    def test_construction_with_a_section_named_twice_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        outline = (
            SectionEntry(name='Checklist', optional=False),
            SectionEntry(name='Checklist', optional=True),
        )

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect(
                path=SPEC_PATH,
                title=None,
                forbid_empty_sections=False,
                outline=outline,
                forbidden=(),
            )

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a name fixes one position, so it cannot be given two'

    def test_construction_forbidding_a_section_its_outline_names_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        outline = (SectionEntry(name='Checklist', optional=True),)

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect(
                path=SPEC_PATH,
                title=None,
                forbid_empty_sections=False,
                outline=outline,
                forbidden=('Checklist',),
            )

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a section cannot be both placed and forbidden'

    def test_construction_with_two_adjacent_any_runs_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        outline = (
            AnySections(),
            AnySections(),
            SectionEntry(name='Checklist', optional=False),
        )

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect(
                path=SPEC_PATH,
                title=None,
                forbid_empty_sections=False,
                outline=outline,
                forbidden=(),
            )

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'two runs side by side match as one, so the outline misleads'


@pytest.mark.unit
class TestStructureAspectAuthority:
    def test_construction_at_a_namespace_path_derives_the_prose_at_its_stem(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/__meta__/code-python.structure.json')

        #: When
        aspect = StructureAspect(
            path=path, title=None, forbid_empty_sections=False, outline=(), forbidden=('Changelog',)
        )

        #: Then
        assert aspect.authority == 'code-python.md', 'the prose is the `.md` file at the same stem'

    def test_construction_at_a_path_that_is_not_a_spec_filename_raises_invalid_structure_schema_error(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/__meta__/notes.txt')

        #: When
        with pytest.raises(InvalidStructureSchemaError) as exc_info:
            StructureAspect(path=path, title=None, forbid_empty_sections=False, outline=(), forbidden=('Changelog',))

        #: Then
        assert exc_info.value.path == path, 'an aspect whose path names no prose has no authority to quote'
