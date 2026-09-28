"""Header validation over a document's parse tree.

``validate_header`` is pure, so every case here is a text literal parsed in memory, a ref and an in-memory
header schema; no document and no schema file is read.
"""

from typing import Final

import pytest

from lorecraft_project.aspect import AspectFilename
from lorecraft_project.corpus import CorpusName
from lorecraft_project.document import DocumentRef
from lorecraft_project.layout import SPECS_DIR
from lorecraft_project.schemas import HeaderAspect, HeaderSchema
from lorecraft_project.syntax import LineNumber, parse_document
from lorecraft_vfs import RootRelativePath

from ..header import validate_header

GUIDE: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('guide'))


def _code_header(schema: dict[str, object]) -> HeaderAspect:
    """The ``code`` corpus header aspect, as the loader would build it from ``docs/__meta__/code.header.json``."""
    return HeaderAspect(path=SPECS_DIR / 'code.header.json', schema=HeaderSchema(schema))


@pytest.mark.unit
class TestValidateHeader:
    def test_validate_header_with_conforming_frontmatter_returns_no_findings(self) -> None:
        #: Given
        document = parse_document('---\nname: guide\ntype: rule\n---\n# Guide\n')
        schemas = (_code_header({'type': 'object', 'required': ['type']}),)

        #: When
        result = validate_header(document, GUIDE, schemas)

        #: Then
        assert result.findings == (), 'a document matching its name and schema is clean'

    def test_validate_header_with_empty_schemas_returns_no_findings(self) -> None:
        #: Given
        document = parse_document('no frontmatter at all\n')
        schemas: tuple[HeaderAspect, ...] = ()

        #: When
        result = validate_header(document, GUIDE, schemas)

        #: Then
        assert result.findings == (), 'an ungoverned document is never checked, whatever its text'

    def test_validate_header_with_name_mismatch_reports_name_rule_on_the_name_line(self) -> None:
        #: Given
        document = parse_document('---\ntype: rule\nname: other\n---\n')
        schemas = (_code_header({'type': 'object'}),)

        #: When
        result = validate_header(document, GUIDE, schemas)

        #: Then
        assert [finding.rule for finding in result.findings] == ['frontmatter.name-matches-filename'], (
            'the frontmatter name must equal the filename stem'
        )
        assert result.findings[0].line == LineNumber(3), (
            f'the finding points at the name key, got line {result.findings[0].line}'
        )
        assert result.findings[0].path == RootRelativePath.parse('docs/code/guide.md'), (
            'the finding reports the root-relative path'
        )

    def test_validate_header_without_frontmatter_block_reports_missing(self) -> None:
        #: Given
        document = parse_document('# Guide\n\nname: guide\n')
        schemas = (_code_header({'type': 'object'}),)

        #: When
        result = validate_header(document, GUIDE, schemas)

        #: Then
        assert [finding.rule for finding in result.findings] == ['frontmatter.missing'], (
            'a document without a delimited block has one missing-frontmatter finding'
        )
        assert result.findings[0].line == LineNumber(1), 'a missing block is reported on line 1'

    def test_validate_header_with_invalid_yaml_reports_unparseable(self) -> None:
        #: Given
        document = parse_document('---\nname: [unclosed\n---\n')
        schemas = (_code_header({'type': 'object'}),)

        #: When
        result = validate_header(document, GUIDE, schemas)

        #: Then
        assert [finding.rule for finding in result.findings] == ['frontmatter.unparseable'], (
            'YAML that does not parse is one unparseable finding'
        )
        assert result.findings[0].message.startswith('frontmatter is not valid YAML'), 'the message names the cause'

    def test_validate_header_with_non_mapping_yaml_reports_unparseable(self) -> None:
        #: Given
        document = parse_document('---\n- guide\n---\n')
        schemas = (_code_header({'type': 'object'}),)

        #: When
        result = validate_header(document, GUIDE, schemas)

        #: Then
        assert [finding.rule for finding in result.findings] == ['frontmatter.unparseable'], (
            'a YAML list is not a frontmatter mapping'
        )
        assert result.findings[0].message == 'frontmatter is not a YAML mapping', 'the message names the shape'

    def test_validate_header_with_missing_required_field_reports_it_under_the_corpus_with_the_schema(self) -> None:
        #: Given
        document = parse_document('---\nname: guide\n---\n')
        schemas = (_code_header({'type': 'object', 'required': ['type']}),)

        #: When
        result = validate_header(document, GUIDE, schemas)

        #: Then
        assert [finding.rule for finding in result.findings] == ['code.type'], (
            'a required field is reported under the corpus namespace and the field name'
        )
        assert result.findings[0].message.endswith('(per docs/__meta__/code.header.json)'), (
            'the finding names the schema that required the field'
        )
        assert result.findings[0].line == LineNumber(1), 'an absent field is reported on line 1'
