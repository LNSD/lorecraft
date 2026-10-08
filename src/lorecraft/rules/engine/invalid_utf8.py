"""`LC001`: a file is not valid UTF-8, so no rule can judge it."""

from dataclasses import dataclass
from typing import ClassVar, assert_never

from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.vfs import Utf8Failure, Utf8Reason

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidUtf8(EngineCondition):
    """A file is not valid UTF-8.

    ## What it does

    Checks for files whose bytes are not valid UTF-8. Such a file is reported once, at the line of its first invalid
    byte, and no rule judges it: every rule reads the file's text, and the file has none.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    An agent that loads the file reads replacement characters, or nothing, where the bytes do not decode, and no
    check can tell whether the rest of the file holds to its specification.

    ## Example

    `docs/guide/setup.md`, saved as Latin-1, so its `é` is the single byte `0xE9`:

    ```markdown
    # Café setup
    ```

    ## Use instead

    Save the file as UTF-8, where `é` is the two bytes `0xC3 0xA9`:

    ```markdown
    # Café setup
    ```

    Attributes:
        failure: Where the file's bytes first stop being UTF-8, and why.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 1)
    NAME: ClassVar[RuleName] = RuleName('invalid-utf8')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    failure: Utf8Failure

    def message(self) -> str:
        """Name the condition."""
        return 'file is not valid UTF-8'

    def primary(self) -> Here:
        """The line of the first byte that does not decode."""
        return Here(LineNumber.from_int(self.failure.line))

    def labels(self) -> tuple[Label, ...]:
        """Name the bytes that do not decode, where they sit in the file, and why the decoder rejected them."""
        invalid = ' '.join(f'0x{byte:02X}' for byte in self.failure.invalid)
        subject = f'{invalid} at byte offset {self.failure.offset}'
        reason = self.failure.reason
        # The decoder's wording is not used: for an invalid continuation byte it points at the lead byte, so it
        # would call the lead byte the bad continuation.
        match reason:
            case Utf8Reason.INVALID_START_BYTE:
                text = f'{subject} cannot start a character'
            case Utf8Reason.INVALID_CONTINUATION_BYTE:
                text = f'{subject} starts a character the next byte does not continue'
            case Utf8Reason.UNEXPECTED_END_OF_DATA:
                text = f'{subject} starts a character the file ends inside'
            case Utf8Reason.OTHER:
                text = f'{subject} does not decode'
            case _:
                assert_never(reason)
        return (Label(self.primary(), text),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say how to fix the file."""
        return (Help('save the file as UTF-8'),)
