"""Where a file's bytes first stop being UTF-8, and why, kept from the decoder's failure.

The decoder's `UnicodeDecodeError` locates the first byte that does not decode, as an offset into the bytes. This
module keeps that as plain data: the line the byte is on, counted by line feeds, its offset, the bytes the decoder
rejected and the reason as a closed type rather than the decoder's wording. Being plain data, a persisted result
keeps it.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Self


class Utf8Reason(Enum):
    """Why the UTF-8 decoder rejected a byte; the value is the decoder's wording, which only looks the member up."""

    INVALID_START_BYTE = 'invalid start byte'
    """The byte cannot begin a UTF-8 sequence."""

    INVALID_CONTINUATION_BYTE = 'invalid continuation byte'
    """The byte begins a sequence whose next byte is not a continuation byte."""

    UNEXPECTED_END_OF_DATA = 'unexpected end of data'
    """The file ends inside a sequence."""

    OTHER = 'invalid data'
    """Any other wording: the three above are CPython's, and a runtime that words a reason differently lands here."""

    @classmethod
    def _missing_(cls, value: object) -> 'Utf8Reason':
        """Map a wording this enum does not know to `OTHER`, so an unfamiliar decoder reports instead of crashing.

        Args:
            value: The decoder's wording of the reason, which no member carries.
        """
        return cls.OTHER


@dataclass(frozen=True, slots=True)
class Utf8Failure:
    """Where a file's bytes first stop being UTF-8, and why.

    Raises:
        ValueError: If `line` is below 1, `offset` is negative or `invalid` is empty.

    Attributes:
        line: The line the first invalid byte is on, at least 1, counted by line feeds, so a file that breaks lines
            with bare carriage returns reports line 1.
        offset: The zero-based offset of the first invalid byte in the file; never negative.
        invalid: The bytes the decoder rejected, starting at `offset`; never empty.
        reason: Why the decoder rejected them.
    """

    line: int
    offset: int
    invalid: bytes
    reason: Utf8Reason

    def __post_init__(self) -> None:
        """Refuse a failure that names no line, a byte before the file or no byte at all."""
        if self.line < 1:
            raise ValueError(f'line must be at least 1, got {self.line}')
        if self.offset < 0:
            raise ValueError(f'offset must not be negative, got {self.offset}')
        if not self.invalid:
            raise ValueError(f'invalid must not be empty, got {self.invalid!r}')

    @classmethod
    def from_error(cls, error: UnicodeDecodeError) -> Self:
        """Keep what the decoder's failure says about the first invalid byte.

        Args:
            error: The failure of decoding a file's bytes as UTF-8.
        """
        return cls(
            line=error.object.count(b'\n', 0, error.start) + 1,
            offset=error.start,
            invalid=error.object[error.start : error.end],
            reason=Utf8Reason(error.reason),
        )
