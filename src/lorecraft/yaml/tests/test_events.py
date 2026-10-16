"""The seam over ruamel.yaml: the events and errors it hands over, as checked values of this package's own."""

import pytest
from ruamel.yaml.error import MarkedYAMLError, StreamMark
from ruamel.yaml.events import ScalarEvent

from lorecraft.core.error import Unreachable

from .._events import Alias, Boundary, ParseFailure, ScalarStart, _EventStream, parse_failure


def _events(text: str) -> list[object]:
    stream = _EventStream(text)
    events: list[object] = []
    while not events or events[-1] is not Boundary.STREAM_END:
        events.append(stream.get_event())
    return events


@pytest.mark.unit
class TestEventStream:
    def test_get_event_with_a_plain_scalar_returns_its_text_and_plainness(self) -> None:
        #: Given
        text = 'a: 1\n'

        #: When
        events = _events(text)

        #: Then
        nodes = [event for event in events if isinstance(event, ScalarStart)]
        assert [(node.text, node.plain) for node in nodes] == [
            ('a', True),
            ('1', True),
        ], f'{text!r} holds two plain scalars, got {nodes!r}'

    def test_get_event_with_a_tag_returns_it_spelled_as_written(self) -> None:
        #: Given
        text = '!!!str a\n'

        #: When
        node = next(event for event in _events(text) if isinstance(event, ScalarStart))

        #: Then
        assert node.tag == '!!!str', f'{text!r} spells its tag !!!str, got {node.tag!r}'

    def test_get_event_with_an_alias_returns_the_anchor_it_names(self) -> None:
        #: Given
        text = '- *a\n'

        #: When
        alias = next(event for event in _events(text) if isinstance(event, Alias))

        #: Then
        assert alias.anchor == 'a', f'{text!r} names the anchor a, got {alias.anchor!r}'

    def test_get_event_with_a_non_string_anchor_raises_unreachable(self) -> None:
        #: Given
        stream = _EventStream('a\n')
        mark = StreamMark('<test>', 0, 0, 0)
        stream._events = iter([ScalarEvent(42, None, (True, False), 'a', mark, mark)])

        #: When / Then
        with pytest.raises(Unreachable):
            stream.get_event()

    def test_first_refusal_with_a_recorded_construct_returns_it(self) -> None:
        #: Given
        stream = _EventStream('? a\n: 1\n')
        while stream.get_event() is not Boundary.STREAM_END:
            pass

        #: When
        recorded = stream.first_refusal()

        #: Then
        assert recorded is not None, 'an explicit key is recorded by the scanner'


@pytest.mark.unit
class TestParseFailure:
    def test_parse_failure_with_no_texts_returns_empty_texts(self) -> None:
        #: Given
        error = MarkedYAMLError()

        #: When
        failure = parse_failure(error)

        #: Then
        assert failure == ParseFailure('', '', None, None), f'a bare error carries nothing, got {failure!r}'
