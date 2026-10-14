"""The line, offset, bytes and reason kept from the decoder's failure to read a file as UTF-8."""

import pytest

from ..utf8_failure import ByteOffset, Utf8Failure, Utf8Line, Utf8Reason


def _decode_error(data: bytes) -> UnicodeDecodeError:
    try:
        data.decode('utf-8')
    except UnicodeDecodeError as exc:
        return exc
    raise AssertionError('unreachable: the bytes decode as UTF-8')


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
            line=Utf8Line(2),
            offset=ByteOffset(11),
            invalid=b'\xe9',
            reason=Utf8Reason.INVALID_CONTINUATION_BYTE,
        ), 'the first invalid byte is located by line and by offset into the file'

    def test_from_error_with_other_line_separators_before_the_byte_counts_only_line_feeds(self) -> None:
        #: Given
        # a vertical tab, a form feed, U+0085 and U+2028, none of which ends a line, then one line feed
        error = _decode_error(b'a\x0bb\x0cc\xc2\x85d\xe2\x80\xa8e\nCaf\xe9')

        #: When
        failure = Utf8Failure.from_error(error)

        #: Then
        assert failure.line == Utf8Line(2), f'a line feed ends a line and these do not, got line {failure.line}'

    def test_from_error_with_carriage_returns_before_the_byte_counts_each_line_break(self) -> None:
        #: Given
        # a lone carriage return, a CRLF pair counted once, then a lone carriage return before the invalid byte
        error = _decode_error(b'a\rb\r\nc\rCaf\xe9')

        #: When
        failure = Utf8Failure.from_error(error)

        #: Then
        assert failure.line == Utf8Line(4), f'a lone `\\r` and a CRLF pair each end one line, got {failure.line}'

    def test_from_error_with_an_invalid_first_byte_returns_the_first_line(self) -> None:
        #: Given
        error = _decode_error(b'\xff# Guide\n')

        #: When
        failure = Utf8Failure.from_error(error)

        #: Then
        assert failure == Utf8Failure(
            line=Utf8Line(1),
            offset=ByteOffset(0),
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
            line=Utf8Line(3),
            offset=ByteOffset(8),
            invalid=b'\xe2\x82',
            reason=Utf8Reason.UNEXPECTED_END_OF_DATA,
        ), 'the incomplete sequence is kept whole, on the line it starts on'


@pytest.mark.unit
class TestUtf8Failure:
    def test_init_with_a_line_below_one_raises_value_error(self) -> None:
        #: Given
        line = Utf8Line(0)
        offset = ByteOffset(0)

        #: When
        with pytest.raises(ValueError) as exc_info:
            Utf8Failure(line=line, offset=offset, invalid=b'\xff', reason=Utf8Reason.INVALID_START_BYTE)

        #: Then
        assert '0' in str(exc_info.value), 'the message names the value received'

    def test_init_with_a_negative_offset_raises_value_error(self) -> None:
        #: Given
        offset = ByteOffset(-1)
        line = Utf8Line(1)

        #: When
        with pytest.raises(ValueError) as exc_info:
            Utf8Failure(line=line, offset=offset, invalid=b'\xff', reason=Utf8Reason.INVALID_START_BYTE)

        #: Then
        assert '-1' in str(exc_info.value), 'the message names the value received'

    def test_init_with_no_invalid_bytes_raises_value_error(self) -> None:
        #: Given
        invalid = b''
        line = Utf8Line(1)
        offset = ByteOffset(0)

        #: When
        with pytest.raises(ValueError) as exc_info:
            Utf8Failure(line=line, offset=offset, invalid=invalid, reason=Utf8Reason.INVALID_START_BYTE)

        #: Then
        assert "b''" in str(exc_info.value), 'the message names the value received'
