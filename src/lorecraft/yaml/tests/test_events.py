"""The seam over ruamel.yaml: its errors, as checked values of this package's own."""

import pytest
from ruamel.yaml.error import MarkedYAMLError

from .._events import ParseFailure, parse_failure


@pytest.mark.unit
class TestParseFailure:
    def test_parse_failure_with_no_texts_returns_empty_texts(self) -> None:
        #: Given
        error = MarkedYAMLError()

        #: When
        failure = parse_failure(error)

        #: Then
        assert failure == ParseFailure('', '', None, None), f'a bare error carries nothing, got {failure!r}'
