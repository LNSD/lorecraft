"""Header validation over a document's frontmatter node.

``validate_header`` is pure, so every case here is a text literal parsed in memory, a filename, a corpus and
an in-memory header schema; no document and no schema file is read.
"""

from typing import Final

import pytest

from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.layout import SPECS_DIR
from lorecraft.project.schemas import HeaderAspect, HeaderSchema
from lorecraft.project.syntax import LineNumber, parse_frontmatter

from ..header import validate_header

GUIDE: Final[AspectFilename] = AspectFilename.parse('guide')
CODE: Final[CorpusName] = CorpusName.parse('code')


def _code_header(schema: dict[str, object]) -> HeaderAspect:
    """The ``code`` corpus header aspect, as the loader would build it from ``docs/__meta__/code.header.json``."""
    return HeaderAspect(path=SPECS_DIR / 'code.header.json', schema=HeaderSchema(schema))


@pytest.mark.unit
class TestValidateHeader:
    def test_validate_header_with_conforming_frontmatter_returns_no_findings(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\ntype: rule\n---\n# Guide\n')
        schemas = (_code_header({'type': 'object', 'required': ['type']}),)

        #: When
        result = validate_header(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (), 'a document matching its name and schema is clean'

    def test_validate_header_with_empty_schemas_returns_no_findings(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('no frontmatter at all\n')
        schemas: tuple[HeaderAspect, ...] = ()

        #: When
        result = validate_header(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert result.violations == (), 'an ungoverned document is never checked, whatever its text'

    def test_validate_header_with_name_mismatch_reports_name_rule_on_the_name_line(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\ntype: rule\nname: other\n---\n')
        schemas = (_code_header({'type': 'object'}),)

        #: When
        result = validate_header(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert [violation.rule for violation in result.violations] == ['frontmatter.name-matches-filename'], (
            'the frontmatter name must equal the filename stem'
        )
        assert result.violations[0].line == LineNumber(3), (
            f'the violation points at the name key, got line {result.violations[0].line}'
        )

    def test_validate_header_without_frontmatter_block_reports_missing(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('# Guide\n\nname: guide\n')
        schemas = (_code_header({'type': 'object'}),)

        #: When
        result = validate_header(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert [violation.rule for violation in result.violations] == ['frontmatter.missing'], (
            'a document without a delimited block has one missing-frontmatter violation'
        )
        assert result.violations[0].line == LineNumber(1), 'a missing block is reported on line 1'

    def test_validate_header_with_invalid_yaml_reports_unparseable(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: [unclosed\n---\n')
        schemas = (_code_header({'type': 'object'}),)

        #: When
        result = validate_header(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert [violation.rule for violation in result.violations] == ['frontmatter.unparseable'], (
            'YAML that does not parse is one unparseable violation'
        )
        assert result.violations[0].message.startswith('frontmatter is not valid YAML'), 'the message names the cause'

    def test_validate_header_with_non_mapping_yaml_reports_unparseable(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\n- guide\n---\n')
        schemas = (_code_header({'type': 'object'}),)

        #: When
        result = validate_header(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert [violation.rule for violation in result.violations] == ['frontmatter.unparseable'], (
            'a YAML list is not a frontmatter mapping'
        )
        assert result.violations[0].message == 'frontmatter is not a YAML mapping', 'the message names the shape'

    def test_validate_header_with_missing_required_field_reports_it_under_the_corpus_with_the_schema(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: guide\n---\n')
        schemas = (_code_header({'type': 'object', 'required': ['type']}),)

        #: When
        result = validate_header(schemas, frontmatter=frontmatter, filename=GUIDE, corpus=CODE)

        #: Then
        assert [violation.rule for violation in result.violations] == ['code.type'], (
            'a required field is reported under the corpus namespace and the field name'
        )
        assert result.violations[0].message.endswith('(per docs/__meta__/code.header.json)'), (
            'the violation names the schema that required the field'
        )
        assert result.violations[0].line == LineNumber(1), 'an absent field is reported on line 1'
