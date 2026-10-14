"""Reading a YAML text into a tree of values, and refusing what the subset leaves out.

The events come from ruamel.yaml's pure-Python reader, scanner and parser, and the tree is built from them here, never
by ruamel.yaml's loader or constructor, so no tag ruamel.yaml resolves and no type it constructs is ever involved. The
text is read lazily and to its end, so a refused construct or a syntax error anywhere in it is reported, and the
constructs the scanner recorded by the time a read fails are the ones written above the failure.
"""

from collections.abc import Iterator

from ruamel.yaml import YAML
from ruamel.yaml.error import StreamMark
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

from lorecraft.core.num import NonZeroUnsignedInt

from .basic_yaml import (
    MERGE_KEY,
    BasicYamlParser,
    BasicYamlReader,
    BasicYamlScanner,
    RecordedRefusal,
    RefusedAliasError,
    RefusedAnchorError,
    RefusedCollectionKeyError,
    RefusedFlowBlockError,
    RefusedFlowNestedCollectionError,
    RefusedMergeKeyError,
    RefusedNestedBlockSequenceError,
    RefusedNonStringKeyError,
    RefusedTagError,
    written_token,
)
from .scalar import resolve_plain_scalar
from .tree import YamlKey, YamlMapping, YamlPosition, YamlScalar, YamlSequence, YamlValue


class YamlEventStream:
    """The events of a text, read lazily, one at a time, with one event of lookahead.

    It is kept by the caller, which asks it for the construct the scanner recorded when a read fails.
    """

    def __init__(self, text: str) -> None:
        """Start reading `text`. No character is read until the first event is asked for.

        Args:
            text: The YAML text to parse.
        """
        # Setting the reader and the scanner already selects the pure parser; `pure` states the intent, so a
        # change in how ruamel.yaml chooses its parser cannot bring the C one, which has no reader of ours, in.
        yaml = YAML(typ='safe', pure=True)
        yaml.Reader = BasicYamlReader
        yaml.Scanner = BasicYamlScanner
        yaml.Parser = BasicYamlParser
        self._text = text
        self._events: Iterator[Event] = iter(yaml.parse(text))
        self._peeked: Event | None = None
        self._yaml = yaml

    def peek_event(self) -> Event:
        """The next event, left unread.

        Raises:
            MarkedYAMLError: The text is not valid YAML.
            ReaderError: The text holds a character YAML does not allow, such as a control character.
        """
        if self._peeked is None:
            self._peeked = next(self._events)
        return self._peeked

    def first_refusal(self) -> RecordedRefusal | None:
        """The first construct the scanner or the reader has recorded, in the order the text writes them, or `None`."""
        scanner = self._yaml.scanner
        reader = self._yaml.reader
        if not isinstance(scanner, BasicYamlScanner) or not isinstance(reader, BasicYamlReader):
            # The types are declared on the parser's base class; `YamlEventStream` always installs its own.
            raise AssertionError("unreachable: the parser is built with `basic_yaml`'s scanner and reader")
        recorded = [*scanner.refusals[:1], *([reader.separator] if reader.separator is not None else [])]
        if not recorded:
            return None
        return min(recorded, key=lambda refusal: refusal.mark.index)

    def get_event(self) -> Event:
        """The next event, read.

        Raises:
            MarkedYAMLError: The text is not valid YAML.
            ReaderError: The text holds a character YAML does not allow, such as a control character.
        """
        event = self.peek_event()
        self._peeked = None
        return event

    def written_tag(self, event: ScalarEvent | SequenceStartEvent | MappingStartEvent) -> str:
        """The tag a node carries, spelled as the text writes it.

        The parser hands over a tag resolved against its handles, so `!!!str` arrives as the tag `!!str` and a tag
        in a flow collection can take the comma after it. The text itself is what the author wrote.

        Args:
            event: The event of a node that carries a tag and no anchor. Its start mark is where the tag begins
                only then, because an anchor written first would start the node, so `_peek_node_start` refuses
                an anchor before it asks for the tag.
        """
        return written_token(self._text, _mark_of(event).index)

    def check_event(self, *kinds: type[Event]) -> bool:
        """Whether the next event is of one of `kinds`, leaving it unread.

        Args:
            kinds: The event classes to test for.
        """
        return isinstance(self.peek_event(), kinds)


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


def _position_of(event: Event) -> YamlPosition:
    """Where an event starts, as the tree states it: one-based.

    Args:
        event: An event the parser emitted.
    """
    mark = _mark_of(event)
    return YamlPosition(NonZeroUnsignedInt(mark.line + 1), NonZeroUnsignedInt(mark.column + 1))


def read_document(parser: YamlEventStream) -> YamlValue | None:
    """Read the text's one document, if any.

    Args:
        parser: The text's parser, before its first event is read.

    Raises:
        MarkedYAMLError: The text is not valid YAML.
        RefusedFlowBlockError: The whole text is a flow collection.
        RefusedAliasError: The text is an alias.
        RefusedAnchorError: The text carries an anchor.
        RefusedTagError: The text carries a tag.
        RefusedCollectionKeyError: A key is a collection.
        RefusedNonStringKeyError: A key is a scalar that reads as something other than a string.
        RefusedMergeKeyError: A key is the plain merge key.
        RefusedFlowNestedCollectionError: A flow collection holds a collection.
        RefusedNestedBlockSequenceError: A block sequence holds a block sequence as an item.
        RefusedDirectiveError, RefusedDocumentMarkerError, RefusedMalformedTagError, RefusedEscapeError: The
            scanner refuses a directive, a document marker, a tag it cannot read or an escape where it reads it, and
            `RefusedAnchorError` and `RefusedAliasError` an anchor or an alias with no name.
    """
    parser.get_event()  # The stream's start.
    if parser.check_event(StreamEndEvent):
        # An empty text, or one holding only comments, has no document at all.
        return None
    parser.get_event()  # The document's start.
    first = _peek_node_start(parser)
    if isinstance(first, SequenceStartEvent | MappingStartEvent) and first.flow_style:
        raise RefusedFlowBlockError(_mark_of(first))
    root = _read_value(parser)
    parser.get_event()  # The document's end.
    if not parser.check_event(StreamEndEvent):
        # A second document starts with a `---` or a `...` marker, which the scanner refuses where it stands.
        raise AssertionError('unreachable: the scanner refuses every document marker')
    return root


def _peek_node_start(parser: YamlEventStream) -> ScalarEvent | SequenceStartEvent | MappingStartEvent:
    """The event the next value starts with, left unread, once it is known to use nothing the subset leaves out.

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
    # The parser gives an event a tag only when one is written in the text, the non-specific `!` included.
    if event.tag is not None:
        raise RefusedTagError(parser.written_tag(event), _mark_of(event))
    return event


def _read_value(parser: YamlEventStream) -> YamlValue:
    """Read one value and everything in it.

    Args:
        parser: The parser, whose next event starts the value.

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
        return _read_mapping(parser, event)
    if isinstance(event, SequenceStartEvent):
        return _read_sequence(parser, event)
    parser.get_event()
    return YamlScalar(_scalar_value(event), _position_of(event))


def _read_mapping(parser: YamlEventStream, start: MappingStartEvent) -> YamlMapping:
    """Read one mapping, every pair in the order it is written, a repeated key once per occurrence.

    Args:
        parser: The parser, whose next event starts the mapping.
        start: The event that starts it, which says whether it is written in flow style.

    Raises:
        MarkedYAMLError: The mapping is not valid YAML.
        RefusedCollectionKeyError: A key is a collection.
        RefusedNonStringKeyError: A key is a scalar that reads as something other than a string.
        RefusedMergeKeyError: A key is the plain merge key.
        RefusedFlowNestedCollectionError: A value is a collection inside a flow mapping.
        RefusedAliasError, RefusedAnchorError, RefusedTagError: A key or a value is an alias, or carries an anchor
            or a tag.
        RefusedMalformedTagError, RefusedEscapeError: The scanner cannot read a tag or an escape in the mapping.
    """
    parser.get_event()  # The mapping's start.
    entries: list[tuple[YamlKey, YamlValue]] = []
    while not parser.check_event(MappingEndEvent):
        key = _read_key(parser)
        _refuse_nested_collection(parser, start)
        entries.append((key, _read_value(parser)))
    parser.get_event()  # The mapping's end.
    return YamlMapping(tuple(entries), _position_of(start))


def _read_sequence(parser: YamlEventStream, start: SequenceStartEvent) -> YamlSequence:
    """Read one sequence, every item in the order it is written.

    Args:
        parser: The parser, whose next event starts the sequence.
        start: The event that starts it, which says whether it is written in flow style.

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
    items: list[YamlValue] = []
    while not parser.check_event(SequenceEndEvent):
        _refuse_nested_collection(parser, start)
        items.append(_read_value(parser))
    parser.get_event()  # The sequence's end.
    return YamlSequence(tuple(items), _position_of(start))


def _read_key(parser: YamlEventStream) -> YamlKey:
    """Read one key of a mapping, which must be a scalar that reads as a string.

    Args:
        parser: The parser, whose next event starts the key.

    Raises:
        RefusedAliasError: The key is an alias.
        RefusedAnchorError: The key carries an anchor.
        RefusedTagError: The key carries a tag.
        RefusedCollectionKeyError: The key is a collection.
        RefusedNonStringKeyError: The key is a scalar that reads as something other than a string.
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
    return YamlKey(name, _position_of(event))


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
    """What a scalar reads as: its text, unless it is plain and its whole text is a core schema null, bool or number.

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
