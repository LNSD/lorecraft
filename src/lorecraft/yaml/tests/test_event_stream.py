"""The event stream of a YAML text: lookahead, order and the constructs the scanner recorded."""

import pytest
from ruamel.yaml.events import DocumentStartEvent, MappingStartEvent, ScalarEvent, StreamEndEvent, StreamStartEvent

from ..reader import YamlEventStream


@pytest.mark.unit
class TestYamlEventStream:
    def test_peek_event_with_an_unread_event_leaves_it_for_the_next_get(self) -> None:
        #: Given
        stream = YamlEventStream('a: 1\n')
        peeked = stream.peek_event()

        #: When
        read = stream.get_event()

        #: Then
        assert peeked is read, 'peeking leaves the event unread, so the next read returns the same one'
        assert isinstance(read, StreamStartEvent), f'a stream opens with its start, got {read!r}'

    def test_get_event_with_a_mapping_returns_the_events_in_the_order_they_are_written(self) -> None:
        #: Given
        stream = YamlEventStream('a: 1\n')

        #: When
        kinds = [type(stream.get_event()) for _ in range(5)]

        #: Then
        assert kinds == [StreamStartEvent, DocumentStartEvent, MappingStartEvent, ScalarEvent, ScalarEvent], (
            f'a mapping of one pair reads as its start, the key and the value, got {kinds}'
        )

    def test_check_event_with_the_end_of_an_empty_text_returns_true_without_reading_it(self) -> None:
        #: Given
        stream = YamlEventStream('')
        stream.get_event()

        #: When
        at_end = stream.check_event(StreamEndEvent)

        #: Then
        assert at_end, 'an empty text ends right after its start'
        assert stream.peek_event() is stream.get_event(), 'the check left the end event unread'

    def test_first_refusal_with_nothing_recorded_returns_none(self) -> None:
        #: Given
        stream = YamlEventStream('a: 1\n')
        while not stream.check_event(StreamEndEvent):
            stream.get_event()

        #: When
        refusal = stream.first_refusal()

        #: Then
        assert refusal is None, f'a text of plain pairs records nothing, got {refusal!r}'

    def test_first_refusal_with_an_explicit_key_returns_it_as_the_one_recorded(self) -> None:
        #: Given
        stream = YamlEventStream('? a\n: 1\n')
        while not stream.check_event(StreamEndEvent):
            stream.get_event()

        #: When
        refusal = stream.first_refusal()

        #: Then
        assert refusal is not None, 'the scanner records an explicit key and reads on'
        assert refusal.construct == 'an explicit key', f'an explicit key is recorded as one, got {refusal}'
