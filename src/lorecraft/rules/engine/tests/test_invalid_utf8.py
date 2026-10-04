"""`LC001`, `invalid-utf8`: the engine's diagnostic for a file whose bytes are not UTF-8."""

import pytest

from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import WholeSubject

from ..invalid_utf8 import InvalidUtf8


@pytest.mark.unit
class TestInvalidUtf8:
    def test_code_of_invalid_utf8_prints_lc001(self) -> None:
        #: Given
        condition = InvalidUtf8

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC001', "the condition is the first of the engine's group"

    def test_severity_of_invalid_utf8_is_error(self) -> None:
        #: Given
        condition = InvalidUtf8

        #: When
        severity = condition.SEVERITY

        #: Then
        assert severity is Severity.ERROR, 'a file that does not decode always fails the run'

    def test_message_of_an_occurrence_names_the_condition(self) -> None:
        #: Given
        occurrence = InvalidUtf8()

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'file is not valid UTF-8', 'the message states the condition, lowercase, with no period'

    def test_primary_of_an_occurrence_is_the_whole_subject(self) -> None:
        #: Given
        occurrence = InvalidUtf8()

        #: When
        primary = occurrence.primary()

        #: Then
        assert primary == WholeSubject(), 'the bytes that do not decode are not located, so the file is pointed at'
