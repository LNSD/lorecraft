"""Validated namespaces shared by document names."""

from dataclasses import dataclass, field
from string import ascii_lowercase, digits
from typing import Self

from lorecraft.core.error import Error

from .filename import AspectFilename
from .timestamp import is_valid_timestamp


class EmptyAspectNamespaceError(Error):
    """A namespace is empty."""

    def __init__(self) -> None:
        super().__init__('namespace cannot be empty')


class InvalidAspectNamespaceCharacterError(Error):
    """A namespace contains a character outside its format.

    Attributes:
        namespace: The rejected namespace.
        position: Zero-based position of the invalid character.
        character: The invalid character.
    """

    namespace: str
    position: int
    character: str

    def __init__(self, namespace: str, position: int) -> None:
        self.namespace = namespace
        self.position = position
        self.character = namespace[position]
        super().__init__(f'invalid character {self.character!r} in namespace {namespace!r}')


@dataclass(frozen=True, slots=True)
class LiteralSegment:
    """A namespace segment that matches only the identical name segment.

    Attributes:
        text: The segment's characters.
    """

    text: str

    def matches(self, name_segment: str) -> bool:
        """Return whether the name segment is this segment's text."""
        return name_segment == self.text


@dataclass(frozen=True, slots=True)
class ZeroRun:
    """A namespace segment of zeroes only, a numeric placeholder for a number of the same width.

    Attributes:
        width: How many digits the placeholder stands for.
    """

    width: int

    def matches(self, name_segment: str) -> bool:
        """Return whether the name segment is a number of exactly this width."""
        return len(name_segment) == self.width and name_segment.isascii() and name_segment.isdigit()


@dataclass(frozen=True, slots=True)
class TimestampToken:
    """A fixed-width timestamp placeholder in a specification namespace."""

    token: str
    width: int

    def matches(self, name_segment: str) -> bool:
        """Return whether a name segment is a valid timestamp of this precision."""
        return is_valid_timestamp(name_segment, self.width)


type NamespaceSegment = LiteralSegment | ZeroRun | TimestampToken

_TIMESTAMP_WIDTHS: dict[str, int] = {
    'YYYY': 4,
    'YYYYMM': 6,
    'YYYYMMDD': 8,
    'YYYYMMDDHH': 10,
    'YYYYMMDDHHMM': 12,
    'YYYYMMDDHHMMSS': 14,
    'YYYYMMDDHHMMSSZZZ': 17,
}


def _parse_segment(text: str) -> NamespaceSegment:
    if text in _TIMESTAMP_WIDTHS:
        return TimestampToken(text, _TIMESTAMP_WIDTHS[text])
    if set(text) == {'0'}:
        return ZeroRun(len(text))
    return LiteralSegment(text)


@dataclass(frozen=True, slots=True)
class AspectNamespace:
    """A validated, possibly nested kebab-case namespace.

    A namespace contains lowercase ASCII and numeric segments, or one of the timestamp tokens
    `YYYY`, `YYYYMM`, `YYYYMMDD`, `YYYYMMDDHH`, `YYYYMMDDHHMM`, `YYYYMMDDHHMMSS`, and
    `YYYYMMDDHHMMSSZZZ`, separated by single hyphens. Timestamp tokens match only a valid segment
    of their exact width; the final token requires literal `UTC`. A segment of zeroes remains a
    numeric placeholder matching decimal digits of the same width.

    Attributes:
        value: The validated namespace, exactly as supplied.
        segments: The hyphen-separated literal, zero-run or timestamp-token segments, read once from the value.
    """

    value: str
    segments: tuple[NamespaceSegment, ...] = field(init=False, compare=False, repr=False)

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated namespace.

        Args:
            raw: Candidate namespace, kept exactly as spelled.

        Raises:
            EmptyAspectNamespaceError: If the namespace is empty.
            InvalidAspectNamespaceCharacterError: If a character falls outside kebab case.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing namespace validation.

        Raises:
            EmptyAspectNamespaceError: If the namespace is empty.
            InvalidAspectNamespaceCharacterError: If a character falls outside kebab case.
        """
        _reject_invalid_namespace(self.value)
        # The class is frozen, so the derived segments are set through `object`; deriving them here means they
        # cannot disagree with the value.
        object.__setattr__(self, 'segments', tuple(_parse_segment(text) for text in self.value.split('-')))

    @property
    def opens_with_placeholder(self) -> bool:
        """True when the namespace's first segment is a numeric placeholder, as the `0000` of `adr-0000`."""
        return isinstance(self.segments[0], ZeroRun)

    def is_prefix_of(self, filename: AspectFilename | str) -> bool:
        """Return whether this namespace is the whole name or its hyphen-delimited prefix.

        A zero-only segment of the namespace matches a digit-only segment of the name of the same width; every
        other segment must be equal. Sequence order and gaps are not looked at.

        Args:
            filename: Document filename stem to test, or a listed name that need not be a valid aspect name, such as
                a skill's directory name.
        """
        name_segments = str(filename).split('-')
        if len(name_segments) < len(self.segments):
            return False
        return all(segment.matches(text) for segment, text in zip(self.segments, name_segments, strict=False))

    def __str__(self) -> str:
        """The namespace exactly as supplied, as findings print it."""
        return self.value


def _reject_invalid_namespace(namespace: str) -> None:
    if not namespace:
        raise EmptyAspectNamespaceError()
    position = 0
    for part in namespace.split('-'):
        if not part:
            raise InvalidAspectNamespaceCharacterError(namespace, min(position, len(namespace) - 1))
        if part not in _TIMESTAMP_WIDTHS:
            for offset, character in enumerate(part):
                if character not in ascii_lowercase and character not in digits:
                    raise InvalidAspectNamespaceCharacterError(namespace, position + offset)
        position += len(part) + 1
