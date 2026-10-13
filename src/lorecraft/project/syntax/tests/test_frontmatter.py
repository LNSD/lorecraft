"""Decoding the YAML of a frontmatter block into its node: every outcome and the line of each key.

``decode_frontmatter`` is pure and takes the lines between the delimiters, so every case here is a block
literal whose first line is document line 2. Finding the block in a document is covered in ``test_document``.
"""

import sys
from textwrap import dedent

import pytest

from lorecraft.core.mapping import FrozenMapping

from ..frontmatter import (
    Frontmatter,
    FrontmatterKey,
    InvalidYamlFrontmatter,
    NonMappingFrontmatter,
    RepeatedKey,
    decode_frontmatter,
    reads_back_as_string,
)
from ..position import LineNumber


@pytest.mark.unit
class TestDecodeFrontmatter:
    def test_decode_frontmatter_with_a_mapping_returns_its_data(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            type: rule
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping({'name': 'guide', 'type': 'rule'}), 'the data is the decoded mapping'

    def test_decode_frontmatter_with_a_mapping_returns_each_key_on_its_document_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide

            type: rule
            """)

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
        block = dedent("""\
            "name": guide
            'type': rule
            """)

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
        block = dedent("""\
            name: guide
            1: one
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the non-string key 1, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'a key YAML reads as an int is refused on its line, named as written'

    def test_decode_frontmatter_with_a_bool_key_returns_invalid_yaml_naming_it_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            true: yes
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the non-string key true, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'a key YAML reads as a bool is refused on its line, named as written'

    def test_decode_frontmatter_with_a_null_key_returns_invalid_yaml_naming_it_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            null: nothing
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the non-string key null, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'a key YAML reads as null is refused on its line, named as written'

    def test_decode_frontmatter_with_an_explicit_empty_key_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            ?
            : nothing
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found an explicit key, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'the `?` that starts a key is refused on its line, whatever it holds'

    def test_decode_frontmatter_with_a_date_key_returns_it_as_a_string_key(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            2026-10-04: launch
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == Frontmatter(
            data=FrozenMapping({'name': 'guide', '2026-10-04': 'launch'}),
            keys=(
                FrontmatterKey('name', LineNumber.from_int(2)),
                FrontmatterKey('2026-10-04', LineNumber.from_int(3)),
            ),
        ), 'a date is no scalar of the core schema, so a key written as one is a string like any other'

    def test_decode_frontmatter_with_a_non_string_key_in_a_list_item_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            tags:
              - label: a
                2: b
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the non-string key 2, which frontmatter does not allow', line=LineNumber.from_int(5)
        ), 'a key nested inside a list item is refused like a top-level one, on its own line'

    def test_decode_frontmatter_with_a_non_string_key_in_a_flow_mapping_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            meta: {owner: me, 3.5: x}
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the non-string key 3.5, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'a key of a flow mapping is refused like a block one'

    def test_decode_frontmatter_with_a_list_written_as_a_key_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            [a, b]: x
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a collection as a key, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'a key written as a list is no string, and has no one piece of text to name'

    def test_decode_frontmatter_with_a_quoted_numeric_key_returns_it_as_a_string_key(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            '1': one
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == Frontmatter(
            data=FrozenMapping({'name': 'guide', '1': 'one'}),
            keys=(FrontmatterKey('name', LineNumber.from_int(2)), FrontmatterKey('1', LineNumber.from_int(3))),
        ), 'a quoted key is a string whatever its text, so it is a field like any other'

    def test_decode_frontmatter_with_a_key_repeated_with_the_same_value_lists_every_occurrence(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            type: rule
            name: guide
            """)

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
        block = dedent("""\
            name: guide
            type: rule
            name: other
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == Frontmatter(
            data=FrozenMapping({'name': 'other', 'type': 'rule'}),
            keys=(
                FrontmatterKey('name', LineNumber.from_int(2)),
                FrontmatterKey('type', LineNumber.from_int(3)),
                FrontmatterKey('name', LineNumber.from_int(4)),
            ),
            repeats=(RepeatedKey('name', LineNumber.from_int(4), LineNumber.from_int(2), LineNumber.from_int(4)),),
        ), 'the data holds the value of the last occurrence, and the keys list every occurrence'

    def test_decode_frontmatter_with_a_key_repeated_in_a_nested_mapping_lists_the_repeat_with_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            metadata:
              author: a
              author: b
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a mapping that repeats a nested key is still frontmatter, got {node!r}'
        assert node.repeats == (
            RepeatedKey('author', LineNumber.from_int(5), LineNumber.from_int(4), LineNumber.from_int(5)),
        ), 'a nested key written again is listed on its own line, pointing back at the first'
        assert node.data == FrozenMapping({'name': 'guide', 'metadata': FrozenMapping({'author': 'b'})}), (
            'the later value stands, so the other fields of the block are still read'
        )

    def test_decode_frontmatter_with_a_key_repeated_in_a_flow_mapping_lists_the_repeat(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            size: {w: 1, w: 2}
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a mapping that repeats a nested key is still frontmatter, got {node!r}'
        assert node.repeats == (
            RepeatedKey('w', LineNumber.from_int(3), LineNumber.from_int(3), LineNumber.from_int(3)),
        ), 'a key written twice on one line of a flow mapping is a repeat, as one over two lines is'

    def test_decode_frontmatter_with_a_key_repeated_in_a_sequence_item_lists_the_repeat(self) -> None:
        #: Given
        block = dedent("""\
            authors:
              - name: a
                name: b
              - name: c
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a mapping that repeats a nested key is still frontmatter, got {node!r}'
        assert node.repeats == (
            RepeatedKey('name', LineNumber.from_int(4), LineNumber.from_int(3), LineNumber.from_int(4)),
        ), 'a key repeated in one item is a repeat, and the same key in another item is not'

    def test_decode_frontmatter_with_the_same_key_in_different_mappings_lists_no_repeat(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            first:
              title: One
            second:
              title: Two
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.repeats == (), 'a key is repeated within one mapping, so the same name under two parents is not'

    def test_decode_frontmatter_with_an_equals_key_returns_it_as_a_string_key(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            =: 1
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == Frontmatter(
            data=FrozenMapping({'name': 'guide', '=': 1}),
            keys=(
                FrontmatterKey('name', LineNumber.from_int(2)),
                FrontmatterKey('=', LineNumber.from_int(3)),
            ),
        ), 'a plain `=` key means nothing special, so it is a string key listed with its line'

    def test_decode_frontmatter_with_an_anchor_on_a_scalar_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            type: rule
            name: &name guide
            """)

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
        block = dedent("""\
            name: guide
            see: *guide
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the alias *guide, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'frontmatter is basic YAML, so an alias is a finding on its line'

    def test_decode_frontmatter_with_a_str_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            description: !!str 2024-01-01
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!str', which frontmatter does not allow",
            line=LineNumber.from_int(3),
        ), 'a scalar tag is refused like any other, even one naming a type YAML resolves unaided'

    def test_decode_frontmatter_with_a_pairs_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            steps: !!pairs [first: 1, second: 2]
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!pairs', which frontmatter does not allow",
            line=LineNumber.from_int(3),
        ), 'a pairs tag, which builds tuples JSON has no counterpart for, is a finding on its line'

    def test_decode_frontmatter_with_an_omap_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            steps: !!omap [first: 1, second: 2]
            """)

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
        block = dedent("""\
            !!set
            ? guide
            ? rule
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!set', which frontmatter does not allow",
            line=LineNumber.from_int(2),
        ), 'a set tag, which builds a set JSON has no counterpart for, is a finding on its line'

    def test_decode_frontmatter_with_a_binary_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            icon: !!binary aGk=
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!binary', which frontmatter does not allow",
            line=LineNumber.from_int(3),
        ), 'a binary tag, which builds bytes JSON has no counterpart for, is a finding on its line'

    def test_decode_frontmatter_with_a_local_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            owner: !team docs
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!team', which frontmatter does not allow", line=LineNumber.from_int(3)
        ), 'a local tag is a finding on its line, not a construction failure'

    def test_decode_frontmatter_with_a_verbatim_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            owner: !<tag:example.com,2026:team> docs
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!<tag:example.com,2026:team>', which frontmatter does not allow",
            line=LineNumber.from_int(3),
        ), 'a verbatim tag is a finding on its line, not a construction failure'

    def test_decode_frontmatter_with_the_non_specific_tag_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            count: ! 3
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!', which frontmatter does not allow", line=LineNumber.from_int(3)
        ), 'the non-specific tag `!`, which makes a plain scalar a string, is refused like any other'

    def test_decode_frontmatter_with_a_tag_of_three_bangs_names_the_tag_as_written(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            count: !!!str 3
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!!str', which frontmatter does not allow", line=LineNumber.from_int(3)
        ), 'the parser reads the third bang into the handle, but the diagnostic quotes what the block writes'

    def test_decode_frontmatter_with_a_tag_in_a_flow_sequence_names_it_without_the_comma(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            tags: [!x, b]
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!x', which frontmatter does not allow", line=LineNumber.from_int(3)
        ), 'a flow indicator ends the tag, so the comma that follows it is not part of the name'

    def test_decode_frontmatter_with_a_tag_on_a_key_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            type: rule
            !!str name: guide
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!str', which frontmatter does not allow",
            line=LineNumber.from_int(3),
        ), 'a tag on a key is refused as one on a value is'

    def test_decode_frontmatter_with_a_tag_nested_in_a_list_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            tags:
              - docs
              - !!int 3
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="found the tag '!!int', which frontmatter does not allow",
            line=LineNumber.from_int(5),
        ), 'a tag at any depth is refused, on the line of the item that carries it'

    def test_decode_frontmatter_with_a_key_indented_under_a_text_value_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            description: a
              b: c
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='this value holds `: `',
            help='Quote the value: `b: "c"`',
            line=LineNumber.from_int(4),
        ), 'a key indented under a text value is reported on the indented line, with the key it sits under'

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
            problem='found an escape that names no Unicode character, which frontmatter does not allow',
            line=LineNumber.from_int(4),
        ), 'an escape that names no character is a finding on its own line, not a crash'

    def test_decode_frontmatter_with_an_escape_just_beyond_unicode_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        # the first code point above U+10FFFF, which fits a C int, unlike `\UFFFFFFFF`
        block = 'name: guide\ndescription: "\\U00110000"\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found an escape that names no Unicode character, which frontmatter does not allow',
            line=LineNumber.from_int(3),
        ), 'an escape one above the last code point is a finding on its line, not a crash'

    def test_decode_frontmatter_with_a_yaml_directive_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            %YAML 1.2
            name: guide
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the directive %YAML, which frontmatter does not allow', line=LineNumber.from_int(2)
        ), 'a version directive is refused on its line, whatever version it names'

    def test_decode_frontmatter_with_a_tag_directive_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            %TAG ! tag:example.com,2026:
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the directive %TAG, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'a directive anywhere in the block is refused on its line'

    def test_decode_frontmatter_with_an_unknown_directive_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            %FOO bar
            name: guide
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the directive %FOO, which frontmatter does not allow', line=LineNumber.from_int(2)
        ), 'any line starting with `%` is a directive, the ones YAML does not define included'

    def test_decode_frontmatter_with_a_yaml_version_too_long_to_read_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        # one digit more than the interpreter converts to an int, read from it rather than assumed to be 4300
        digits = '1' * (sys.get_int_max_str_digits() + 1)
        directive = f'%YAML 1.{digits}\n'
        document = dedent("""\
            name: guide
            """)
        block = directive + document

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the directive %YAML, which frontmatter does not allow', line=LineNumber.from_int(2)
        ), 'a directive is refused before its version is read, so a number too long to convert is no crash'

    def test_decode_frontmatter_with_a_directive_ending_in_a_flow_indicator_names_it_without_the_indicator(
        self,
    ) -> None:
        #: Given
        block = dedent("""\
            name: guide
            %b]
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the directive %b, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'a flow indicator ends the name, so the diagnostic does not quote the rest of the line'

    def test_decode_frontmatter_with_a_directive_name_holding_a_colon_names_it_up_to_the_colon(self) -> None:
        #: Given
        block = dedent("""\
            %YAML:1.1
            name: guide
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the directive %YAML, which frontmatter does not allow', line=LineNumber.from_int(2)
        ), 'a `:` ends the name, as it does a key'

    def test_decode_frontmatter_with_a_directive_before_a_second_document_returns_invalid_yaml_on_the_directive(
        self,
    ) -> None:
        #: Given
        block = dedent("""\
            a: 1
            %YAML 1.1
            ---
            b: 2
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the directive %YAML, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'the directive is refused on its own line, ahead of the second document it introduces'

    def test_decode_frontmatter_with_a_directive_after_an_end_marker_returns_invalid_yaml_on_the_end_marker(
        self,
    ) -> None:
        #: Given
        block = dedent("""\
            a: 1
            ...
            %YAML 1.1


            ---
            b: 2
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the document marker ..., which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'the end marker comes before the directive, so it is the one reported'

    def test_decode_frontmatter_with_a_percent_sign_that_starts_no_line_returns_it_as_text(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            score: 50%
            rate: "%YAML"
            note: a %TAG
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping({'name': 'guide', 'score': '50%', 'rate': '%YAML', 'note': 'a %TAG'}), (
            'a `%` is a directive only as the first character of a line'
        )

    def test_decode_frontmatter_with_flow_collections_nested_to_the_recursion_limit_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        # the second `[` is refused where it stands, so no depth of flow collections can reach the stack's limit
        depth = sys.getrecursionlimit()
        name_line = 'name: guide\n'
        description_line = f'description: {"[" * depth}{"]" * depth}\n'
        block = name_line + description_line

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a collection inside a flow collection, which frontmatter does not allow',
            line=LineNumber.from_int(3),
        ), 'a flow collection holds no collection, so nesting is refused at the second level'

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

    def test_decode_frontmatter_with_an_explicit_key_above_nesting_too_deep_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        # the scanner recorded the `?` before the stack ran out, and it is written above the depth
        depth = sys.getrecursionlimit()
        nested = ''.join(f'{" " * level}nested:\n' for level in range(depth))
        block = f'name: guide\n? a\n{nested}{" " * depth}a: b\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found an explicit key, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'the construct written above the nesting is the finding, not the depth'

    def test_decode_frontmatter_with_an_integer_too_long_to_read_returns_it_as_a_string(self) -> None:
        #: Given
        # one digit more than the interpreter converts to an int, read from it rather than assumed to be 4300
        digits = '1' * (sys.get_int_max_str_digits() + 1)
        name_line = 'name: guide\n'
        count_line = f'count: {digits}\n'
        block = name_line + count_line

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping({'name': 'guide', 'count': digits}), (
            'an integer with more digits than Python converts stays its text, rather than failing the block'
        )

    def test_decode_frontmatter_with_a_float_too_large_returns_it_as_a_string(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            weight: 1e999
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping({'name': 'guide', 'weight': '1e999'}), (
            'a float past what Python holds would be infinity, which JSON has no number for, so it stays its text'
        )

    def test_decode_frontmatter_with_core_schema_scalars_returns_their_json_values(self) -> None:
        #: Given
        block = dedent("""\
            a: ~
            b: null
            c:
            d: true
            e: FALSE
            f: 12
            g: -012
            h: 0o12
            i: 0x1F
            j: -1.5
            k: 1e3
            l: .5
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping(
            {
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
            }
        ), 'a plain scalar the core schema reads as null, a bool, an int or a float decodes to that value'

    def test_decode_frontmatter_with_scalars_only_yaml_1_1_resolves_returns_them_as_strings(self) -> None:
        #: Given
        block = dedent("""\
            a: yes
            b: on
            c: 2026-10-05
            d: 1:30
            e: 0b101
            f: 1_000
            g: .inf
            h: .nan
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping(
            {
                'a': 'yes',
                'b': 'on',
                'c': '2026-10-05',
                'd': '1:30',
                'e': '0b101',
                'f': '1_000',
                'g': '.inf',
                'h': '.nan',
            }
        ), 'a plain scalar the core schema does not read as null, a bool or a JSON number is a string'

    def test_decode_frontmatter_with_quoted_and_block_scalars_returns_them_as_strings(self) -> None:
        #: Given
        block = dedent("""\
            a: "12"
            b: 'true'
            c: |
              12
            d: >
              null
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping({'a': '12', 'b': 'true', 'c': '12\n', 'd': 'null\n'}), (
            'only a plain scalar is resolved; a quoted or block scalar is its text, whatever it reads like'
        )

    def test_decode_frontmatter_with_a_document_start_marker_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            --- type: rule
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the document marker ---, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'a `---` inside the block would start a second document, and is a finding on its own line'

    def test_decode_frontmatter_with_a_document_start_marker_on_the_first_line_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = '--- a\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the document marker ---, which frontmatter does not allow', line=LineNumber.from_int(2)
        ), 'a marker is refused where the block opens as well'

    def test_decode_frontmatter_with_a_document_end_marker_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            ...
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the document marker ..., which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'the end marker is refused like the start one, although the parser would end the document there'

    def test_decode_frontmatter_with_a_document_end_marker_on_the_first_line_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = dedent("""\
            ...
            name: guide
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the document marker ..., which frontmatter does not allow', line=LineNumber.from_int(2)
        ), 'a leading end marker is refused, although the parser would skip it without an event'

    def test_decode_frontmatter_with_a_document_marker_on_a_quoted_continuation_line_returns_invalid_yaml(
        self,
    ) -> None:
        #: Given
        block = dedent("""\
            a: "x
            --- y"
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the document marker ---, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'a marker inside a quoted scalar is refused as every other marker is, not in the parser words'

    def test_decode_frontmatter_with_a_document_marker_after_a_blank_line_of_a_quoted_scalar_returns_invalid_yaml(
        self,
    ) -> None:
        #: Given
        block = dedent("""\
            a: 'x

            ... y'
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the document marker ..., which frontmatter does not allow', line=LineNumber.from_int(4)
        ), 'a blank line before the marker does not hide it'

    def test_decode_frontmatter_with_an_indented_marker_in_a_quoted_continuation_line_returns_it_as_text(self) -> None:
        #: Given
        block = dedent("""\
            a: "x
              --- y"
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping({'a': 'x --- y'}), (
            'a marker is three characters at the start of a line, so an indented one is text'
        )

    def test_decode_frontmatter_with_marker_like_text_returns_it_as_text(self) -> None:
        #: Given
        block = dedent("""\
            a: ---
            b: ...
            c: "--- x"
            d: |
              ---
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping({'a': '---', 'b': '...', 'c': '--- x', 'd': '---\n'}), (
            'a marker is three characters at the start of a line, not inside a value or an indented line'
        )

    def test_decode_frontmatter_with_a_bad_indent_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            a:
              b: 1
             c: 2
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem="this line's indentation matches no key or item above it",
            help='Indent it like the keys or items it belongs with',
            line=LineNumber.from_int(4),
        ), 'a line indented to no level of the block is reported on that line'

    def test_decode_frontmatter_with_an_unclosed_flow_collection_returns_invalid_yaml_on_the_line_it_opens(
        self,
    ) -> None:
        #: Given
        block = dedent("""\
            name: guide
            tags: [a, b
            type: rule
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a flow collection spread over lines, which frontmatter does not allow',
            line=LineNumber.from_int(3),
        ), 'a flow collection left open is spread over lines, and is reported where it opens'

    def test_decode_frontmatter_with_a_second_colon_in_a_plain_value_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            a: b: c
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='this value holds `: `', help='Quote the value: `a: "b: c"`', line=LineNumber.from_int(3)
        ), 'a `: ` inside a plain value is reported on the line holding it'

    def test_decode_frontmatter_with_an_unclosed_quote_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            description: "never closed
            type: rule
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='this quote is never closed',
            help='Close it on the line it continues to, or remove it',
            line=LineNumber.from_int(3),
        ), 'a quoted scalar left open is reported on the line its quote opens on'

    def test_decode_frontmatter_with_a_tab_indent_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'a:\n\tb: 1\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='the block cannot be read from this line on', line=LineNumber.from_int(3)
        ), 'a tab where indentation is expected is reported on its line'

    def test_decode_frontmatter_with_a_tab_in_a_flow_collection_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\ntags: [a,\tb]\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='the block cannot be read from this line on', line=LineNumber.from_int(3)
        ), 'a tab is not whitespace in a flow collection either'

    def test_decode_frontmatter_with_a_key_written_as_nothing_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            : value
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found an empty key, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'a `:` with no key before it is an empty key, and is reported on its line'

    def test_decode_frontmatter_with_an_unindented_top_level_block_scalar_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = dedent("""\
            >
            text
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='the block cannot be read from this line on',
            line=LineNumber.from_int(3),
        ), 'a top-level block scalar must be indented, so the line after it is reported'

    def test_decode_frontmatter_with_a_nested_block_scalar_after_a_short_blank_line_returns_its_text(self) -> None:
        #: Given
        block = 'name: guide\nnotes:\n  summary: |\n  \n    First paragraph.\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a blank line shorter than the text is part of the scalar, got {node!r}'
        assert node.data == FrozenMapping(
            {'name': 'guide', 'notes': FrozenMapping({'summary': '\nFirst paragraph.\n'})}
        ), 'the blank line is part of the scalar, before the text'

    def test_decode_frontmatter_with_a_literal_scalar_after_a_one_space_line_returns_its_text(self) -> None:
        #: Given
        block = 'a: |\n \n  x\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a one-space line before the text is accepted, got {node!r}'
        assert node.data == FrozenMapping({'a': '\nx\n'}), 'the scalar is a blank line and the text'

    def test_decode_frontmatter_with_a_folded_scalar_after_a_one_space_line_returns_its_text(self) -> None:
        #: Given
        block = 'a: >\n \n  x\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a one-space line before the text is accepted, got {node!r}'
        assert node.data == FrozenMapping({'a': '\nx\n'}), 'the scalar is a blank line and the text'

    def test_decode_frontmatter_with_a_literal_scalar_after_a_line_of_the_parent_indent_returns_its_text(self) -> None:
        #: Given
        block = 'a: |\n  \n   x\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a blank line indented less than the text is accepted, got {node!r}'
        assert node.data == FrozenMapping({'a': '\nx\n'}), 'the scalar is a blank line and the text'

    def test_decode_frontmatter_with_a_merge_key_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: review
            <<: {license: MIT}
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the merge key <<, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'a plain `<<` key is YAML 1.1 merge syntax, refused whatever value follows it'

    def test_decode_frontmatter_with_a_merge_key_of_an_alias_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: review
            <<: *base
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found the merge key <<, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'the merge key is the first construct on the line, so it is the one reported'

    def test_decode_frontmatter_with_a_quoted_merge_key_or_a_merge_value_returns_it_as_text(self) -> None:
        #: Given
        block = dedent("""\
            name: review
            "<<": a
            other: <<
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping({'name': 'review', '<<': 'a', 'other': '<<'}), (
            'only a plain `<<` key merges: a quoted one, and a `<<` value, are text'
        )

    def test_decode_frontmatter_with_anchor_alias_and_tag_characters_inside_text_returns_it_as_text(self) -> None:
        #: Given
        block = dedent("""\
            a: b&c
            b: 2*3
            c: wow!
            d: "&x *y !z"
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping({'a': 'b&c', 'b': '2*3', 'c': 'wow!', 'd': '&x *y !z'}), (
            'an anchor, an alias or a tag starts a node; inside a value the character is text'
        )

    def test_decode_frontmatter_with_a_question_mark_ending_a_plain_scalar_in_a_flow_sequence_is_no_explicit_key(
        self,
    ) -> None:
        #: Given
        block = 'a: [what?]\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='the block cannot be read from this line on', line=LineNumber.from_int(2)
        ), 'a `?` inside a plain scalar is no explicit key, so it is the parser that stops there, not a refusal'

    def test_decode_frontmatter_with_a_spaced_question_mark_in_a_flow_sequence_is_no_explicit_key(self) -> None:
        #: Given
        block = 'a: [what ? x]\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='the block cannot be read from this line on', line=LineNumber.from_int(2)
        ), 'a `?` after a scalar is no explicit key, so it is the parser that stops there'

    def test_decode_frontmatter_with_a_question_mark_alone_in_a_flow_sequence_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = 'a: [?]\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found an explicit key, which frontmatter does not allow', line=LineNumber.from_int(2)
        ), 'a `?` where a node may start is an explicit key, whatever follows it'

    def test_decode_frontmatter_with_an_explicit_key_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: a
            ? b
            : c
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found an explicit key, which frontmatter does not allow', line=LineNumber.from_int(3)
        ), 'the `?` that starts a key is refused on its line, with the key it starts'

    def test_decode_frontmatter_with_a_flow_collection_spread_over_lines_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            tags: [a,
              b]
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a flow collection spread over lines, which frontmatter does not allow',
            line=LineNumber.from_int(3),
        ), 'a flow collection is one line, so one that continues below is refused where it opens'

    def test_decode_frontmatter_with_a_flow_sequence_holding_a_collection_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = 'a: [[1], {b: 2}]\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a collection inside a flow collection, which frontmatter does not allow',
            line=LineNumber.from_int(2),
        ), 'a flow collection holds scalars only, so the collection it holds is refused on its line'

    def test_decode_frontmatter_with_a_flow_sequence_holding_a_pair_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'a: [b: c]\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a collection inside a flow collection, which frontmatter does not allow',
            line=LineNumber.from_int(2),
        ), 'a `key: value` pair in a flow sequence is a mapping, which a flow collection does not hold'

    def test_decode_frontmatter_with_a_flow_mapping_as_the_block_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = '{name: a}\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a flow collection as the block, which frontmatter does not allow',
            line=LineNumber.from_int(2),
        ), 'the block is a block mapping, one key to a line, so a flow mapping that is the whole block is refused'

    def test_decode_frontmatter_with_a_flow_sequence_as_the_block_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = '[a, b]\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a flow collection as the block, which frontmatter does not allow',
            line=LineNumber.from_int(2),
        ), 'a flow sequence that is the whole block is refused rather than read as a list that is no mapping'

    def test_decode_frontmatter_with_an_indentation_indicator_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            d: |2
                x
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a block scalar indentation indicator, which frontmatter does not allow',
            line=LineNumber.from_int(3),
        ), 'the indentation a block scalar is written at is read from its text, so an indicator is refused on its line'

    def test_decode_frontmatter_with_a_block_sequence_in_a_block_sequence_returns_invalid_yaml_on_its_line(
        self,
    ) -> None:
        #: Given
        block = dedent("""\
            name: guide
            tags:
              - a
              - - b
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='found a block sequence as an item of a block sequence, which frontmatter does not allow',
            line=LineNumber.from_int(5),
        ), 'a list of lists is written with a flow sequence, so a nested block sequence is refused on its line'

    def test_decode_frontmatter_with_a_question_mark_or_an_empty_quoted_key_returns_them_as_string_keys(self) -> None:
        #: Given
        block = dedent("""\
            why?: a
            '': b
            c: d?
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping({'why?': 'a', '': 'b', 'c': 'd?'}), (
            'a `?` inside a plain scalar is text, and a quoted empty key is a string'
        )

    def test_decode_frontmatter_with_flow_collections_of_scalars_on_one_line_returns_them(self) -> None:
        #: Given
        block = dedent("""\
            tags: [a, "b c"]
            size: {w: 1, h: 2}
            none: []
            empty: {}
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping(
            {'tags': ('a', 'b c'), 'size': FrozenMapping({'w': 1, 'h': 2}), 'none': (), 'empty': FrozenMapping({})}
        ), 'a flow collection of scalars on one line is accepted, empty or not'

    def test_decode_frontmatter_with_chomping_indicators_returns_them(self) -> None:
        #: Given
        block = dedent("""\
            keep: |+
              x
            strip: >-
              y
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping({'keep': 'x\n', 'strip': 'y'}), (
            'a chomping indicator is accepted, and only an indentation indicator is refused'
        )

    def test_decode_frontmatter_with_block_sequence_items_returns_them(self) -> None:
        #: Given
        block = dedent("""\
            people:
              - name: a
                url: b
              - [c, d]
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping({'people': (FrozenMapping({'name': 'a', 'url': 'b'}), ('c', 'd'))}), (
            'a block mapping and a flow sequence are accepted as items of a block sequence'
        )

    def test_decode_frontmatter_with_text_after_a_closing_quote_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'name: "a" b\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='text follows the closing quote',
            help='Put the whole value inside the quotes',
            line=LineNumber.from_int(2),
        ), 'text written after a closing quote is reported on its line'

    def test_decode_frontmatter_with_text_after_a_flow_collection_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'a: [b, c] d\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='the block cannot be read from this line on', line=LineNumber.from_int(2)
        ), 'an error no kind of the table matches is reported on the parser line, with no help'

    def test_decode_frontmatter_with_a_stray_flow_close_returns_invalid_yaml_on_its_line(self) -> None:
        #: Given
        block = 'a: ]\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert node == InvalidYamlFrontmatter(
            problem='the block cannot be read from this line on', line=LineNumber.from_int(2)
        ), 'an error no kind of the table matches is reported on the parser line, with no help'

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

    def test_decode_frontmatter_with_nested_collections_freezes_them_all_the_way_down(self) -> None:
        #: Given
        block = dedent("""\
            tags: [a, b]
            meta:
              owner: me
              see:
                - x: 1
            """)

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a YAML mapping is frontmatter, got {node!r}'
        assert node.data == FrozenMapping(
            {
                'tags': ('a', 'b'),
                'meta': FrozenMapping({'owner': 'me', 'see': (FrozenMapping({'x': 1}),)}),
            }
        ), 'every mapping is a frozen mapping and every list a tuple, at any depth'

    def test_hash_with_two_equal_nested_frontmatters_returns_the_same_hash(self) -> None:
        #: Given
        block = dedent("""\
            name: guide
            meta: {see: [a, b]}
            """)
        first = decode_frontmatter(block)
        second = decode_frontmatter(block)

        #: When
        hashed_alike = hash(first) == hash(second)

        #: Then
        assert first == second, 'one block decodes to equal frontmatter each time'
        assert hashed_alike, 'equal frontmatter, nested collections included, hashes alike'


@pytest.mark.unit
class TestFrontmatterFindKeyLine:
    def test_find_key_line_with_a_present_key_returns_its_line(self) -> None:
        #: Given
        frontmatter = Frontmatter(
            data=FrozenMapping({'type': 'rule'}), keys=(FrontmatterKey('type', LineNumber.from_int(3)),)
        )

        #: When
        line = frontmatter.find_key_line('type')

        #: Then
        assert line == LineNumber.from_int(3), f'the type key is on line 3, got {line}'

    def test_find_key_line_with_a_repeated_key_returns_the_line_of_its_last_occurrence(self) -> None:
        #: Given
        frontmatter = Frontmatter(
            data=FrozenMapping({'name': 'other'}),
            keys=(FrontmatterKey('name', LineNumber.from_int(2)), FrontmatterKey('name', LineNumber.from_int(5))),
        )

        #: When
        line = frontmatter.find_key_line('name')

        #: Then
        assert line == LineNumber.from_int(5), f'the last occurrence is the one whose value the data holds, got {line}'

    def test_find_key_line_with_an_absent_key_returns_none(self) -> None:
        #: Given
        frontmatter = Frontmatter(
            data=FrozenMapping({'type': 'rule'}), keys=(FrontmatterKey('type', LineNumber.from_int(3)),)
        )

        #: When
        line = frontmatter.find_key_line('name')

        #: Then
        assert line is None, f'an absent key has no line, got {line}'


@pytest.mark.unit
class TestReadsBackAsString:
    def test_reads_back_as_string_with_a_decimal_returns_false(self) -> None:
        #: When
        result = reads_back_as_string('1.0')

        #: Then
        assert result is False, '`1.0` unquoted decodes to a number, not to itself'

    def test_reads_back_as_string_with_a_boolean_returns_false(self) -> None:
        #: When
        result = reads_back_as_string('true')

        #: Then
        assert result is False, '`true` unquoted decodes to a boolean, not to itself'

    def test_reads_back_as_string_with_an_octal_integer_returns_false(self) -> None:
        #: When
        result = reads_back_as_string('0o17')

        #: Then
        assert result is False, '`0o17` unquoted decodes to an integer, not to itself'

    def test_reads_back_as_string_with_an_exponent_returns_false(self) -> None:
        #: When
        result = reads_back_as_string('1e3')

        #: Then
        assert result is False, '`1e3` unquoted decodes to a number, not to itself'

    def test_reads_back_as_string_with_empty_text_returns_false(self) -> None:
        #: When
        result = reads_back_as_string('')

        #: Then
        assert result is False, 'an empty value decodes to null'

    def test_reads_back_as_string_with_text_that_is_not_yaml_returns_false(self) -> None:
        #: When
        result = reads_back_as_string('[unclosed')

        #: Then
        assert result is False, 'text the frontmatter reader rejects does not read back'

    def test_reads_back_as_string_with_a_plain_string_returns_true(self) -> None:
        #: When
        result = reads_back_as_string('guide')

        #: Then
        assert result is True, 'a plain word decodes to itself'
