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

GUIDE: Final[AspectFilename] = AspectFilename.parse('guide')
CODE: Final[CorpusName] = CorpusName.parse('code')


def _code_frontmatter(schema: dict[str, object]) -> FrontmatterSchema:
    """The ``code`` corpus frontmatter schema, as the loader would build it from the ``frontmatter`` key of
    ``docs/__meta__/code.structure.json``."""
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

    def test_validate_frontmatter_with_non_mapping_yaml_reports_unparseable(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\n- guide\n---\n')
        schemas = (_code_frontmatter({'type': 'object'}),)

        #: When
        result = validate_frontmatter(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert [violation.rule for violation in result.violations] == ['frontmatter.unparseable'], (
            'a YAML list is not a frontmatter mapping'
        )
        assert result.violations[0].message == 'frontmatter is not a YAML mapping', 'the message names the shape'

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
