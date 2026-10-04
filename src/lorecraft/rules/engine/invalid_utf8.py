"""`LC001`: a file is not valid UTF-8, so no rule can judge it."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import WholeSubject

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidUtf8(EngineCondition):
    """A file is not valid UTF-8.

    ## What it does

    Checks for files whose bytes are not valid UTF-8. Such a file is reported once, at the whole file, and no rule
    judges it: every rule reads the file's text, and the file has none.

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
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 1)
    NAME: ClassVar[RuleName] = RuleName('invalid-utf8')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    def message(self) -> str:
        """Name the condition."""
        return 'file is not valid UTF-8'

    def primary(self) -> WholeSubject:
        """The whole file, since the bytes that do not decode are not located."""
        return WholeSubject()
