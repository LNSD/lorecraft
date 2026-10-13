"""The frontmatter parser's `FM002` problems and lines against PyYAML's, which it replaced.

`decode_frontmatter` reads ruamel.yaml's events, where it once read PyYAML's, and what lorecraft accepts as
frontmatter and the line of every `FM002` must not move. These tests hold the two parsers to each other on every
error probe: the problem and the line each reports. This tier alone may import PyYAML, a development dependency: the
package never does.
"""

import pytest
import yaml
from yaml.error import MarkedYAMLError as PyYamlMarkedError
from yaml.reader import ReaderError as PyYamlReaderError

from lorecraft.core.mapping import FrozenMapping
from lorecraft.project.syntax.frontmatter import Frontmatter, InvalidYamlFrontmatter, decode_frontmatter

type ErrorSummary = tuple[str, int | None]
"""What `FM002` reports about a block: the problem, and the block line it is on, counted from 0."""


def pyyaml_error(block: str) -> ErrorSummary:
    """The problem and block line PyYAML reports for a block that does not parse, as `FM002` reports them.

    Args:
        block: The YAML text, which PyYAML fails to parse.
    """
    try:
        for _event in yaml.parse(block):
            pass
    except PyYamlReaderError as exc:
        return exc.reason, block.count('\n', 0, exc.position)
    except PyYamlMarkedError as exc:
        mark = exc.problem_mark or exc.context_mark
        return exc.problem or exc.context, None if mark is None else mark.line
    raise AssertionError('PyYAML parsed a block meant to be an error probe')


def frontmatter_error(block: str) -> ErrorSummary:
    """The problem and block line `FM002` reports for a block, counted from the block's first line as 0.

    Args:
        block: The YAML text, which `decode_frontmatter` refuses.
    """
    node = decode_frontmatter(block)
    assert isinstance(node, InvalidYamlFrontmatter), f'the block should be refused as invalid YAML, got {node!r}'
    return node.problem, None if node.line is None else node.line.number - 2


@pytest.mark.it
class TestInvalidYamlParity:
    def test_decode_frontmatter_with_a_bad_indent_reports_pyyamls_problem_and_line(self) -> None:
        #: Given
        block = 'a:\n  b: 1\n c: 2\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'a mis-indented line is reported as PyYAML reports it'

    def test_decode_frontmatter_with_a_nested_mapping_value_reports_pyyamls_problem_and_line(self) -> None:
        #: Given
        block = 'name: guide\na: b: c\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'a second colon in a plain scalar is reported as PyYAML reports it'

    def test_decode_frontmatter_with_an_unclosed_quote_reports_pyyamls_problem_and_line(self) -> None:
        #: Given
        block = 'name: guide\ndescription: "never closed\ntype: rule\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'an unclosed quoted scalar is reported as PyYAML reports it'

    def test_decode_frontmatter_with_a_tab_indent_reports_pyyamls_problem_and_line(self) -> None:
        #: Given
        block = 'a:\n\tb: 1\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'a tab where indentation is expected is reported as PyYAML reports it'

    def test_decode_frontmatter_with_an_unclosed_flow_collection_reports_pyyamls_problem_and_line(self) -> None:
        #: Given
        block = 'name: guide\ntags: [a, b\ntype: rule\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'an unclosed flow collection is reported as PyYAML reports it'

    def test_decode_frontmatter_with_a_control_character_reports_pyyamls_problem_and_line(self) -> None:
        #: Given
        block = 'name: guide\ntitle: bad\x07bell\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'a control character is reported as PyYAML reports it'

    def test_decode_frontmatter_with_an_escape_above_the_last_code_point_reports_it_on_its_line(self) -> None:
        #: Given
        block = 'name: guide\nglyph: "\\U00110000"\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == ('found an escape sequence that names no Unicode character', 1), (
            'an escape naming no character is invalid YAML on its line, not an exception'
        )

    def test_decode_frontmatter_with_an_overlong_yaml_version_reports_it_on_its_line(self) -> None:
        #: Given
        block = '%YAML 1.' + '1' * 5000 + '\n---\na: 1\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == ('found a YAML version number too long to read', 0), (
            'a version number too long to convert is invalid YAML on its line, not an exception'
        )

    def test_decode_frontmatter_with_a_tab_in_a_flow_collection_reports_pyyamls_problem_and_line(self) -> None:
        #: Given
        block = 'name: guide\ntags: [a,\tb]\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'a tab is not whitespace in a flow collection, as for PyYAML'

    def test_decode_frontmatter_with_an_alias_ending_in_an_indicator_reports_pyyamls_problem_and_line(self) -> None:
        #: Given
        block = 'name: guide\ndescription: *emphasis*\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'a name takes only letters, digits, `-` and `_`, as for PyYAML'

    def test_decode_frontmatter_with_a_key_written_as_nothing_reports_pyyamls_problem_and_line(self) -> None:
        #: Given
        block = 'name: guide\n: value\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'YAML 1.1 has no key written as nothing, so the block is not YAML'

    def test_decode_frontmatter_with_a_yaml_directive_named_with_a_colon_reports_pyyamls_problem_and_line(
        self,
    ) -> None:
        #: Given
        block = '%YAML:1.1\n---\nname: guide\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'a directive name takes only letters, digits, `-` and `_`'

    def test_decode_frontmatter_with_a_malformed_yaml_version_reports_pyyamls_problem_and_line(self) -> None:
        #: Given
        block = '%YAML 1.1;\n---\nname: guide\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'the problem names what PyYAML expects after the minor number'

    def test_decode_frontmatter_with_content_after_a_document_end_marker_reports_pyyamls_problem_and_line(
        self,
    ) -> None:
        #: Given
        block = 'name: guide\n... trailing\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'content on the line of a `...` marker is reported as PyYAML does'

    def test_decode_frontmatter_with_an_unindented_top_level_block_scalar_reports_pyyamls_problem_and_line(
        self,
    ) -> None:
        #: Given
        block = '>\n?\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'a top-level block scalar must be indented, as in YAML 1.1'

    def test_decode_frontmatter_with_an_explicit_empty_key_reports_it_on_the_line_pyyaml_marks(self) -> None:
        #: Given
        block = 'name: guide\n? \n: value\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == ('found a key that is not a string', 1), 'an empty key is null, which is not a string'

    def test_decode_frontmatter_with_a_yaml_directive_alone_of_minor_version_0_reports_pyyamls_problem(self) -> None:
        #: Given
        block = '%YAML 1.0\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'a version ruamel.yaml refuses to store is reported, not raised'

    def test_decode_frontmatter_with_a_yaml_directive_alone_of_minor_version_3_reports_pyyamls_problem(self) -> None:
        #: Given
        block = '%YAML 1.3\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'a version ruamel.yaml refuses to store is reported, not raised'

    def test_decode_frontmatter_with_a_bare_double_bang_tag_reports_pyyamls_problem_and_line(self) -> None:
        #: Given
        block = 'a: !!\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'a tag of two bangs and no suffix is not a tag, as for PyYAML'

    def test_decode_frontmatter_with_a_next_line_character_after_a_handle_reports_pyyamls_problem_and_line(
        self,
    ) -> None:
        #: Given
        block = 'a: !!\x85str b\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == pyyaml_error(block), 'a next line character ends the line the tag is on, as for PyYAML'

    def test_decode_frontmatter_with_a_tag_of_three_bangs_reports_the_tag_as_written(self) -> None:
        #: Given
        block = 'a: !!!str b\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == ("found the tag '!!!str', which frontmatter does not allow", 0), (
            'the tag is quoted as the block writes it'
        )

    def test_decode_frontmatter_with_an_anchor_named_like_a_parser_typo_reports_the_name_as_written(self) -> None:
        #: Given
        block = 'a: &hexdecimal b\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == ('found the anchor &hexdecimal, which frontmatter does not allow', 0), (
            'a name the block writes is never reworded as the parser'
        )

    def test_decode_frontmatter_with_a_yaml_directive_of_minor_version_0_returns_its_mapping(self) -> None:
        #: Given
        block = '%YAML 1.0\n---\na: 1\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a version ruamel.yaml refuses to store is read, got {node!r}'
        assert node.data == FrozenMapping({'a': 1}), 'the block decodes as it does under any other version'

    def test_decode_frontmatter_with_a_yaml_directive_of_minor_version_3_returns_its_mapping(self) -> None:
        #: Given
        block = '%YAML 1.3\n---\na: 1\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a version ruamel.yaml refuses to store is read, got {node!r}'
        assert node.data == FrozenMapping({'a': 1}), 'the block decodes as it does under any other version'


@pytest.mark.it
class TestAcceptedYamlParity:
    def test_decode_frontmatter_with_a_nested_block_scalar_after_a_short_blank_line_returns_its_text(self) -> None:
        #: Given
        block = 'name: guide\nnotes:\n  summary: |\n  \n    First paragraph.\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a blank line shorter than the text is part of the scalar, got {node!r}'
        assert node.data == FrozenMapping(
            {'name': 'guide', 'notes': FrozenMapping({'summary': '\nFirst paragraph.\n'})}
        )

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


@pytest.mark.it
class TestSecondDocumentParity:
    def test_decode_frontmatter_with_a_directive_before_a_second_document_names_the_directive_line(self) -> None:
        #: Given
        block = 'a: 1\n%YAML 1.1\n---\nb: 2\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == ('found a second document, which frontmatter does not allow', 1), (
            'the second document starts on its first directive, as it does for PyYAML'
        )

    def test_decode_frontmatter_with_a_directive_after_an_end_marker_names_the_directive_line(self) -> None:
        #: Given
        block = 'a: 1\n...\n%YAML 1.1\n\n\n---\nb: 2\n'

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert reported == ('found a second document, which frontmatter does not allow', 2), (
            'blank lines between the directive and the `---` do not move the line'
        )
