"""The structure specification.

`parse` deserializes a file's text into the dialect's shape, and construction refuses rules that are not usable.
"""

import json
import re
from textwrap import dedent
from typing import Final

import pytest

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath

from ..frontmatter_problem import (
    BlockProblem,
    FieldGuidance,
    InvalidValueProblem,
    JsonType,
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
from ..name import SpecName, parse_spec_name
from ..section_name import PaddedSectionNameError, SectionName
from ..spec_file import SpecFileType, StructureSpecFile, spec_filename
from ..structure import (
    AdjacentAnyRunsError,
    AnySections,
    EmptyStructureSpecError,
    ForbiddenOutlineSectionError,
    ForeignFrontmatterDialectError,
    FrontmatterSchema,
    FrontmatterSchemaIdError,
    InvalidFrontmatterSchemaError,
    InvalidTitlePatternError,
    RepeatedForbiddenSectionError,
    RepeatedOutlineSectionError,
    SectionEntry,
    StructureSchema,
    StructureSpec,
    StructureSpecDecodeError,
    TitleChecks,
    TitlePattern,
    UntypedFrontmatterSchemaError,
)

SPECS_DIR: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__')
SPEC_NAME: Final[SpecName] = parse_spec_name('code')
SPEC_PATH: Final[RootRelativePath] = SPECS_DIR / spec_filename(SPEC_NAME, SpecFileType.STRUCTURE)
SPEC_FILE: Final[StructureSpecFile] = StructureSpecFile(path=SPEC_PATH, name=SPEC_NAME)

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
                  "title": {"words": 8, "chars": 60},
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
        structure_spec = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert structure_spec == StructureSpec(
            file=SPEC_FILE,
            title=TitleChecks(words=NonZeroUnsignedInt(8), chars=NonZeroUnsignedInt(60), pattern=None),
            forbid_empty_sections=True,
            outline=(
                AnySections(words=NonZeroUnsignedInt(350)),
                SectionEntry(name=SectionName('Checklist'), words=NonZeroUnsignedInt(250)),
                SectionEntry(name=SectionName('References'), optional=True),
            ),
            forbidden=(SectionName('Changelog'),),
            tokens=NonZeroUnsignedInt(5000),
            frontmatter=FrontmatterSchema(
                path=SPEC_PATH, schema=FrozenMapping.from_plain({'type': 'object', 'required': ['name']})
            ),
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
        structure_spec = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert structure_spec.outline == (
            SectionEntry(
                name=SectionName('Checklist'),
                description=CHECKLIST_DESCRIPTION,
                examples=(LOGGING_CHECKLIST, DOCSTRINGS_CHECKLIST),
            ),
        ), f'a section entry keeps its description and every example, in order, got {structure_spec.outline!r}'

    def test_parse_with_a_section_without_description_or_examples_states_neither(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist"}]}')

        #: When
        structure_spec = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert structure_spec.outline == (
            SectionEntry(name=SectionName('Checklist'), description=None, examples=()),
        ), f'both keys are optional, and absent they state nothing, got {structure_spec.outline!r}'

    def test_parse_with_an_empty_section_description_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "description": ""}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an empty description would print empty help, so it is refused'

    def test_parse_with_an_empty_list_of_section_examples_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "examples": []}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'no examples are written by leaving the key out, so `[]` is refused'

    def test_parse_with_an_empty_section_example_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema(
            json.dumps({'outline': [{'section': 'Checklist', 'examples': [LOGGING_CHECKLIST, '']}]})
        )

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an empty example would print a heading alone, so it is refused'

    def test_parse_with_a_section_description_that_is_not_a_string_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema(
            json.dumps({'outline': [{'section': 'Checklist', 'description': [CHECKLIST_DESCRIPTION]}]})
        )

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a description is one string of text, not a list of lines'

    def test_parse_with_section_examples_given_as_one_string_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema(json.dumps({'outline': [{'section': 'Checklist', 'examples': LOGGING_CHECKLIST}]}))

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'examples are a list, so one bare string is refused'

    def test_parse_with_a_section_example_that_is_not_a_string_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "examples": [3]}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the file is read strictly, so a number is not an example'

    def test_parse_with_a_description_on_an_any_run_raises_structure_spec_decode_error(self) -> None:
        #: Given
        # a run can never be missing, so nothing would ever report what it holds
        schema = StructureSchema('{"outline": [{"any": true, "description": "The document\'s own sections."}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'only a named section takes a description'

    def test_parse_with_examples_on_an_any_run_raises_structure_spec_decode_error(self) -> None:
        #: Given
        # a run can never be missing, so nothing would ever report an example of it
        schema = StructureSchema(json.dumps({'outline': [{'any': True, 'examples': [LOGGING_CHECKLIST]}]}))

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'only a named section takes examples'

    def test_parse_with_only_a_frontmatter_schema_returns_a_structure_spec_with_that_schema(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"type": "object"}}')

        #: When
        structure_spec = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert structure_spec.frontmatter == FrontmatterSchema(
            path=SPEC_PATH, schema=FrozenMapping.from_plain({'type': 'object'})
        ), 'a frontmatter schema is a rule, so a file stating only it is usable'

    def test_parse_with_a_nested_frontmatter_schema_holds_it_frozen_all_the_way_down(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"type": "object", "properties": {"tags": {"enum": [["a"]]}}}}')

        #: When
        structure_spec = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert structure_spec.frontmatter is not None, 'the file states a frontmatter schema'
        assert structure_spec.frontmatter.schema == FrozenMapping(
            {'type': 'object', 'properties': FrozenMapping({'tags': FrozenMapping({'enum': (('a',),)})})}
        ), 'every object in the schema is a frozen mapping and every array a tuple, at any depth'

    def test_parse_with_a_frontmatter_schema_returns_a_hashable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"type": "object", "required": ["name"]}}')

        #: When
        structure_spec = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(hash(structure_spec), int), 'a structure specification holding a frontmatter schema hashes'

    def test_parse_with_a_malformed_frontmatter_schema_raises_invalid_frontmatter_schema_error(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"type": "object", "minProperties": -1}}')

        #: When
        with pytest.raises(InvalidFrontmatterSchemaError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

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
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the object type is stated, not implied'

    def test_parse_with_a_frontmatter_value_that_is_not_an_object_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": true}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a boolean schema is refused by the shape'

    def test_parse_with_a_null_frontmatter_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 100, "frontmatter": null}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

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
            StructureSpec.parse(SPEC_FILE, schema)

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
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the editor lets a foreign $schema through, the load refuses it'
        assert exc_info.value.dialect == 'http://json-schema.org/draft-07/schema#', (
            f'the error carries the dialect the schema names, got {exc_info.value.dialect!r}'
        )

    def test_parse_with_only_a_token_budget_returns_a_structure_spec_with_that_budget(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 4000}')

        #: When
        structure_spec = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert structure_spec.tokens == NonZeroUnsignedInt(4000), (
            'a token budget is a rule, so a file stating only it is usable'
        )

    def test_parse_with_a_token_budget_of_zero_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 0}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'no document satisfies a budget of 0 tokens'
        assert exc_info.value.problems == ('tokens: must be at least 1, got 0',), (
            f'the problem names the field and reads with the count rejection, got {exc_info.value.problems}'
        )

    def test_parse_with_a_document_word_cap_raises_structure_spec_decode_error(self) -> None:
        #: Given
        # words are capped per section only; the document as a whole has a token budget instead
        schema = StructureSchema('{"words": 1800}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a top-level `words` is not a field, so it is refused, not ignored'

    def test_parse_with_a_section_word_cap_of_zero_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "words": 0}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'no section satisfies a cap of 0 words'
        assert 'outline.0.StructureFileSection.words: must be at least 1, got 0' in exc_info.value.problems, (
            f'the section shape reports the cap with the count rejection, got {exc_info.value.problems}'
        )

    def test_parse_with_an_any_word_cap_of_zero_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"any": true, "words": 0}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'no section in a run satisfies a cap of 0 words'

    def test_parse_with_a_string_word_cap_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "words": "250"}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the file is read strictly, so a string is not a word cap'

    def test_parse_with_a_fractional_token_budget_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 5000.5}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a token budget is a whole number of tokens'

    def test_parse_with_a_boolean_section_word_cap_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "words": true}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

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
        structure_spec = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert structure_spec == StructureSpec(
            file=SPEC_FILE,
            title=None,
            forbid_empty_sections=False,
            outline=(),
            forbidden=(SectionName('Changelog'),),
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
            StructureSpec.parse(SPEC_FILE, schema)

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
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'text that is not JSON is refused at the edge, naming the file'
        assert exc_info.value.source is exc_info.value.__cause__, 'the validation error is kept as the cause'

    def test_parse_with_only_a_title_word_cap_returns_a_structure_spec_with_that_cap(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"words": 8}}')

        #: When
        structure_spec = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert structure_spec.title == TitleChecks(words=NonZeroUnsignedInt(8), chars=None, pattern=None), (
            'a cap on the title is a rule, so a file stating only it is usable'
        )

    def test_parse_with_a_title_word_cap_of_zero_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"words": 0}}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'no title satisfies a cap of 0 words'
        assert exc_info.value.problems == ('title.words: must be at least 1, got 0',), (
            f'the problem names the cap and reads with the count rejection, got {exc_info.value.problems}'
        )

    def test_parse_with_a_negative_title_word_cap_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"words": -3}}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a word cap is a count of words, never below 1'
        assert len(exc_info.value.problems) == 1, f'one field is wrong, got {exc_info.value.problems}'
        assert exc_info.value.problems[0].startswith('title.words: '), (
            f'the problem opens with the dotted path of the cap, got {exc_info.value.problems[0]!r}'
        )

    def test_parse_with_a_boolean_title_word_cap_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"words": true}}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a JSON boolean is not a word cap, though Python treats it as one'
        assert len(exc_info.value.problems) == 1, f'one field is wrong, got {exc_info.value.problems}'
        assert exc_info.value.problems[0].startswith('title.words: '), (
            f'the problem opens with the dotted path of the cap, got {exc_info.value.problems[0]!r}'
        )

    def test_parse_with_only_a_title_character_cap_returns_a_structure_spec_with_that_cap(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"chars": 60}}')

        #: When
        structure_spec = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert structure_spec.title == TitleChecks(words=None, chars=NonZeroUnsignedInt(60), pattern=None), (
            "a cap on the title's characters is a rule, so a file stating only it is usable"
        )

    def test_parse_with_a_title_character_cap_of_zero_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"chars": 0}}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'no title satisfies a cap of 0 characters'
        assert exc_info.value.problems == ('title.chars: must be at least 1, got 0',), (
            f'the problem names the cap and reads with the count rejection, got {exc_info.value.problems}'
        )

    def test_parse_with_a_negative_title_character_cap_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"chars": -3}}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a character cap is a count of characters, never below 1'
        assert len(exc_info.value.problems) == 1, f'one field is wrong, got {exc_info.value.problems}'
        assert exc_info.value.problems[0].startswith('title.chars: '), (
            f'the problem opens with the dotted path of the cap, got {exc_info.value.problems[0]!r}'
        )

    def test_parse_with_a_boolean_title_character_cap_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"chars": true}}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a JSON boolean is not a character cap, though Python treats it as one'
        assert len(exc_info.value.problems) == 1, f'one field is wrong, got {exc_info.value.problems}'
        assert exc_info.value.problems[0].startswith('title.chars: '), (
            f'the problem opens with the dotted path of the cap, got {exc_info.value.problems[0]!r}'
        )

    def test_parse_with_an_empty_title_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                  "title": {},
                  "empty_sections": "forbidden"
                }
                """
            )
        )

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a `title` stating no check would state nothing'
        assert exc_info.value.problems == (
            'title: Value error, states no check; leave the key out for no title check',
        ), f'the problem names the key and says how to state no title check, got {exc_info.value.problems}'

    def test_parse_with_only_a_title_pattern_returns_a_structure_spec_with_that_pattern_compiled(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"pattern": "^[A-Z]"}}')

        #: When
        structure_spec = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert structure_spec.title == TitleChecks(
            words=None, chars=None, pattern=TitlePattern(re.compile('^[A-Z]'))
        ), 'a pattern on the title is a rule, so a file stating only it is usable, and it is held compiled'

    def test_parse_with_a_title_word_cap_and_pattern_returns_a_structure_spec_with_both(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"words": 8, "pattern": "^[A-Z]"}}')

        #: When
        structure_spec = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert structure_spec.title == TitleChecks(
            words=NonZeroUnsignedInt(8), chars=None, pattern=TitlePattern(re.compile('^[A-Z]'))
        ), 'a cap and a pattern are independent, and the title carries both'

    def test_parse_with_a_title_pattern_that_does_not_compile_raises_invalid_title_pattern_error(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"pattern": "^(unclosed"}}')

        #: When
        with pytest.raises(InvalidTitlePatternError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a pattern that does not compile is refused, naming the file'
        assert exc_info.value.pattern == '^(unclosed', 'the error carries the pattern exactly as written'
        assert exc_info.value.problem == 'missing ), unterminated subpattern', (
            f'the error carries what the compiler rejected as a field, got {exc_info.value.problem!r}'
        )
        assert str(exc_info.value) == (
            f"invalid structure schema {SPEC_PATH}: title pattern '^(unclosed' is not a valid regular expression"
        ), f'the message names the file and the pattern, and leaves the reason to its cause, got {exc_info.value}'

    def test_parse_with_a_non_string_title_pattern_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"pattern": 3}}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a JSON number is not a pattern'
        assert exc_info.value.problems == ('title.pattern: Input should be a valid string',), (
            f'the problem names the pattern with the type rejection, got {exc_info.value.problems}'
        )

    def test_parse_with_an_empty_title_pattern_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"pattern": ""}}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an empty pattern matches every title, so it would check nothing'
        assert exc_info.value.problems == ('title.pattern: String should have at least 1 character',), (
            f'the problem names the pattern with the length rejection, got {exc_info.value.problems}'
        )

    def test_parse_with_an_unknown_key_in_the_title_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"words": 8, "count": 1}}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a misspelt or removed title check is an error, not ignored'
        assert len(exc_info.value.problems) == 1, f'one key is wrong, got {exc_info.value.problems}'
        assert exc_info.value.problems[0].startswith('title.count: '), (
            f'the problem opens with the dotted path of the unknown key, got {exc_info.value.problems[0]!r}'
        )

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
            StructureSpec.parse(SPEC_FILE, schema)

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
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the error names the rejected file'

    def test_parse_with_a_spec_field_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"spec": "code.md", "forbidden": ["Changelog"]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

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
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, '"forbidden" is the only value `empty_sections` takes'

    def test_parse_with_two_wrong_fields_lists_one_problem_each_in_the_message(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 0, "empty_sections": "allowed"}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert len(exc_info.value.problems) == 2, f'each wrong field is its own problem, got {exc_info.value.problems}'
        assert exc_info.value.problems[0].startswith('tokens: '), (
            f'the first problem opens with the dotted path of its field, got {exc_info.value.problems[0]!r}'
        )
        assert exc_info.value.problems[1].startswith('empty_sections: '), (
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
            StructureSpec.parse(SPEC_FILE, schema)

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
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, '`forbidden` holds section names only'

    def test_parse_with_a_padded_section_name_raises_structure_spec_decode_error(self) -> None:
        #: Given
        # a heading's text never has whitespace at either end, so no document could hold this section
        schema = StructureSchema('{"outline": [{"section": " Checklist"}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, "the mistake is the specification's, so the load refuses it"
        expected = f'outline.0.StructureFileSection.section: {PaddedSectionNameError(" Checklist")}'
        assert expected in exc_info.value.problems, (
            f'the section shape reports the name with its rejection, got {exc_info.value.problems}'
        )

    def test_parse_with_an_empty_section_name_raises_structure_spec_decode_error(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": ""}]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an empty name matches only a heading with no text'

    def test_parse_with_a_padded_forbidden_entry_raises_structure_spec_decode_error(self) -> None:
        #: Given
        # a forbidden name no heading can carry would forbid nothing, silently
        schema = StructureSchema('{"forbidden": ["Changelog "]}')

        #: When
        with pytest.raises(StructureSpecDecodeError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.problems == (f'forbidden.0: {PaddedSectionNameError("Changelog ")}',), (
            f'the problem names the entry and reads with the name rejection, got {exc_info.value.problems}'
        )

    def test_parse_with_a_forbidden_entry_given_twice_raises_repeated_forbidden_section_error(self) -> None:
        #: Given
        schema = StructureSchema('{"forbidden": ["Changelog", "Changelog"]}')

        #: When
        with pytest.raises(RepeatedForbiddenSectionError) as exc_info:
            StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the shape lets a repeated entry through, the rules refuse it'
        assert exc_info.value.sections == ('Changelog',), (
            f'the error carries the repeated name once, got {exc_info.value.sections}'
        )


@pytest.mark.unit
class TestStructureSpecConstruction:
    def test_construction_without_any_rule_raises_empty_structure_spec_error(self) -> None:
        #: Given
        file = SPEC_FILE

        #: When
        with pytest.raises(EmptyStructureSpecError) as exc_info:
            StructureSpec(
                file=file,
                title=None,
                forbid_empty_sections=False,
                outline=(),
                forbidden=(),
                tokens=None,
                frontmatter=None,
            )

        #: Then
        assert exc_info.value.path == file.path, 'a specification stating no rule would check nothing'

    def test_construction_with_a_title_stating_no_check_alone_raises_empty_structure_spec_error(self) -> None:
        #: Given
        file = SPEC_FILE

        #: When
        with pytest.raises(EmptyStructureSpecError) as exc_info:
            StructureSpec(
                file=file,
                title=TitleChecks(words=None, chars=None, pattern=None),
                forbid_empty_sections=False,
                outline=(),
                forbidden=(),
                tokens=None,
                frontmatter=None,
            )

        #: Then
        assert exc_info.value.path == file.path, (
            'the title is checked whatever the specification states, so a title with no check states no rule'
        )

    def test_construction_with_a_section_named_twice_raises_repeated_outline_section_error(self) -> None:
        #: Given
        outline = (
            SectionEntry(name=SectionName('Checklist')),
            SectionEntry(name=SectionName('Checklist'), optional=True),
        )

        #: When
        with pytest.raises(RepeatedOutlineSectionError) as exc_info:
            StructureSpec(
                file=SPEC_FILE,
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

    def test_construction_forbidding_a_section_twice_raises_repeated_forbidden_section_error(self) -> None:
        #: Given
        forbidden = (SectionName('Changelog'), SectionName('History'), SectionName('Changelog'))

        #: When
        with pytest.raises(RepeatedForbiddenSectionError) as exc_info:
            StructureSpec(
                file=SPEC_FILE,
                title=None,
                forbid_empty_sections=False,
                outline=(),
                forbidden=forbidden,
                tokens=None,
                frontmatter=None,
            )

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a second entry would report every forbidden section twice'
        assert exc_info.value.sections == ('Changelog',), (
            f'the error carries only the repeated name, once, got {exc_info.value.sections}'
        )
        assert 'Changelog' in str(exc_info.value), f'the message names the repeated section, got {exc_info.value}'

    def test_construction_forbidding_a_section_its_outline_names_raises_forbidden_outline_section_error(self) -> None:
        #: Given
        outline = (SectionEntry(name=SectionName('Checklist'), optional=True),)

        #: When
        with pytest.raises(ForbiddenOutlineSectionError) as exc_info:
            StructureSpec(
                file=SPEC_FILE,
                title=None,
                forbid_empty_sections=False,
                outline=outline,
                forbidden=(SectionName('Checklist'),),
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
            SectionEntry(name=SectionName('Checklist')),
        )

        #: When
        with pytest.raises(AdjacentAnyRunsError) as exc_info:
            StructureSpec(
                file=SPEC_FILE,
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


@pytest.mark.unit
class TestTitlePattern:
    def test_parse_with_a_pattern_that_compiles_returns_it_compiled(self) -> None:
        #: Given
        text = '^[A-Z]'

        #: When
        pattern = TitlePattern.parse(text, path=SPEC_PATH)

        #: Then
        assert pattern == TitlePattern(re.compile(text)), f'the pattern is held compiled, got {pattern!r}'

    def test_parse_with_a_pattern_that_does_not_compile_raises_invalid_title_pattern_error(self) -> None:
        #: Given
        text = '^(unclosed'

        #: When
        with pytest.raises(InvalidTitlePatternError) as exc_info:
            TitlePattern.parse(text, path=SPEC_PATH)

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a pattern that does not compile is refused, naming the file'
        assert exc_info.value.pattern == text, 'the error carries the pattern exactly as written'
        assert isinstance(exc_info.value.__cause__, re.error), "the compiler's error is kept as the cause"

    def test_is_found_in_with_text_holding_the_pattern_inside_it_returns_true(self) -> None:
        #: Given
        pattern = TitlePattern(re.compile('Guide'))

        #: When
        is_found = pattern.is_found_in('The Guide to Setup')

        #: Then
        assert is_found, "an unanchored pattern is searched for anywhere in the text, as JSON Schema's `pattern` is"

    def test_is_found_in_with_an_anchored_pattern_found_only_inside_the_text_returns_false(self) -> None:
        #: Given
        pattern = TitlePattern(re.compile('^Guide$'))

        #: When
        is_found = pattern.is_found_in('The Guide to Setup')

        #: Then
        assert not is_found, 'a pattern anchored at both ends must hold the whole text'

    def test_str_with_a_pattern_returns_it_as_written(self) -> None:
        #: Given
        pattern = TitlePattern(re.compile('^[A-Z][^:]*$'))

        #: When
        text = str(pattern)

        #: Then
        assert text == '^[A-Z][^:]*$', f'the pattern reads back exactly as written, got {text!r}'


@pytest.mark.unit
class TestStructureSpecAuthority:
    def test_construction_at_a_namespace_path_derives_the_prose_at_its_stem(self) -> None:
        #: Given
        name = parse_spec_name('code-python')
        file = StructureSpecFile(path=SPECS_DIR / spec_filename(name, SpecFileType.STRUCTURE), name=name)

        #: When
        structure_spec = StructureSpec(
            file=file,
            title=None,
            forbid_empty_sections=False,
            outline=(),
            forbidden=(SectionName('Changelog'),),
            tokens=None,
            frontmatter=None,
        )

        #: Then
        assert structure_spec.authority == 'code-python.md', 'the prose is the `.md` file at the same spec name'


@pytest.mark.unit
class TestFrontmatterSchema:
    def test_construction_with_an_object_schema_keeps_it(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'required': ['name'], 'description': 'read by people'}

        #: When
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))

        #: Then
        assert frontmatter.schema == FrozenMapping.from_plain(schema), 'a well-formed object schema is held unchanged'

    def test_construction_with_the_draft_2020_12_dialect_in_schema_keeps_it(self) -> None:
        #: Given
        schema: dict[str, object] = {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object'}

        #: When
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))

        #: Then
        assert frontmatter.schema == FrozenMapping.from_plain(schema), 'naming the dialect the check applies is allowed'

    def test_construction_with_root_combinators_beside_the_type_keeps_it(self) -> None:
        #: Given
        schema: dict[str, object] = {
            'type': 'object',
            'if': {'properties': {'type': {'const': 'pattern'}}},
            'then': {'required': ['scope']},
        }

        #: When
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))

        #: Then
        assert frontmatter.schema == FrozenMapping.from_plain(schema), (
            'a combinator at the root is allowed next to the object type'
        )

    def test_construction_with_an_id_inside_an_enum_value_keeps_it(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'properties': {'ref': {'enum': [{'$id': 'data'}]}}}

        #: When
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))

        #: Then
        assert frontmatter.schema == FrozenMapping.from_plain(schema), (
            'a value under enum is data, not a schema, so its $id is no resource'
        )

    def test_construction_with_a_malformed_schema_raises_invalid_frontmatter_schema_error(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'required': 'name'}

        #: When
        with pytest.raises(InvalidFrontmatterSchemaError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))

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
            FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an implied object type is refused'
        assert str(SPEC_PATH) in str(exc_info.value), f'the message names the file, got {exc_info.value}'

    def test_construction_with_a_non_object_type_raises_untyped_frontmatter_schema_error(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'array'}

        #: When
        with pytest.raises(UntypedFrontmatterSchemaError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a frontmatter is always a mapping'

    def test_construction_with_a_type_list_raises_untyped_frontmatter_schema_error(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': ['object', 'null']}

        #: When
        with pytest.raises(UntypedFrontmatterSchemaError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'the type is exactly "object"'

    def test_construction_with_an_id_raises_frontmatter_schema_id_error(self) -> None:
        #: Given
        schema: dict[str, object] = {'$id': 'https://example.com/code', 'type': 'object'}

        #: When
        with pytest.raises(FrontmatterSchemaIdError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an $id would change how relative $refs resolve'
        assert str(SPEC_PATH) in str(exc_info.value), f'the message names the file, got {exc_info.value}'

    def test_construction_with_an_id_in_a_nested_schema_raises_frontmatter_schema_id_error(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'properties': {'name': {'$id': 'https://example.com/name'}}}

        #: When
        with pytest.raises(FrontmatterSchemaIdError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'an $id at any depth makes a resource of its own'

    def test_construction_with_a_foreign_dialect_raises_foreign_frontmatter_dialect_error(self) -> None:
        #: Given
        schema: dict[str, object] = {'$schema': 'http://json-schema.org/draft-07/schema#', 'type': 'object'}

        #: When
        with pytest.raises(ForeignFrontmatterDialectError) as exc_info:
            FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))

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
            FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))

        #: Then
        assert exc_info.value.path == SPEC_PATH, 'a nested schema may not switch dialect either'

    def test_validate_with_a_conforming_frontmatter_returns_no_problems(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(
            path=SPEC_PATH, schema=FrozenMapping.from_plain({'type': 'object', 'required': ['name']})
        )
        data: dict[str, object] = {'name': 'guide'}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (), 'a frontmatter the schema accepts has no problems'

    def test_validate_without_two_required_fields_returns_one_missing_problem_each(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(
            path=SPEC_PATH, schema=FrozenMapping.from_plain({'type': 'object', 'required': ['name', 'type']})
        )
        data: dict[str, object] = {}

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
            path=SPEC_PATH, schema=FrozenMapping.from_plain({'type': 'object', 'required': ['name', 'type']})
        )
        data: dict[str, object] = {'name': 'guide'}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

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
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'name': 3, 'type': 'guide'}

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
        schema: dict[str, object] = {
            'type': 'object',
            'properties': {'name': {}},
            'patternProperties': {'^x-': {}},
            'additionalProperties': False,
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'name': 'guide', 'x-owner': 'me', 'model': 'opus', 'tier': 1}

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
        schema: dict[str, object] = {
            'type': 'object',
            'allOf': [{'$ref': '#/$defs/base'}],
            'properties': {'status': {}},
            'unevaluatedProperties': False,
            '$defs': {'base': {'properties': {'name': {}, 'description': {}}}},
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {
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
        schema: dict[str, object] = {
            'type': 'object',
            'allOf': [{'properties': {'name': {}}}],
            'unevaluatedProperties': {'type': 'string'},
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'name': 3, 'owner': 'me', 'tier': 1}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (InvalidValueProblem('tier', "1 is not of type 'string'", OtherValueConstraint()),), (
            'an unevaluated field is held to the rule schema, and only one breaking it is a problem, on that field'
        )

    def test_validate_with_a_value_of_the_wrong_type_returns_a_wrong_type_problem(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'properties': {'name': {'type': 'string'}}}
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'name': 3}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            WrongTypeProblem('name', "3 is not of type 'string'", (JsonType.STRING,), JsonType.INTEGER),
        ), "the message is the validator's, and the types are the schema's and the value's"

    def test_validate_with_a_value_outside_an_enum_returns_an_invalid_value_problem(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'properties': {'type': {'enum': ['rule', 'pattern']}}}
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'type': 'guide'}

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
        schema: dict[str, object] = {
            'type': 'object',
            'properties': {'name': {'type': 'string', 'description': 'Kebab-case.', 'examples': ['setup-guide']}},
            'allOf': [{'properties': {'name': {'pattern': '^[a-z-]+$'}}, '$comment': 'Lowercase words only.'}],
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'name': 'Setup'}

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
        schema: dict[str, object] = {
            'type': 'object',
            'properties': {
                'description': {
                    'type': 'string',
                    'allOf': [{'not': {'pattern': r'\.\s*$'}, '$comment': 'No trailing period.'}],
                }
            },
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'description': 'Load when x.'}

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

    def test_validate_with_a_value_other_than_a_const_returns_the_value_allowed(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'properties': {'type': {'const': 'rule'}}}
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'type': 'guide'}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

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
        schema: dict[str, object] = {
            'type': 'object',
            'properties': {'tags': {'type': 'array', 'items': {'enum': ['a', 'b']}}},
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'tags': ['c']}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (InvalidValueProblem('tags', "'c' is not one of ['a', 'b']", OtherValueConstraint()),), (
            "the enum limits the items, not the field, so the field's own value is not said to be outside it"
        )

    def test_validate_with_an_item_breaking_a_pattern_returns_an_untyped_constraint(self) -> None:
        #: Given
        schema: dict[str, object] = {
            'type': 'object',
            'properties': {'tags': {'type': 'array', 'items': {'pattern': '^[a-z]+$'}}},
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'tags': ['A']}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (InvalidValueProblem('tags', "'A' does not match '^[a-z]+$'", OtherValueConstraint()),), (
            "the pattern limits the items, not the field, so the field's own value is not said to break it"
        )

    def test_validate_with_an_unknown_key_inside_a_field_returns_an_invalid_value_problem_on_the_field(self) -> None:
        #: Given
        schema: dict[str, object] = {
            'type': 'object',
            'properties': {'metadata': {'type': 'object', 'properties': {'author': {}}, 'additionalProperties': False}},
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'metadata': {'owner': 'me'}}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

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
        schema: dict[str, object] = {
            'type': 'object',
            'properties': {'tags': {'type': 'array', 'items': {'type': 'string'}}, 'meta': {'type': 'object'}},
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'tags': ['a', 'b'], 'meta': {'owner': 'me'}}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (), 'a frozen list is still a JSON array to the schema, and a frozen mapping an object'

    def test_validate_with_a_list_where_a_string_belongs_quotes_it_as_a_list(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'properties': {'name': {'type': 'string'}}}
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'name': ['a']}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            WrongTypeProblem('name', "['a'] is not of type 'string'", (JsonType.STRING,), JsonType.ARRAY),
        ), 'the message quotes the value as the YAML decoded it, not as the tuple it is frozen into'

    def test_validate_with_a_rule_over_the_whole_block_returns_a_block_problem(self) -> None:
        #: Given
        frontmatter = FrontmatterSchema(
            path=SPEC_PATH, schema=FrozenMapping.from_plain({'type': 'object', 'minProperties': 1})
        )
        data: dict[str, object] = {}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (BlockProblem('{} should be non-empty', MinFields(1), 0),), (
            'a rule over the block concerns no field'
        )

    def test_validate_with_too_many_fields_returns_a_block_problem_with_the_limit_and_the_description(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'description': 'A guide.', 'maxProperties': 1}
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'name': 'guide', 'type': 'rule'}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            BlockProblem(
                "{'name': 'guide', 'type': 'rule'} has too many properties", MaxFields(1), 2, description='A guide.'
            ),
        ), 'the limit, the number of fields written and the root description are carried'

    def test_validate_with_another_rule_over_the_block_returns_a_block_problem_without_a_typed_limit(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'not': {'required': ['name']}}
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'name': 'guide'}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            BlockProblem(
                "{'name': 'guide'} should not be valid under {'required': ['name']}", OtherBlockConstraint(), 1
            ),
        ), "a keyword with no typed constraint keeps the validator's wording"

    def test_validate_with_a_key_propertynames_rejects_returns_an_invalid_value_problem_on_the_key(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'propertyNames': {'pattern': '^[a-z]+$'}}
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'name': 'guide', 'B_': 2}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            InvalidValueProblem('B_', "'B_' does not match '^[a-z]+$'", PatternMismatch('^[a-z]+$')),
        ), 'a key the names rule rejects names a field, so it is not a problem of the whole block'

    def test_validate_with_a_missing_dependency_returns_an_invalid_value_problem_on_the_field(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'dependentRequired': {'status': ['owner', 'date']}}
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'status': 'draft', 'owner': 'me'}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            InvalidValueProblem('status', "'date' is a dependency of 'status'", OtherValueConstraint()),
        ), 'the field that needs another is the one at fault, and a dependency present is not reported'

    def test_validate_with_a_missing_field_the_schema_describes_returns_its_guidance(self) -> None:
        #: Given
        schema: dict[str, object] = {
            'type': 'object',
            'required': ['type', 'name'],
            'properties': {
                'type': {'enum': ['rule', 'pattern'], 'description': 'The kind of document.'},
                'name': {'type': 'string', 'examples': ['setup', 'install']},
            },
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            MissingFieldProblem(
                'type',
                "'type' is a required property",
                guidance=FieldGuidance(description='The kind of document.', allowed=('rule', 'pattern')),
            ),
            MissingFieldProblem('name', "'name' is a required property", guidance=FieldGuidance(example='setup')),
        ), 'the description, the values allowed and the first example come from the property'

    def test_validate_with_a_required_field_in_a_branch_returns_it_without_guidance(self) -> None:
        #: Given
        schema: dict[str, object] = {
            'type': 'object',
            'properties': {'status': {'type': 'string'}, 'owner': {'description': 'Who maintains it.'}},
            'if': {'properties': {'status': {'const': 'stable'}}, 'required': ['status']},
            'then': {'required': ['owner']},
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'status': 'stable'}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (MissingFieldProblem('owner', "'owner' is a required property"),), (
            "a branch's `required` sits in a schema without `properties`, so the property is not read"
        )

    def test_validate_with_a_value_of_one_of_several_types_returns_every_type_expected(self) -> None:
        #: Given
        schema: dict[str, object] = {'type': 'object', 'properties': {'tags': {'type': ['string', 'null']}}}
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'tags': True}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            WrongTypeProblem(
                'tags', "True is not of type 'string', 'null'", (JsonType.STRING, JsonType.NULL), JsonType.BOOLEAN
            ),
        ), 'a boolean is not an integer, and every type the schema accepts is expected'

    def test_validate_with_a_number_found_returns_the_number_type(self) -> None:
        #: Given
        schema: dict[str, object] = {
            'type': 'object',
            'properties': {'version': {'type': 'string', 'description': 'The version.'}},
        }
        frontmatter = FrontmatterSchema(path=SPEC_PATH, schema=FrozenMapping.from_plain(schema))
        data: dict[str, object] = {'version': 1.5}

        #: When
        problems = frontmatter.validate(FrozenMapping.from_plain(data))

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
