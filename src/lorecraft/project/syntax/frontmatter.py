"""The frontmatter node of a document's parse tree: the decoded YAML mapping and where each key sits.

A document's frontmatter is a `---` delimited block on its first lines. Finding the block is the Markdown
parser's job (`markdown.parse_markdown_frontmatter`); decoding it is this module's. Parsing has exactly four
outcomes, one type each: no block, a block that is not YAML, a block that is YAML but not a mapping, and a mapping.
Every outcome is a value, never an exception, because a broken block is a fact about the document that a check
reports, not a failure of the parse.

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

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, assert_never

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
from ruamel.yaml.reader import ReaderError

from lorecraft.core.mapping import Frozen, FrozenMapping
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.yaml.basic_yaml import (
    MERGE_KEY,
    REFUSALS,
    RecordedRefusal,
    Refusal,
    RefusedAliasError,
    RefusedAnchorError,
    RefusedCollectionKeyError,
    RefusedFlowBlockError,
    RefusedFlowNestedCollectionError,
    RefusedMergeKeyError,
    RefusedNestedBlockSequenceError,
    RefusedNonStringKeyError,
    RefusedTagError,
)
from lorecraft.yaml.reader import YamlEventStream
from lorecraft.yaml.scalar import resolve_plain_scalar

from .position import LineNumber
from .syntax_error import SyntaxProblem, describe_control_character, describe_error

_FIRST_BLOCK_LINE: Final[int] = 2
"""The document line the block's first YAML line sits on: the opening delimiter is always line 1."""


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
    """The document does not open with a `---` line, or the block is never closed by one."""


@dataclass(frozen=True, slots=True)
class InvalidYamlFrontmatter:
    """The block is there but is not valid YAML, or uses YAML beyond the basic subset frontmatter is read as.

    A value, compared by value, so it holds the parser's facts rather than the parser's exception, which compares
    by identity.

    Attributes:
        problem: What is wrong, in lorecraft's words, such as `this value holds ': '`, or `found the tag '!!str',
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
    stream = YamlEventStream(block)
    try:
        node = _read_document(stream)
    except ReaderError as exc:
        # The reader checks every character as it is built, so a control character fails before the first event.
        return _invalid_yaml(describe_control_character(exc, block), stream)
    except REFUSALS as exc:
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


def _document_line(block_line: int) -> LineNumber:
    r"""The document line a line of the block is.

    The reader ends a line where `core/lines.py` does, at a `\n`, a `\r\n` or a lone `\r`, so its count is the
    document's.

    Args:
        block_line: The line as the reader's mark counts it, from 0 at the block's first line.
    """
    # The block starts on document line 2, below the opening delimiter.
    return LineNumber(NonZeroUnsignedInt(block_line + _FIRST_BLOCK_LINE))


def _invalid_refusal(
    refusal: RecordedRefusal | Refusal,
    stream: YamlEventStream,
) -> InvalidYamlFrontmatter:
    """The facts about a block that writes a construct frontmatter leaves out: the problem, and its line.

    Args:
        refusal: The construct, as the scanner recorded it or as the read stopped on it.
        stream: The block's events, which turns the construct's line into a document line.
    """
    refusal_help = refusal.help if isinstance(refusal, RecordedRefusal) else None
    return InvalidYamlFrontmatter(problem=refusal.problem, line=_document_line(refusal.mark.line), help=refusal_help)


def _mark_of(event: Event) -> StreamMark:
    """Where an event starts.

    Args:
        event: An event the parser emitted.
    """
    mark = event.start_mark
    if not isinstance(mark, StreamMark):
        # An event's mark is optional only in its constructor's signature: the parser marks every event it emits.
        raise AssertionError('unreachable: ruamel.yaml marks every event it parses')
    return mark


def _read_document(parser: YamlEventStream) -> Frontmatter | NonMappingFrontmatter:
    """Read the block's one document, if any, and decode it.

    Every value is read to its end even when the document is not a mapping, so a refused construct or a syntax
    error anywhere in the block is reported rather than hidden behind the document's shape.

    Args:
        parser: The block's parser, before its first event is read.

    Raises:
        MarkedYAMLError: The block is not valid YAML.
        RefusedFlowBlockError: The whole block is a flow collection.
        RefusedAliasError: The block is an alias.
        RefusedAnchorError: The block carries an anchor.
        RefusedTagError: The block carries a tag.
        RefusedCollectionKeyError: A key is a collection.
        RefusedNonStringKeyError: A key is a scalar that decodes to something other than a string.
        RefusedMergeKeyError: A key is the plain merge key.
        RefusedFlowNestedCollectionError: A flow collection holds a collection.
        RefusedNestedBlockSequenceError: A block sequence holds a block sequence as an item.
        RefusedDirectiveError, RefusedDocumentMarkerError, RefusedMalformedTagError, RefusedEscapeError: The
            scanner refuses a directive, a document marker, a tag it cannot read or an escape where it reads it, and
            `RefusedAnchorError` and `RefusedAliasError` an anchor or an alias with no name.
    """
    parser.get_event()  # The stream's start.
    if parser.check_event(StreamEndEvent):
        # An empty block, or one holding only comments, has no document at all.
        return NonMappingFrontmatter()
    parser.get_event()  # The document's start.
    first = _peek_node_start(parser)
    if isinstance(first, SequenceStartEvent | MappingStartEvent) and first.flow_style:
        raise RefusedFlowBlockError(_mark_of(first))
    repeats: list[RepeatedKey] = []
    if isinstance(first, MappingStartEvent):
        entries = _read_mapping(parser, first, repeats)
        # An inner mapping ends before the one that holds it, so its repeats came first; document order is by line.
        in_document_order = tuple(sorted(repeats, key=lambda repeat: repeat.line))
        node: Frontmatter | NonMappingFrontmatter = _frontmatter(entries, in_document_order)
    else:
        _read_value(parser, repeats)
        node = NonMappingFrontmatter()
    parser.get_event()  # The document's end.
    if not parser.check_event(StreamEndEvent):
        # A second document starts with a `---` or a `...` marker, which the scanner refuses where it stands.
        raise AssertionError('unreachable: the scanner refuses every document marker')
    return node


def _peek_node_start(parser: YamlEventStream) -> ScalarEvent | SequenceStartEvent | MappingStartEvent:
    """The event the next value starts with, left unread, once it is known to use nothing basic YAML leaves out.

    Args:
        parser: The parser, whose next event starts a value.

    Raises:
        RefusedAliasError: The value is an alias, marked where it is written.
        RefusedAnchorError: The value carries an anchor.
        RefusedTagError: The value carries a tag.
    """
    event = parser.peek_event()
    if isinstance(event, AliasEvent):
        raise RefusedAliasError(event.anchor, _mark_of(event))
    if not isinstance(event, ScalarEvent | SequenceStartEvent | MappingStartEvent):
        # Only an end event or a document event is left, and the parser never gives one where a value starts.
        raise AssertionError(f'unreachable: {type(event).__name__} where a value starts')
    if event.anchor is not None:
        raise RefusedAnchorError(event.anchor, _mark_of(event))
    # The parser gives an event a tag only when one is written in the block, the non-specific `!` included.
    if event.tag is not None:
        raise RefusedTagError(parser.written_tag(event), _mark_of(event))
    return event


def _read_value(parser: YamlEventStream, repeats: list[RepeatedKey]) -> Frozen:
    """Read one value and everything in it, and decode it frozen: to a `FrozenMapping`, a tuple or a scalar.

    Args:
        parser: The parser, whose next event starts the value.
        repeats: The keys written again so far in the document, which the mappings in the value add to.

    Raises:
        MarkedYAMLError: The value is not valid YAML.
        RefusedAliasError: The value is an alias, or one in a collection it holds is.
        RefusedAnchorError: The value, or one in a collection it holds, carries an anchor.
        RefusedTagError: The value, or one in a collection it holds, carries a tag.
        RefusedCollectionKeyError: A key in the value is a collection.
        RefusedNonStringKeyError: A key in the value is not a string.
        RefusedMergeKeyError: A key in the value is the plain merge key.
        RefusedFlowNestedCollectionError: A flow collection in the value holds a collection.
        RefusedNestedBlockSequenceError: A block sequence in the value holds a block sequence as an item.
        RefusedMalformedTagError, RefusedEscapeError: The scanner cannot read a tag or an escape in the value.
    """
    event = _peek_node_start(parser)
    if isinstance(event, MappingStartEvent):
        return _to_mapping(_read_mapping(parser, event, repeats))
    if isinstance(event, SequenceStartEvent):
        return _read_sequence(parser, event, repeats)
    parser.get_event()
    return _scalar_value(event)


def _read_mapping(parser: YamlEventStream, start: MappingStartEvent, repeats: list[RepeatedKey]) -> list[_Entry]:
    """Read one mapping, every pair in the order it is written, a repeated key once per occurrence.

    The keys it and the mappings inside it write again are added to `repeats`, those of the inner ones first.

    Args:
        parser: The parser, whose next event starts the mapping.
        start: The event that starts it, which says whether it is written in flow style.
        repeats: The keys written again so far in the document, which this call adds to.

    Raises:
        MarkedYAMLError: The mapping is not valid YAML.
        RefusedCollectionKeyError: A key is a collection.
        RefusedNonStringKeyError: A key is a scalar that decodes to something other than a string.
        RefusedMergeKeyError: A key is the plain merge key.
        RefusedFlowNestedCollectionError: A value is a collection inside a flow mapping.
        RefusedAliasError, RefusedAnchorError, RefusedTagError: A key or a value is an alias, or carries an anchor
            or a tag.
        RefusedMalformedTagError, RefusedEscapeError: The scanner cannot read a tag or an escape in the mapping.
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


def _read_sequence(
    parser: YamlEventStream, start: SequenceStartEvent, repeats: list[RepeatedKey]
) -> tuple[Frozen, ...]:
    """Read one sequence, every item in the order it is written, as a tuple, the sequence that cannot change.

    Args:
        parser: The parser, whose next event starts the sequence.
        start: The event that starts it, which says whether it is written in flow style.
        repeats: The keys written again so far in the document, which the mappings among its items add to.

    Raises:
        MarkedYAMLError: An item is not valid YAML.
        RefusedFlowNestedCollectionError: An item is a collection inside a flow sequence.
        RefusedNestedBlockSequenceError: An item is a block sequence inside a block sequence.
        RefusedAliasError, RefusedAnchorError, RefusedTagError: An item is an alias, or carries an anchor or a tag.
        RefusedCollectionKeyError, RefusedNonStringKeyError, RefusedMergeKeyError: A mapping among the items has
            such a key.
        RefusedMalformedTagError, RefusedEscapeError: The scanner cannot read a tag or an escape in the sequence.
    """
    parser.get_event()  # The sequence's start.
    items: list[Frozen] = []
    while not parser.check_event(SequenceEndEvent):
        _refuse_nested_collection(parser, start)
        items.append(_read_value(parser, repeats))
    parser.get_event()  # The sequence's end.
    return tuple(items)


def _read_key(parser: YamlEventStream) -> FrontmatterKey:
    """Read one key of a mapping, which must be a scalar that decodes to a string.

    Args:
        parser: The parser, whose next event starts the key.

    Raises:
        RefusedAliasError: The key is an alias.
        RefusedAnchorError: The key carries an anchor.
        RefusedTagError: The key carries a tag.
        RefusedCollectionKeyError: The key is a collection.
        RefusedNonStringKeyError: The key is a scalar that decodes to something other than a string.
        RefusedMergeKeyError: The key is the plain merge key.
    """
    event = _peek_node_start(parser)
    if not isinstance(event, ScalarEvent):
        raise RefusedCollectionKeyError(_mark_of(event))
    parser.get_event()
    name = _scalar_value(event)
    mark = _mark_of(event)
    if not isinstance(name, str):
        raise RefusedNonStringKeyError(event.value, mark)
    if event.style is None and name == MERGE_KEY:
        # A plain `<<` is YAML 1.1's merge key, which pulls in the entries of the mapping an alias names.
        raise RefusedMergeKeyError(mark)
    return FrontmatterKey(name=name, line=_document_line(mark.line))


def _refuse_nested_collection(parser: YamlEventStream, parent: SequenceStartEvent | MappingStartEvent) -> None:
    """Refuse the next value when it is a collection `parent` does not hold.

    A flow collection holds no collection, and a block sequence holds no block sequence. A block mapping is the item
    a block sequence of records is made of, and a flow collection is one line of scalars, so those stay.

    Args:
        parser: The parser, whose next event starts a value of `parent`.
        parent: The event that started the collection the value belongs to.

    Raises:
        RefusedAliasError: The value is an alias.
        RefusedAnchorError: The value carries an anchor.
        RefusedTagError: The value carries a tag.
        RefusedFlowNestedCollectionError: The value is a collection inside a flow collection.
        RefusedNestedBlockSequenceError: The value is a block sequence that is an item of a block sequence.
    """
    event = _peek_node_start(parser)
    if not isinstance(event, SequenceStartEvent | MappingStartEvent):
        return
    if parent.flow_style:
        raise RefusedFlowNestedCollectionError(_mark_of(event))
    if isinstance(parent, SequenceStartEvent) and isinstance(event, SequenceStartEvent) and not event.flow_style:
        raise RefusedNestedBlockSequenceError(_mark_of(event))


def _scalar_value(event: ScalarEvent) -> str | int | float | bool | None:
    """What a scalar decodes to: its text, unless it is plain and its whole text is a core schema null, bool or number.

    Args:
        event: The scalar's event, which carries no tag.
    """
    text = event.value
    if not isinstance(text, str):
        # An event's value is typed as optional text; a scalar event always carries its text.
        raise AssertionError('unreachable: ruamel.yaml reads a scalar as text')
    # A quoted scalar, and a literal `|` or folded `>` block, has a style; only a plain one is resolved.
    if event.style is not None:
        return text
    return resolve_plain_scalar(text)


def _to_mapping(entries: Sequence[_Entry]) -> FrozenMapping[str, Frozen]:
    """The mapping the pairs decode to: a key written more than once holds the value of its last occurrence.

    Args:
        entries: The mapping's pairs, in the order they are written.
    """
    mapping: dict[str, Frozen] = {}
    for key, value in entries:
        mapping[key.name] = value
    return FrozenMapping(mapping)


def _frontmatter(entries: Sequence[_Entry], repeats: tuple[RepeatedKey, ...]) -> Frontmatter:
    """The mapping a block's top-level pairs decode to, with `data` and `keys` built from the same pairs.

    Args:
        entries: The top-level pairs, in the order they are written, a repeated key once per occurrence.
        repeats: The keys written again at any depth, in document order.
    """
    return Frontmatter(data=_to_mapping(entries), keys=tuple(key for key, _value in entries), repeats=repeats)


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


def _invalid_yaml(problem: SyntaxProblem, stream: YamlEventStream) -> InvalidYamlFrontmatter:
    """The node for a syntax error: its label, help and line, as the block's document lines count them.

    Args:
        problem: The syntax error as lorecraft words it, on the line the reader counted.
        stream: The block's events, which turns that line into a document line.
    """
    line = None if problem.line is None else _document_line(problem.line)
    return InvalidYamlFrontmatter(problem=problem.label, line=line, help=problem.help)
