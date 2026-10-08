"""The line, offset, bytes and reason kept from the decoder's failure to read a file as UTF-8."""

import pytest

from ..utf8_failure import Utf8Failure, Utf8Reason


def _decode_error(data: bytes) -> UnicodeDecodeError:
    try:
        data.decode('utf-8')
    except UnicodeDecodeError as exc:
        return exc
    raise AssertionError('the bytes decode as UTF-8')


@pytest.mark.unit
class TestUtf8Reason:
    def test_utf8_reason_with_an_unknown_decoder_wording_returns_other(self) -> None:
        #: Given
        wording = 'some future wording'

        #: When
        reason = Utf8Reason(wording)

        #: Then
        assert reason is Utf8Reason.OTHER, 'a wording the enum does not know is still a reportable reason'


@pytest.mark.unit
class TestUtf8FailureFromError:
    def test_from_error_with_a_latin1_byte_on_the_second_line_keeps_its_line_offset_and_bytes(self) -> None:
        #: Given
        error = _decode_error(b'# Guide\nCaf\xe9 setup\n')

        #: When
        failure = Utf8Failure.from_error(error)

        #: Then
        assert failure == Utf8Failure(
            line=2,
            offset=11,
            invalid=b'\xe9',
            reason=Utf8Reason.INVALID_CONTINUATION_BYTE,
        ), 'the first invalid byte is located by line and by offset into the file'

    def test_from_error_with_an_invalid_first_byte_returns_the_first_line(self) -> None:
        #: Given
        error = _decode_error(b'\xff# Guide\n')

        #: When
        failure = Utf8Failure.from_error(error)

        #: Then
        assert failure == Utf8Failure(
            line=1,
            offset=0,
            invalid=b'\xff',
            reason=Utf8Reason.INVALID_START_BYTE,
        ), 'a byte that cannot begin a sequence is rejected as a start byte'

    def test_from_error_with_a_file_ending_inside_a_sequence_keeps_the_truncated_bytes(self) -> None:
        #: Given
        error = _decode_error(b'one\ntwo\n\xe2\x82')

        #: When
        failure = Utf8Failure.from_error(error)

        #: Then
        assert failure == Utf8Failure(
            line=3,
            offset=8,
            invalid=b'\xe2\x82',
            reason=Utf8Reason.UNEXPECTED_END_OF_DATA,
        ), 'the incomplete sequence is kept whole, on the line it starts on'


@pytest.mark.unit
class TestUtf8Failure:
    def test_init_with_a_line_below_one_raises_value_error(self) -> None:
        #: Given
        line = 0

        #: When
        with pytest.raises(ValueError, match='line') as exc_info:
            Utf8Failure(line=line, offset=0, invalid=b'\xff', reason=Utf8Reason.INVALID_START_BYTE)

        #: Then
        assert '0' in str(exc_info.value), 'the message names the value received'

    def test_init_with_a_negative_offset_raises_value_error(self) -> None:
        #: Given
        offset = -1

        #: When
        with pytest.raises(ValueError, match='offset') as exc_info:
            Utf8Failure(line=1, offset=offset, invalid=b'\xff', reason=Utf8Reason.INVALID_START_BYTE)

        #: Then
        assert '-1' in str(exc_info.value), 'the message names the value received'

    def test_init_with_no_invalid_bytes_raises_value_error(self) -> None:
        #: Given
        invalid = b''

        #: When
        with pytest.raises(ValueError, match='invalid') as exc_info:
            Utf8Failure(line=1, offset=0, invalid=invalid, reason=Utf8Reason.INVALID_START_BYTE)

        #: Then
        assert "b''" in str(exc_info.value), 'the message names the value received'
