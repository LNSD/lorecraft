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
from lorecraft.core.path import PathComponent, RootRelativePath

from ..name import SpecName, parse_spec_name
from ..section_name import PaddedSectionNameError, SectionName
from ..spec_file import SpecFileType, StructureSpecFile, spec_filename
from ..structure import (
    AnySections,
    CharCappedTitleChecks,
    FrontmatterSchema,
    PatternedTitleChecks,
    SectionEntry,
    StructureSchema,
    StructureSpec,
    StructureSpecProblem,
    TitlePattern,
    WordCappedTitleChecks,
)
from ..structure_failure import (
    AdjacentAnyRuns,
    EmptyStructureSpec,
    ForbiddenOutlineSections,
    ForeignFrontmatterDialect,
    FrontmatterSchemaId,
    InvalidFrontmatterSchema,
    InvalidTitlePattern,
    RepeatedForbiddenSections,
    RepeatedOutlineSections,
    UndecodableStructureSpec,
    UntypedFrontmatterSchema,
)

SPECS_DIR: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__')
SPEC_NAME: Final[SpecName] = parse_spec_name('code')
SPEC_PATH: Final[RootRelativePath] = SPECS_DIR / PathComponent.parse(
    spec_filename(SPEC_NAME, SpecFileType.LEGACY_STRUCTURE)
)
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


def _parse_usable(schema: StructureSchema) -> StructureSpec:
    """The structure specification a test's text states, which must be usable.

    Args:
        schema: The text of a structure specification a test states as usable.
    """
    parsed = StructureSpec.parse(SPEC_FILE, schema)
    assert isinstance(parsed, StructureSpec), f'the test states a usable specification, got {parsed!r}'
    return parsed


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
        structure_spec = _parse_usable(schema)

        #: Then
        assert structure_spec == StructureSpec(
            file=SPEC_FILE,
            title=WordCappedTitleChecks(words=NonZeroUnsignedInt(8), chars=NonZeroUnsignedInt(60)),
            forbid_empty_sections=True,
            outline=(
                AnySections(words=NonZeroUnsignedInt(350)),
                SectionEntry(name=SectionName('Checklist'), words=NonZeroUnsignedInt(250)),
                SectionEntry(name=SectionName('References'), optional=True),
            ),
            forbidden=(SectionName('Changelog'),),
            tokens=NonZeroUnsignedInt(5000),
            frontmatter=FrontmatterSchema(schema=FrozenMapping.from_plain({'type': 'object', 'required': ['name']})),
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
        structure_spec = _parse_usable(schema)

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
        structure_spec = _parse_usable(schema)

        #: Then
        assert structure_spec.outline == (
            SectionEntry(name=SectionName('Checklist'), description=None, examples=()),
        ), f'both keys are optional, and absent they state nothing, got {structure_spec.outline!r}'

    def test_parse_with_an_empty_section_description_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "description": ""}]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'an empty description would print empty help, so it is refused'
        )

    def test_parse_with_an_empty_list_of_section_examples_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "examples": []}]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'no examples are written by leaving the key out, so `[]` is refused'
        )

    def test_parse_with_an_empty_section_example_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema(
            json.dumps({'outline': [{'section': 'Checklist', 'examples': [LOGGING_CHECKLIST, '']}]})
        )

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'an empty example would print a heading alone, so it is refused'
        )

    def test_parse_with_a_section_description_that_is_not_a_string_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema(
            json.dumps({'outline': [{'section': 'Checklist', 'description': [CHECKLIST_DESCRIPTION]}]})
        )

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'a description is one string of text, not a list of lines'

    def test_parse_with_section_examples_given_as_one_string_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema(json.dumps({'outline': [{'section': 'Checklist', 'examples': LOGGING_CHECKLIST}]}))

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'examples are a list, so one bare string is refused'

    def test_parse_with_a_section_example_that_is_not_a_string_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "examples": [3]}]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'the file is read strictly, so a number is not an example'

    def test_parse_with_a_description_on_an_any_run_returns_undecodable_structure_spec(self) -> None:
        #: Given
        # a run can never be missing, so nothing would ever report what it holds
        schema = StructureSchema('{"outline": [{"any": true, "description": "The document\'s own sections."}]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'only a named section takes a description'

    def test_parse_with_examples_on_an_any_run_returns_undecodable_structure_spec(self) -> None:
        #: Given
        # a run can never be missing, so nothing would ever report an example of it
        schema = StructureSchema(json.dumps({'outline': [{'any': True, 'examples': [LOGGING_CHECKLIST]}]}))

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'only a named section takes examples'

    def test_parse_with_only_a_frontmatter_schema_returns_a_structure_spec_with_that_schema(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"type": "object"}}')

        #: When
        structure_spec = _parse_usable(schema)

        #: Then
        assert structure_spec.frontmatter == FrontmatterSchema(schema=FrozenMapping.from_plain({'type': 'object'})), (
            'a frontmatter schema is a rule, so a file stating only it is usable'
        )

    def test_parse_with_a_nested_frontmatter_schema_holds_it_frozen_all_the_way_down(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"type": "object", "properties": {"tags": {"enum": [["a"]]}}}}')

        #: When
        structure_spec = _parse_usable(schema)

        #: Then
        assert structure_spec.frontmatter is not None, 'the file states a frontmatter schema'
        assert structure_spec.frontmatter.schema == FrozenMapping(
            {'type': 'object', 'properties': FrozenMapping({'tags': FrozenMapping({'enum': (('a',),)})})}
        ), 'every object in the schema is a frozen mapping and every array a tuple, at any depth'

    def test_parse_with_a_frontmatter_schema_returns_a_hashable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"type": "object", "required": ["name"]}}')

        #: When
        structure_spec = _parse_usable(schema)

        #: Then
        assert isinstance(hash(structure_spec), int), 'a structure specification holding a frontmatter schema hashes'

    def test_parse_with_a_malformed_frontmatter_schema_returns_invalid_frontmatter_schema(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"type": "object", "minProperties": -1}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert failure == InvalidFrontmatterSchema('-1 is less than the minimum of 0'), (
            f'the failure carries what the meta-schema rejected, got {failure!r}'
        )

    def test_parse_with_a_bad_title_pattern_and_a_untyped_frontmatter_schema_returns_the_title_failure(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"pattern": "^(unclosed"}, "frontmatter": {"type": "string"}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, InvalidTitlePattern), f'the title is checked before the frontmatter, got {failure!r}'

    def test_parse_with_a_frontmatter_id_and_a_repeated_outline_section_returns_the_frontmatter_failure(self) -> None:
        #: Given
        schema = StructureSchema(
            '{"frontmatter": {"$id": "x", "type": "object"}, "outline": [{"section": "Usage"}, {"section": "Usage"}]}'
        )

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert failure == FrontmatterSchemaId(), (
            f'the frontmatter schema is checked before the outline rules, got {failure!r}'
        )

    def test_parse_with_a_frontmatter_schema_without_an_object_type_returns_untyped_frontmatter_schema(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"required": ["name"]}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert failure == UntypedFrontmatterSchema(), 'the object type is stated, not implied'

    def test_parse_with_a_frontmatter_value_that_is_not_an_object_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": true}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'a boolean schema is refused by the shape'

    def test_parse_with_a_null_frontmatter_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 100, "frontmatter": null}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'the editor refuses null too; no rule is written by leaving the key out'
        )
        assert any('frontmatter' in str(problem) for problem in failure.problems), (
            f'a problem names the key that may not be null, got {failure.problems}'
        )

    def test_parse_with_a_frontmatter_schema_carrying_an_id_returns_frontmatter_schema_id(self) -> None:
        #: Given
        schema = StructureSchema('{"frontmatter": {"$id": "https://example.com/code", "type": "object"}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert failure == FrontmatterSchemaId(), 'the editor lets an $id through, the load refuses it'

    def test_parse_with_a_frontmatter_schema_in_a_foreign_dialect_returns_foreign_frontmatter_dialect(self) -> None:
        #: Given
        schema = StructureSchema(
            '{"frontmatter": {"$schema": "http://json-schema.org/draft-07/schema#", "type": "object"}}'
        )

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert failure == ForeignFrontmatterDialect('http://json-schema.org/draft-07/schema#'), (
            f'the failure carries the dialect the schema names, got {failure!r}'
        )

    def test_parse_with_only_a_token_budget_returns_a_structure_spec_with_that_budget(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 4000}')

        #: When
        structure_spec = _parse_usable(schema)

        #: Then
        assert structure_spec.tokens == NonZeroUnsignedInt(4000), (
            'a token budget is a rule, so a file stating only it is usable'
        )

    def test_parse_with_a_token_budget_of_zero_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 0}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'no document satisfies a budget of 0 tokens'
        assert failure.problems == (StructureSpecProblem(('tokens',), 'must be at least 1, got 0'),), (
            f'the problem names the field and reads with the count rejection, got {failure.problems}'
        )

    def test_parse_with_a_document_word_cap_returns_undecodable_structure_spec(self) -> None:
        #: Given
        # words are capped per section only; the document as a whole has a token budget instead
        schema = StructureSchema('{"words": 1800}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'a top-level `words` is not a field, so it is refused, not ignored'
        )

    def test_parse_with_a_section_word_cap_of_zero_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "words": 0}]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'no section satisfies a cap of 0 words'
        assert (
            StructureSpecProblem(('outline', 0, 'StructureFileSection', 'words'), 'must be at least 1, got 0')
            in failure.problems
        ), f'the section shape reports the cap with the count rejection, got {failure.problems}'

    def test_parse_with_an_any_word_cap_of_zero_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"any": true, "words": 0}]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'no section in a run satisfies a cap of 0 words'

    def test_parse_with_a_string_word_cap_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "words": "250"}]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'the file is read strictly, so a string is not a word cap'

    def test_parse_with_a_fractional_token_budget_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 5000.5}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'a token budget is a whole number of tokens'

    def test_parse_with_a_boolean_section_word_cap_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist", "words": true}]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'a JSON boolean is not a word cap, though Python treats it as one'
        )

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
        structure_spec = _parse_usable(schema)

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

    def test_parse_with_a_schema_reference_that_is_not_a_string_returns_undecodable_structure_spec(self) -> None:
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
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'the shape refuses it with the problem it found'

    def test_parse_with_text_that_is_not_json_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema(
            dedent(
                """
                {
                """
            )
        )

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'text that is not JSON is refused at the edge, with the problem the decoder found'
        )

    def test_parse_with_only_a_title_word_cap_returns_a_structure_spec_with_that_cap(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"words": 8}}')

        #: When
        structure_spec = _parse_usable(schema)

        #: Then
        assert structure_spec.title == WordCappedTitleChecks(words=NonZeroUnsignedInt(8)), (
            'a cap on the title is a rule, so a file stating only it is usable'
        )

    def test_parse_with_a_title_word_cap_of_zero_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"words": 0}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'no title satisfies a cap of 0 words'
        assert failure.problems == (StructureSpecProblem(('title', 'words'), 'must be at least 1, got 0'),), (
            f'the problem names the cap and reads with the count rejection, got {failure.problems}'
        )

    def test_parse_with_a_negative_title_word_cap_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"words": -3}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'a word cap is a count of words, never below 1'
        assert len(failure.problems) == 1, f'one field is wrong, got {failure.problems}'
        assert str(failure.problems[0]).startswith('title.words: '), (
            f'the problem opens with the dotted path of the cap, got {failure.problems[0]!r}'
        )

    def test_parse_with_a_boolean_title_word_cap_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"words": true}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'a JSON boolean is not a word cap, though Python treats it as one'
        )
        assert len(failure.problems) == 1, f'one field is wrong, got {failure.problems}'
        assert str(failure.problems[0]).startswith('title.words: '), (
            f'the problem opens with the dotted path of the cap, got {failure.problems[0]!r}'
        )

    def test_parse_with_only_a_title_character_cap_returns_a_structure_spec_with_that_cap(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"chars": 60}}')

        #: When
        structure_spec = _parse_usable(schema)

        #: Then
        assert structure_spec.title == CharCappedTitleChecks(chars=NonZeroUnsignedInt(60)), (
            "a cap on the title's characters is a rule, so a file stating only it is usable"
        )

    def test_parse_with_a_title_character_cap_of_zero_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"chars": 0}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'no title satisfies a cap of 0 characters'
        assert failure.problems == (StructureSpecProblem(('title', 'chars'), 'must be at least 1, got 0'),), (
            f'the problem names the cap and reads with the count rejection, got {failure.problems}'
        )

    def test_parse_with_a_negative_title_character_cap_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"chars": -3}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'a character cap is a count of characters, never below 1'
        assert len(failure.problems) == 1, f'one field is wrong, got {failure.problems}'
        assert str(failure.problems[0]).startswith('title.chars: '), (
            f'the problem opens with the dotted path of the cap, got {failure.problems[0]!r}'
        )

    def test_parse_with_a_boolean_title_character_cap_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"chars": true}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'a JSON boolean is not a character cap, though Python treats it as one'
        )
        assert len(failure.problems) == 1, f'one field is wrong, got {failure.problems}'
        assert str(failure.problems[0]).startswith('title.chars: '), (
            f'the problem opens with the dotted path of the cap, got {failure.problems[0]!r}'
        )

    def test_parse_with_an_empty_title_returns_undecodable_structure_spec(self) -> None:
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
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'a `title` stating no check would state nothing'
        assert failure.problems == (
            StructureSpecProblem(('title',), 'Value error, states no check; leave the key out for no title check'),
        ), f'the problem names the key and says how to state no title check, got {failure.problems}'

    def test_parse_with_only_a_title_pattern_returns_a_structure_spec_with_that_pattern_compiled(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"pattern": "^[A-Z]"}}')

        #: When
        structure_spec = _parse_usable(schema)

        #: Then
        assert structure_spec.title == PatternedTitleChecks(pattern=TitlePattern(re.compile('^[A-Z]'))), (
            'a pattern on the title is a rule, so a file stating only it is usable, and it is held compiled'
        )

    def test_parse_with_a_title_word_cap_and_pattern_returns_a_structure_spec_with_both(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"words": 8, "pattern": "^[A-Z]"}}')

        #: When
        structure_spec = _parse_usable(schema)

        #: Then
        assert structure_spec.title == PatternedTitleChecks(
            pattern=TitlePattern(re.compile('^[A-Z]')), words=NonZeroUnsignedInt(8)
        ), 'a cap and a pattern are independent, and the title carries both'

    def test_parse_with_a_title_pattern_that_does_not_compile_returns_invalid_title_pattern(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"pattern": "^(unclosed"}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, InvalidTitlePattern), 'a pattern that does not compile is no title check'
        assert failure.pattern == '^(unclosed', 'the failure carries the pattern as written'
        assert failure.problem, 'the failure carries what the compiler rejected'

    def test_parse_with_a_non_string_title_pattern_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"pattern": 3}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'a JSON number is not a pattern'
        assert failure.problems == (StructureSpecProblem(('title', 'pattern'), 'Input should be a valid string'),), (
            f'the problem names the pattern with the type rejection, got {failure.problems}'
        )

    def test_parse_with_an_empty_title_pattern_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"pattern": ""}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'an empty pattern matches every title, so it would check nothing'
        )
        assert failure.problems == (
            StructureSpecProblem(('title', 'pattern'), 'String should have at least 1 character'),
        ), f'the problem names the pattern with the length rejection, got {failure.problems}'

    def test_parse_with_an_unknown_key_in_the_title_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"title": {"words": 8, "count": 1}}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'a misspelt or removed title check is an error, not ignored'
        )
        assert len(failure.problems) == 1, f'one key is wrong, got {failure.problems}'
        assert str(failure.problems[0]).startswith('title.count: '), (
            f'the problem opens with the dotted path of the unknown key, got {failure.problems[0]!r}'
        )

    def test_parse_with_a_string_for_a_boolean_returns_undecodable_structure_spec(self) -> None:
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
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'the file is read strictly, so no value is coerced into another type'
        )

    def test_parse_with_an_unknown_field_returns_undecodable_structure_spec(self) -> None:
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
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'the shape refuses it with the problem it found'

    def test_parse_with_a_spec_field_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"spec": "code.md", "forbidden": ["Changelog"]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'the prose is named by the filename, so `spec` is not a field'
        )

    def test_parse_with_an_empty_sections_value_other_than_forbidden_returns_undecodable_structure_spec(
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
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), '"forbidden" is the only value `empty_sections` takes'

    def test_parse_with_two_wrong_fields_returns_one_problem_each(self) -> None:
        #: Given
        schema = StructureSchema('{"tokens": 0, "empty_sections": "allowed"}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), f'the text does not decode, got {failure!r}'
        assert len(failure.problems) == 2, f'each wrong field is its own problem, got {failure.problems}'
        assert str(failure.problems[0]).startswith('tokens: '), (
            f'the first problem opens with the dotted path of its field, got {failure.problems[0]!r}'
        )
        assert str(failure.problems[1]).startswith('empty_sections: '), (
            f'the second problem names its field, got {failure.problems[1]!r}'
        )

    def test_parse_with_an_outline_entry_of_neither_shape_returns_undecodable_structure_spec(self) -> None:
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
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            'an outline entry is a section or an `any` run, nothing else'
        )

    def test_parse_with_a_forbidden_entry_that_is_not_a_string_returns_undecodable_structure_spec(self) -> None:
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
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), '`forbidden` holds section names only'

    def test_parse_with_a_padded_section_name_returns_undecodable_structure_spec(self) -> None:
        #: Given
        # a heading's text never has whitespace at either end, so no document could hold this section
        schema = StructureSchema('{"outline": [{"section": " Checklist"}]}')
        expected = StructureSpecProblem(
            ('outline', 0, 'StructureFileSection', 'section'), str(PaddedSectionNameError(' Checklist'))
        )

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), (
            "the mistake is the specification's, so the load refuses it"
        )
        assert expected in failure.problems, (
            f'the section shape reports the name with its rejection, got {failure.problems}'
        )

    def test_parse_with_an_empty_section_name_returns_undecodable_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": ""}]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), 'an empty name matches only a heading with no text'

    def test_parse_with_a_padded_forbidden_entry_returns_undecodable_structure_spec(self) -> None:
        #: Given
        # a forbidden name no heading can carry would forbid nothing, silently
        schema = StructureSchema('{"forbidden": ["Changelog "]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert isinstance(failure, UndecodableStructureSpec), f'the text does not decode, got {failure!r}'
        assert failure.problems == (
            StructureSpecProblem(('forbidden', 0), str(PaddedSectionNameError('Changelog '))),
        ), f'the problem names the entry and reads with the name rejection, got {failure.problems}'

    def test_parse_with_a_forbidden_entry_given_twice_returns_repeated_forbidden_sections(self) -> None:
        #: Given
        schema = StructureSchema('{"forbidden": ["Changelog", "Changelog"]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert failure == RepeatedForbiddenSections((SectionName('Changelog'),)), (
            f'the shape lets a repeated entry through, the rules refuse it naming it once, got {failure!r}'
        )

    def test_parse_without_any_rule_returns_empty_structure_spec(self) -> None:
        #: Given
        schema = StructureSchema('{}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert failure == EmptyStructureSpec(), 'a specification stating no rule would check nothing'

    def test_parse_with_a_section_named_twice_returns_repeated_outline_sections(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"section": "Checklist"}, {"section": "Checklist", "optional": true}]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert failure == RepeatedOutlineSections((SectionName('Checklist'),)), (
            f'a name fixes one position, so it cannot be given two, got {failure!r}'
        )

    def test_parse_forbidding_a_section_twice_among_others_returns_only_the_repeated_name(self) -> None:
        #: Given
        schema = StructureSchema('{"forbidden": ["Changelog", "History", "Changelog"]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert failure == RepeatedForbiddenSections((SectionName('Changelog'),)), (
            f'a second entry would report every forbidden section twice, got {failure!r}'
        )

    def test_parse_forbidding_a_section_its_outline_names_returns_forbidden_outline_sections(self) -> None:
        #: Given
        schema = StructureSchema(
            '{"outline": [{"section": "Checklist", "optional": true}], "forbidden": ["Checklist"]}'
        )

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert failure == ForbiddenOutlineSections((SectionName('Checklist'),)), (
            f'a section cannot be both placed and forbidden, got {failure!r}'
        )

    def test_parse_with_two_adjacent_any_runs_returns_adjacent_any_runs(self) -> None:
        #: Given
        schema = StructureSchema('{"outline": [{"any": true}, {"any": true}, {"section": "Checklist"}]}')

        #: When
        failure = StructureSpec.parse(SPEC_FILE, schema)

        #: Then
        assert failure == AdjacentAnyRuns(), (
            f'two runs side by side match as one, so the outline misleads, got {failure!r}'
        )


@pytest.mark.unit
class TestTitlePattern:
    def test_parse_with_a_pattern_that_compiles_returns_it_compiled(self) -> None:
        #: Given
        text = '^[A-Z]'

        #: When
        pattern = TitlePattern.parse(text)

        #: Then
        assert pattern == TitlePattern(re.compile(text)), f'the pattern is held compiled, got {pattern!r}'

    def test_parse_with_a_pattern_that_does_not_compile_returns_invalid_title_pattern(self) -> None:
        #: Given
        text = '^(unclosed'

        #: When
        failure = TitlePattern.parse(text)

        #: Then
        assert failure == InvalidTitlePattern(text, 'missing ), unterminated subpattern'), (
            f'the failure carries the pattern exactly as written and what the compiler rejected, got {failure!r}'
        )

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
        file = StructureSpecFile(
            path=SPECS_DIR / PathComponent.parse(spec_filename(name, SpecFileType.LEGACY_STRUCTURE)), name=name
        )

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


class TestStructureSpecProblem:
    def test_str_with_a_location_joins_its_parts_with_dots_before_the_message(self) -> None:
        #: Given
        problem = StructureSpecProblem(('outline', 0, 'StructureFileSection', 'words'), 'must be at least 1, got 0')

        #: When
        text = str(problem)

        #: Then
        assert text == 'outline.0.StructureFileSection.words: must be at least 1, got 0', (
            'the location reads as a dotted path, indexes included'
        )

    def test_str_without_a_location_is_the_bare_message(self) -> None:
        #: Given
        problem = StructureSpecProblem((), 'Invalid JSON: EOF while parsing a value')

        #: When
        text = str(problem)

        #: Then
        assert text == 'Invalid JSON: EOF while parsing a value', 'a problem about the whole file has no path to show'
