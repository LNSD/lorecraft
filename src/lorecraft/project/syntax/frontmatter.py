"""The frontmatter node of a document's parse tree: the decoded YAML mapping and where each key sits.

A document's frontmatter is a `---` delimited block on its first lines. Finding the block is the Markdown
parser's job (see `document`); decoding it is this module's. Parsing has exactly four outcomes, one type each:
no block, a block that is not YAML, a block that is YAML but not a mapping, and a mapping. Every outcome is a
value, never an exception, because a broken block is a fact about the document that a check reports, not a
failure of the parse.

The block is read as basic YAML, which decodes to exactly what JSON can hold: block and flow mappings whose keys
are strings, block and flow sequences, and scalars. A quoted or block scalar is a string. A plain scalar is null,
a boolean, an integer or a float when its whole text is one in YAML 1.2's core schema, such as `~`, `true`, `12` or
`1.5`, and a string otherwise, so `yes`, `2026-10-05` and `1:30` are strings. An anchor, an alias, an explicit tag
and a key that is not a string are refused, on their line, as a block that is not YAML: none is needed to write a
document's metadata, an alias can make a collection hold itself, a tag builds values JSON has no counterpart for,
and JSON names every key with a string.
"""

import math
import re
import string
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Final, assert_never

from ruamel.yaml import YAML
from ruamel.yaml.error import MarkedYAMLError, StreamMark
from ruamel.yaml.events import (
    AliasEvent,
    DocumentStartEvent,
    Event,
    MappingEndEvent,
    MappingStartEvent,
    ScalarEvent,
    SequenceEndEvent,
    SequenceStartEvent,
    StreamEndEvent,
)
from ruamel.yaml.parser import ParserError
from ruamel.yaml.reader import Reader, ReaderError
from ruamel.yaml.resolver import VersionedResolver
from ruamel.yaml.scanner import Scanner, ScannerError
from ruamel.yaml.tokens import AliasToken, AnchorToken, DirectiveToken, ScalarToken, TagToken

from lorecraft.core.mapping import Frozen, FrozenMapping

from .position import LineNumber

_FIRST_BLOCK_LINE: Final[int] = 2
"""The document line the block's first YAML line sits on: the opening delimiter is always line 1."""

_YAML_TAG_PREFIX: Final[str] = 'tag:yaml.org,2002:'
"""The prefix the `!!` shorthand stands for: the full name of every tag YAML itself defines."""

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

_ANCHOR_NAME_CHARACTERS: Final[str] = string.ascii_letters + string.digits + '-_'
"""The characters an anchor's or an alias's name is made of."""

_SPACE_CHARACTERS: Final[str] = '\0 \t\r\n\x85\u2028\u2029'
"""The characters that end a plain scalar: the end of the text, a space or tab, or a line break."""

_LINE_END_CHARACTERS: Final[str] = '\0\r\n\x85\u2028\u2029'
"""The characters that end a line: the end of the text, or a line break."""

_DIRECTIVE_END_CHARACTERS: Final[str] = '\0 \r\n\x85\u2028\u2029'
"""The characters a directive's name may be followed by: the end of the text, a space or a line break."""

_ANCHOR_END_CHARACTERS: Final[str] = '\0 \t\r\n\x85\u2028\u2029?:,]}%@`'
"""The characters a name may be followed by: the end of the text, a space or a break, or an indicator."""

_TOKEN_IN_TUPLE: Final[re.Pattern[str]] = re.compile(r"but found \(('[^']*'),\)$")
"""The end of a parser problem that ruamel.yaml 0.19 words with its token in a tuple, `but found ('<x>',)`."""

_CONTENT_AFTER_DOCUMENT_END: Final[re.Pattern[str]] = re.compile(
    r"found non-comment content after document end marker, \(('[^']*'),\)$"
)
"""The problem ruamel.yaml words for content on the line of a `...` marker, where PyYAML expects a document start."""

_PYYAML_WORDING: Final[tuple[tuple[str, str], ...]] = (
    ('hexdecimal numbers', 'hexadecimal numbers'),
    ("expected '!' but found", "expected '!', but found"),
    ('while scanning an tag', 'while scanning a tag'),
    ('while scanning an directive', 'while scanning a directive'),
)
"""Where ruamel.yaml 0.19 words a scanner problem differently from PyYAML, as (ruamel.yaml's text, PyYAML's text)."""


@dataclass(frozen=True, slots=True)
class FrontmatterKey:
    """One top-level key of a frontmatter mapping and the line it is written on.

    Attributes:
        name: The key as YAML decoded it.
        line: The document line the key starts on.
    """

    name: str
    line: LineNumber


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
    """

    data: FrozenMapping[str, Frozen]
    keys: tuple[FrontmatterKey, ...]

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
        problem: What the YAML parser found wrong, such as `mapping values are not allowed here`: in the parser's
            own words, or in this module's, where the parser fails with a plain Python exception or where the block
            uses what basic YAML leaves out, a key that is not a string included.
        line: The document line the problem is on, or None when it cannot be known: when the parser does not say,
            or when the block nests collections too deeply, where reading stops at whatever depth the interpreter's
            stack allows rather than at a line of the document.
    """

    problem: str
    line: LineNumber | None


@dataclass(frozen=True, slots=True)
class NonMappingFrontmatter:
    """The block is valid YAML, but it decodes to something other than a mapping, such as a list or nothing."""


type FrontmatterNode = Frontmatter | MissingFrontmatter | InvalidYamlFrontmatter | NonMappingFrontmatter
"""Every outcome of parsing a document's frontmatter."""

type _Entry = tuple[FrontmatterKey, Frozen]
"""One pair of a mapping as it is written: the key, with its line, and the decoded value."""


def decode_frontmatter(block: str) -> FrontmatterNode:
    """Decode the YAML between a document's `---` delimiters into its node. Pure: raises nothing.

    Never `MissingFrontmatter`: whether a block exists is decided before this is called. Every block the YAML
    parser cannot parse is `InvalidYamlFrontmatter`, including the few it fails on with a plain Python exception
    rather than its own error, and so is every block that uses an anchor, an alias or a tag, writes a key, at any
    depth, that is not a string, such as `1:`, `true:` or `null:`, nests collections too deeply to read, or holds
    more than one document.

    Args:
        block: The lines between the delimiters, line endings kept; the first of them is document line 2.
    """
    try:
        return _read_document(EventStream(block))
    except ReaderError as exc:
        # The reader checks every character as it is built, so a control character fails before the first event.
        line = LineNumber.from_int(block.count('\n', 0, exc.position) + _FIRST_BLOCK_LINE)
        return InvalidYamlFrontmatter(problem=exc.reason, line=line)
    except MarkedYAMLError as exc:
        # The parser's own errors, and every refusal of what basic YAML leaves out, which this module raises as one.
        return _invalid_yaml(exc)
    except RecursionError:
        # The value is read with one call per level of nesting, so only a deeply nested block reaches the
        # interpreter's limit. By the time this clause runs the stack has unwound to this frame, so there is room
        # to go on, and the half-read parser is dropped. The line is left out, because the depth reading stops at
        # depends on the interpreter's recursion limit and on how deep the caller's stack already was.
        return InvalidYamlFrontmatter(problem='found collections nested too deeply to parse', line=None)


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


class _BasicYaml(YAML):
    """ruamel.yaml's entry point, without a state of its own to keep: the YAML version is always 1.1.

    The reader and the scanner read the block as YAML 1.1 through `_BasicYamlResolver`, so the version a document
    declares has no use here. ruamel.yaml stores it all the same, in a setter that asserts it is 1.1 or 1.2, and an
    assertion error is no `FM002`.
    """

    @property
    def version(self) -> None:
        """The version a document declared, which is never kept."""
        return None

    @version.setter
    def version(self, value: object) -> None:
        # PyYAML takes a `%YAML` directive of any 1.x version, and ruamel.yaml's setter asserts on `1.0` and `1.3`.
        pass


class EventStream:
    """The events of a block, read lazily, one at a time, with one event of lookahead.

    The events come from ruamel.yaml's pure-Python reader, scanner and parser. The value is built from them by this
    module, never by ruamel.yaml's loader or constructor, so no tag ruamel.yaml resolves and no type it constructs
    is ever involved. They are read lazily so that a refusal early in the block is reported before a syntax error
    further down, as the parser reaches them.

    The package does not re-export it. It is public in this module so the tests can read the events the decoding
    reads, and hold them to another parser's.
    """

    def __init__(self, block: str) -> None:
        """Start reading `block`. No character is read until the first event is asked for.

        Args:
            block: The YAML text to parse.
        """
        # Setting the reader and the scanner already selects the pure parser; `pure` states the intent, so a
        # change in how ruamel.yaml chooses its parser cannot bring the C one, which has no reader of ours, in.
        yaml = _BasicYaml(typ='safe', pure=True)
        yaml.Reader = _BasicYamlReader
        yaml.Resolver = _BasicYamlResolver
        # PyYAML reads a top-level block scalar's content as indented, which ruamel.yaml does for YAML 1.1 only
        # when the loader says so.
        yaml.top_level_block_style_scalar_no_indent_error_1_1 = True
        yaml.Scanner = _BasicYamlScanner
        self._yaml = yaml
        self._events: Iterator[Event] = iter(yaml.parse(block))
        self._peeked: Event | None = None

    def peek_event(self) -> Event:
        """The next event, left unread.

        Raises:
            MarkedYAMLError: The block is not valid YAML.
            ReaderError: The block holds a character YAML does not allow, such as a control character.
        """
        if self._peeked is None:
            self._peeked = next(self._events)
            if isinstance(self._peeked, DocumentStartEvent):
                self._mark_document_start(self._peeked)
        return self._peeked

    def _mark_document_start(self, event: DocumentStartEvent) -> None:
        """Move a document start's mark to the first directive written before it, where there is one.

        Args:
            event: The document start the parser has just produced.
        """
        # ruamel.yaml marks a document start on its `---`, and PyYAML on the first directive above it, which is the
        # line a second document is reported on.
        directive_marks: list[StreamMark] = self._yaml.scanner.directive_marks
        if directive_marks:
            event.start_mark = directive_marks[0]
            directive_marks.clear()

    def get_event(self) -> Event:
        """The next event, read.

        Raises:
            MarkedYAMLError: The block is not valid YAML.
            ReaderError: The block holds a character YAML does not allow, such as a control character.
        """
        event = self.peek_event()
        self._peeked = None
        return event

    def check_event(self, *kinds: type[Event]) -> bool:
        """Whether the next event is of one of `kinds`, leaving it unread.

        Args:
            kinds: The event classes to test for.
        """
        return isinstance(self.peek_event(), kinds)


class _BasicYamlReader(Reader):
    """ruamel.yaml's reader, counting a next line character and a Unicode line or paragraph separator as a line."""

    def forward(self, length: int = 1) -> None:
        """Advance `length` characters, counting every YAML 1.1 line break as one line.

        Args:
            length: The number of characters to advance by.
        """
        # `str.splitlines` finds the block and breaks at those characters, so a line count that ignores them puts
        # every later key one line short. ruamel.yaml has a counter that does not, `forward_1_1`, and never selects it.
        self.forward_1_1(length)


class _BasicYamlResolver(VersionedResolver):
    """The resolver the scanner and parser ask which YAML version they read as, always 1.1."""

    @property
    def processing_version(self) -> tuple[int, int]:
        """The YAML version the scanner and parser read as."""
        # ruamel.yaml reads YAML 1.2 unless a directive says otherwise, and the grammars accept different blocks:
        # 1.2 takes a key written as nothing, `: value`, and `?` inside a plain scalar, which PyYAML refuses. The
        # scalars are resolved by this module's own core schema rules, never by the resolver.
        return (1, 1)


class _BasicYamlScanner(Scanner):
    r"""ruamel.yaml's scanner, reading the YAML 1.1 grammar and failing only with a `ScannerError`.

    A block is accepted or refused by the YAML 1.1 grammar, and a refusal names the problem and the line the scanner
    found it on. The scanner also keeps the mark of every directive it scans, for the document start that follows.

    Two places let a plain Python exception escape, and each is raised here as the scanner's error, which
    `decode_frontmatter` turns into invalid YAML:

    - A double-quoted `\U` escape above `U+10FFFF` names no character, and `chr` raises a `ValueError`,
      or an `OverflowError` for one too large for a C `int`. It is a `ScannerError` on the escape's line.
    - A `%YAML` directive whose version number has more digits than Python converts to an `int`, 4300 by
      default, raises a `ValueError`. It is a `ScannerError` on the directive's line.
    """

    # Where ruamel.yaml's scanner differs from PyYAML's, the method below is PyYAML's reading, because `FM002` has
    # always reported what PyYAML's scanner found: the same blocks refused, with the same problem on the same line.

    def __init__(self, loader: object = None) -> None:
        """Start scanning with no directive seen.

        Args:
            loader: The object ruamel.yaml's entry point passes in, which holds the reader.
        """
        super().__init__(loader)
        self.directive_marks: list[StreamMark] = []

    def scan_directive(self) -> DirectiveToken:
        """Scan a directive, and keep where it starts.

        Raises:
            ScannerError: The directive is malformed.
        """
        token = super().scan_directive()
        self.directive_marks.append(token.start_mark)
        return token

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
            ScannerError: An escape names no Unicode character, or the text is not valid YAML.
        """
        try:
            return super().scan_flow_scalar_non_spaces(double, start_mark)
        except (ValueError, OverflowError) as exc:
            # The scanner checks that an escape is written in hexadecimal, but not that the code point it names is
            # at most U+10FFFF, so `chr` raises: a ValueError for `\U00110000`, and for `\UFFFFFFFF`, which does not
            # fit a C int, an OverflowError on the interpreters that convert the argument first. Nothing else in
            # this method raises either. The scanner stops on the escape's digits, so its current mark is on the
            # escape's line.
            problem = 'found an escape sequence that names no Unicode character'
            raise ScannerError(None, None, problem, self.reader.get_mark()) from exc

    def scan_yaml_directive_number(self, start_mark: StreamMark) -> int:
        """Scan one number of a `%YAML` directive's version.

        Args:
            start_mark: Where the directive starts, for the scanner's own error messages.

        Raises:
            ScannerError: The number is too long to read, or the text is not a number.
        """
        try:
            return super().scan_yaml_directive_number(start_mark)
        except ValueError as exc:
            # The scanner reads every digit there is and converts them with `int`, which refuses more digits than
            # the interpreter's integer string conversion limit. The scanner stops before the digits, so its
            # current mark is on the directive's line.
            problem = 'found a YAML version number too long to read'
            raise ScannerError(None, None, problem, self.reader.get_mark()) from exc

    def scan_yaml_directive_value(self, start_mark: StreamMark) -> tuple[int, int]:
        """Scan a `%YAML` directive's version, two numbers joined by a `.` and followed by a space or a line break.

        Args:
            start_mark: Where the directive starts, for the scanner's own error messages.

        Raises:
            ScannerError: The version is not two numbers joined by a `.`, or is followed by a character that cannot
                follow it.
        """
        # PyYAML says "or ' '" after the minor number, where ruamel.yaml repeats "or '.'", and `FM002` has
        # always quoted PyYAML.
        while self.reader.peek() == ' ':
            self.reader.forward()
        major = self.scan_yaml_directive_number(start_mark)
        if self.reader.peek() != '.':
            problem = f"expected a digit or '.', but found {self.reader.peek()!r}"
            raise ScannerError('while scanning a directive', start_mark, problem, self.reader.get_mark())
        self.reader.forward()
        minor = self.scan_yaml_directive_number(start_mark)
        if self.reader.peek() not in _DIRECTIVE_END_CHARACTERS:
            problem = f"expected a digit or ' ', but found {self.reader.peek()!r}"
            raise ScannerError('while scanning a directive', start_mark, problem, self.reader.get_mark())
        return major, minor

    def scan_to_next_token(self) -> None:
        r"""Skip spaces, comments and line breaks to the next token; a tab is no whitespace, in a flow collection too.

        A tab is a character that cannot start a token, so `[a,\tb]` is refused.
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

    def scan_directive_name(self, start_mark: StreamMark) -> str:
        """Scan a directive's name, made of ASCII letters, digits, `-` and `_`.

        Args:
            start_mark: Where the directive starts, for the scanner's own error messages.

        Raises:
            ScannerError: The name is empty, or is followed by a character that cannot follow it.
        """
        # ruamel.yaml also takes `:` and `.` into the name, so `%YAML:1.1` is a directive there, and PyYAML's is not.
        length = 0
        while self.reader.peek(length) in _ANCHOR_NAME_CHARACTERS:
            length += 1
        if length == 0 or self.reader.peek(length) not in _DIRECTIVE_END_CHARACTERS:
            self.reader.forward(length)
            problem = f'expected alphabetic or numeric character, but found {self.reader.peek()!r}'
            raise ScannerError('while scanning a directive', start_mark, problem, self.reader.get_mark())
        name = self.reader.prefix(length)
        self.reader.forward(length)
        return name

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
                flow_indicator = self.flow_level and ch in ',?[]{}'
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

    def scan_anchor(self, TokenClass: type[AliasToken] | type[AnchorToken]) -> AliasToken | AnchorToken:
        """Scan an anchor or an alias, whose name is made of ASCII letters, digits, `-` and `_`.

        Args:
            TokenClass: The token to build, an anchor's or an alias's.

        Raises:
            ScannerError: The name is empty, or is followed by a character that cannot follow it.
        """
        # ruamel.yaml takes more characters into a name, so `*emphasis*` is one alias there and an error here.
        # A block that writes one is refused either way, but `FM002` has always named PyYAML's problem and name.
        start_mark = self.reader.get_mark()
        kind = 'alias' if self.reader.peek() == '*' else 'anchor'
        self.reader.forward()
        length = 0
        while self.reader.peek(length) in _ANCHOR_NAME_CHARACTERS:
            length += 1
        if length == 0 or self.reader.peek(length) not in _ANCHOR_END_CHARACTERS:
            self.reader.forward(length)
            problem = f'expected alphabetic or numeric character, but found {self.reader.peek()!r}'
            raise ScannerError(f'while scanning an {kind}', start_mark, problem, self.reader.get_mark())
        name = self.reader.prefix(length)
        self.reader.forward(length)
        return TokenClass(name, start_mark, self.reader.get_mark())

    def scan_tag(self) -> TagToken:
        """Scan a tag: `!`, `!suffix`, `!handle!suffix`, or `!<uri>`, followed by a space or a line break.

        Raises:
            ScannerError: The tag is malformed.
        """
        # ruamel.yaml shifts a leading `!!` into its short handle before it looks at the rest, so `!!!str` and
        # `!!` are tags there that PyYAML refuses, and its problems are worded differently.
        start_mark = self.reader.get_mark()
        ch = self.reader.peek(1)
        if ch == '<':
            handle = None
            self.reader.forward(2)
            suffix = self.scan_tag_uri('tag', start_mark)
            if self.reader.peek() != '>':
                problem = f"expected '>', but found {self.reader.peek()!r}"
                raise ScannerError('while parsing a tag', start_mark, problem, self.reader.get_mark())
            self.reader.forward()
        elif ch in _SPACE_CHARACTERS:
            handle = None
            suffix = '!'
            self.reader.forward()
        else:
            length = 1
            use_handle = False
            while ch not in _DIRECTIVE_END_CHARACTERS:
                if ch == '!':
                    use_handle = True
                    break
                length += 1
                ch = self.reader.peek(length)
            if use_handle:
                handle = self.scan_tag_handle('tag', start_mark)
            else:
                handle = '!'
                self.reader.forward()
            suffix = self.scan_tag_uri('tag', start_mark)
        ch = self.reader.peek()
        if ch not in _DIRECTIVE_END_CHARACTERS:
            problem = f"expected ' ', but found {ch!r}"
            raise ScannerError('while scanning a tag', start_mark, problem, self.reader.get_mark())
        return TagToken((handle, suffix), start_mark, self.reader.get_mark())


def _read_document(parser: EventStream) -> Frontmatter | NonMappingFrontmatter:
    """Read the block's one document, if any, and decode it.

    Every value is read to its end even when the document is not a mapping, so a refused construct or a syntax
    error anywhere in the block is reported rather than hidden behind the document's shape.

    Args:
        parser: The block's parser, before its first event is read.

    Raises:
        MarkedYAMLError: The block is not valid YAML, uses what basic YAML leaves out, or holds a second
            document.
    """
    parser.get_event()  # The stream's start.
    if parser.check_event(StreamEndEvent):
        # An empty block, or one holding only comments, has no document at all.
        return NonMappingFrontmatter()
    parser.get_event()  # The document's start.
    if isinstance(_peek_node_start(parser), MappingStartEvent):
        entries = _read_mapping(parser)
        node: Frontmatter | NonMappingFrontmatter = Frontmatter(data=_to_mapping(entries), keys=_keys(entries))
    else:
        _read_value(parser)
        node = NonMappingFrontmatter()
    parser.get_event()  # The document's end.
    if not parser.check_event(StreamEndEvent):
        problem = 'found a second document, which frontmatter does not allow'
        raise MarkedYAMLError(problem=problem, problem_mark=parser.peek_event().start_mark)
    return node


def _peek_node_start(parser: EventStream) -> ScalarEvent | SequenceStartEvent | MappingStartEvent:
    """The event the next value starts with, left unread, once it is known to use nothing basic YAML leaves out.

    Args:
        parser: The parser, whose next event starts a value.

    Raises:
        MarkedYAMLError: The value is an alias, or carries an anchor or a tag, marked where it is written.
    """
    event = parser.peek_event()
    if isinstance(event, AliasEvent):
        problem = f'found the alias *{event.anchor}, which frontmatter does not allow'
        raise MarkedYAMLError(problem=problem, problem_mark=event.start_mark)
    if not isinstance(event, ScalarEvent | SequenceStartEvent | MappingStartEvent):
        # Only an end event or a document event is left, and the parser never gives one where a value starts.
        raise AssertionError(f'unreachable: {type(event).__name__} where a value starts')
    if event.anchor is not None:
        problem = f'found the anchor &{event.anchor}, which frontmatter does not allow'
        raise MarkedYAMLError(problem=problem, problem_mark=event.start_mark)
    # The parser gives an event a tag only when one is written in the block, the non-specific `!` included.
    if event.tag is not None:
        problem = f'found the tag {_written_tag(event.tag)!r}, which frontmatter does not allow'
        raise MarkedYAMLError(problem=problem, problem_mark=event.start_mark)
    return event


def _read_value(parser: EventStream) -> Frozen:
    """Read one value and everything in it, and decode it frozen: to a `FrozenMapping`, a tuple or a scalar.

    Args:
        parser: The parser, whose next event starts the value.

    Raises:
        MarkedYAMLError: The value is not valid YAML or uses what basic YAML leaves out.
    """
    event = _peek_node_start(parser)
    if isinstance(event, MappingStartEvent):
        return _to_mapping(_read_mapping(parser))
    if isinstance(event, SequenceStartEvent):
        return _read_sequence(parser)
    parser.get_event()
    return _scalar_value(event)


def _read_mapping(parser: EventStream) -> list[_Entry]:
    """Read one mapping, every pair in the order it is written, a repeated key once per occurrence.

    Args:
        parser: The parser, whose next event starts the mapping.

    Raises:
        MarkedYAMLError: A key is not a string, or the mapping is not valid YAML or uses what basic YAML
            leaves out.
    """
    parser.get_event()  # The mapping's start.
    entries: list[_Entry] = []
    while not parser.check_event(MappingEndEvent):
        key = _read_key(parser)
        value = _read_value(parser)
        entries.append((key, value))
    parser.get_event()  # The mapping's end.
    return entries


def _read_sequence(parser: EventStream) -> tuple[Frozen, ...]:
    """Read one sequence, every item in the order it is written, as a tuple, the sequence that cannot change.

    Args:
        parser: The parser, whose next event starts the sequence.

    Raises:
        MarkedYAMLError: An item is not valid YAML or uses what basic YAML leaves out.
    """
    parser.get_event()  # The sequence's start.
    items: list[Frozen] = []
    while not parser.check_event(SequenceEndEvent):
        items.append(_read_value(parser))
    parser.get_event()  # The sequence's end.
    return tuple(items)


def _read_key(parser: EventStream) -> FrontmatterKey:
    """Read one key of a mapping, which must be a scalar that decodes to a string.

    Args:
        parser: The parser, whose next event starts the key.

    Raises:
        MarkedYAMLError: The key is a collection, or a scalar that decodes to something other than a string,
            or uses what basic YAML leaves out.
    """
    event = _peek_node_start(parser)
    if not isinstance(event, ScalarEvent):
        raise MarkedYAMLError(problem='found a key that is not a string', problem_mark=event.start_mark)
    parser.get_event()
    name = _scalar_value(event)
    if not isinstance(name, str):
        raise MarkedYAMLError(problem=_non_string_key_problem(event), problem_mark=event.start_mark)
    mark = event.start_mark
    if mark is None:
        # An event's mark is optional only in its constructor's signature: the parser marks every event it emits.
        raise AssertionError('unreachable: ruamel.yaml marks every event it parses')
    return FrontmatterKey(name=name, line=_document_line(mark.line))


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


def _keys(entries: list[_Entry]) -> tuple[FrontmatterKey, ...]:
    """Every key of the mapping, in the order it is written, a repeated key once per occurrence.

    Args:
        entries: The mapping's pairs, in the order they are written.
    """
    keys: list[FrontmatterKey] = []
    for key, _value in entries:
        keys.append(key)
    return tuple(keys)


def _non_string_key_problem(key_event: ScalarEvent) -> str:
    """What a reader is told about a scalar key that does not decode to a string, naming the key as written.

    Args:
        key_event: The key's event.
    """
    # A key written as nothing at all reads as null, and has no text to name.
    if key_event.value:
        return f'found the key {key_event.value}, which is not a string'
    return 'found a key that is not a string'


def _document_line(block_line: int) -> LineNumber:
    """The document line a line of the block is.

    Args:
        block_line: The line as a parser's mark counts it, from 0 at the block's first line.
    """
    # The block starts on document line 2, below the opening delimiter.
    return LineNumber.from_int(block_line + _FIRST_BLOCK_LINE)


def _invalid_yaml(error: MarkedYAMLError) -> InvalidYamlFrontmatter:
    """The parser's facts about a block that does not parse: its problem, and the line it marked.

    Args:
        error: Failure raised while reading the block; its mark may be absent.
    """
    # The parser names the problem, or, for a few errors, only the construct it was reading when it stopped.
    problem = error.problem or error.context or 'the block is not valid YAML'
    # Only the parser's own wording is touched: a refusal of this module quotes a name the user wrote.
    if isinstance(error, ScannerError | ParserError):
        problem = _pyyaml_wording(problem)
    mark = error.problem_mark or error.context_mark
    if mark is None:
        return InvalidYamlFrontmatter(problem=problem, line=None)
    return InvalidYamlFrontmatter(problem=problem, line=_document_line(mark.line))


def _pyyaml_wording(problem: str) -> str:
    """The problem as PyYAML words it, where ruamel.yaml 0.19 words it with a typo or in another form.

    Args:
        problem: What the parser found wrong.
    """
    # ruamel.yaml writes the token of two problems, the content after a document's end, as a one-item tuple.
    problem = _CONTENT_AFTER_DOCUMENT_END.sub(r"expected '<document start>', but found \1", problem)
    problem = _TOKEN_IN_TUPLE.sub(r'but found \1', problem)
    for ruamel_text, pyyaml_text in _PYYAML_WORDING:
        problem = problem.replace(ruamel_text, pyyaml_text)
    return problem


def _written_tag(tag: str) -> str:
    """The tag spelled as a block writes it: `!!str` for one YAML defines, `!team` for a local one, else `!<...>`.

    The parser hands over a tag resolved to its full name, so `!!str` arrives as `tag:yaml.org,2002:str`, which an
    author reading the problem would not recognise as what they wrote. Any other full name, written verbatim or
    through a `%TAG` shorthand, is printed in the verbatim `!<...>` form, which names it exactly.

    Args:
        tag: A tag the block writes, as the parser resolved it.
    """
    if tag.startswith(_YAML_TAG_PREFIX):
        return '!!' + tag.removeprefix(_YAML_TAG_PREFIX)
    # A local tag, and the non-specific `!`, arrive as written.
    if tag.startswith('!'):
        return tag
    return f'!<{tag}>'
