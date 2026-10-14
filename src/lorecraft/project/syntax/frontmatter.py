"""The frontmatter node of a document's parse tree: the decoded YAML mapping and where each key sits.

A document's frontmatter is a `---` delimited block on its first lines. Finding the block is the Markdown
parser's job (see `document`); decoding it is this module's. Parsing has exactly four outcomes, one type each:
no block, a block that is not YAML, a block that is YAML but not a mapping, and a mapping. Every outcome is a
value, never an exception, because a broken block is a fact about the document that a check reports, not a
failure of the parse.

The block is read as basic YAML, which decodes to exactly what JSON can hold, and accepts only these constructs:

- the block itself is one block mapping, one key to a line, whose keys are plain, single-quoted or double-quoted
  scalars that read as strings;
- a value is any accepted node, or nothing, which is null; a block mapping nested as a value is indented by spaces;
- a block sequence is a value, indented or not, and its items are scalars, flow collections or block mappings;
- a flow sequence or a flow mapping is written on one line and holds only scalars, or nothing;
- a plain scalar is written on one line or continued on more indented lines; a single-quoted scalar writes `''`
  for a quote and a double-quoted one takes YAML's escapes, both on one or more lines;
- a literal (`|`) or folded (`>`) block scalar takes an optional `-` or `+` chomping indicator;
- a comment, on its own line or after a node, blank lines, CRLF line breaks and a BOM before the first line are
  nothing.

A quoted or block scalar is a string. A plain scalar is null,
a boolean, an integer or a float when its whole text is one in YAML 1.2's core schema, such as `~`, `true`, `12` or
`1.5`, and a string otherwise, so `yes`, `2026-10-05` and `1:30` are strings. A directive, a document marker, an
anchor, an alias, a merge key, a tag, an explicit or empty key, a key that is not a string, a flow collection
that spreads over lines, holds a collection or is the whole block, a block scalar's indentation indicator and a
block sequence as an item of a block sequence are refused, on their line, as a block that is not YAML: none is
needed to write a document's metadata, an alias can make a collection hold itself, a tag builds values JSON has no
counterpart for, and JSON names every key with a string.
"""

import math
import re
import sys
from bisect import bisect_left
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Final, Never, assert_never

from ruamel.yaml import YAML
from ruamel.yaml.compat import check_anchorname_char
from ruamel.yaml.error import MarkedYAMLError, StreamMark
from ruamel.yaml.events import (
    AliasEvent,
    Event,
    MappingEndEvent,
    MappingStartEvent,
    ScalarEvent,
    SequenceEndEvent,
    SequenceStartEvent,
    StreamEndEvent,
)
from ruamel.yaml.parser import Parser
from ruamel.yaml.reader import Reader, ReaderError
from ruamel.yaml.resolver import VersionedResolver
from ruamel.yaml.scanner import Scanner, ScannerError
from ruamel.yaml.tag import Tag
from ruamel.yaml.tokens import ScalarToken, TagToken, Token

from lorecraft.core.error import Error
from lorecraft.core.lines import newline_offsets
from lorecraft.core.mapping import Frozen, FrozenMapping

from .position import LineNumber
from .syntax_error import SyntaxProblem, describe_control_character, describe_error, yaml_line_starts

_FIRST_BLOCK_LINE: Final[int] = 2
"""The document line the block's first YAML line sits on: the opening delimiter is always line 1."""

_NULL_WORDS: Final[frozenset[str]] = frozenset({'', '~', 'null', 'Null', 'NULL'})
"""The plain scalars YAML 1.2's core schema reads as null; the empty one is a key or an item written with no value."""

_TRUE_WORDS: Final[frozenset[str]] = frozenset({'true', 'True', 'TRUE'})
"""The plain scalars YAML 1.2's core schema reads as true."""

_FALSE_WORDS: Final[frozenset[str]] = frozenset({'false', 'False', 'FALSE'})
"""The plain scalars YAML 1.2's core schema reads as false."""

_DECIMAL_INT: Final[re.Pattern[str]] = re.compile(r'[-+]?[0-9]+')
"""A plain scalar YAML 1.2's core schema reads as a decimal integer. A leading zero does not make it octal."""

_OCTAL_INT: Final[re.Pattern[str]] = re.compile(r'0o[0-7]+')
"""A plain scalar YAML 1.2's core schema reads as an octal integer."""

_HEX_INT: Final[re.Pattern[str]] = re.compile(r'0x[0-9a-fA-F]+')
"""A plain scalar YAML 1.2's core schema reads as a hexadecimal integer."""

_FLOAT: Final[re.Pattern[str]] = re.compile(r'[-+]?(\.[0-9]+|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?')
"""A plain scalar YAML 1.2's core schema reads as a float. It matches every decimal integer too, so the integer
patterns are tried first. The core schema's `.inf` and `.nan` are left out: JSON has no number for either."""

_MERGE_KEY: Final[str] = '<<'
"""The plain key YAML 1.1 reads as a merge: the entries of the mapping an alias names join the mapping."""

_NOT_ALLOWED: Final[str] = 'which frontmatter does not allow'
"""How the problem of a refused construct ends: `found <construct>, which frontmatter does not allow`."""

_SPACE_CHARACTERS: Final[str] = '\0 \t\r\n\x85\u2028\u2029'
"""The characters that end a plain scalar: the end of the text, a space or tab, or a line break."""

_LINE_END_CHARACTERS: Final[str] = '\0\r\n\x85\u2028\u2029'
"""The characters that end a line: the end of the text, or a line break."""

_TOKEN_END_CHARACTERS: Final[str] = _SPACE_CHARACTERS + ',[]{}'
"""The characters that end an anchor, an alias or a tag as a block writes it: whitespace or a flow indicator."""

_DIRECTIVE_NAME_END_CHARACTERS: Final[str] = _SPACE_CHARACTERS + ',[]{}:'
"""The characters that end the name a refused directive is reported by: whitespace, a flow indicator or a `:`."""


@dataclass(frozen=True, slots=True)
class FrontmatterKey:
    """One key of a frontmatter mapping, at any depth, and the line it is written on.

    Attributes:
        name: The key as YAML decoded it.
        line: The document line the key starts on.
    """

    name: str
    line: LineNumber


@dataclass(frozen=True, slots=True)
class RepeatedKey:
    """A key a mapping writes again after its first occurrence, at any depth.

    Attributes:
        name: The key as YAML decoded it.
        line: The document line this later occurrence is written on.
        first_line: The line the mapping's first occurrence of the key is written on.
        kept_line: The line of the mapping's last occurrence, whose value the data holds.
    """

    name: str
    line: LineNumber
    first_line: LineNumber
    kept_line: LineNumber


@dataclass(frozen=True, slots=True)
class Frontmatter:
    """A frontmatter block that decoded to a YAML mapping.

    Every key in it is a string, at any depth: a block writing any other key, such as `1:` or `true:`, does not
    decode to frontmatter at all, so no check ever meets a key a JSON Schema cannot name.

    Attributes:
        data: The decoded mapping, frozen all the way down: every mapping in it is a `FrozenMapping`, every list a
            tuple, and every scalar a string, an integer, a float, a boolean or `None`, which is what `json.loads`
            would build for the same data, frozen. So no check can write to it, at any depth, although the parse tree
            is shared by every check that reads the document.
        keys: Every top-level key the mapping writes, in document order, with its line. A key written more than
            once appears once per occurrence, although `data` holds only one value for it.
        repeats: Every key written again within one mapping, at any depth, in document order: one per occurrence after
            the first, which is the line it points back at. The last occurrence's value is the one `data` holds.
    """

    data: FrozenMapping[str, Frozen]
    keys: tuple[FrontmatterKey, ...]
    repeats: tuple[RepeatedKey, ...] = ()

    def find_key_line(self, name: str) -> LineNumber | None:
        """The line the last top-level key called `name` is written on, or `None` when there is none.

        The last, because a key written twice decodes to the value of its last occurrence, so the last line is
        where the value in `data` is written.

        Args:
            name: Key to look up, spelled as written.
        """
        line: LineNumber | None = None
        for key in self.keys:
            if key.name == name:
                line = key.line
        return line


@dataclass(frozen=True, slots=True)
class MissingFrontmatter:
    """The document does not open with a ``---`` line, or the block is never closed by one."""


@dataclass(frozen=True, slots=True)
class InvalidYamlFrontmatter:
    """The block is there but is not valid YAML, or uses YAML beyond the basic subset frontmatter is read as.

    A value, compared by value, so it holds the parser's facts rather than the parser's exception, which compares
    by identity.

    Attributes:
        problem: What is wrong, in lorecraft's words, such as `this value holds `: ``, or `found the tag '!!str',
            which frontmatter does not allow` where the block uses what basic YAML leaves out, a key that is not a
            string included.
        help: What to do about it, where a syntax error has a fix to name, and None for a construct frontmatter
            does not allow, which the problem already names.
        line: The document line the problem is on, or None when it cannot be known: when the parser does not say,
            or when the block nests collections too deeply, where reading stops at whatever depth the interpreter's
            stack allows rather than at a line of the document.
    """

    problem: str
    line: LineNumber | None
    help: str | None = None


@dataclass(frozen=True, slots=True)
class NonMappingFrontmatter:
    """The block is valid YAML, but it decodes to something other than a mapping, such as a list or nothing."""


type FrontmatterNode = Frontmatter | MissingFrontmatter | InvalidYamlFrontmatter | NonMappingFrontmatter
"""Every outcome of parsing a document's frontmatter."""

type _Entry = tuple[FrontmatterKey, Frozen]
"""One pair of a mapping as it is written: the key, with its line, and the decoded value."""


class _RecordedConstruct(Enum):
    """The constructs the scanner records without stopping, each with how the problem names it."""

    EXPLICIT_KEY = 'an explicit key'
    EMPTY_KEY = 'an empty key'
    INDENTATION_INDICATOR = 'a block scalar indentation indicator'
    SPREAD_FLOW_COLLECTION = 'a flow collection spread over lines'


@dataclass(frozen=True, slots=True)
class _RecordedRefusal:
    """A construct frontmatter leaves out, which the scanner met and recorded without stopping.

    Attributes:
        construct: Which construct it is.
        mark: Where it is written.
    """

    construct: _RecordedConstruct
    mark: StreamMark

    @property
    def problem(self) -> str:
        """The problem as `FM002` words it, `found <construct>, which frontmatter does not allow`."""
        return f'found {self.construct.value}, {_NOT_ALLOWED}'


class _RefusedConstructError(Error):
    """What the constructs refused where the block is read have in common. It is never raised itself.

    `decode_frontmatter` catches this class to place the construct against the ones the scanner recorded; each
    subclass is raised for one construct and words its own problem.

    Attributes:
        mark: Where the construct is written.
        problem: The problem as `FM002` words it.
    """

    mark: StreamMark
    problem: str

    def __init__(self, mark: StreamMark, problem: str) -> None:
        self.mark = mark
        self.problem = problem
        super().__init__(problem)


class _RefusedDirectiveError(_RefusedConstructError):
    """The block holds a directive, a `%` line.

    Attributes:
        name: The `%` and the name that follows it.
    """

    name: str

    def __init__(self, name: str, mark: StreamMark) -> None:
        self.name = name
        super().__init__(mark, f'found the directive {name}, {_NOT_ALLOWED}')


class _RefusedDocumentMarkerError(_RefusedConstructError):
    """The block writes a `---` or `...` marker, though it is the body of one document.

    Attributes:
        marker: The three characters of the marker.
    """

    marker: str

    def __init__(self, marker: str, mark: StreamMark) -> None:
        self.marker = marker
        super().__init__(mark, f'found the document marker {marker}, {_NOT_ALLOWED}')


class _RefusedAliasError(_RefusedConstructError):
    """A value is an alias.

    Attributes:
        anchor: The anchor's name, without the `*`.
    """

    anchor: str

    def __init__(self, anchor: str, mark: StreamMark) -> None:
        self.anchor = anchor
        super().__init__(mark, f'found the alias *{anchor}, {_NOT_ALLOWED}')


class _RefusedAnchorError(_RefusedConstructError):
    """A value carries an anchor.

    Attributes:
        anchor: The anchor's name, without the `&`.
    """

    anchor: str

    def __init__(self, anchor: str, mark: StreamMark) -> None:
        self.anchor = anchor
        super().__init__(mark, f'found the anchor &{anchor}, {_NOT_ALLOWED}')


class _RefusedTagError(_RefusedConstructError):
    """A value carries a tag, the non-specific `!` included.

    Attributes:
        tag: The tag as the block writes it.
    """

    tag: str

    def __init__(self, tag: str, mark: StreamMark) -> None:
        self.tag = tag
        super().__init__(mark, f'found the tag {tag!r}, {_NOT_ALLOWED}')


class _RefusedMalformedTagError(_RefusedConstructError):
    """A tag the scanner cannot read.

    That is a tag such as a verbatim tag left open or empty, a bad `%` escape, or a tag with no space after it.

    Attributes:
        tag: The tag as the block writes it.
        source: The scanner's error.
    """

    tag: str
    source: ScannerError

    def __init__(self, tag: str, mark: StreamMark, *, source: ScannerError) -> None:
        self.tag = tag
        self.source = source
        super().__init__(mark, f'found the tag {tag!r}, {_NOT_ALLOWED}')
        self.__cause__ = source


class _RefusedMergeKeyError(_RefusedConstructError):
    """A mapping writes the plain key `<<`, which YAML 1.1 reads as a merge."""

    def __init__(self, mark: StreamMark) -> None:
        super().__init__(mark, f'found the merge key {_MERGE_KEY}, {_NOT_ALLOWED}')


class _RefusedCollectionKeyError(_RefusedConstructError):
    """A mapping's key is a collection, not a string."""

    def __init__(self, mark: StreamMark) -> None:
        super().__init__(mark, f'found a collection as a key, {_NOT_ALLOWED}')


class _RefusedNonStringKeyError(_RefusedConstructError):
    """A mapping's key is a scalar that decodes to null, a boolean or a number, not a string.

    Attributes:
        key: The key as written, which is empty for a key written as nothing at all.
    """

    key: str

    def __init__(self, key: str, mark: StreamMark) -> None:
        self.key = key
        super().__init__(mark, f'found the non-string key {key}, {_NOT_ALLOWED}')


class _RefusedFlowBlockError(_RefusedConstructError):
    """The whole block is a flow collection, not a block mapping."""

    def __init__(self, mark: StreamMark) -> None:
        super().__init__(mark, f'found a flow collection as the block, {_NOT_ALLOWED}')


class _RefusedFlowNestedCollectionError(_RefusedConstructError):
    """A flow collection holds a collection."""

    def __init__(self, mark: StreamMark) -> None:
        super().__init__(mark, f'found a collection inside a flow collection, {_NOT_ALLOWED}')


class _RefusedNestedBlockSequenceError(_RefusedConstructError):
    """A block sequence holds a block sequence as an item."""

    def __init__(self, mark: StreamMark) -> None:
        super().__init__(mark, f'found a block sequence as an item of a block sequence, {_NOT_ALLOWED}')


class _RefusedEscapeError(_RefusedConstructError):
    """A double-quoted escape names a code point above `U+10FFFF`, which `chr` cannot build.

    Attributes:
        source: The failure `chr` raised.
    """

    source: ValueError | OverflowError

    def __init__(self, mark: StreamMark, *, source: ValueError | OverflowError) -> None:
        self.source = source
        super().__init__(mark, f'found an escape that names no Unicode character, {_NOT_ALLOWED}')
        self.__cause__ = source


def decode_frontmatter(block: str) -> FrontmatterNode:
    """Decode the YAML between a document's `---` delimiters into its node. Pure: raises nothing.

    Never `MissingFrontmatter`: whether a block exists is decided before this is called. Every block the YAML
    parser cannot parse is `InvalidYamlFrontmatter`, including the few it fails on with a plain Python exception
    rather than its own error, and so is every block that uses a directive, a document marker, an anchor, an
    alias, a merge key or a tag, writes a key, at any depth, that is not a string, such as `1:`, `true:` or `null:`,
    or nests collections too deeply to read.

    Args:
        block: The lines between the delimiters, line endings kept; the first of them is document line 2.
    """
    stream = _EventStream(block)
    try:
        node = _read_document(stream)
    except ReaderError as exc:
        # The reader checks every character as it is built, so a control character fails before the first event.
        return _invalid_yaml(describe_control_character(exc, block), stream)
    except _RefusedConstructError as exc:
        # The read stopped at a construct this module refuses. The scanner reads ahead of the parser, so it may
        # have recorded one written above it, which is the one the block is reported for.
        refusal = stream.first_refusal()
        if refusal is not None and refusal.mark.index <= exc.mark.index:
            return _invalid_refusal(refusal, stream)
        return _invalid_refusal(exc, stream)
    except MarkedYAMLError as exc:
        # Every other `MarkedYAMLError` is ruamel.yaml's own. The scanner reads ahead of the parser, so a construct
        # it recorded is written above whatever the parser or the scanner failed on.
        refusal = stream.first_refusal()
        if refusal is not None:
            return _invalid_refusal(refusal, stream)
        return _invalid_yaml(describe_error(exc, block), stream)
    except RecursionError:
        # The value is read with one call per level of nesting, so only a deeply nested block reaches the
        # interpreter's limit. By the time this clause runs the stack has unwound to this frame, so there is room
        # to go on, and the half-read parser is dropped. The line is left out, because the depth reading stops at
        # depends on the interpreter's recursion limit and on how deep the caller's stack already was. A construct
        # the scanner recorded above the depth is reported instead, on its line.
        refusal = stream.first_refusal()
        if refusal is not None:
            return _invalid_refusal(refusal, stream)
        return InvalidYamlFrontmatter(problem='found collections nested too deeply to parse', line=None)
    # The block was read to its end, so every construct the scanner recorded is written above the end.
    refusal = stream.first_refusal()
    if refusal is not None:
        return _invalid_refusal(refusal, stream)
    return node


def reads_back_as_string(text: str) -> bool:
    """Whether a frontmatter field written as `text` without quotes decodes to that same string.

    It goes through `decode_frontmatter`, so the answer is the one the frontmatter reader gives: `1.0`, `true`,
    `0o17` and `1e3` read back as another value, and so does an empty text or one that is not YAML at all.

    Args:
        text: The text to write after `field: `.
    """
    node = decode_frontmatter(f'field: {text}\n')
    match node:
        case Frontmatter():
            return node.data.get('field') == text
        case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
            return False
        case _:
            assert_never(node)


class _EventStream:
    """The events of a block, read lazily, one at a time, with one event of lookahead.

    The events come from ruamel.yaml's pure-Python reader, scanner and parser. The value is built from them by this
    module, never by ruamel.yaml's loader or constructor, so no tag ruamel.yaml resolves and no type it constructs
    is ever involved. They are read lazily, so a block that fails stops being read where it fails, and the constructs
    the scanner recorded by then are the ones written above the failure.
    """

    def __init__(self, block: str) -> None:
        """Start reading `block`. No character is read until the first event is asked for.

        Args:
            block: The YAML text to parse.
        """
        # Setting the reader and the scanner already selects the pure parser; `pure` states the intent, so a
        # change in how ruamel.yaml chooses its parser cannot bring the C one, which has no reader of ours, in.
        yaml = YAML(typ='safe', pure=True)
        yaml.Reader = _BasicYamlReader
        yaml.Resolver = _BasicYamlResolver
        # PyYAML reads a top-level block scalar's content as indented, which ruamel.yaml does for YAML 1.1 only
        # when the loader says so.
        yaml.top_level_block_style_scalar_no_indent_error_1_1 = True
        yaml.Scanner = _BasicYamlScanner
        yaml.Parser = _BasicYamlParser
        self._block = block
        self._document_lines = _document_line_indexes(block)
        self._events: Iterator[Event] = iter(yaml.parse(block))
        self._peeked: Event | None = None
        self._yaml = yaml

    def peek_event(self) -> Event:
        """The next event, left unread.

        Raises:
            MarkedYAMLError: The block is not valid YAML.
            ReaderError: The block holds a character YAML does not allow, such as a control character.
        """
        if self._peeked is None:
            self._peeked = next(self._events)
        return self._peeked

    def document_line(self, block_line: int) -> LineNumber:
        r"""The document line a line of the block is.

        The reader counts a line at every YAML 1.1 break, which keeps its columns and marks agreeing with the text
        the parser reads. A finding is numbered by `\n`, as every other one is, so a line leaves the YAML layer here.

        Args:
            block_line: The line as the reader's mark counts it, from 0 at the block's first line.
        """
        # The block starts on document line 2, below the opening delimiter.
        return LineNumber.from_int(self._document_lines[block_line] + _FIRST_BLOCK_LINE)

    def first_refusal(self) -> _RecordedRefusal | None:
        """The first construct the scanner has recorded, in the order the block writes them, or `None`."""
        refusals: list[_RecordedRefusal] = self._yaml.scanner.refusals
        return refusals[0] if refusals else None

    def get_event(self) -> Event:
        """The next event, read.

        Raises:
            MarkedYAMLError: The block is not valid YAML.
            ReaderError: The block holds a character YAML does not allow, such as a control character.
        """
        event = self.peek_event()
        self._peeked = None
        return event

    def written_tag(self, event: ScalarEvent | SequenceStartEvent | MappingStartEvent) -> str:
        """The tag a node carries, spelled as the block writes it.

        The parser hands over a tag resolved against its handles, so `!!!str` arrives as the tag `!!str` and a tag
        in a flow collection can take the comma after it. The block's own text is what the author wrote.

        Args:
            event: The event of a node that carries a tag and no anchor. Its start mark is where the tag begins
                only then, because an anchor written first would start the node, so `_peek_node_start` refuses
                an anchor before it asks for the tag.
        """
        mark = event.start_mark
        if mark is None:
            # An event's mark is optional only in its constructor's signature: the parser marks every event it emits.
            raise AssertionError('unreachable: ruamel.yaml marks every event it parses')
        return _written_token(self._block, mark.index)

    def check_event(self, *kinds: type[Event]) -> bool:
        """Whether the next event is of one of `kinds`, leaving it unread.

        Args:
            kinds: The event classes to test for.
        """
        return isinstance(self.peek_event(), kinds)


def _written_token(text: str, start: int) -> str:
    """The anchor, alias or tag that starts at `start` in `text`, spelled as the block writes it.

    Args:
        text: The block, or the reader's buffer, which ends with a NUL.
        start: The index of the `&`, the `*` or the `!` the token starts with.
    """
    end = start
    if text.startswith('!<', start):
        # A verbatim tag is a URI, which may hold a `,` or a `]`, so it runs to its closing `>`, or to the end of the
        # line when it is never closed.
        while end < len(text) and text[end] not in _LINE_END_CHARACTERS and text[end] != '>':
            end += 1
        if end < len(text) and text[end] == '>':
            end += 1
    else:
        while end < len(text) and text[end] not in _TOKEN_END_CHARACTERS:
            end += 1
    return text[start:end]


class _AnyHandleMapping(dict[str, str]):
    """The tag handles a parser resolves a tag against, with every handle defined: an unknown one stands for itself."""

    def __contains__(self, handle: object) -> bool:
        return True

    def __missing__(self, handle: str) -> str:
        return handle


class _BasicYamlParser(Parser):
    """ruamel.yaml's parser, taking a tag whose handle no directive defines as it takes `!` and `!!`.

    A directive is the only way to define a handle, and a directive is refused, so the parser would otherwise fail
    on `!e!x` with an error of its own, before `_peek_node_start` reaches the node, and report the tag ahead of a
    construct written above it. Taking every handle lets the tag reach that function as an event, refused in the
    order the block writes it, like `!!str`.
    """

    def select_tag_transform(self, tag: Tag) -> None:
        """Make the tag resolve against every handle.

        Args:
            tag: The tag of the node the parser is on.
        """
        super().select_tag_transform(tag)
        tag.handles = _AnyHandleMapping(tag.handles)


class _BasicYamlReader(Reader):
    """ruamel.yaml's reader, counting a next line character and a Unicode line or paragraph separator as a line."""

    def forward(self, length: int = 1) -> None:
        """Advance `length` characters, counting every YAML 1.1 line break as one line.

        Args:
            length: The number of characters to advance by.
        """
        # The column restarts at every YAML 1.1 break, which the scanner reads indentation from, so the line is
        # counted at each of them too: a mark's line and column then name one place in the block.
        # `_EventStream.document_line` turns that line into the document line a finding reports.
        self.forward_1_1(length)


class _BasicYamlResolver(VersionedResolver):
    """The resolver the scanner and parser ask which YAML version they read as, always 1.1."""

    @property
    def processing_version(self) -> tuple[int, int]:
        """The YAML version the scanner and parser read as."""
        # ruamel.yaml reads YAML 1.2 unless told otherwise, and the grammars accept different blocks:
        # 1.2 takes a key written as nothing, `: value`, and `?` inside a plain scalar, which PyYAML refuses. The
        # scalars are resolved by this module's own core schema rules, never by the resolver.
        return (1, 1)


class _BasicYamlScanner(Scanner):
    r"""ruamel.yaml's scanner, reading the YAML 1.1 grammar and failing with a `ScannerError`.

    A block is accepted or refused by the YAML 1.1 grammar, and a refusal names the problem and the line the scanner
    found it on.

    A directive and a document marker are refused at their indicator, before anything after it is read, so the
    block's own text never reaches ruamel.yaml's directive scanner, whose version number conversion raises a plain
    `ValueError` for more digits than Python converts to an `int`, 4300 by default. Those refusals are
    errors of lorecraft's own, not a `ScannerError`: `decode_frontmatter` reports them as they are worded, where
    it rewords the scanner's problems.

    An explicit key, an empty key, a flow collection spread over lines and a block scalar's indentation indicator
    are not refused where the scanner meets them. It records each in `refusals`, in the order the block writes them,
    for `decode_frontmatter` to report once the read ends or fails. The scanner reads ahead of the parser, so
    raising at once would report a construct written below a tag or an anchor before the tag or the anchor. It
    holds `_flow_start`, where the outermost open flow collection begins, to tell a collection spread over lines.

    An anchor or an alias with no name, and a tag the scanner cannot read, are refused here too, as the anchor, alias
    or tag they are. The tag's refusal is chained from the scanner's error.

    A double-quoted `\U` escape above `U+10FFFF` is the one other place a plain Python exception escapes: `chr`
    raises a `ValueError`, or an `OverflowError` for one too large for a C `int`. It is refused here, on the
    escape's line, as `decode_frontmatter` refuses every construct frontmatter does not allow.
    """

    def __init__(self, loader: object = None) -> None:
        """Start scanning outside any flow collection, with nothing recorded.

        Args:
            loader: The object ruamel.yaml's entry point passes in, which holds the reader.
        """
        super().__init__(loader)
        self._flow_start: StreamMark | None = None
        self.refusals: list[_RecordedRefusal] = []

    def fetch_directive(self) -> Never:
        """Refuse a directive, a `%` line, naming it by the `%` and the name that follows it.

        Raises:
            _RefusedDirectiveError: Always: frontmatter holds no directive.
        """
        start_mark = self.reader.get_mark()
        length = 1
        while self.reader.peek(length) not in _DIRECTIVE_NAME_END_CHARACTERS:
            length += 1
        raise _RefusedDirectiveError(self.reader.prefix(length), start_mark)

    def fetch_document_start(self) -> Never:
        """Refuse a `---` marker written inside the block.

        Raises:
            _RefusedDocumentMarkerError: Always: the block is the body of one document, whose delimiters are not part
                of it.
        """
        self._refuse_document_marker()

    def fetch_document_end(self) -> Never:
        """Refuse a `...` marker written inside the block.

        Raises:
            _RefusedDocumentMarkerError: Always: the block is the body of one document, whose delimiters are not part
                of it.
        """
        self._refuse_document_marker()

    def _refuse_document_marker(self) -> Never:
        """Refuse the three-character marker the reader is on.

        Raises:
            _RefusedDocumentMarkerError: Always: the marker is not allowed inside the block.
        """
        raise _RefusedDocumentMarkerError(self.reader.prefix(3), self.reader.get_mark())

    def scan_anchor(self, TokenClass: type[Token]) -> Token:
        """Scan an anchor or an alias, refusing one with no name as the anchor or alias it is.

        Args:
            TokenClass: The token to build, an anchor's or an alias's.

        Raises:
            _RefusedAnchorError: An anchor has no name, or a name with a character the scanner rejects.
            _RefusedAliasError: An alias has no name, or a name with a character the scanner rejects.
        """
        # The scanner ends a name at the first character `check_anchorname_char` rejects, such as U+FEFF, and fails
        # when that character is not one that may follow a name. The block's own spelling runs to the next token
        # end, so a character it rejects anywhere in it is the case the scanner would fail on.
        written = _written_token(self.reader.buffer, self.reader.pointer)
        name = written[1:]
        if not name or not all(check_anchorname_char(character) for character in name):
            start_mark = self.reader.get_mark()
            if written[0] == '*':
                raise _RefusedAliasError(name, start_mark)
            raise _RefusedAnchorError(name, start_mark)
        return super().scan_anchor(TokenClass)

    def scan_tag(self) -> TagToken:
        """Scan a tag, refusing one the scanner cannot read as the tag it is.

        Raises:
            _RefusedMalformedTagError: The scanner cannot read the tag, such as a verbatim tag left open or empty, a
                bad `%` escape, or a tag with no space after it.
        """
        start_mark = self.reader.get_mark()
        # The reader's buffer holds the whole block, ended by a NUL, and the pointer is where the tag starts.
        written = _written_token(self.reader.buffer, self.reader.pointer)
        try:
            return super().scan_tag()
        except ScannerError as exc:
            raise _RefusedMalformedTagError(written, start_mark, source=exc) from exc

    def fetch_key(self) -> None:
        """Fetch a `?` that starts a key, and record it as an explicit key where a node may start."""
        # The scanner's flow context takes every `?` for a key. A `?` that follows a scalar, as in `[what?]` and
        # `[what ? x]`, is part of a plain scalar in YAML 1.2, and the scanner has stopped allowing a node by then,
        # so it is left to the parser. After `[`, `{`, `,` or the start of a block line, a node may start.
        if self.allow_simple_key:
            self.refusals.append(_RecordedRefusal(_RecordedConstruct.EXPLICIT_KEY, self.reader.get_mark()))
        super().fetch_key()

    def fetch_value(self) -> None:
        """Fetch a `:`, and record it as an empty key when no key was written before it."""
        # The scanner saves the start of every scalar that may be a simple key, and `:` finds it. With none saved,
        # and a key allowed here, the key is written as nothing. Where a key is not allowed, as after `a: b`, the
        # scanner fails with its own problem, which is a syntax error of the value, not an empty key.
        if self.flow_level not in self.possible_simple_keys and (self.flow_level or self.allow_simple_key):
            self.refusals.append(_RecordedRefusal(_RecordedConstruct.EMPTY_KEY, self.reader.get_mark()))
        super().fetch_value()

    def fetch_flow_collection_start(self, TokenClass: type[Token], to_push: str) -> None:
        """Fetch a `[` or a `{`, remembering where the outermost flow collection opens.

        Args:
            TokenClass: The token to build, a sequence's or a mapping's start.
            to_push: The character the flow context records.
        """
        if self._flow_start is None:
            self._flow_start = self.reader.get_mark()
        super().fetch_flow_collection_start(TokenClass, to_push)

    def fetch_flow_collection_end(self, TokenClass: type[Token]) -> None:
        """Fetch a `]` or a `}`, forgetting where the outermost flow collection opened once it closes.

        Args:
            TokenClass: The token to build, a sequence's or a mapping's end.
        """
        super().fetch_flow_collection_end(TokenClass)
        if not self.flow_level:
            self._flow_start = None

    def scan_block_scalar_indicators(self, start_mark: StreamMark) -> tuple[bool | None, int | None]:
        """Scan a block scalar's chomping and indentation indicators, recording an indentation indicator.

        Args:
            start_mark: Where the scalar starts, for the scanner's own error messages.
        """
        chomping, increment = super().scan_block_scalar_indicators(start_mark)
        if increment is not None:
            self.refusals.append(_RecordedRefusal(_RecordedConstruct.INDENTATION_INDICATOR, start_mark))
        return chomping, increment

    def scan_flow_scalar_breaks(self, double: bool, start_mark: StreamMark) -> list[str]:
        """Scan the line breaks and blank lines inside a quoted scalar, refusing a marker that starts a line.

        Args:
            double: True for a double-quoted scalar; False for a single-quoted one.
            start_mark: Where the scalar starts, for the scanner's own error messages.

        Raises:
            _RefusedDocumentMarkerError: A line of the scalar starts with a `---` or `...` marker.
        """
        # ruamel.yaml refuses a marker on a continuation line itself, in its own words, and the format refuses
        # every marker the same way, so the loop is its own with that one check changed.
        chunks: list[str] = []
        while True:
            if self.reader.prefix(3) in ('---', '...') and self.reader.peek(3) in _SPACE_CHARACTERS:
                self._refuse_document_marker()
            while self.reader.peek() in ' \t':
                self.reader.forward()
            if self.reader.peek() not in '\r\n\x85\u2028\u2029':
                return chunks
            chunks.append(self.scan_line_break())

    # Where ruamel.yaml's scanner differs from PyYAML's, each method below is PyYAML's reading, because `FM002` has
    # always reported what PyYAML's scanner found: the same blocks refused, with the same problem on the same line.

    def scan_block_scalar_indentation(self) -> tuple[list[str], int, StreamMark]:
        """Scan the blank lines before a block scalar's text, and the widest indent among them.

        A blank line holding fewer spaces than the text's indent is accepted.
        """
        # ruamel.yaml raises "more indented follow up line than first in a block scalar" for a leading blank line
        # that holds spaces, which a block scalar written under an auto-indenting editor often has.
        chunks: list[str] = []
        max_indent = 0
        end_mark = self.reader.get_mark()
        while self.reader.peek() in ' \r\n\x85\u2028\u2029':
            if self.reader.peek() != ' ':
                chunks.append(self.scan_line_break())
                end_mark = self.reader.get_mark()
            else:
                self.reader.forward()
                max_indent = max(max_indent, self.reader.column)
        return chunks, max_indent, end_mark

    def scan_flow_scalar_non_spaces(self, double: bool, start_mark: StreamMark) -> list[str]:
        """Scan the text of a quoted scalar up to its next space.

        Args:
            double: True for a double-quoted scalar, whose backslash escapes are decoded; False for a single-quoted one.
            start_mark: Where the scalar starts, for the scanner's own error messages.

        Raises:
            _RefusedEscapeError: An escape names no Unicode character.
        """
        try:
            return super().scan_flow_scalar_non_spaces(double, start_mark)
        except (ValueError, OverflowError) as exc:
            # The scanner checks that an escape is written in hexadecimal, but not that the code point it names is
            # at most U+10FFFF, so `chr` raises: a ValueError for `\U00110000`, and for `\UFFFFFFFF`, which does not
            # fit a C int, an OverflowError on the interpreters that convert the argument first. Nothing else in
            # this method raises either. The scanner stops on the escape's digits, so its current mark is on the
            # escape's line.
            raise _RefusedEscapeError(self.reader.get_mark(), source=exc) from exc

    def scan_to_next_token(self) -> None:
        r"""Skip spaces, comments and line breaks to the next token; a tab is no whitespace, in a flow collection too.

        A tab is a character that cannot start a token, so `[a,\tb]` is refused. Where the next token is on a later
        line than the one the flow collection it is in opened on, the collection is recorded as a refusal.
        """
        # ruamel.yaml also skips a tab inside a flow collection, as YAML 1.2 allows, which PyYAML refuses.
        if self.reader.index == 0 and self.reader.peek() == '\ufeff':
            self.reader.forward()
        found = False
        while not found:
            while self.reader.peek() == ' ':
                self.reader.forward()
            if self.reader.peek() == '#':
                while self.reader.peek() not in _LINE_END_CHARACTERS:
                    self.reader.forward()
            if self.scan_line_break():
                if not self.flow_level:
                    self.allow_simple_key = True
            else:
                found = True
        # The next token is the first thing the collection holds on a line below the one it opened on, or the end of
        # the block, where an unclosed one stops. A construct written between the opening and the line break, such as
        # the tag of `a: [b, !x c,` / `  d]`, was recorded or met before this point, so it is reported first, on the
        # same line.
        if self._flow_start is not None and self.reader.line != self._flow_start.line:
            # This runs for every token below the opening line, and the collection is refused once.
            if not any(refusal.mark is self._flow_start for refusal in self.refusals):
                self.refusals.append(_RecordedRefusal(_RecordedConstruct.SPREAD_FLOW_COLLECTION, self._flow_start))

    def scan_plain(self) -> ScalarToken:
        """Scan a plain scalar, which ends at a `:` before a flow indicator inside a flow collection."""
        # ruamel.yaml keeps such a `:` in the scalar, so `{c:[d]}` and `[a:, b]` read differently: PyYAML reads
        # `c` and `a` as keys.
        chunks: list[str] = []
        start_mark = self.reader.get_mark()
        end_mark = start_mark
        indent = self.indent + 1
        spaces: list[str] = []
        while True:
            length = 0
            if self.reader.peek() == '#':
                break
            while True:
                ch = self.reader.peek(length)
                colon_ends_scalar = ch == ':' and self.reader.peek(length + 1) in (
                    _SPACE_CHARACTERS + (',[]{}' if self.flow_level else '')
                )
                flow_indicator = self.flow_level and ch in ',[]{}'
                if ch in _SPACE_CHARACTERS or colon_ends_scalar or flow_indicator:
                    break
                length += 1
            if length == 0:
                break
            self.allow_simple_key = False
            chunks.extend(spaces)
            chunks.append(self.reader.prefix(length))
            self.reader.forward(length)
            end_mark = self.reader.get_mark()
            spaces = self.scan_plain_spaces(indent, start_mark)
            if not spaces or self.reader.peek() == '#' or (not self.flow_level and self.reader.column < indent):
                break
        return ScalarToken(''.join(chunks), True, start_mark, end_mark)


def _invalid_refusal(
    refusal: _RecordedRefusal | _RefusedConstructError, stream: _EventStream
) -> InvalidYamlFrontmatter:
    """The facts about a block that writes a construct frontmatter leaves out: the problem, and its line.

    Args:
        refusal: The construct, as the scanner recorded it or as the read stopped on it.
        stream: The block's events, which turns the construct's line into a document line.
    """
    return InvalidYamlFrontmatter(problem=refusal.problem, line=stream.document_line(refusal.mark.line))


def _mark_of(event: Event) -> StreamMark:
    """Where an event starts.

    Args:
        event: An event the parser emitted.
    """
    mark = event.start_mark
    if mark is None:
        # An event's mark is optional only in its constructor's signature: the parser marks every event it emits.
        raise AssertionError('unreachable: ruamel.yaml marks every event it parses')
    return mark


def _read_document(parser: _EventStream) -> Frontmatter | NonMappingFrontmatter:
    """Read the block's one document, if any, and decode it.

    Every value is read to its end even when the document is not a mapping, so a refused construct or a syntax
    error anywhere in the block is reported rather than hidden behind the document's shape.

    Args:
        parser: The block's parser, before its first event is read.

    Raises:
        MarkedYAMLError: The block is not valid YAML.
        _RefusedConstructError: The block uses what basic YAML leaves out; the subclass names what.
    """
    parser.get_event()  # The stream's start.
    if parser.check_event(StreamEndEvent):
        # An empty block, or one holding only comments, has no document at all.
        return NonMappingFrontmatter()
    parser.get_event()  # The document's start.
    first = _peek_node_start(parser)
    if isinstance(first, SequenceStartEvent | MappingStartEvent) and first.flow_style:
        raise _RefusedFlowBlockError(_mark_of(first))
    repeats: list[RepeatedKey] = []
    if isinstance(first, MappingStartEvent):
        entries = _read_mapping(parser, first, repeats)
        # An inner mapping ends before the one that holds it, so its repeats came first; document order is by line.
        in_document_order = tuple(sorted(repeats, key=lambda repeat: repeat.line.number))
        node: Frontmatter | NonMappingFrontmatter = Frontmatter(
            data=_to_mapping(entries), keys=_keys(entries), repeats=in_document_order
        )
    else:
        _read_value(parser, repeats)
        node = NonMappingFrontmatter()
    parser.get_event()  # The document's end.
    if not parser.check_event(StreamEndEvent):
        # A second document starts with a `---` or a `...` marker, which the scanner refuses where it stands.
        raise AssertionError('unreachable: the scanner refuses every document marker')
    return node


def _peek_node_start(parser: _EventStream) -> ScalarEvent | SequenceStartEvent | MappingStartEvent:
    """The event the next value starts with, left unread, once it is known to use nothing basic YAML leaves out.

    Args:
        parser: The parser, whose next event starts a value.

    Raises:
        _RefusedAliasError: The value is an alias, marked where it is written.
        _RefusedAnchorError: The value carries an anchor, marked where it is written.
        _RefusedTagError: The value carries a tag, marked where it is written.
    """
    event = parser.peek_event()
    if isinstance(event, AliasEvent):
        raise _RefusedAliasError(event.anchor, _mark_of(event))
    if not isinstance(event, ScalarEvent | SequenceStartEvent | MappingStartEvent):
        # Only an end event or a document event is left, and the parser never gives one where a value starts.
        raise AssertionError(f'unreachable: {type(event).__name__} where a value starts')
    if event.anchor is not None:
        raise _RefusedAnchorError(event.anchor, _mark_of(event))
    # The parser gives an event a tag only when one is written in the block, the non-specific `!` included.
    if event.tag is not None:
        raise _RefusedTagError(parser.written_tag(event), _mark_of(event))
    return event


def _read_value(parser: _EventStream, repeats: list[RepeatedKey]) -> Frozen:
    """Read one value and everything in it, and decode it frozen: to a `FrozenMapping`, a tuple or a scalar.

    Args:
        parser: The parser, whose next event starts the value.
        repeats: The keys written again so far in the document, which the mappings in the value add to.

    Raises:
        MarkedYAMLError: The value is not valid YAML.
        _RefusedConstructError: The value uses what basic YAML leaves out; the subclass names what.
    """
    event = _peek_node_start(parser)
    if isinstance(event, MappingStartEvent):
        return _to_mapping(_read_mapping(parser, event, repeats))
    if isinstance(event, SequenceStartEvent):
        return _read_sequence(parser, event, repeats)
    parser.get_event()
    return _scalar_value(event)


def _read_mapping(parser: _EventStream, start: MappingStartEvent, repeats: list[RepeatedKey]) -> list[_Entry]:
    """Read one mapping, every pair in the order it is written, a repeated key once per occurrence.

    The keys it and the mappings inside it write again are added to `repeats`, those of the inner ones first.

    Args:
        parser: The parser, whose next event starts the mapping.
        start: The event that starts it, which says whether it is written in flow style.
        repeats: The keys written again so far in the document, which this call adds to.

    Raises:
        MarkedYAMLError: The mapping is not valid YAML.
        _RefusedConstructError: A key is not a string, or the mapping uses what basic YAML leaves out; the subclass
            names what.
    """
    parser.get_event()  # The mapping's start.
    entries: list[_Entry] = []
    while not parser.check_event(MappingEndEvent):
        key = _read_key(parser)
        _refuse_nested_collection(parser, start)
        value = _read_value(parser, repeats)
        entries.append((key, value))
    parser.get_event()  # The mapping's end.
    repeats.extend(_repeats(entries))
    return entries


def _read_sequence(parser: _EventStream, start: SequenceStartEvent, repeats: list[RepeatedKey]) -> tuple[Frozen, ...]:
    """Read one sequence, every item in the order it is written, as a tuple, the sequence that cannot change.

    Args:
        parser: The parser, whose next event starts the sequence.
        start: The event that starts it, which says whether it is written in flow style.
        repeats: The keys written again so far in the document, which the mappings among its items add to.

    Raises:
        MarkedYAMLError: An item is not valid YAML.
        _RefusedConstructError: An item uses what basic YAML leaves out; the subclass names what.
    """
    parser.get_event()  # The sequence's start.
    items: list[Frozen] = []
    while not parser.check_event(SequenceEndEvent):
        _refuse_nested_collection(parser, start)
        items.append(_read_value(parser, repeats))
    parser.get_event()  # The sequence's end.
    return tuple(items)


def _read_key(parser: _EventStream) -> FrontmatterKey:
    """Read one key of a mapping, which must be a scalar that decodes to a string.

    Args:
        parser: The parser, whose next event starts the key.

    Raises:
        _RefusedCollectionKeyError: The key is a collection.
        _RefusedNonStringKeyError: The key is a scalar that decodes to something other than a string.
        _RefusedMergeKeyError: The key is the plain merge key.
        _RefusedAliasError: The key is an alias.
        _RefusedAnchorError: The key carries an anchor.
        _RefusedTagError: The key carries a tag.
    """
    event = _peek_node_start(parser)
    if not isinstance(event, ScalarEvent):
        raise _RefusedCollectionKeyError(_mark_of(event))
    parser.get_event()
    name = _scalar_value(event)
    mark = _mark_of(event)
    if not isinstance(name, str):
        raise _RefusedNonStringKeyError(event.value, mark)
    if event.style is None and name == _MERGE_KEY:
        # A plain `<<` is YAML 1.1's merge key, which pulls in the entries of the mapping an alias names.
        raise _RefusedMergeKeyError(mark)
    return FrontmatterKey(name=name, line=parser.document_line(mark.line))


def _refuse_nested_collection(parser: _EventStream, parent: SequenceStartEvent | MappingStartEvent) -> None:
    """Refuse the next value when it is a collection `parent` does not hold.

    A flow collection holds no collection, and a block sequence holds no block sequence. A block mapping is the item
    a block sequence of records is made of, and a flow collection is one line of scalars, so those stay.

    Args:
        parser: The parser, whose next event starts a value of `parent`.
        parent: The event that started the collection the value belongs to.

    Raises:
        _RefusedFlowNestedCollectionError: The value is a collection inside a flow collection.
        _RefusedNestedBlockSequenceError: The value is a block sequence that is an item of a block sequence.
    """
    event = _peek_node_start(parser)
    if not isinstance(event, SequenceStartEvent | MappingStartEvent):
        return
    if parent.flow_style:
        raise _RefusedFlowNestedCollectionError(_mark_of(event))
    if isinstance(parent, SequenceStartEvent) and isinstance(event, SequenceStartEvent) and not event.flow_style:
        raise _RefusedNestedBlockSequenceError(_mark_of(event))


def _scalar_value(event: ScalarEvent) -> str | int | float | bool | None:
    """What a scalar decodes to: its text, unless it is plain and its whole text is a core schema null, bool or number.

    Args:
        event: The scalar's event, which carries no tag.
    """
    text: str = event.value
    # A quoted scalar, and a literal `|` or folded `>` block, has a style; only a plain one is resolved.
    if event.style is not None:
        return text
    if text in _NULL_WORDS:
        return None
    if text in _TRUE_WORDS:
        return True
    if text in _FALSE_WORDS:
        return False
    if _OCTAL_INT.fullmatch(text):
        return int(text.removeprefix('0o'), 8)
    if _HEX_INT.fullmatch(text):
        return int(text.removeprefix('0x'), 16)
    # `int` refuses more decimal digits than the interpreter's integer string conversion limit, 4300 by default,
    # so a longer integer stays the text it is written as. The octal and hexadecimal conversions have no limit.
    if _DECIMAL_INT.fullmatch(text):
        if len(text.lstrip('+-')) > sys.get_int_max_str_digits():
            return text
        return int(text)
    if _FLOAT.fullmatch(text):
        number = float(text)
        # An exponent past what a float holds converts to infinity, which JSON has no number for, so the scalar
        # stays the text it is written as, like `.inf`.
        if not math.isinf(number):
            return number
    return text


def _to_mapping(entries: list[_Entry]) -> FrozenMapping[str, Frozen]:
    """The mapping the pairs decode to: a key written more than once holds the value of its last occurrence.

    Args:
        entries: The mapping's pairs, in the order they are written.
    """
    mapping: dict[str, Frozen] = {}
    for key, value in entries:
        mapping[key.name] = value
    return FrozenMapping(mapping)


def _repeats(entries: list[_Entry]) -> list[RepeatedKey]:
    """The keys the mapping writes again, one per occurrence after the first, in the order they are written.

    Args:
        entries: The mapping's pairs, in the order they are written.
    """
    first_lines: dict[str, LineNumber] = {}
    last_lines: dict[str, LineNumber] = {}
    for key, _value in entries:
        first_lines.setdefault(key.name, key.line)
        last_lines[key.name] = key.line
    seen: set[str] = set()
    repeats: list[RepeatedKey] = []
    for key, _value in entries:
        if key.name in seen:
            repeats.append(RepeatedKey(key.name, key.line, first_lines[key.name], last_lines[key.name]))
        seen.add(key.name)
    return repeats


def _keys(entries: list[_Entry]) -> tuple[FrontmatterKey, ...]:
    """Every key of the mapping, in the order it is written, a repeated key once per occurrence.

    Args:
        entries: The mapping's pairs, in the order they are written.
    """
    keys: list[FrontmatterKey] = []
    for key, _value in entries:
        keys.append(key)
    return tuple(keys)


def _document_line_indexes(block: str) -> tuple[int, ...]:
    r"""For each YAML line of the block, how many `\n` the block holds before the line starts.

    That is the line's index among the block's document lines, from 0. Two YAML lines share one when a break between
    them, such as U+0085, is no `\n`.

    Args:
        block: The lines between the delimiters, line endings kept.
    """
    newlines = newline_offsets(block)
    return tuple(bisect_left(newlines, start) for start in yaml_line_starts(block))


def _invalid_yaml(problem: SyntaxProblem, stream: _EventStream) -> InvalidYamlFrontmatter:
    """The node for a syntax error: its label, help and line, as the block's document lines count them.

    Args:
        problem: The syntax error as lorecraft words it, on the line the reader counted.
        stream: The block's events, which turns that line into a document line.
    """
    line = None if problem.line is None else stream.document_line(problem.line)
    return InvalidYamlFrontmatter(problem=problem.label, line=line, help=problem.help)
