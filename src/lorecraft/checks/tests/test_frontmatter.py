"""Frontmatter validation over a document's frontmatter node.

``validate_frontmatter`` is pure, so every case here is a text literal parsed in memory, a filename, a corpus and
an in-memory frontmatter schema; no document and no specification file is read.
"""

from typing import Final

import pytest

from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.layout import SPECS_DIR
from lorecraft.project.schemas import FrontmatterSchema
from lorecraft.project.syntax import LineNumber, parse_frontmatter

from ..frontmatter import validate_frontmatter
from ..reporting import Violation

GUIDE: Final[AspectFilename] = AspectFilename.parse('guide')
CODE: Final[CorpusName] = CorpusName.parse('code')


def _code_frontmatter(schema: dict[str, object]) -> FrontmatterSchema:
    """The `code` corpus frontmatter schema.

    Built as the loader would build it from the `frontmatter` key of `docs/__meta__/code.structure.json`.

    Args:
        schema: The JSON Schema the frontmatter is validated against, as it appears under that key.
    """
    return FrontmatterSchema(path=SPECS_DIR / 'code.structure.json', schema=schema)


@pytest.mark.unit
class TestValidateFrontmatter:
    def test_validate_frontmatter_with_conforming_frontmatter_returns_no_findings(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\ntype: rule\n---\n# Guide\n')
        schemas = (_code_frontmatter({'type': 'object', 'required': ['type']}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (), 'a document matching its name and schema is clean'

    def test_validate_frontmatter_with_empty_schemas_returns_no_findings(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('no frontmatter at all\n')
        schemas: tuple[FrontmatterSchema, ...] = ()

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (), 'an ungoverned document is never checked, whatever its text'

    def test_validate_frontmatter_with_name_mismatch_reports_name_rule_on_the_name_line(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\ntype: rule\nname: other\n---\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert [violation.rule for violation in result.violations] == ['frontmatter.name-matches-filename'], (
            'the frontmatter name must equal the filename stem'
        )
        assert result.violations[0].line == LineNumber(3), (
            f'the violation points at the name key, got line {result.violations[0].line}'
        )

    def test_validate_frontmatter_without_frontmatter_block_reports_missing(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('# Guide\n\nname: guide\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert [violation.rule for violation in result.violations] == ['frontmatter.missing'], (
            'a document without a delimited block has one missing-frontmatter violation'
        )
        assert result.violations[0].line == LineNumber(1), 'a missing block is reported on line 1'

    def test_validate_frontmatter_with_invalid_yaml_reports_unparseable(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: [unclosed\n---\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert [violation.rule for violation in result.violations] == ['frontmatter.unparseable'], (
            'YAML that does not parse is one unparseable violation'
        )
        assert result.violations[0].message.startswith('frontmatter is not valid YAML'), 'the message names the cause'
        assert result.violations[0].line == LineNumber(3), 'the violation sits on the line the parser stopped at'

    def test_validate_frontmatter_with_a_tagged_value_its_tag_cannot_construct_reports_unparseable(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\ncount: !!int many\n---\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
                rule='frontmatter.unparseable',
                message=(
                    "frontmatter is not valid YAML: could not construct a value for the tag 'tag:yaml.org,2002:int'"
                ),
            ),
        ), 'a scalar its tag cannot construct is one unparseable violation on its line, not a crash'

    def test_validate_frontmatter_with_non_mapping_yaml_reports_unparseable(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\n- guide\n---\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(line=LineNumber(1), rule='frontmatter.unparseable', message='frontmatter is not a YAML mapping'),
        ), 'a YAML list is not a frontmatter mapping, reported on the line the block opens'

    def test_validate_frontmatter_with_missing_required_field_reports_it_under_the_corpus_with_the_schema(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\n---\n')
        schemas = (_code_frontmatter({'type': 'object', 'required': ['type']}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert [violation.rule for violation in result.violations] == ['code.type'], (
            'a required field is reported under the corpus namespace and the field name'
        )
        assert result.violations[0].message.endswith('(per docs/__meta__/code.structure.json)'), (
            'the violation names the schema that required the field'
        )
        assert result.violations[0].line == LineNumber(1), 'an absent field is reported on line 1'

    def test_validate_frontmatter_with_a_field_the_schema_does_not_allow_reports_it_unknown_on_its_line(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\nmodel: opus\n---\n')
        schemas = (_code_frontmatter({'type': 'object', 'properties': {'name': {}}, 'additionalProperties': False}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert [(violation.line, violation.rule) for violation in result.violations] == [
            (LineNumber(3), 'code.unknown-field')
        ], 'a field the schema does not allow is reported on its own line, as the skill check reports one'

    def test_validate_frontmatter_with_a_name_mismatch_and_a_schema_problem_reports_the_name_first(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: other\n---\n')
        schemas = (_code_frontmatter({'type': 'object', 'required': ['type']}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert [violation.message for violation in result.violations] == [
            "`name` is 'other'; expected 'guide', the document's filename",
            "'type' is a required property (per docs/__meta__/code.structure.json)",
        ], 'the name is compared before the schemas are applied, as in the skill check'

    def test_validate_frontmatter_with_a_key_repeated_with_the_same_value_reports_the_repetition(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\ntype: rule\nname: guide\n---\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='frontmatter.duplicate-key',
                message="'name' is already written on line 2",
            ),
        ), 'a key written twice is a finding on the repeated line, even when both values agree'

    def test_validate_frontmatter_with_a_key_repeated_with_another_value_reports_the_repetition(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\ntype: rule\ntype: pattern\n---\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='frontmatter.duplicate-key',
                message="'type' is already written on line 3",
            ),
        ), 'a key written twice with another value is a finding on the line whose value is kept'

    def test_validate_frontmatter_with_a_key_written_three_times_points_each_repetition_at_the_first(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\nname: guide\nname: guide\n---\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
                rule='frontmatter.duplicate-key',
                message="'name' is already written on line 2",
            ),
            Violation(
                line=LineNumber(4),
                rule='frontmatter.duplicate-key',
                message="'name' is already written on line 2",
            ),
        ), 'each later occurrence is its own finding, and each names the line of the first'

    def test_validate_frontmatter_with_the_wrong_name_written_last_reports_it_on_the_last_line(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\ntype: rule\nname: other\n---\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='frontmatter.name-matches-filename',
                message="`name` is 'other'; expected 'guide', the document's filename",
            ),
            Violation(
                line=LineNumber(4),
                rule='frontmatter.duplicate-key',
                message="'name' is already written on line 2",
            ),
        ), 'the name the decoder kept is judged on the line it is written on, and the repetition is reported last'

    def test_validate_frontmatter_with_the_right_name_written_last_reports_only_the_repetition(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: other\ntype: rule\nname: guide\n---\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='frontmatter.duplicate-key',
                message="'name' is already written on line 2",
            ),
        ), 'the decoder kept the right name, so the overwritten wrong one is reported only as a repetition'

    def test_validate_frontmatter_with_a_bad_value_written_last_reports_it_on_the_last_line(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\ntype: rule\ntype: bad\n---\n')
        schemas = (_code_frontmatter({'type': 'object', 'properties': {'type': {'enum': ['rule', 'pattern']}}}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='code.type',
                message="'bad' is not one of ['rule', 'pattern'] (per docs/__meta__/code.structure.json)",
                spec=SPECS_DIR / 'code.structure.json',
            ),
            Violation(
                line=LineNumber(4),
                rule='frontmatter.duplicate-key',
                message="'type' is already written on line 3",
            ),
        ), 'the schema judges the value the decoder kept, on the line it is written on, before the repetition'

    def test_validate_frontmatter_with_a_good_value_written_last_reports_only_the_repetition(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\ntype: bad\ntype: rule\n---\n')
        schemas = (_code_frontmatter({'type': 'object', 'properties': {'type': {'enum': ['rule', 'pattern']}}}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='frontmatter.duplicate-key',
                message="'type' is already written on line 3",
            ),
        ), 'the decoder kept the good value, so the overwritten bad one is reported only as a repetition'

    def test_validate_frontmatter_with_an_unknown_key_repeated_reports_it_on_the_last_line(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\nmodel: a\nmodel: b\n---\n')
        schemas = (
            _code_frontmatter(
                {
                    'type': 'object',
                    'properties': {'name': {}, 'type': {}},
                    'additionalProperties': False,
                }
            ),
        )

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='code.unknown-field',
                message=(
                    "Additional properties are not allowed ('model' was unexpected) "
                    '(per docs/__meta__/code.structure.json)'
                ),
                spec=SPECS_DIR / 'code.structure.json',
            ),
            Violation(
                line=LineNumber(4),
                rule='frontmatter.duplicate-key',
                message="'model' is already written on line 3",
            ),
        ), 'an unknown key written twice is reported once, on its last line, before the repetition'

    def test_validate_frontmatter_with_a_merge_overriding_a_written_key_reports_no_repetition(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\ntype: rule\n<<: {name: other}\n---\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (), 'a key a merge supplies is not written twice, and the written name wins'

    def test_validate_frontmatter_with_a_repeated_lone_surrogate_key_reports_it_escaped(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\n"\\ud83d": a\n"\\ud83d": b\n---\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='frontmatter.duplicate-key',
                message="'\\ud83d' is already written on line 3",
            ),
        ), 'a key no terminal can print is named by its escape, so the message can be written out'

    def test_validate_frontmatter_with_a_repeated_key_holding_a_newline_reports_it_on_one_line(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\n"a\\nb": 1\n"a\\nb": 2\n---\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(4),
                rule='frontmatter.duplicate-key',
                message="'a\\nb' is already written on line 3",
            ),
        ), 'a newline in the key is printed as its escape, so the finding stays on one line'

    def test_validate_frontmatter_with_a_field_only_a_merge_supplies_reports_it_on_line_1(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\nbase: &b\n  type: bad\n<<: *b\n---\n')
        schemas = (_code_frontmatter({'type': 'object', 'properties': {'type': {'enum': ['rule', 'pattern']}}}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(1),
                rule='code.type',
                message="'bad' is not one of ['rule', 'pattern'] (per docs/__meta__/code.structure.json)",
                spec=SPECS_DIR / 'code.structure.json',
            ),
        ), 'a field written only inside a merged mapping has no top-level line, so it is reported on line 1'

    def test_validate_frontmatter_with_an_unknown_equals_key_reports_it_on_its_own_line(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\n=: 1\n---\n')
        schemas = (_code_frontmatter({'type': 'object', 'properties': {'name': {}}, 'additionalProperties': False}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
                rule='code.unknown-field',
                message=(
                    "Additional properties are not allowed ('=' was unexpected) (per docs/__meta__/code.structure.json)"
                ),
                spec=SPECS_DIR / 'code.structure.json',
            ),
        ), 'a plain `=` key, which YAML tags as a value key, is still reported on the line it is written on'
