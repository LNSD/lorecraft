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
import sys
from dataclasses import dataclass
from typing import Final, assert_never

import yaml
from yaml.error import Mark
from yaml.events import (
    AliasEvent,
    MappingEndEvent,
    MappingStartEvent,
    ScalarEvent,
    SequenceEndEvent,
    SequenceStartEvent,
    StreamEndEvent,
)
from yaml.parser import Parser
from yaml.reader import Reader, ReaderError
from yaml.scanner import Scanner, ScannerError

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

    Never `MissingFrontmatter`: whether a block exists is decided before this is called. Every block PyYAML
    cannot parse is `InvalidYamlFrontmatter`, including the few it fails on with a plain Python exception rather
    than its own error, and so is every block that uses an anchor, an alias or a tag, writes a key, at any depth,
    that is not a string, such as `1:`, `true:` or `null:`, nests collections too deeply to read, or holds more
    than one document.

    Args:
        block: The lines between the delimiters, line endings kept; the first of them is document line 2.
    """
    try:
        # The reader checks every character as it is built, so a control character fails here, not in the parse.
        parser = _BasicYamlParser(block)
    except ReaderError as exc:
        line = LineNumber.from_int(block.count('\n', 0, exc.position) + _FIRST_BLOCK_LINE)
        return InvalidYamlFrontmatter(problem=exc.reason, line=line)
    try:
        return _read_document(parser)
    except yaml.MarkedYAMLError as exc:
        # PyYAML's own errors, and every refusal of what basic YAML leaves out, which this module raises as one.
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


class _BasicYamlParser(Reader, Scanner, Parser):
    r"""PyYAML's parser, which turns the block into a stream of events, raising its own error where PyYAML does not.

    Only the reader, the scanner and the parser are used: the value is built from the events by this module, not
    by PyYAML's composer and constructor, so no tag PyYAML resolves and no type it constructs is ever involved.

    PyYAML's scanner lets a plain Python exception escape in two places, and each is raised here as the scanner's
    error, which `decode_frontmatter` turns into invalid YAML:

    - A double-quoted `\U` escape above `U+10FFFF` names no character, and `chr` raises a `ValueError`,
      or an `OverflowError` for one too large for a C `int`. It is a `ScannerError` on the escape's line.
    - A `%YAML` directive whose version number has more digits than Python converts to an `int`, 4300 by
      default, raises a `ValueError`. It is a `ScannerError` on the directive's line.
    """

    def __init__(self, block: str) -> None:
        """Start reading `block`, checking every character of it first.

        Args:
            block: The YAML text to parse.

        Raises:
            ReaderError: The block holds a character YAML does not allow, such as a control character.
        """
        Reader.__init__(self, block)
        Scanner.__init__(self)
        Parser.__init__(self)

    def scan_flow_scalar_non_spaces(self, double: bool, start_mark: Mark) -> list[str]:
        """Scan the text of a quoted scalar up to its next space, as PyYAML's scanner does.

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
            raise ScannerError(None, None, problem, self.get_mark()) from exc

    def scan_yaml_directive_number(self, start_mark: Mark) -> int:
        """Scan one number of a `%YAML` directive's version, as PyYAML's scanner does.

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
            raise ScannerError(None, None, problem, self.get_mark()) from exc


def _read_document(parser: _BasicYamlParser) -> Frontmatter | NonMappingFrontmatter:
    """Read the block's one document, if any, and decode it.

    Every value is read to its end even when the document is not a mapping, so a refused construct or a syntax
    error anywhere in the block is reported rather than hidden behind the document's shape.

    Args:
        parser: The block's parser, before its first event is read.

    Raises:
        yaml.MarkedYAMLError: The block is not valid YAML, uses what basic YAML leaves out, or holds a second
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
        raise yaml.MarkedYAMLError(problem=problem, problem_mark=parser.peek_event().start_mark)
    return node


def _peek_node_start(parser: _BasicYamlParser) -> ScalarEvent | SequenceStartEvent | MappingStartEvent:
    """The event the next value starts with, left unread, once it is known to use nothing basic YAML leaves out.

    Args:
        parser: The parser, whose next event starts a value.

    Raises:
        yaml.MarkedYAMLError: The value is an alias, or carries an anchor or a tag, marked where it is written.
    """
    event = parser.peek_event()
    if isinstance(event, AliasEvent):
        problem = f'found the alias *{event.anchor}, which frontmatter does not allow'
        raise yaml.MarkedYAMLError(problem=problem, problem_mark=event.start_mark)
    if event.anchor is not None:
        problem = f'found the anchor &{event.anchor}, which frontmatter does not allow'
        raise yaml.MarkedYAMLError(problem=problem, problem_mark=event.start_mark)
    # The parser gives an event a tag only when one is written in the block, the non-specific `!` included.
    if event.tag is not None:
        problem = f'found the tag {_written_tag(event.tag)!r}, which frontmatter does not allow'
        raise yaml.MarkedYAMLError(problem=problem, problem_mark=event.start_mark)
    return event


def _read_value(parser: _BasicYamlParser) -> Frozen:
    """Read one value and everything in it, and decode it frozen: to a `FrozenMapping`, a tuple or a scalar.

    Args:
        parser: The parser, whose next event starts the value.

    Raises:
        yaml.MarkedYAMLError: The value is not valid YAML or uses what basic YAML leaves out.
    """
    event = _peek_node_start(parser)
    if isinstance(event, MappingStartEvent):
        return _to_mapping(_read_mapping(parser))
    if isinstance(event, SequenceStartEvent):
        return _read_sequence(parser)
    parser.get_event()
    return _scalar_value(event)


def _read_mapping(parser: _BasicYamlParser) -> list[_Entry]:
    """Read one mapping, every pair in the order it is written, a repeated key once per occurrence.

    Args:
        parser: The parser, whose next event starts the mapping.

    Raises:
        yaml.MarkedYAMLError: A key is not a string, or the mapping is not valid YAML or uses what basic YAML
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


def _read_sequence(parser: _BasicYamlParser) -> tuple[Frozen, ...]:
    """Read one sequence, every item in the order it is written, as a tuple, the sequence that cannot change.

    Args:
        parser: The parser, whose next event starts the sequence.

    Raises:
        yaml.MarkedYAMLError: An item is not valid YAML or uses what basic YAML leaves out.
    """
    parser.get_event()  # The sequence's start.
    items: list[Frozen] = []
    while not parser.check_event(SequenceEndEvent):
        items.append(_read_value(parser))
    parser.get_event()  # The sequence's end.
    return tuple(items)


def _read_key(parser: _BasicYamlParser) -> FrontmatterKey:
    """Read one key of a mapping, which must be a scalar that decodes to a string.

    Args:
        parser: The parser, whose next event starts the key.

    Raises:
        yaml.MarkedYAMLError: The key is a collection, or a scalar that decodes to something other than a string,
            or uses what basic YAML leaves out.
    """
    event = _peek_node_start(parser)
    if not isinstance(event, ScalarEvent):
        raise yaml.MarkedYAMLError(problem='found a key that is not a string', problem_mark=event.start_mark)
    parser.get_event()
    name = _scalar_value(event)
    if not isinstance(name, str):
        raise yaml.MarkedYAMLError(problem=_non_string_key_problem(event), problem_mark=event.start_mark)
    mark = event.start_mark
    if mark is None:
        # An event's mark is optional only in its constructor's signature: the parser marks every event it emits.
        raise AssertionError('unreachable: PyYAML marks every event it parses')
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


def _invalid_yaml(error: yaml.MarkedYAMLError) -> InvalidYamlFrontmatter:
    """The parser's facts about a block that does not parse: its problem, and the line it marked.

    Args:
        error: Failure raised while reading the block; its mark may be absent.
    """
    # The parser names the problem, or, for a few errors, only the construct it was reading when it stopped.
    problem = error.problem or error.context or 'the block is not valid YAML'
    mark = error.problem_mark or error.context_mark
    if mark is None:
        return InvalidYamlFrontmatter(problem=problem, line=None)
    return InvalidYamlFrontmatter(problem=problem, line=_document_line(mark.line))


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
