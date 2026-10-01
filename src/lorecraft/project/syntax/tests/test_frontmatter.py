"""Decoding the YAML of a frontmatter block into its node: every outcome and the line of each key.

``decode_frontmatter`` is pure and takes the lines between the delimiters, so every case here is a block
literal whose first line is document line 2. Finding the block in a document is covered in ``test_document``.
"""

import sys

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

    def test_decode_frontmatter_with_a_key_repeated_with_the_same_value_lists_every_occurrence(self) -> None:
        #: Given
        block = 'name: guide\ntype: rule\nname: guide\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a mapping that repeats a key is still frontmatter, got {node!r}'
        assert node.keys == (
            FrontmatterKey('name', LineNumber(2)),
            FrontmatterKey('type', LineNumber(3)),
            FrontmatterKey('name', LineNumber(4)),
        ), 'a key written twice is listed once per occurrence, in document order'

    def test_decode_frontmatter_with_a_key_repeated_with_another_value_keeps_the_last_value(self) -> None:
        #: Given
        block = 'name: guide\ntype: rule\nname: other\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == Frontmatter(
            data={'name': 'other', 'type': 'rule'},
            keys=(
                FrontmatterKey('name', LineNumber(2)),
                FrontmatterKey('type', LineNumber(3)),
                FrontmatterKey('name', LineNumber(4)),
            ),
        ), 'the data holds the value of the last occurrence, and the keys list every occurrence'

    def test_decode_frontmatter_with_an_equals_key_lists_it_on_its_document_line(self) -> None:
        #: Given
        block = 'name: guide\n=: 1\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == Frontmatter(
            data={'name': 'guide', '=': 1},
            keys=(
                FrontmatterKey('name', LineNumber(2)),
                FrontmatterKey('=', LineNumber(3)),
            ),
        ), 'a plain `=` key, which YAML tags as a value key, decodes to a string key and is listed with its line'

    def test_decode_frontmatter_with_an_equals_key_repeated_lists_every_occurrence(self) -> None:
        #: Given
        block = '=: a\n=: b\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == Frontmatter(
            data={'=': 'b'},
            keys=(
                FrontmatterKey('=', LineNumber(2)),
                FrontmatterKey('=', LineNumber(3)),
            ),
        ), 'a `=` key written twice is listed once per occurrence, like any other key'

    def test_decode_frontmatter_with_a_key_repeated_under_the_value_tag_lists_both_and_finds_the_last(self) -> None:
        #: Given
        block = 'name: wrong\n!!value name: guide\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a mapping that repeats a key is still frontmatter, got {node!r}'
        assert node.data == {'name': 'guide'}, 'the key tagged `!!value` decodes to the same string, and its value wins'
        assert node.keys == (
            FrontmatterKey('name', LineNumber(2)),
            FrontmatterKey('name', LineNumber(3)),
        ), 'a key tagged `!!value` is listed as the string it decodes to'
        assert node.key_line('name') == LineNumber(3), 'the line of the key is the one whose value the data holds'

    def test_decode_frontmatter_with_a_merge_overriding_a_written_key_lists_only_the_written_keys(self) -> None:
        #: Given
        block = 'name: review\ndescription: d\n<<: {name: other, license: MIT}\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == Frontmatter(
            data={'name': 'review', 'license': 'MIT', 'description': 'd'},
            keys=(
                FrontmatterKey('name', LineNumber(2)),
                FrontmatterKey('description', LineNumber(3)),
            ),
        ), 'the keys are the ones the mapping writes, in document order; the data holds the merge as PyYAML gives it'

    def test_decode_frontmatter_with_a_merge_through_an_alias_lists_only_the_written_keys(self) -> None:
        #: Given
        block = 'base: &b\n  name: x\n<<: *b\nname: review\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a mapping with a merge is still frontmatter, got {node!r}'
        assert node.keys == (
            FrontmatterKey('base', LineNumber(2)),
            FrontmatterKey('name', LineNumber(5)),
        ), 'neither the merge key nor the keys it brings in are listed, only the ones the mapping writes'

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

    def test_decode_frontmatter_with_an_escape_beyond_unicode_returns_invalid_yaml_on_the_escapes_line(
        self,
    ) -> None:
        #: Given
        # the quoted scalar starts on line 3 and its escape, above U+10FFFF, sits on line 4
        block = 'name: guide\ndescription: "a guide\n  \\UFFFFFFFF"\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found an escape sequence that names no Unicode character', line=LineNumber(4)
        ), 'an escape that names no character is a finding on its own line, not a crash'

    def test_decode_frontmatter_with_an_escape_just_beyond_unicode_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        # the first code point above U+10FFFF, which fits a C int, unlike `\UFFFFFFFF`
        block = 'name: guide\ndescription: "\\U00110000"\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found an escape sequence that names no Unicode character', line=LineNumber(3)
        ), 'an escape one above the last code point is a finding on its line, not a crash'

    def test_decode_frontmatter_with_a_yaml_version_too_long_to_read_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        # one digit more than the interpreter converts to an int, read from it rather than assumed to be 4300
        digits = '1' * (sys.get_int_max_str_digits() + 1)
        block = f'%YAML 1.{digits}\nname: guide\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a YAML version number too long to read', line=LineNumber(2)
        ), 'a version number too long to read is a finding on the directive line, not a crash'

    def test_decode_frontmatter_with_flow_collections_nested_too_deeply_returns_invalid_yaml_with_no_line(
        self,
    ) -> None:
        #: Given
        # the composer spends at least one frame per level, so as many levels as the recursion limit always
        # exhaust the stack, whatever the limit is
        depth = sys.getrecursionlimit()
        block = f'name: guide\ndescription: {"[" * depth}{"]" * depth}\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(problem='found collections nested too deeply to parse', line=None), (
            'flow collections nested past the stack are a finding with no line, not a crash'
        )

    def test_decode_frontmatter_with_block_mappings_nested_too_deeply_returns_invalid_yaml_with_no_line(
        self,
    ) -> None:
        #: Given
        # the composer spends at least one frame per level, so as many levels as the recursion limit always
        # exhaust the stack, whatever the limit is
        depth = sys.getrecursionlimit()
        block = 'name: guide\n' + ''.join(f'{" " * level}nested:\n' for level in range(depth)) + f'{" " * depth}a: b\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(problem='found collections nested too deeply to parse', line=None), (
            'block mappings nested past the stack are a finding with no line, not a crash'
        )

    def test_decode_frontmatter_with_an_int_tagged_value_that_is_not_an_int_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = 'name: guide\ncount: !!int many\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="could not construct a value for the tag 'tag:yaml.org,2002:int'", line=LineNumber(3)
        ), 'a value the int tag cannot construct is a finding on its line, not a crash'

    def test_decode_frontmatter_with_an_int_tagged_key_that_is_not_an_int_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = 'name: guide\n!!int count: 1\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="could not construct a value for the tag 'tag:yaml.org,2002:int'", line=LineNumber(3)
        ), 'a key the int tag cannot construct is a finding on its line, not a crash'

    def test_decode_frontmatter_with_an_empty_int_tagged_value_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\ncount: !!int ""\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="could not construct a value for the tag 'tag:yaml.org,2002:int'", line=LineNumber(3)
        ), 'empty text under the int tag is a finding on its line, not a crash'

    def test_decode_frontmatter_with_a_bool_tagged_value_that_is_not_a_bool_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = 'name: guide\ndraft: !!bool maybe\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="could not construct a value for the tag 'tag:yaml.org,2002:bool'", line=LineNumber(3)
        ), 'a value the bool tag cannot construct is a finding on its line, not a crash'

    def test_decode_frontmatter_with_a_bool_tagged_key_that_is_not_a_bool_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = 'name: guide\n!!bool draft: true\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="could not construct a value for the tag 'tag:yaml.org,2002:bool'", line=LineNumber(3)
        ), 'a key the bool tag cannot construct is a finding on its line, not a crash'

    def test_decode_frontmatter_with_a_float_tagged_value_that_is_not_a_float_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = 'name: guide\nweight: !!float heavy\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="could not construct a value for the tag 'tag:yaml.org,2002:float'", line=LineNumber(3)
        ), 'a value the float tag cannot construct is a finding on its line, not a crash'

    def test_decode_frontmatter_with_a_float_tagged_key_that_is_not_a_float_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = 'name: guide\n!!float weight: 1.5\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="could not construct a value for the tag 'tag:yaml.org,2002:float'", line=LineNumber(3)
        ), 'a key the float tag cannot construct is a finding on its line, not a crash'

    def test_decode_frontmatter_with_a_timestamp_tagged_value_that_is_not_a_date_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = 'name: guide\ncreated: !!timestamp yesterday\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="could not construct a value for the tag 'tag:yaml.org,2002:timestamp'", line=LineNumber(3)
        ), 'a value the timestamp tag cannot construct is a finding on its line, not a crash'

    def test_decode_frontmatter_with_a_timestamp_tagged_key_that_is_not_a_date_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = 'name: guide\n!!timestamp created: 2024-01-01\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="could not construct a value for the tag 'tag:yaml.org,2002:timestamp'", line=LineNumber(3)
        ), 'a key the timestamp tag cannot construct is a finding on its line, not a crash'

    def test_decode_frontmatter_with_a_timestamp_tagged_mapping_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\ncreated: !!timestamp {=: 2024-01-01}\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="could not construct a value for the tag 'tag:yaml.org,2002:timestamp'", line=LineNumber(3)
        ), 'a mapping under the timestamp tag, read through its `=` key, is a finding on its line, not a crash'

    def test_decode_frontmatter_with_an_untagged_date_out_of_range_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\ncreated: 2024-13-01\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="could not construct a value for the tag 'tag:yaml.org,2002:timestamp'", line=LineNumber(3)
        ), 'a plain scalar YAML reads as a date, with no such month, is a finding on its line, not a crash'

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

    def test_key_line_with_a_repeated_key_returns_the_line_of_its_last_occurrence(self) -> None:
        #: Given
        frontmatter = Frontmatter(
            data={'name': 'other'},
            keys=(FrontmatterKey('name', LineNumber(2)), FrontmatterKey('name', LineNumber(5))),
        )

        #: When
        line = frontmatter.key_line('name')

        #: Then
        assert line == LineNumber(5), f'the last occurrence is the one whose value the data holds, got {line}'

    def test_key_line_with_an_absent_key_returns_none(self) -> None:
        #: Given
        frontmatter = Frontmatter(data={'type': 'rule'}, keys=(FrontmatterKey('type', LineNumber(3)),))

        #: When
        line = frontmatter.key_line('name')

        #: Then
        assert line is None, f'an absent key has no line, got {line}'
