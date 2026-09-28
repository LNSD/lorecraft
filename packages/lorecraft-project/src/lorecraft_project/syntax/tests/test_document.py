"""Parsing a document's text into its parse tree: where the frontmatter block is found, and where it is not.

``parse_document`` is pure, so every case here is a text literal. The Markdown parser behind it decides what
counts as a block; these pin the rules the checks report against.
"""

import pytest

from ..document import parse_document
from ..frontmatter import Frontmatter, FrontmatterKey, InvalidYamlFrontmatter, MissingFrontmatter
from ..position import LineNumber


@pytest.mark.unit
class TestParseDocument:
    def test_parse_document_with_a_delimited_block_returns_its_frontmatter(self) -> None:
        #: Given
        text = '---\nname: guide\ntype: rule\n---\n# Guide\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.frontmatter == Frontmatter(
            data={'name': 'guide', 'type': 'rule'},
            keys=(FrontmatterKey('name', LineNumber(2)), FrontmatterKey('type', LineNumber(3))),
        ), 'the block between the delimiters is decoded, each key on its document line'

    def test_parse_document_with_trailing_whitespace_on_the_delimiters_returns_its_frontmatter(self) -> None:
        #: Given
        text = '---  \nname: guide\n--- \n'

        #: When
        document = parse_document(text)

        #: Then
        assert isinstance(document.frontmatter, Frontmatter), (
            f'a delimiter may carry trailing whitespace, got {document.frontmatter!r}'
        )

    def test_parse_document_with_crlf_line_endings_returns_each_key_on_its_document_line(self) -> None:
        #: Given
        text = '---\r\nname: guide\r\ntype: rule\r\n---\r\n# Guide\r\n'

        #: When
        document = parse_document(text)

        #: Then
        assert isinstance(document.frontmatter, Frontmatter), f'a CRLF block is found, got {document.frontmatter!r}'
        assert document.frontmatter.keys == (
            FrontmatterKey('name', LineNumber(2)),
            FrontmatterKey('type', LineNumber(3)),
        ), 'a CRLF line ending counts as one line break'

    def test_parse_document_with_invalid_yaml_returns_invalid_yaml_frontmatter(self) -> None:
        #: Given
        text = '---\nname: [unclosed\n---\n# Guide\n'

        #: When
        document = parse_document(text)

        #: Then
        assert isinstance(document.frontmatter, InvalidYamlFrontmatter), (
            f'a block that is not YAML is a value, not a failed parse, got {document.frontmatter!r}'
        )

    def test_parse_document_without_an_opening_delimiter_returns_missing(self) -> None:
        #: Given
        text = '# Guide\n\nname: guide\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.frontmatter == MissingFrontmatter(), 'a document not opening with `---` has no frontmatter'

    def test_parse_document_with_a_block_after_the_first_line_returns_missing(self) -> None:
        #: Given
        text = '\n---\nname: guide\n---\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.frontmatter == MissingFrontmatter(), 'the opening delimiter must be the first line'

    def test_parse_document_with_an_indented_opening_delimiter_returns_missing(self) -> None:
        #: Given
        text = '  ---\nname: guide\n---\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.frontmatter == MissingFrontmatter(), 'a delimiter allows no leading whitespace'

    def test_parse_document_without_a_closing_delimiter_returns_missing(self) -> None:
        #: Given
        text = '---\nname: guide\n'

        #: When
        document = parse_document(text)

        #: Then
        assert document.frontmatter == MissingFrontmatter(), 'an unclosed block is not frontmatter'
