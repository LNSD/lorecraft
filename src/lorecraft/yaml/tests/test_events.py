"""The seam over ruamel.yaml: its errors, as checked values of this package's own."""

import pytest
from ruamel.yaml.error import MarkedYAMLError
from ruamel.yaml.events import StreamEndEvent

from .._events import ParseFailure, _EventStream, parse_failure


@pytest.mark.unit
class TestEventStream:
    def test_first_refusal_with_a_recorded_construct_returns_it(self) -> None:
        #: Given
        stream = _EventStream('? a\n: 1\n')
        while not stream.check_event(StreamEndEvent):
            stream.get_event()

        #: When
        recorded = stream.first_refusal()

        #: Then
        assert recorded is not None, 'an explicit key is recorded by the scanner'

    def test_first_refusal_with_no_recorded_construct_returns_none(self) -> None:
        #: Given
        stream = _EventStream('a: 1\n')
        while not stream.check_event(StreamEndEvent):
            stream.get_event()

        #: When
        recorded = stream.first_refusal()

        #: Then
        assert recorded is None, f'a plain mapping records nothing, got {recorded!r}'


@pytest.mark.unit
class TestParseFailure:
    def test_parse_failure_with_no_texts_returns_empty_texts(self) -> None:
        #: Given
        error = MarkedYAMLError()

        #: When
        failure = parse_failure(error)

        #: Then
        assert failure == ParseFailure('', '', None, None), f'a bare error carries nothing, got {failure!r}'
