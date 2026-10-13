"""The frontmatter parser's ruamel.yaml events and errors against PyYAML's, which it replaced.

`decode_frontmatter` reads ruamel.yaml's events, where it once read PyYAML's, and what lorecraft accepts as
frontmatter and the line of every `FM002` must not move. These tests hold the two parsers to each other: the events of
every frontmatter block of the repository's own documents and of blocks covering the syntax a block may use, and the
problem and line of every error probe. This tier alone may import PyYAML, a development dependency: the package never
does.
"""

import re
from pathlib import Path
from typing import Final

import pytest
import yaml
from ruamel.yaml.error import MarkedYAMLError
from ruamel.yaml.reader import ReaderError
from yaml.error import MarkedYAMLError as PyYamlMarkedError
from yaml.parser import Parser as PyYamlParser
from yaml.reader import Reader as PyYamlReader
from yaml.reader import ReaderError as PyYamlReaderError
from yaml.scanner import Scanner as PyYamlScanner

from lorecraft.core.mapping import FrozenMapping
from lorecraft.project.syntax.frontmatter import (
    EventStream,
    Frontmatter,
    InvalidYamlFrontmatter,
    decode_frontmatter,
)

REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
"""The repository the tests run in, whose documents are the corpus."""

CORPUS_DIRECTORIES: Final[tuple[str, ...]] = ('docs', 'skills', '.claude/skills')
"""The directories of the repository whose Markdown documents hold the corpus.

Mutation testing runs the tests from a copy of the repository that holds only `skills/` of these, so the corpus
is whatever of them is on disk, and the test below asks that it is not empty rather than how large it is."""

type EventSummary = tuple[str, str | None, str | None, str | None, str | None, int | None]
"""One event as both parsers must agree on it: its type, value, style, anchor, tag and block line."""

type ErrorSummary = tuple[str, int | None]
"""What `FM002` reports about a block: the problem, and the block line it is on, counted from 0."""


def pyyaml_events(block: str) -> list[EventSummary]:
    """The events PyYAML's reader, scanner and parser read from the block, ending with the error if it raises one.

    Args:
        block: The YAML text, as `decode_frontmatter` takes it.
    """

    class Parser(PyYamlReader, PyYamlScanner, PyYamlParser):
        """PyYAML's reader, scanner and parser, which read a string into events and build no value."""

        def __init__(self, text: str) -> None:
            PyYamlReader.__init__(self, text)
            PyYamlScanner.__init__(self)
            PyYamlParser.__init__(self)

    events: list[object] = []
    failure: EventSummary | None = None
    try:
        parser = Parser(block)
        while parser.check_event():
            events.append(parser.get_event())
    except (PyYamlMarkedError, PyYamlReaderError) as exc:
        failure = ('error', str(exc).splitlines()[0], None, None, None, None)
    return summarize_stream(events, failure)


def ruamel_events(block: str) -> list[EventSummary]:
    """The events `decode_frontmatter` reads from the block, ending with the error if the parser raises one.

    Args:
        block: The YAML text, as `decode_frontmatter` takes it.
    """
    events: list[object] = []
    failure: EventSummary | None = None
    stream = EventStream(block)
    try:
        while True:
            event = stream.get_event()
            events.append(event)
            if type(event).__name__ == 'StreamEndEvent':
                break
    except (MarkedYAMLError, ReaderError) as exc:
        failure = ('error', str(exc).splitlines()[0], None, None, None, None)
    return summarize_stream(events, failure)


def summarize_stream(events: list[object], failure: EventSummary | None) -> list[EventSummary]:
    """The events as both parsers must agree on them, followed by the error that ended the stream, if one did.

    Args:
        events: The events of either library, in the order they were read.
        failure: The error the parser raised after them, or None when it read to the stream's end.
    """
    summaries: list[EventSummary] = []
    # One entry per open collection: whether the next node of a mapping is a key, or None for a sequence.
    expects_key: list[bool | None] = []
    for event in events:
        kind = type(event).__name__
        is_node = kind in ('ScalarEvent', 'AliasEvent', 'SequenceStartEvent', 'MappingStartEvent')
        is_mapping_value = False
        if is_node and expects_key and expects_key[-1] is not None:
            is_mapping_value = not expects_key[-1]
            expects_key[-1] = not expects_key[-1]
        if kind == 'MappingStartEvent':
            expects_key.append(True)
        elif kind == 'SequenceStartEvent':
            expects_key.append(None)
        elif kind in ('MappingEndEvent', 'SequenceEndEvent'):
            expects_key.pop()
        summaries.append(summarize(event, is_mapping_value))
    if failure is not None:
        summaries.append(failure)
    return summaries


def summarize(event: object, is_mapping_value: bool) -> EventSummary:
    """One event as both parsers must agree on it.

    Args:
        event: An event of either library.
        is_mapping_value: Whether the event is the value of a mapping's pair.
    """
    kind = type(event).__name__
    value = getattr(event, 'value', None)
    tag = getattr(event, 'tag', None)
    mark = getattr(event, 'start_mark', None)
    # The one mark that differs is a mapping value written as nothing, `a:` and then no text, with no tag or anchor
    # and not quoted: ruamel.yaml puts it on the next token's line where PyYAML puts it after the `:`. Nothing
    # reads it. `decode_frontmatter` takes a line from the start of a key, and from an anchor, a tag or an alias,
    # and an empty value has none of those. The empty scalar of a tagged or anchored value starts at its tag or
    # anchor, which is compared. A key written as nothing is compared too, and read in a test below.
    is_unread_mark = (
        is_mapping_value
        and kind == 'ScalarEvent'
        and value == ''
        and tag is None
        and getattr(event, 'anchor', None) is None
        and getattr(event, 'style', None) is None
    )
    return (
        kind,
        value,
        getattr(event, 'style', None),
        getattr(event, 'anchor', None),
        None if tag is None else str(tag),
        None if mark is None or is_unread_mark else mark.line,
    )


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


def corpus_blocks() -> dict[str, str]:
    """The frontmatter block of every Markdown document under the corpus directories, by path.

    A document's block is its lines between a first line of `---` and the next line of `---`.
    """
    blocks: dict[str, str] = {}
    for directory in CORPUS_DIRECTORIES:
        for path in sorted((REPOSITORY_ROOT / directory).rglob('*.md')):
            lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
            if not lines or lines[0].rstrip() != '---':
                continue
            closing = next((n for n, line in enumerate(lines[1:], start=1) if re.fullmatch(r'---\s*', line)), None)
            if closing is not None:
                blocks[str(path.relative_to(REPOSITORY_ROOT))] = ''.join(lines[1:closing])
    return blocks


def reads_same_events(block: str) -> bool:
    """Whether both parsers read the block as the same events, with the same type, value, style, anchor, tag, line.

    Args:
        block: The YAML text to read with both.
    """
    return ruamel_events(block) == pyyaml_events(block)


@pytest.mark.it
class TestCorpusEventParity:
    def test_event_stream_with_the_repository_corpus_matches_pyyaml(self) -> None:
        #: Given
        # The one test that loops: the cases are the documents found on disk, so there is no case to name, and the
        # names of the differing blocks are what the failure reports.
        blocks = corpus_blocks()

        #: When
        names = [name for name, block in blocks.items() if not reads_same_events(block)]

        #: Then
        assert blocks, 'discovery should find the documents of the directories the corpus is read from'
        assert names == [], 'every block reads as the same events, with the same type, value, style, anchor, tag, line'


@pytest.mark.it
class TestSyntaxEventParity:
    def test_event_stream_with_a_block_mapping_and_sequence_matches_pyyaml(self) -> None:
        #: Given
        block = 'name: guide\ntags:\n  - a\n  - b\nnested:\n  key: value\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a block mapping and sequence read as the same events'

    def test_event_stream_with_an_indentless_sequence_matches_pyyaml(self) -> None:
        #: Given
        block = 'tags:\n- a\n- b\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, "a sequence written at its key's indent reads as the same events"

    def test_event_stream_with_flow_collections_matches_pyyaml(self) -> None:
        #: Given
        block = 'a: [1, two, {three: 3}]\nb: {c: [d, e], f: g}\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'flow collections read as the same events'

    def test_event_stream_with_quoted_scalars_matches_pyyaml(self) -> None:
        #: Given
        block = "a: \"double \\x41 \\u00e9 \\n \\/\"\nb: 'it''s'\n"

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'escapes and doubled quotes read as the same events'

    def test_event_stream_with_multi_line_scalars_matches_pyyaml(self) -> None:
        #: Given
        block = 'a: plain\n  continued\nb: "quoted\n  continued"\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a scalar continued on the next line reads as the same events'

    def test_event_stream_with_block_scalars_matches_pyyaml(self) -> None:
        #: Given
        block = 'a: |\n  literal\n  text\nb: >-\n  folded\n  text\n\nc: |+\n  keep\n\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'literal and folded block scalars read as the same events'

    def test_event_stream_with_comments_and_blank_lines_matches_pyyaml(self) -> None:
        #: Given
        block = '# head\na: 1 # tail\n\n# between\nb: 2\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'comments and blank lines read as the same events, on the same lines'

    def test_event_stream_with_an_explicit_key_matches_pyyaml(self) -> None:
        #: Given
        block = '? a\n: b\n? [c]\n: d\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a key written with `?` reads as the same events'

    def test_event_stream_with_empty_values_matches_pyyaml(self) -> None:
        #: Given
        block = 'a:\nb: ~\nc: null\nd: ""\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a value written as nothing reads as the same events'

    def test_event_stream_with_an_anchor_and_an_alias_matches_pyyaml(self) -> None:
        #: Given
        block = 'a: &x 1\nb: *x\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'an anchor and its alias read as the same events, with the same anchor name'

    def test_event_stream_with_tags_matches_pyyaml(self) -> None:
        #: Given
        block = 'a: !!str 1\nb: !local 2\nc: !<tag:example.org,2026:t> 3\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a shorthand, a local and a verbatim tag read as the same events, with the same tag'

    def test_event_stream_with_a_tag_of_three_bangs_matches_pyyaml(self) -> None:
        #: Given
        block = 'a: !!!str b\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a handle of two bangs followed by `!str` reads as the same tag'

    def test_event_stream_with_directives_matches_pyyaml(self) -> None:
        #: Given
        block = '%YAML 1.1\n%TAG !e! tag:example.org,2026:\n---\na: !e!t 1\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a YAML and a TAG directive read as the same events'

    def test_event_stream_with_a_yaml_directive_of_minor_version_0_matches_pyyaml(self) -> None:
        #: Given
        block = '%YAML 1.0\n---\na: 1\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a version ruamel.yaml refuses to store is read, as PyYAML reads it'

    def test_event_stream_with_a_yaml_directive_of_minor_version_3_matches_pyyaml(self) -> None:
        #: Given
        block = '%YAML 1.3\n---\na: 1\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a version ruamel.yaml refuses to store is read, as PyYAML reads it'

    def test_event_stream_with_explicit_document_markers_matches_pyyaml(self) -> None:
        #: Given
        block = '---\na: 1\n...\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'explicit document start and end markers read as the same events'

    def test_event_stream_with_two_documents_matches_pyyaml(self) -> None:
        #: Given
        block = '---\na: 1\n---\nb: 2\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a second document reads as the same events'

    def test_event_stream_with_crlf_line_endings_matches_pyyaml(self) -> None:
        #: Given
        block = 'a: 1\r\nb:\r\n  - 2\r\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a CRLF line ending counts as one line break'

    def test_event_stream_with_a_byte_order_mark_matches_pyyaml(self) -> None:
        #: Given
        block = '\ufeffa: 1\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a byte order mark before the first key is skipped'

    def test_event_stream_with_line_separators_between_keys_matches_pyyaml(self) -> None:
        #: Given
        block = 'a: 1\u2028b: 2\u0085c: 3\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a Unicode line separator and a next line character each end a line, and each is counted'

    def test_event_stream_with_a_colon_before_a_flow_indicator_matches_pyyaml(self) -> None:
        #: Given
        block = 'a: {c:[d, e], f: g}\nb: [h:, i]\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a colon before a flow indicator ends the scalar, so `c` and `h` are keys'

    def test_event_stream_with_explicit_empty_keys_matches_pyyaml(self) -> None:
        #: Given
        block = '? \n: x\n? [a]\n: y\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a key written as `?` and nothing reads as the same events'

    def test_event_stream_with_non_ascii_text_matches_pyyaml(self) -> None:
        #: Given
        block = 'título: café ☕\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'non-ASCII keys and values read as the same events'

    def test_event_stream_with_a_scalar_document_matches_pyyaml(self) -> None:
        #: Given
        block = 'just text\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a document that is one scalar reads as the same events'

    def test_event_stream_with_an_empty_block_matches_pyyaml(self) -> None:
        #: Given
        block = ''

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'an empty block reads as the same events'

    def test_event_stream_with_a_comment_only_block_matches_pyyaml(self) -> None:
        #: Given
        block = '# nothing\n'

        #: When
        same = reads_same_events(block)

        #: Then
        assert same, 'a block of one comment reads as the same events'


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


@pytest.mark.it
class TestEmptyValueParity:
    def test_decode_frontmatter_with_an_empty_value_before_blank_lines_returns_each_key_on_its_line(self) -> None:
        #: Given
        # ruamel.yaml marks the empty value of `kind:` on line 4, the next token, and PyYAML on line 1.
        block = 'name: guide\nkind:\n\n\ntype: rule\n'

        #: When
        node = decode_frontmatter(block)

        #: Then
        assert isinstance(node, Frontmatter), f'a value written as nothing is null, got {node!r}'
        assert node.data == FrozenMapping({'name': 'guide', 'kind': None, 'type': 'rule'}), 'the value is null'
        assert [key.line.number for key in node.keys] == [2, 3, 6], 'only a key marks a line, so none moved'

    def test_decode_frontmatter_with_a_tag_on_an_empty_value_reports_the_tag_line_pyyaml_marks(self) -> None:
        #: Given
        block = 'name: guide\nkind: !!str\n\n\ntype: rule\n'
        tag_events = [event for event in pyyaml_events(block) if event[0] == 'ScalarEvent' and event[4] is not None]

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert tag_events[0][5] == 1, 'PyYAML marks the empty value on its tag, not on the next token'
        assert reported == ("found the tag '!!str', which frontmatter does not allow", 1), (
            'the refusal is on the tag line, which is where the empty value starts'
        )

    def test_decode_frontmatter_with_an_anchor_on_an_empty_value_reports_the_anchor_line_pyyaml_marks(self) -> None:
        #: Given
        block = 'name: guide\nkind: &k\n\n\ntype: rule\n'
        anchor_events = [event for event in pyyaml_events(block) if event[0] == 'ScalarEvent' and event[3] is not None]

        #: When
        reported = frontmatter_error(block)

        #: Then
        assert anchor_events[0][5] == 1, 'PyYAML marks the empty value on its anchor, not on the next token'
        assert reported == ('found the anchor &k, which frontmatter does not allow', 1), (
            'the refusal is on the anchor line, which is where the empty value starts'
        )
