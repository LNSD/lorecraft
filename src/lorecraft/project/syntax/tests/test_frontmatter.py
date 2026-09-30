"""Decoding the YAML of a frontmatter block into its node: every outcome and the line of each key.

``decode_frontmatter`` is pure and takes the lines between the delimiters, so every case here is a block
literal whose first line is document line 2. Finding the block in a document is covered in ``test_document``.
"""

import pytest

from ..frontmatter import (
    Frontmatter,
    FrontmatterKey,
    InvalidYamlFrontmatter,
    NonMappingFrontmatter,
    decode_frontmatter,
)
from ..position import LineNumber


@pytest.mark.unit
class TestDecodeFrontmatter:
    def test_decode_frontmatter_with_a_mapping_returns_its_data(self) -> None:
        #: Given
        block = 'name: guide\ntype: rule\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == {'name': 'guide', 'type': 'rule'}, 'the data is the decoded mapping'

    def test_decode_frontmatter_with_a_mapping_returns_each_key_on_its_document_line(self) -> None:
        #: Given
        block = 'name: guide\n\ntype: rule\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.keys == (
            FrontmatterKey('name', LineNumber(2)),
            FrontmatterKey('type', LineNumber(4)),
        ), 'each key carries its document line, counting the opening delimiter as line 1'

    def test_decode_frontmatter_with_crlf_line_endings_returns_each_key_on_its_document_line(self) -> None:
        #: Given
        block = 'name: guide\r\ntype: rule\r\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.keys == (
            FrontmatterKey('name', LineNumber(2)),
            FrontmatterKey('type', LineNumber(3)),
        ), 'a CRLF line ending counts as one line break'

    def test_decode_frontmatter_with_quoted_keys_returns_each_key_by_its_decoded_name(self) -> None:
        #: Given
        block = '"name": guide\n\'type\': rule\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.keys == (
            FrontmatterKey('name', LineNumber(2)),
            FrontmatterKey('type', LineNumber(3)),
        ), 'a quoted key is found by the name YAML decodes it to, whatever the quotes'

    def test_decode_frontmatter_with_a_non_string_key_leaves_it_out_of_the_keys(self) -> None:
        #: Given
        block = '1: one\nname: guide\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.keys == (FrontmatterKey('name', LineNumber(3)),), 'only keys written as strings are listed'

    def test_decode_frontmatter_with_invalid_yaml_returns_the_parsers_problem_and_line(self) -> None:
        #: Given
        block = 'name: [unclosed\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="expected ',' or ']', but got '<stream end>'", line=LineNumber(3)
        ), 'the parser names the problem, and the document line it stopped on follows the opening delimiter'

    def test_decode_frontmatter_with_a_control_character_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: a\x00b\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(problem='special characters are not allowed', line=LineNumber(2)), (
            'a character the reader refuses is a finding on its line, not a crash'
        )

    def test_decode_frontmatter_with_a_yaml_list_returns_non_mapping(self) -> None:
        #: Given
        block = '- guide\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == NonMappingFrontmatter(), f'a YAML list is not a frontmatter mapping, got {node!r}'

    def test_decode_frontmatter_with_an_empty_block_returns_non_mapping(self) -> None:
        #: Given
        block = ''

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == NonMappingFrontmatter(), f'an empty block decodes to nothing, not a mapping, got {node!r}'


@pytest.mark.unit
class TestFrontmatterKeyLine:
    def test_key_line_with_a_present_key_returns_its_line(self) -> None:
        #: Given
        frontmatter = Frontmatter(data={'type': 'rule'}, keys=(FrontmatterKey('type', LineNumber(3)),))

        #: When
        line = frontmatter.key_line('type')

        #: Then
        assert line == LineNumber(3), f'the type key is on line 3, got {line}'

    def test_key_line_with_an_absent_key_returns_none(self) -> None:
        #: Given
        frontmatter = Frontmatter(data={'type': 'rule'}, keys=(FrontmatterKey('type', LineNumber(3)),))

        #: When
        line = frontmatter.key_line('name')

        #: Then
        assert line is None, f'an absent key has no line, got {line}'
