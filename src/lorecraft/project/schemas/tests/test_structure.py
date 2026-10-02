"""The structure specification.

`parse` deserializes a file's text into the dialect's shape, and construction refuses rules that are not usable.
"""

import json
from textwrap import dedent
from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath

from ..frontmatter_problem import (
    BlockProblem,
    InvalidValueProblem,
    MissingFieldProblem,
    NonStringKeyProblem,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from ..structure import (
    AdjacentAnyRunsError,
    AnySections,
    EmptyStructureSpecError,
    ForbiddenOutlineSectionError,
    ForeignFrontmatterDialectError,
    FrontmatterSchema,
    FrontmatterSchemaIdError,
    InvalidFrontmatterSchemaError,
    InvalidTitleCountError,
    InvalidTokenBudgetError,
    InvalidWordCapError,
    RepeatedOutlineSectionError,
    SectionEntry,
    StructureSchema,
    StructureSpec,
    StructureSpecDecodeError,
    StructureSpecFilenameError,
    TitleRule,
    UntypedFrontmatterSchemaError,
)

SPEC_PATH: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')

# What a rule document's Checklist holds, as the outline entry naming it states it.
CHECKLIST_DESCRIPTION: Final[str] = (
    'The items a reviewer verifies before committing a change the rule document governs.'
)

# The body of the Checklist of docs/code/logging.md, trimmed: an example of a rule document's Checklist.
LOGGING_CHECKLIST: Final[str] = (
    'Before committing code, verify:\n'
    '\n'
    '- [ ] Every module that logs has exactly one `logger = logging.getLogger(__name__)` after its imports\n'
    '- [ ] No logger is stored as `self.logger` or any other instance or class attribute\n'
    '- [ ] No log call sits in a per-line loop, whatever its level'
)

# The body of the Checklist of docs/code/python-docstrings.md, trimmed: a second example of the same section.
DOCSTRINGS_CHECKLIST: Final[str] = (
    'Before committing code, verify:\n'
    '\n'
    '- [ ] Every new class and public function has a docstring whose first line is a one-line summary\n'
    '- [ ] No `Returns:` section restates the return annotation\n'
    '- [ ] A generator documents `Yields:`, never `Returns:`'
)


@pytest.mark.unit
class TestStructureSpecParse:
    def test_parse_with_every_field_returns_the_rules_it_states(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                  "description": "read by people only",
                  "title": {"count": 1, "first": true},
                  "empty_sections": "forbidden",
                  "tokens": 5000,
                  "frontmatter": {"type": "object", "required": ["name"]},
                  "outline": [
                    {"any": true, "words": 350},
                    {"section": "Checklist", "words": 250},
                    {"section": "References", "optional": true}
                  ],
                  "forbidden": ["Changelog"]
                }
                """
            )
        )

        #: When
        structure_spec = StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert structure_spec == StructureSpec(
            path=SPEC_PATH,
            title=TitleRule(count=1, first=True),
            forbid_empty_sections=True,
            outline=(
                AnySections(words=350),
                SectionEntry(name='Checklist', words=250),
                SectionEntry(name='References', optional=True),
            ),
            forbidden=('Changelog',),
            tokens=5000,
            frontmatter=FrontmatterSchema(path=SPEC_PATH, schema={'type': 'object', 'required': ['name']}),
        ), 'every field is read into its typed rule, and an entry without `words` has no cap'

    def test_parse_with_a_section_description_and_examples_carries_them_into_its_entry_in_order(self) -> None:
        #: Given
        schema = StructureSchema(
            json.dumps(
                {
                    'outline': [
                        {
                            'section': 'Checklist',
                            'description': CHECKLIST_DESCRIPTION,
                            'examples': [LOGGING_CHECKLIST, DOCSTRINGS_CHECKLIST],
                        }
                    ]
                }
            )
        )

        #: When
        structure_spec = StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert structure_spec.outline == (
            SectionEntry(
                name='Checklist',
                description=CHECKLIST_DESCRIPTION,
                examples=(LOGGING_CHECKLIST, DOCSTRINGS_CHECKLIST),
            ),
        ), f'a section entry keeps its description and every example, in order, got {structure_spec.outline!r}'

    def test_parse_with_a_section_without_description_or_examples_states_neither(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist"}]}')

        #: When
        structure_spec = StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert structure_spec.outline == (SectionEntry(name='Checklist', description=None, examples=()),), (
            f'both keys are optional, and absent they state nothing, got {structure_spec.outline!r}'
        )

    def test_parse_with_an_empty_section_description_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "description": ""}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an empty description would print empty help, so it is refused'

    def test_parse_with_an_empty_list_of_section_examples_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "examples": []}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'no examples are written by leaving the key out, so `[]` is refused'

    def test_parse_with_an_empty_section_example_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema(
            json.dumps({'outline': [{'section': 'Checklist', 'examples': [LOGGING_CHECKLIST, '']}]})
        )

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an empty example would print a heading alone, so it is refused'

    def test_parse_with_a_section_description_that_is_not_a_string_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema(
            json.dumps({'outline': [{'section': 'Checklist', 'description': [CHECKLIST_DESCRIPTION]}]})
        )

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a description is one string of text, not a list of lines'

    def test_parse_with_section_examples_given_as_one_string_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema(json.dumps({'outline': [{'section': 'Checklist', 'examples': LOGGING_CHECKLIST}]}))

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'examples are a list, so one bare string is refused'

    def test_parse_with_a_section_example_that_is_not_a_string_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "examples": [3]}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the file is read strictly, so a number is not an example'

    def test_parse_with_a_description_on_an_any_run_raises_structure_spec_decode_error(self) -> None:
        #: Given
        # a run can never be missing, so nothing would ever report what it holds
        schema = StructureSchema('{"outline": [{"any": true, "description": "The document\'s own sections."}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'only a named section takes a description'

    def test_parse_with_examples_on_an_any_run_raises_structure_spec_decode_error(self) -> None:
        #: Given
        # a run can never be missing, so nothing would ever report an example of it
        schema = StructureSchema(json.dumps({'outline': [{'any': True, 'examples': [LOGGING_CHECKLIST]}]}))

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'only a named section takes examples'

    def test_parse_with_only_a_frontmatter_schema_returns_a_structure_spec_with_that_schema(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"type": "object"}}')

        #: When
        structure_spec = StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert structure_spec.frontmatter == FrontmatterSchema(path=SPEC_PATH, schema={'type': 'object'}), (
            'a frontmatter schema is a rule, so a file stating only it is usable'
        )

    def test_parse_with_a_malformed_frontmatter_schema_raises_invalid_frontmatter_schema_error(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"type": "object", "minProperties": -1}}')

        #: When
        with pytest.raises(InvalidFrontmatterSchemaError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the error names the structure specification the schema is in'
        assert exc_info.value.source is exc_info.value.__cause__, 'the schema error is kept as the cause'

    def test_parse_with_a_frontmatter_schema_without_an_object_type_raises_untyped_frontmatter_schema_error(
        self,
    ) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"required": ["name"]}}')

        #: When
        with pytest.raises(UntypedFrontmatterSchemaError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the object type is stated, not implied'

    def test_parse_with_a_frontmatter_value_that_is_not_an_object_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": true}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a boolean schema is refused by the shape'

    def test_parse_with_a_null_frontmatter_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 100, "frontmatter": null}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, (
            'the editor refuses null too; no rule is written by leaving the key out'
        )
        assert 'frontmatter' in str(exc_info.value), (
            f'the message names the key that may not be null, got {exc_info.value}'
        )

    def test_parse_with_a_frontmatter_schema_carrying_an_id_raises_frontmatter_schema_id_error(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"$id": "https://example.com/code", "type": "object"}}')

        #: When
        with pytest.raises(FrontmatterSchemaIdError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the editor lets an $id through, the load refuses it naming the file'

    def test_parse_with_a_frontmatter_schema_in_a_foreign_dialect_raises_foreign_frontmatter_dialect_error(
        self,
    ) -> None:
        #: Given
        schema = StructureSchema(
            '{"frontmatter": {"$schema": "http://json-schema.org/draft-07/schema#", "type": "object"}}'
        )

        #: When
        with pytest.raises(ForeignFrontmatterDialectError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the editor lets a foreign $schema through, the load refuses it'
        assert exc_info.value.dialect == 'http://json-schema.org/draft-07/schema#', (
            f'the error carries the dialect the schema names, got {exc_info.value.dialect!r}'
        )

    def test_parse_with_only_a_token_budget_returns_a_structure_spec_with_that_budget(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 4000}')

        #: When
        structure_spec = StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert structure_spec.tokens == 4000, 'a token budget is a rule, so a file stating only it is usable'

    def test_parse_with_a_token_budget_of_zero_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 0}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'no document satisfies a budget of 0 tokens'

    def test_parse_with_a_document_word_cap_raises_structure_spec_decode_error(self) -> None:
        #: Given
        # words are capped per section only; the document as a whole has a token budget instead
        schema = StructureSchema('{"words": 1800}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a top-level `words` is not a field, so it is refused, not ignored'

    def test_parse_with_a_section_word_cap_of_zero_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "words": 0}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'no section satisfies a cap of 0 words'

    def test_parse_with_an_any_word_cap_of_zero_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"any": true, "words": 0}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'no section in a run satisfies a cap of 0 words'

    def test_parse_with_a_string_word_cap_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "words": "250"}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the file is read strictly, so a string is not a word cap'

    def test_parse_with_a_fractional_token_budget_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 5000.5}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a token budget is a whole number of tokens'

    def test_parse_with_a_boolean_section_word_cap_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "words": true}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a JSON boolean is not a word cap, though Python treats it as one'

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
        structure_spec = StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert structure_spec == StructureSpec(
            path=SPEC_PATH,
            title=None,
            forbid_empty_sections=False,
            outline=(),
            forbidden=('Changelog',),
            tokens=None,
            frontmatter=None,
        ), 'the `$schema` reference is for editors and changes no rule'

    def test_parse_with_a_schema_reference_that_is_not_a_string_raises_structure_spec_decode_error(self) -> None:
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
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the error names the rejected file'

    def test_parse_with_text_that_is_not_json_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                """
            )
        )

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'text that is not JSON is refused at the edge, naming the file'
        assert exc_info.value.source is exc_info.value.__cause__, 'the validation error is kept as the cause'

    def test_parse_with_a_title_count_below_one_raises_structure_spec_decode_error(self) -> None:
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
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'no document satisfies a count of 0'

    def test_parse_with_a_string_for_a_boolean_raises_structure_spec_decode_error(self) -> None:
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
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the file is read strictly, so no value is coerced into another type'

    def test_parse_with_an_unknown_field_raises_structure_spec_decode_error(self) -> None:
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
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the error names the rejected file'

    def test_parse_with_a_spec_field_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"spec": "code.md", "forbidden": ["Changelog"]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the prose is named by the filename, so `spec` is not a field'

    def test_parse_with_an_empty_sections_value_other_than_forbidden_raises_structure_spec_decode_error(
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
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, '"forbidden" is the only value `empty_sections` takes'

    def test_parse_with_a_boolean_title_count_raises_structure_spec_decode_error(self) -> None:
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
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a JSON boolean is not a count, though Python treats it as one'
        assert len(exc_info.value.problems) == 1, f'one field is wrong, got {exc_info.value.problems}'
        assert exc_info.value.problems[0].startswith('title.count: '), (
            f'the problem opens with the dotted path of the field at fault, got {exc_info.value.problems[0]!r}'
        )

    def test_parse_with_two_wrong_title_fields_lists_one_problem_each_in_the_message(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"count": 0, "first": "yes"}}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert len(exc_info.value.problems) == 2, f'each wrong field is its own problem, got {exc_info.value.problems}'
        assert exc_info.value.problems[0].startswith('title.count: '), (
            f'the first problem names its field, got {exc_info.value.problems[0]!r}'
        )
        assert exc_info.value.problems[1].startswith('title.first: '), (
            f'the second problem names its field, got {exc_info.value.problems[1]!r}'
        )
        assert '; '.join(exc_info.value.problems) in str(exc_info.value), (
            f'the message lists every problem, separated by semicolons, got {exc_info.value}'
        )

    def test_parse_with_an_outline_entry_of_neither_shape_raises_structure_spec_decode_error(self) -> None:
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
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an outline entry is a section or an `any` run, nothing else'

    def test_parse_with_a_forbidden_entry_that_is_not_a_string_raises_structure_spec_decode_error(self) -> None:
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
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_PATH, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, '`forbidden` holds section names only'


@pytest.mark.unit
class TestStructureSpecConstruction:
    def test_construction_without_any_rule_raises_empty_structure_spec_error(self) -> None:
        #: Given
        path = SPEC_PATH

        #: When
        with pytest.raises(EmptyStructureSpecError) as exc_info:
            StructureSpec(
                path=path,
                title=None,
                forbid_empty_sections=False,
                outline=(),
                forbidden=(),
                tokens=None,
                frontmatter=None,
            )

        #: Then
        assert exc_info.value.path == path, 'a specification stating no rule would check nothing'

    def test_construction_with_a_title_count_of_zero_raises_invalid_title_count_error(self) -> None:
        #: Given
        title = TitleRule(count=0, first=False)

        #: When
        with pytest.raises(InvalidTitleCountError) as exc_info:
            StructureSpec(
                path=SPEC_PATH,
                title=title,
                forbid_empty_sections=False,
                outline=(),
                forbidden=(),
                tokens=None,
                frontmatter=None,
            )

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a title rule asks for at least one title'
        assert exc_info.value.count == 0, f'the error carries the count stated, got {exc_info.value.count}'
        assert str(SPEC_PATH) in str(exc_info.value), f'the message names the file, got {exc_info.value}'

    def test_construction_with_a_section_named_twice_raises_repeated_outline_section_error(self) -> None:
        #: Given
        outline = (
            SectionEntry(name='Checklist'),
            SectionEntry(name='Checklist', optional=True),
        )

        #: When
        with pytest.raises(RepeatedOutlineSectionError) as exc_info:
            StructureSpec(
                path=SPEC_PATH,
                title=None,
                forbid_empty_sections=False,
                outline=outline,
                forbidden=(),
                tokens=None,
                frontmatter=None,
            )

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a name fixes one position, so it cannot be given two'
        assert exc_info.value.sections == ('Checklist',), (
            f'the error carries the repeated name once, got {exc_info.value.sections}'
        )
        assert 'Checklist' in str(exc_info.value), f'the message names the repeated section, got {exc_info.value}'

    def test_construction_forbidding_a_section_its_outline_names_raises_forbidden_outline_section_error(self) -> None:
        #: Given
        outline = (SectionEntry(name='Checklist', optional=True),)

        #: When
        with pytest.raises(ForbiddenOutlineSectionError) as exc_info:
            StructureSpec(
                path=SPEC_PATH,
                title=None,
                forbid_empty_sections=False,
                outline=outline,
                forbidden=('Checklist',),
                tokens=None,
                frontmatter=None,
            )

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a section cannot be both placed and forbidden'
        assert exc_info.value.sections == ('Checklist',), (
            f'the error carries the contradicted name, got {exc_info.value.sections}'
        )
        assert 'Checklist' in str(exc_info.value), f'the message names the contradicted section, got {exc_info.value}'

    def test_construction_with_two_adjacent_any_runs_raises_adjacent_any_runs_error(self) -> None:
        #: Given
        outline = (
            AnySections(),
            AnySections(),
            SectionEntry(name='Checklist'),
        )

        #: When
        with pytest.raises(AdjacentAnyRunsError) as exc_info:
            StructureSpec(
                path=SPEC_PATH,
                title=None,
                forbid_empty_sections=False,
                outline=outline,
                forbidden=(),
                tokens=None,
                frontmatter=None,
            )

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'two runs side by side match as one, so the outline misleads'
        assert str(SPEC_PATH) in str(exc_info.value), f'the message names the file, got {exc_info.value}'

    def test_construction_with_a_token_budget_of_zero_raises_invalid_token_budget_error(self) -> None:
        #: Given
        tokens = 0

        #: When
        with pytest.raises(InvalidTokenBudgetError) as exc_info:
            StructureSpec(
                path=SPEC_PATH,
                title=None,
                forbid_empty_sections=False,
                outline=(),
                forbidden=('Changelog',),
                tokens=tokens,
                frontmatter=None,
            )

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a budget of 0 tokens is one no document can meet'
        assert exc_info.value.tokens == 0, f'the error carries the budget stated, got {exc_info.value.tokens}'
        assert str(SPEC_PATH) in str(exc_info.value), f'the message names the file, got {exc_info.value}'

    def test_construction_with_a_token_budget_of_one_keeps_it(self) -> None:
        #: Given
        tokens = 1

        #: When
        structure_spec = StructureSpec(
            path=SPEC_PATH,
            title=None,
            forbid_empty_sections=False,
            outline=(),
            forbidden=(),
            tokens=tokens,
            frontmatter=None,
        )

        #: Then
        assert structure_spec.tokens == 1, (
            f'1 token is the smallest budget a document can meet, got {structure_spec.tokens}'
        )

    def test_construction_with_a_section_word_cap_of_zero_raises_invalid_word_cap_error(self) -> None:
        #: Given
        outline = (SectionEntry(name='Checklist', words=0),)

        #: When
        with pytest.raises(InvalidWordCapError) as exc_info:
            StructureSpec(
                path=SPEC_PATH,
                title=None,
                forbid_empty_sections=False,
                outline=outline,
                forbidden=(),
                tokens=None,
                frontmatter=None,
            )

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a section cap of 0 words is one no section with prose can meet'
        assert exc_info.value.entry == SectionEntry(name='Checklist', words=0), (
            f'the error carries the entry stating the cap, got {exc_info.value.entry}'
        )
        assert exc_info.value.words == 0, f'the error carries the cap stated, got {exc_info.value.words}'
        assert 'Checklist' in str(exc_info.value), f'the message names the capped section, got {exc_info.value}'

    def test_construction_with_a_negative_any_word_cap_raises_invalid_word_cap_error(self) -> None:
        #: Given
        outline = (AnySections(words=-1),)

        #: When
        with pytest.raises(InvalidWordCapError) as exc_info:
            StructureSpec(
                path=SPEC_PATH,
                title=None,
                forbid_empty_sections=False,
                outline=outline,
                forbidden=(),
                tokens=None,
                frontmatter=None,
            )

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a run cap below 1 word is one no section with prose can meet'
        assert exc_info.value.entry == AnySections(words=-1), (
            f'the error carries the entry stating the cap, got {exc_info.value.entry}'
        )
        assert exc_info.value.words == -1, f'the error carries the cap stated, got {exc_info.value.words}'
        assert 'any' in str(exc_info.value), f'the message names the entry as an `any` run, got {exc_info.value}'


@pytest.mark.unit
class TestStructureSpecAuthority:
    def test_construction_at_a_namespace_path_derives_the_prose_at_its_stem(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/__meta__/code-python.structure.json')

        #: When
        structure_spec = StructureSpec(
            path=path,
            title=None,
            forbid_empty_sections=False,
            outline=(),
            forbidden=('Changelog',),
            tokens=None,
            frontmatter=None,
        )

        #: Then
        assert structure_spec.authority == 'code-python.md', 'the prose is the `.md` file at the same spec name'

    def test_construction_at_a_path_that_is_not_a_spec_filename_raises_structure_spec_filename_error(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/__meta__/notes.txt')

        #: When
        with pytest.raises(StructureSpecFilenameError) as exc_info:
            StructureSpec(
                path=path,
                title=None,
                forbid_empty_sections=False,
                outline=(),
                forbidden=('Changelog',),
                tokens=None,
                frontmatter=None,
            )

        #: Then
        assert exc_info.value.path == path, (
            'a structure specification whose path names no prose has no authority to quote'
        )
        assert exc_info.value.source is exc_info.value.__cause__, 'why the filename is refused is kept as the cause'
        assert str(path) in str(exc_info.value), f'the message names the file, got {exc_info.value}'


@pytest.mark.unit
class TestFrontmatterSchema:
    def test_construction_with_an_object_schema_keeps_it(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'required': ['name'], 'description': 'read by people'}

        #: When
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=schema)

        #: Then
        assert frontmatter.schema == schema, 'a well-formed object schema is held unchanged'

    def test_construction_with_the_draft_2020_12_dialect_in_schema_keeps_it(self) -> None:
        #: Given
        schema: dict[str, object] = {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object'}

        #: When
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=schema)

        #: Then
        assert frontmatter.schema == schema, 'naming the dialect the check applies is allowed'

    def test_construction_with_root_combinators_beside_the_type_keeps_it(self) -> None:
        #: Given
        schema: dict[str, object] = {
            'type': 'object',
            'if': {'properties': {'type': {'const': 'pattern'}}},
            'then': {'required': ['scope']},
        }

        #: When
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=schema)

        #: Then
        assert frontmatter.schema == schema, 'a combinator at the root is allowed next to the object type'

    def test_construction_with_an_id_inside_an_enum_value_keeps_it(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'properties': {'ref': {'enum': [{'$id': 'data'}]}}}

        #: When
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=schema)

        #: Then
        assert frontmatter.schema == schema, 'a value under enum is data, not a schema, so its $id is no resource'

    def test_construction_with_a_malformed_schema_raises_invalid_frontmatter_schema_error(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'required': 'name'}

        #: When
        with pytest.raises(InvalidFrontmatterSchemaError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a malformed schema is refused, naming the structure specification'
        assert exc_info.value.problem == exc_info.value.source.message, (
            f'the problem is what the meta-schema rejected, got {exc_info.value.problem!r}'
        )
        assert exc_info.value.problem in str(exc_info.value), f'the message quotes the problem, got {exc_info.value}'

    def test_construction_without_a_type_raises_untyped_frontmatter_schema_error(self) -> None:
        #: Given
        schema: dict[str, object] = {'required': ['name']}

        #: When
        with pytest.raises(UntypedFrontmatterSchemaError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an implied object type is refused'
        assert str(SPEC_PATH) in str(exc_info.value), f'the message names the file, got {exc_info.value}'

    def test_construction_with_a_non_object_type_raises_untyped_frontmatter_schema_error(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'array'}

        #: When
        with pytest.raises(UntypedFrontmatterSchemaError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a frontmatter is always a mapping'

    def test_construction_with_a_type_list_raises_untyped_frontmatter_schema_error(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': ['object', 'null']}

        #: When
        with pytest.raises(UntypedFrontmatterSchemaError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the type is exactly "object"'

    def test_construction_with_an_id_raises_frontmatter_schema_id_error(self) -> None:
        #: Given
        schema: dict[str, object] = {'$id': 'https://example.com/code', 'type': 'object'}

        #: When
        with pytest.raises(FrontmatterSchemaIdError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an $id would change how relative $refs resolve'
        assert str(SPEC_PATH) in str(exc_info.value), f'the message names the file, got {exc_info.value}'

    def test_construction_with_an_id_in_a_nested_schema_raises_frontmatter_schema_id_error(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'properties': {'name': {'$id': 'https://example.com/name'}}}

        #: When
        with pytest.raises(FrontmatterSchemaIdError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an $id at any depth makes a resource of its own'

    def test_construction_with_a_foreign_dialect_raises_foreign_frontmatter_dialect_error(self) -> None:
        #: Given
        schema: dict[str, object] = {'$schema': 'http://json-schema.org/draft-07/schema#', 'type': 'object'}

        #: When
        with pytest.raises(ForeignFrontmatterDialectError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a schema written for another dialect is refused'
        assert exc_info.value.dialect == 'http://json-schema.org/draft-07/schema#', (
            f'the error carries the dialect the schema names, got {exc_info.value.dialect!r}'
        )
        assert 'http://json-schema.org/draft-07/schema#' in str(exc_info.value), (
            f'the message names the foreign dialect, got {exc_info.value}'
        )

    def test_construction_with_a_foreign_dialect_in_a_nested_schema_raises_foreign_frontmatter_dialect_error(
        self,
    ) -> None:
        #: Given
        schema: dict[str, object] = {
            'type': 'object',
            '$defs': {'scope': {'$schema': 'http://json-schema.org/draft-07/schema#', 'type': 'string'}},
        }

        #: When
        with pytest.raises(ForeignFrontmatterDialectError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a nested schema may not switch dialect either'

    def test_validate_with_a_conforming_frontmatter_returns_no_problems(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema={'type': 'object', 'required': ['name']})
        data: dict[object, object] = {'name': 'guide'}

        #: When
        problems = frontmatter.validate(data)

        #: Then
        assert problems == (), 'a frontmatter the schema accepts has no problems'

    def test_validate_without_two_required_fields_returns_one_missing_problem_each(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema={'type': 'object', 'required': ['name', 'type']})
        data: dict[object, object] = {}

        #: When
        problems = frontmatter.validate(data)

        #: Then
        assert problems == (
            MissingFieldProblem('name', "'name' is a required property"),
            MissingFieldProblem('type', "'type' is a required property"),
        ), 'jsonschema reports each absent field once, however many the schema requires'

    def test_validate_with_one_of_two_required_fields_present_returns_a_missing_problem_for_the_other(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema={'type': 'object', 'required': ['name', 'type']})
        data: dict[object, object] = {'name': 'guide'}

        #: When
        problems = frontmatter.validate(data)

        #: Then
        assert problems == (MissingFieldProblem('type', "'type' is a required property"),), (
            'a required field the frontmatter carries is not reported missing'
        )

    def test_validate_with_two_fields_at_fault_orders_the_problems_by_field_before_message(self) -> None:
        #: Given
        # `name` sorts before `type`, while their messages sort the other way round
        schema: dict[str, object] = {
            'type': 'object',
            'properties': {'name': {'type': 'string'}, 'type': {'enum': ['rule', 'pattern']}},
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=schema)
        data: dict[object, object] = {'name': 3, 'type': 'guide'}

        #: When
        problems = frontmatter.validate(data)

        #: Then
        assert problems == (
            WrongTypeProblem('name', "3 is not of type 'string'"),
            InvalidValueProblem('type', "'guide' is not one of ['rule', 'pattern']"),
        ), 'problems are ordered by the field they concern first, and by their message only within a field'

    def test_validate_with_fields_the_schema_does_not_allow_returns_one_unknown_field_problem_each(self) -> None:
        #: Given
        schema: dict[str, object] = {
            'type': 'object',
            'properties': {'name': {}},
            'patternProperties': {'^x-': {}},
            'additionalProperties': False,
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=schema)
        data: dict[object, object] = {'name': 'guide', 'x-owner': 'me', 'model': 'opus', 'tier': 1}

        #: When
        problems = frontmatter.validate(data)

        #: Then
        assert problems == (
            UnknownFieldProblem(
                'model',
                "Additional properties are not allowed ('model' was unexpected)",
            ),
            UnknownFieldProblem(
                'tier',
                "Additional properties are not allowed ('tier' was unexpected)",
            ),
        ), 'each field neither properties nor patternProperties names is its own problem'

    def test_validate_with_a_key_that_is_not_a_string_returns_a_non_string_key_problem(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema={'type': 'object', 'additionalProperties': False})
        data: dict[object, object] = {123: 'x'}

        #: When
        problems = frontmatter.validate(data)

        #: Then
        assert problems == (NonStringKeyProblem('Additional properties are not allowed (123 was unexpected)'),), (
            'a key that is not a string names no field'
        )

    def test_validate_with_a_value_of_the_wrong_type_returns_a_wrong_type_problem(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'properties': {'name': {'type': 'string'}}}
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=schema)
        data: dict[object, object] = {'name': 3}

        #: When
        problems = frontmatter.validate(data)

        #: Then
        assert problems == (WrongTypeProblem('name', "3 is not of type 'string'"),), (
            "the message is the validator's, naming the constraint the schema wrote"
        )

    def test_validate_with_a_value_outside_an_enum_returns_an_invalid_value_problem(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'properties': {'type': {'enum': ['rule', 'pattern']}}}
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=schema)
        data: dict[object, object] = {'type': 'guide'}

        #: When
        problems = frontmatter.validate(data)

        #: Then
        assert problems == (InvalidValueProblem('type', "'guide' is not one of ['rule', 'pattern']"),), (
            'a value of the right type breaking another rule is invalid'
        )

    def test_validate_with_an_unknown_key_inside_a_field_returns_an_invalid_value_problem_on_the_field(self) -> None:
        #: Given
        schema: dict[str, object] = {
            'type': 'object',
            'properties': {'metadata': {'type': 'object', 'properties': {'author': {}}, 'additionalProperties': False}},
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=schema)
        data: dict[object, object] = {'metadata': {'owner': 'me'}}

        #: When
        problems = frontmatter.validate(data)

        #: Then
        assert problems == (
            InvalidValueProblem(
                'metadata',
                "Additional properties are not allowed ('owner' was unexpected)",
            ),
        ), "a key inside a field makes that field's value invalid; the field itself is known"

    def test_validate_with_a_rule_over_the_whole_block_returns_a_block_problem(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema={'type': 'object', 'minProperties': 1})
        data: dict[object, object] = {}

        #: When
        problems = frontmatter.validate(data)

        #: Then
        assert problems == (BlockProblem('{} should be non-empty'),), 'a rule over the block concerns no field'
