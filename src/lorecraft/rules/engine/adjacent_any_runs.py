"""`LC008`: a structure file places two `any` runs side by side in its outline."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import Help, Subdiagnostic, WholeSubject

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class AdjacentAnyRuns(EngineCondition):
    """A structure file places two `any` runs side by side in its outline.

    ## What it does

    Checks for structure files whose `outline` holds two `any` entries next to each other. Two runs side by side match
    exactly what one run matches, so the outline would mean something other than what it says.
    Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
    coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
    the file does not govern is checked as if the file were fixed.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
    agent loads them unreviewed.

    ## Example

    `docs/__meta__/guide.structure.json`, with two runs in a row:

    ```json
    {
      "outline": [
        {"any": true},
        {"any": true, "words": 200}
      ]
    }
    ```

    ## Use instead

    State one run, with the cap the two together were meant to carry:

    ```json
    {
      "outline": [
        {"any": true, "words": 200}
      ]
    }
    ```
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 8)
    NAME: ClassVar[RuleName] = RuleName('adjacent-any-runs')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    def message(self) -> str:
        """Name the condition."""
        return 'outline places two any runs side by side'

    def primary(self) -> WholeSubject:
        """The structure file as a whole: no line of it is at fault."""
        return WholeSubject()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say how to fix the outline."""
        return (Help('state one any run in their place'),)
