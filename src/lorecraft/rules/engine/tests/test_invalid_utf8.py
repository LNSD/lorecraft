"""`LC001`, `invalid-utf8`: the engine's diagnostic for a file whose bytes are not UTF-8."""

import pytest

from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import Help, Here, Label
from lorecraft.vfs import Utf8Failure, Utf8Reason

from ..invalid_utf8 import InvalidUtf8


def _occurrence() -> InvalidUtf8:
    """`é` saved as Latin-1 on line 4, the 32nd byte of the file."""
    failure = Utf8Failure(
        line=4,
        offset=31,
        invalid=b'\xe9',
        reason=Utf8Reason.INVALID_CONTINUATION_BYTE,
    )
    return InvalidUtf8(failure=failure)


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
        occurrence = _occurrence()

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'file is not valid UTF-8', 'the message states the condition, lowercase, with no period'

    def test_primary_of_an_occurrence_is_the_line_of_the_first_invalid_byte(self) -> None:
        #: Given
        occurrence = _occurrence()

        #: When
        primary = occurrence.primary()

        #: Then
        assert primary == Here(LineNumber.from_int(4)), 'the file is pointed at where its bytes stop being UTF-8'

    def test_labels_of_an_occurrence_name_the_bytes_their_offset_and_the_reason_at_that_line(self) -> None:
        #: Given
        occurrence = _occurrence()

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (
            Label(
                Here(LineNumber.from_int(4)),
                '0xE9 at byte offset 31 starts a character the next byte does not continue',
            ),
        ), 'the one label sits on the primary line and says what the decoder rejected'

    def test_labels_of_an_occurrence_rejecting_several_bytes_name_each(self) -> None:
        #: Given
        failure = Utf8Failure(
            line=1,
            offset=0,
            invalid=b'\xe2\x82',
            reason=Utf8Reason.UNEXPECTED_END_OF_DATA,
        )
        occurrence = InvalidUtf8(failure=failure)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (
            Label(Here(LineNumber.from_int(1)), '0xE2 0x82 at byte offset 0 starts a character the file ends inside'),
        ), 'every rejected byte is named, in file order'

    def test_labels_of_an_occurrence_with_another_reason_say_only_that_the_bytes_do_not_decode(self) -> None:
        #: Given
        failure = Utf8Failure(line=1, offset=2, invalid=b'\xed', reason=Utf8Reason.OTHER)
        occurrence = InvalidUtf8(failure=failure)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(1)), '0xED at byte offset 2 does not decode'),), (
            'a reason the package has no wording for is not worded after the decoder'
        )

    def test_children_of_an_occurrence_say_to_save_the_file_as_utf8(self) -> None:
        #: Given
        occurrence = _occurrence()

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Help('save the file as UTF-8'),), 'the one sub-diagnostic is the fix, with no place'
