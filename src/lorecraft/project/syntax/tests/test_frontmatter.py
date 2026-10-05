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
            FrontmatterKey('name', LineNumber.from_int(2)),
            FrontmatterKey('type', LineNumber.from_int(4)),
        ), 'each key carries its document line, counting the opening delimiter as line 1'

    def test_decode_frontmatter_with_crlf_line_endings_returns_each_key_on_its_document_line(self) -> None:
        #: Given
        block = 'name: guide\r\ntype: rule\r\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.keys == (
            FrontmatterKey('name', LineNumber.from_int(2)),
            FrontmatterKey('type', LineNumber.from_int(3)),
        ), 'a CRLF line ending counts as one line break'

    def test_decode_frontmatter_with_quoted_keys_returns_each_key_by_its_decoded_name(self) -> None:
        #: Given
        block = '"name": guide\n\'type\': rule\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.keys == (
            FrontmatterKey('name', LineNumber.from_int(2)),
            FrontmatterKey('type', LineNumber.from_int(3)),
        ), 'a quoted key is found by the name YAML decodes it to, whatever the quotes'

    def test_decode_frontmatter_with_an_int_key_returns_invalid_yaml_naming_it_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\n1: one\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the key 1, which is not a string', line=LineNumber.from_int(3)
        ), 'a key YAML reads as an int is refused on its line, named as written'

    def test_decode_frontmatter_with_a_bool_key_returns_invalid_yaml_naming_it_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\ntrue: yes\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the key true, which is not a string', line=LineNumber.from_int(3)
        ), 'a key YAML reads as a bool is refused on its line, named as written'

    def test_decode_frontmatter_with_a_null_key_returns_invalid_yaml_naming_it_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\nnull: nothing\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the key null, which is not a string', line=LineNumber.from_int(3)
        ), 'a key YAML reads as null is refused on its line, named as written'

    def test_decode_frontmatter_with_an_empty_key_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\n?\n: nothing\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a key that is not a string', line=LineNumber.from_int(3)
        ), 'a key written as nothing is null, and has no text to name'

    def test_decode_frontmatter_with_a_date_key_returns_it_as_a_string_key(self) -> None:
        #: Given
        block = 'name: guide\n2026-10-04: launch\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == Frontmatter(
            data={'name': 'guide', '2026-10-04': 'launch'},
            keys=(
                FrontmatterKey('name', LineNumber.from_int(2)),
                FrontmatterKey('2026-10-04', LineNumber.from_int(3)),
            ),
        ), 'a date is no scalar of the core schema, so a key written as one is a string like any other'

    def test_decode_frontmatter_with_a_non_string_key_in_a_list_item_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\ntags:\n  - label: a\n    2: b\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the key 2, which is not a string', line=LineNumber.from_int(5)
        ), 'a key nested inside a list item is refused like a top-level one, on its own line'

    def test_decode_frontmatter_with_a_non_string_key_in_a_flow_mapping_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\nmeta: {owner: me, 3.5: x}\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the key 3.5, which is not a string', line=LineNumber.from_int(3)
        ), 'a key of a flow mapping is refused like a block one'

    def test_decode_frontmatter_with_a_list_written_as_a_key_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\n[a, b]: x\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a key that is not a string', line=LineNumber.from_int(3)
        ), 'a key written as a list is no string, and has no one piece of text to name'

    def test_decode_frontmatter_with_a_quoted_numeric_key_returns_it_as_a_string_key(self) -> None:
        #: Given
        block = "name: guide\n'1': one\n"

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == Frontmatter(
            data={'name': 'guide', '1': 'one'},
            keys=(FrontmatterKey('name', LineNumber.from_int(2)), FrontmatterKey('1', LineNumber.from_int(3))),
        ), 'a quoted key is a string whatever its text, so it is a field like any other'

    def test_decode_frontmatter_with_a_key_repeated_with_the_same_value_lists_every_occurrence(self) -> None:
        #: Given
        block = 'name: guide\ntype: rule\nname: guide\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a mapping that repeats a key is still frontmatter, got {node!r}'
        assert node.keys == (
            FrontmatterKey('name', LineNumber.from_int(2)),
            FrontmatterKey('type', LineNumber.from_int(3)),
            FrontmatterKey('name', LineNumber.from_int(4)),
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
                FrontmatterKey('name', LineNumber.from_int(2)),
                FrontmatterKey('type', LineNumber.from_int(3)),
                FrontmatterKey('name', LineNumber.from_int(4)),
            ),
        ), 'the data holds the value of the last occurrence, and the keys list every occurrence'

    def test_decode_frontmatter_with_an_equals_key_returns_it_as_a_string_key(self) -> None:
        #: Given
        block = 'name: guide\n=: 1\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == Frontmatter(
            data={'name': 'guide', '=': 1},
            keys=(
                FrontmatterKey('name', LineNumber.from_int(2)),
                FrontmatterKey('=', LineNumber.from_int(3)),
            ),
        ), 'a plain `=` key means nothing special, so it is a string key listed with its line'

    def test_decode_frontmatter_with_a_merge_key_returns_it_as_a_string_key(self) -> None:
        #: Given
        block = 'name: review\n<<: {license: MIT}\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == Frontmatter(
            data={'name': 'review', '<<': {'license': 'MIT'}},
            keys=(
                FrontmatterKey('name', LineNumber.from_int(2)),
                FrontmatterKey('<<', LineNumber.from_int(3)),
            ),
        ), 'a plain `<<` merges nothing, so it is a string key holding its value, left to the schema to judge'

    def test_decode_frontmatter_with_an_anchor_on_a_scalar_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'type: rule\nname: &name guide\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the anchor &name, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'frontmatter is basic YAML, so an anchor is a finding on its line'

    def test_decode_frontmatter_with_a_list_anchored_to_hold_itself_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        # the anchored list names itself through its alias, which `yaml.safe_load` decodes to a list holding itself
        block = 'see: &loop [*loop]\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the anchor &loop, which frontmatter does not allow', line=LineNumber.from_int(2)
        ), 'the anchor is refused before its alias is read, so no value can hold itself'

    def test_decode_frontmatter_with_an_alias_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\nsee: *guide\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the alias *guide, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'frontmatter is basic YAML, so an alias is a finding on its line'

    def test_decode_frontmatter_with_a_str_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\ndescription: !!str 2024-01-01\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!str', which frontmatter does not allow",
            line=LineNumber.from_int(3),
        ), 'a scalar tag is refused like any other, even one naming a type YAML resolves unaided'

    def test_decode_frontmatter_with_a_pairs_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\nsteps: !!pairs [first: 1, second: 2]\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!pairs', which frontmatter does not allow",
            line=LineNumber.from_int(3),
        ), 'a pairs tag, which builds tuples JSON has no counterpart for, is a finding on its line'

    def test_decode_frontmatter_with_an_omap_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\nsteps: !!omap [first: 1, second: 2]\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!omap', which frontmatter does not allow",
            line=LineNumber.from_int(3),
        ), 'an omap tag, which builds tuples JSON has no counterpart for, is a finding on its line'

    def test_decode_frontmatter_with_a_set_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        # YAML writes a set as a mapping whose keys have no values, so without the refusal the node is a mapping
        # but the value is not
        block = '!!set\n? guide\n? rule\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!set', which frontmatter does not allow",
            line=LineNumber.from_int(2),
        ), 'a set tag, which builds a set JSON has no counterpart for, is a finding on its line'

    def test_decode_frontmatter_with_a_binary_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\nicon: !!binary aGk=\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!binary', which frontmatter does not allow",
            line=LineNumber.from_int(3),
        ), 'a binary tag, which builds bytes JSON has no counterpart for, is a finding on its line'

    def test_decode_frontmatter_with_a_local_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\nowner: !team docs\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!team', which frontmatter does not allow", line=LineNumber.from_int(3)
        ), 'a local tag is a finding on its line, not a construction failure'

    def test_decode_frontmatter_with_a_verbatim_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\nowner: !<tag:example.com,2026:team> docs\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!<tag:example.com,2026:team>', which frontmatter does not allow",
            line=LineNumber.from_int(3),
        ), 'a verbatim tag is a finding on its line, not a construction failure'

    def test_decode_frontmatter_with_the_non_specific_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\ncount: ! 3\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!', which frontmatter does not allow", line=LineNumber.from_int(3)
        ), 'the non-specific tag `!`, which makes a plain scalar a string, is refused like any other'

    def test_decode_frontmatter_with_a_tag_on_a_key_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'type: rule\n!!str name: guide\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!str', which frontmatter does not allow",
            line=LineNumber.from_int(3),
        ), 'a tag on a key is refused as one on a value is'

    def test_decode_frontmatter_with_a_tag_nested_in_a_list_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\ntags:\n  - docs\n  - !!int 3\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!int', which frontmatter does not allow",
            line=LineNumber.from_int(5),
        ), 'a tag at any depth is refused, on the line of the item that carries it'

    def test_decode_frontmatter_with_invalid_yaml_returns_the_parsers_problem_and_line(self) -> None:
        #: Given
        block = 'name: [unclosed\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="expected ',' or ']', but got '<stream end>'", line=LineNumber.from_int(3)
        ), 'the parser names the problem, and the document line it stopped on follows the opening delimiter'

    def test_decode_frontmatter_with_a_control_character_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: a\x00b\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='special characters are not allowed', line=LineNumber.from_int(2)
        ), 'a character the reader refuses is a finding on its line, not a crash'

    def test_decode_frontmatter_with_a_control_character_after_a_blank_line_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        # the block opens with a blank line, so the control character sits on document line 3
        block = '\nname: a\x00b\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='special characters are not allowed', line=LineNumber.from_int(3)
        ), 'the line counts every line break before the refused character'

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
            problem='found an escape sequence that names no Unicode character', line=LineNumber.from_int(4)
        ), 'an escape that names no character is a finding on its own line, not a crash'

    def test_decode_frontmatter_with_an_escape_just_beyond_unicode_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        # the first code point above U+10FFFF, which fits a C int, unlike `\UFFFFFFFF`
        block = 'name: guide\ndescription: "\\U00110000"\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found an escape sequence that names no Unicode character', line=LineNumber.from_int(3)
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
            problem='found a YAML version number too long to read', line=LineNumber.from_int(2)
        ), 'a version number too long to read is a finding on the directive line, not a crash'

    def test_decode_frontmatter_with_flow_collections_nested_too_deeply_returns_invalid_yaml_with_no_line(
        self,
    ) -> None:
        #: Given
        # reading spends at least one frame per level, so as many levels as the recursion limit always
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
        # reading spends at least one frame per level, so as many levels as the recursion limit always
        # exhaust the stack, whatever the limit is
        depth = sys.getrecursionlimit()
        block = 'name: guide\n' + ''.join(f'{" " * level}nested:\n' for level in range(depth)) + f'{" " * depth}a: b\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(problem='found collections nested too deeply to parse', line=None), (
            'block mappings nested past the stack are a finding with no line, not a crash'
        )

    def test_decode_frontmatter_with_an_integer_too_long_to_read_returns_it_as_a_string(self) -> None:
        #: Given
        # one digit more than the interpreter converts to an int, read from it rather than assumed to be 4300
        digits = '1' * (sys.get_int_max_str_digits() + 1)
        block = f'name: guide\ncount: {digits}\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == {'name': 'guide', 'count': digits}, (
            'an integer with more digits than Python converts stays its text, rather than failing the block'
        )

    def test_decode_frontmatter_with_a_float_too_large_returns_it_as_a_string(self) -> None:
        #: Given
        block = 'name: guide\nweight: 1e999\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == {'name': 'guide', 'weight': '1e999'}, (
            'a float past what Python holds would be infinity, which JSON has no number for, so it stays its text'
        )

    def test_decode_frontmatter_with_core_schema_scalars_returns_their_json_values(self) -> None:
        #: Given
        block = 'a: ~\nb: null\nc:\nd: true\ne: FALSE\nf: 12\ng: -012\nh: 0o12\ni: 0x1F\nj: -1.5\nk: 1e3\nl: .5\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == {
            'a': None,
            'b': None,
            'c': None,
            'd': True,
            'e': False,
            'f': 12,
            'g': -12,
            'h': 10,
            'i': 31,
            'j': -1.5,
            'k': 1000.0,
            'l': 0.5,
        }, 'a plain scalar the core schema reads as null, a bool, an int or a float decodes to that value'

    def test_decode_frontmatter_with_scalars_only_yaml_1_1_resolves_returns_them_as_strings(self) -> None:
        #: Given
        block = 'a: yes\nb: on\nc: 2026-10-05\nd: 1:30\ne: 0b101\nf: 1_000\ng: .inf\nh: .nan\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == {
            'a': 'yes',
            'b': 'on',
            'c': '2026-10-05',
            'd': '1:30',
            'e': '0b101',
            'f': '1_000',
            'g': '.inf',
            'h': '.nan',
        }, 'a plain scalar the core schema does not read as null, a bool or a JSON number is a string'

    def test_decode_frontmatter_with_quoted_and_block_scalars_returns_them_as_strings(self) -> None:
        #: Given
        block = 'a: "12"\nb: \'true\'\nc: |\n  12\nd: >\n  null\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == {'a': '12', 'b': 'true', 'c': '12\n', 'd': 'null\n'}, (
            'only a plain scalar is resolved; a quoted or block scalar is its text, whatever it reads like'
        )

    def test_decode_frontmatter_with_a_second_document_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        # a `---` line with content after it starts a document without closing the block, as a bare one would
        block = 'name: guide\n--- type: rule\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a second document, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'a block holds one document, so a second is a finding on the line that starts it'

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
class TestFrontmatterFindKeyLine:
    def test_find_key_line_with_a_present_key_returns_its_line(self) -> None:
        #: Given
        frontmatter = Frontmatter(data={'type': 'rule'}, keys=(FrontmatterKey('type', LineNumber.from_int(3)),))

        #: When
        line = frontmatter.find_key_line('type')

        #: Then
        assert line == LineNumber.from_int(3), f'the type key is on line 3, got {line}'

    def test_find_key_line_with_a_repeated_key_returns_the_line_of_its_last_occurrence(self) -> None:
        #: Given
        frontmatter = Frontmatter(
            data={'name': 'other'},
            keys=(FrontmatterKey('name', LineNumber.from_int(2)), FrontmatterKey('name', LineNumber.from_int(5))),
        )

        #: When
        line = frontmatter.find_key_line('name')

        #: Then
        assert line == LineNumber.from_int(5), f'the last occurrence is the one whose value the data holds, got {line}'

    def test_find_key_line_with_an_absent_key_returns_none(self) -> None:
        #: Given
        frontmatter = Frontmatter(data={'type': 'rule'}, keys=(FrontmatterKey('type', LineNumber.from_int(3)),))

        #: When
        line = frontmatter.find_key_line('name')

        #: Then
        assert line is None, f'an absent key has no line, got {line}'
