"""The events of a YAML text, read through the grammar the subset is held to.

The events come from ruamel.yaml's pure-Python reader, scanner and parser, bent by the subclasses in `basic_yaml`.
They are read lazily, so a text that fails stops being read where it fails, and the constructs the scanner recorded by
then are the ones written above the failure.
"""

from collections.abc import Iterator

from ruamel.yaml import YAML
from ruamel.yaml.events import Event, MappingStartEvent, ScalarEvent, SequenceStartEvent

from .basic_yaml import BasicYamlParser, BasicYamlReader, BasicYamlScanner, RecordedRefusal, written_token


class YamlEventStream:
    """The events of a text, read lazily, one at a time, with one event of lookahead.

    The value is built from them by the caller, never by ruamel.yaml's loader or constructor, so no tag ruamel.yaml
    resolves and no type it constructs is ever involved.
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
            raise AssertionError("unreachable: the parser is built with `lorecraft.yaml`'s scanner and reader")
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
        mark = event.start_mark
        if mark is None:
            # An event's mark is optional only in its constructor's signature: the parser marks every event it emits.
            raise AssertionError('unreachable: ruamel.yaml marks every event it parses')
        return written_token(self._text, mark.index)

    def check_event(self, *kinds: type[Event]) -> bool:
        """Whether the next event is of one of `kinds`, leaving it unread.

        Args:
            kinds: The event classes to test for.
        """
        return isinstance(self.peek_event(), kinds)
