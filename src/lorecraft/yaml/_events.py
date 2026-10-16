"""The seam over ruamel.yaml: its events and errors, read by the tree builder in `reader`.

`_EventStream` hands over the parser's events one at a time, and `parse_failure` and `code_point` convert the
library's errors into checked values of this package's own, so the reader builds its problems from them.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from ruamel.yaml import YAML
from ruamel.yaml.error import MarkedYAMLError, StreamMark
from ruamel.yaml.events import Event, MappingStartEvent, ScalarEvent, SequenceStartEvent
from ruamel.yaml.reader import ReaderError

from lorecraft.core.error import Unreachable

from .basic_yaml import BasicYamlParser, BasicYamlReader, BasicYamlScanner, RecordedRefusal, written_token


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


def mark_of(event: Event) -> StreamMark:
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

    `check_event` and its sibling `peek_event` keep ruamel.yaml's names: they mirror its `Parser` protocol, which
    the composer calls.
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
        if not isinstance(scanner, BasicYamlScanner):
            # SAFETY: the types are declared on the parser's base class; `_EventStream` always installs its own.
            raise Unreachable("the parser is built with `basic_yaml`'s scanner")
        return scanner.first_refusal()

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
        return written_token(self._text, mark_of(event).index)

    def check_event(self, *kinds: type[Event]) -> bool:
        """Whether the next event is of one of `kinds`, leaving it unread.

        Args:
            kinds: The event classes to test for.

        Raises:
            MarkedYAMLError: The text is not valid YAML.
            ReaderError: The text holds a character YAML does not allow, such as a control character.
        """
        return isinstance(self.peek_event(), kinds)
