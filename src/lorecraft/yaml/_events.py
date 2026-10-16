"""The seam over ruamel.yaml's events and errors: each is checked once here and read as a value of this package's own.

ruamel.yaml types an event's fields and an error's texts loosely, as optional or `Any`. `_EventStream` converts every
event the parser emits into a frozen value, and `parse_failure` and `code_point` convert the library's errors, so the
tree builder in `reader` reads checked values and no library value reaches it.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum, auto

from ruamel.yaml import YAML
from ruamel.yaml.error import MarkedYAMLError, StreamMark
from ruamel.yaml.events import (
    AliasEvent,
    DocumentEndEvent,
    DocumentStartEvent,
    Event,
    MappingEndEvent,
    MappingStartEvent,
    ScalarEvent,
    SequenceEndEvent,
    SequenceStartEvent,
    StreamEndEvent,
    StreamStartEvent,
)
from ruamel.yaml.reader import ReaderError

from lorecraft.core.error import Unreachable

from .basic_yaml import (
    BasicYamlParser,
    BasicYamlReader,
    BasicYamlScanner,
    RecordedRefusal,
    written_token,
)


class Boundary(Enum):
    """The events that open or close a stream, a document or a collection, and carry nothing else."""

    STREAM_START = auto()
    STREAM_END = auto()
    DOCUMENT_START = auto()
    DOCUMENT_END = auto()
    MAPPING_END = auto()
    SEQUENCE_END = auto()


@dataclass(frozen=True, slots=True)
class ScalarStart:
    """The event that starts a scalar.

    Attributes:
        anchor: The anchor the scalar carries, or `None`.
        tag: The tag the scalar carries, spelled as the text writes it when no anchor is written first, or `None`.
        plain: Whether it is written plain, with no quotes and not as a block.
        text: Its text.
        mark: Where it starts.
    """

    anchor: str | None
    tag: str | None
    plain: bool
    text: str
    mark: StreamMark


@dataclass(frozen=True, slots=True)
class SequenceStart:
    """The event that starts a sequence.

    Attributes:
        anchor: The anchor the sequence carries, or `None`.
        tag: The tag the sequence carries, spelled as the text writes it when no anchor is written first, or `None`.
        flow: Whether it is written in flow style.
        mark: Where it starts.
    """

    anchor: str | None
    tag: str | None
    flow: bool
    mark: StreamMark


@dataclass(frozen=True, slots=True)
class MappingStart:
    """The event that starts a mapping.

    Attributes:
        anchor: The anchor the mapping carries, or `None`.
        tag: The tag the mapping carries, spelled as the text writes it when no anchor is written first, or `None`.
        flow: Whether it is written in flow style.
        mark: Where it starts.
    """

    anchor: str | None
    tag: str | None
    flow: bool
    mark: StreamMark


type CollectionStart = SequenceStart | MappingStart
type NodeStart = ScalarStart | CollectionStart


@dataclass(frozen=True, slots=True)
class Alias:
    """The event of an alias.

    Attributes:
        anchor: The anchor the alias names.
        mark: Where it is written.
    """

    anchor: str
    mark: StreamMark


type StreamEvent = Boundary | NodeStart | Alias


@dataclass(frozen=True, slots=True)
class ParseFailure:
    """What ruamel.yaml's parser or scanner reported when the text is not valid YAML.

    Attributes:
        problem: What went wrong; empty where the library gave none.
        context: What it was reading; empty where the library gave none.
        problem_mark: Where it went wrong, or `None`.
        context_mark: Where the context starts, or `None`.
    """

    problem: str
    context: str
    problem_mark: StreamMark | None
    context_mark: StreamMark | None


def parse_failure(error: MarkedYAMLError) -> ParseFailure:
    """The report of a failed read, checked.

    Args:
        error: The library's error.
    """
    return ParseFailure(error.problem or '', error.context or '', error.problem_mark, error.context_mark)


def code_point(error: ReaderError) -> int:
    """The code point of the character the reader refused.

    Args:
        error: The reader's error, whose character is a code point, or a one-character text.
    """
    character = error.character
    return character if isinstance(character, int) else ord(character)


def _mark_of(event: Event) -> StreamMark:
    """Where an event starts.

    Args:
        event: An event the parser emitted.
    """
    mark = event.start_mark
    if not isinstance(mark, StreamMark):
        # SAFETY: an event's mark is optional only in its constructor's signature; the parser marks every event.
        raise Unreachable('ruamel.yaml marks every event it parses')
    return mark


class _EventStream:
    """The events of a text, read lazily, one at a time, with one event of lookahead.

    `peek_event`, `get_event` and `check_event` mirror ruamel.yaml's `Parser` protocol, but hand over checked values.
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
        self._peeked: StreamEvent | None = None
        self._yaml = yaml

    def peek_event(self) -> StreamEvent:
        """The next event, left unread.

        Raises:
            MarkedYAMLError: The text is not valid YAML.
            ReaderError: The text holds a character YAML does not allow, such as a control character.
        """
        if self._peeked is None:
            self._peeked = self._convert(next(self._events))
        return self._peeked

    def get_event(self) -> StreamEvent:
        """The next event, read.

        Raises:
            MarkedYAMLError: The text is not valid YAML.
            ReaderError: The text holds a character YAML does not allow, such as a control character.
        """
        event = self.peek_event()
        self._peeked = None
        return event

    def check_boundary(self, boundary: Boundary) -> bool:
        """Whether the next event is `boundary`, leaving it unread.

        Args:
            boundary: The event to test for.

        Raises:
            MarkedYAMLError: The text is not valid YAML.
            ReaderError: The text holds a character YAML does not allow, such as a control character.
        """
        return self.peek_event() is boundary

    def first_refusal(self) -> RecordedRefusal | None:
        """The first construct the scanner or the reader has recorded, in the order the text writes them, or `None`."""
        scanner = self._yaml.scanner
        if not isinstance(scanner, BasicYamlScanner):
            # SAFETY: the types are declared on the parser's base class; `_EventStream` always installs its own.
            raise Unreachable("the parser is built with `basic_yaml`'s scanner")
        return scanner.first_refusal()

    def _convert(self, event: Event) -> StreamEvent:
        """Check an event the parser emitted, once, and read it as a value of this package's own.

        Args:
            event: The parser's event.
        """
        match event:
            case AliasEvent():
                anchor = event.anchor
                if not isinstance(anchor, str):
                    # SAFETY: an alias event is typed with an optional anchor; the parser always names it.
                    raise Unreachable('ruamel.yaml names every alias')
                return Alias(anchor, _mark_of(event))
            case ScalarEvent():
                text = event.value
                if not isinstance(text, str):
                    # SAFETY: an event's value is typed as optional text; a scalar event always carries its text.
                    raise Unreachable('ruamel.yaml reads a scalar as text')
                anchor, tag = self._anchor_and_tag(event)
                return ScalarStart(anchor, tag, event.style is None, text, _mark_of(event))
            case SequenceStartEvent():
                anchor, tag = self._anchor_and_tag(event)
                return SequenceStart(anchor, tag, bool(event.flow_style), _mark_of(event))
            case MappingStartEvent():
                anchor, tag = self._anchor_and_tag(event)
                return MappingStart(anchor, tag, bool(event.flow_style), _mark_of(event))
            case StreamStartEvent():
                return Boundary.STREAM_START
            case StreamEndEvent():
                return Boundary.STREAM_END
            case DocumentStartEvent():
                return Boundary.DOCUMENT_START
            case DocumentEndEvent():
                return Boundary.DOCUMENT_END
            case MappingEndEvent():
                return Boundary.MAPPING_END
            case SequenceEndEvent():
                return Boundary.SEQUENCE_END
            case _:
                # SAFETY: the parser emits only the events above.
                raise Unreachable(f'{type(event).__name__} from the parser')

    def _anchor_and_tag(
        self, event: ScalarEvent | SequenceStartEvent | MappingStartEvent
    ) -> tuple[str | None, str | None]:
        """A node's anchor and its tag, checked, the tag spelled as the text writes it.

        The parser hands over a tag resolved against its handles, so `!!!str` arrives as the tag `!!str` and a tag
        in a flow collection can take the comma after it. The text itself is what the author wrote. The node's start
        mark is where the tag begins only when no anchor is written first, so an anchored node keeps the parser's tag.

        Args:
            event: The parser's event.
        """
        anchor = event.anchor
        if anchor is not None and not isinstance(anchor, str):
            # SAFETY: an event's anchor is typed loosely; the parser gives the anchor's name or nothing.
            raise Unreachable('ruamel.yaml names an anchor with text')
        tag = event.tag
        if tag is not None and not isinstance(tag, str):
            # SAFETY: an event's tag is typed loosely; the parser gives the tag's text or nothing.
            raise Unreachable('ruamel.yaml names a tag with text')
        # The parser gives an event a tag only when one is written in the text, the non-specific `!` included.
        if tag is not None and anchor is None:
            tag = written_token(self._text, _mark_of(event).index)
        return anchor, tag
