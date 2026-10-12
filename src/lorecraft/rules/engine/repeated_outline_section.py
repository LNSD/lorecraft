"""`LC005`: a structure file names an outline section more than once."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import Help, Note, Subdiagnostic, WholeSubject

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class RepeatedOutlineSection(EngineCondition):
    """A structure file names an outline section more than once.

    ## What it does

    Checks for structure files whose `outline` names one section more than once, so a document could never hold to it.
    Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
    coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
    the file does not govern is checked as if the file were fixed.

    `lorecraft check` does not report this code yet: it stops with exit status 2 at a structure file it cannot
    use, so the file is not reported and no document it governs is listed as skipped.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
    agent loads them unreviewed.

    ## Example

    `docs/__meta__/guide.structure.json`, naming `Overview` twice:

    ```json
    {
      "outline": [
        {"section": "Overview"},
        {"section": "Details"},
        {"section": "Overview"}
      ]
    }
    ```

    ## Use instead

    Name each section once:

    ```json
    {
      "outline": [
        {"section": "Overview"},
        {"section": "Details"}
      ]
    }
    ```

    Attributes:
        sections: The section names the outline repeats, sorted.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 5)
    NAME: ClassVar[RuleName] = RuleName('repeated-outline-section')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    sections: tuple[str, ...]

    def message(self) -> str:
        """Name the condition."""
        return 'outline names a section more than once'

    def primary(self) -> WholeSubject:
        """The structure file as a whole: no line of it is at fault."""
        return WholeSubject()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Name the repeated sections, then say to name each once."""
        return (
            Note(f'repeated: {", ".join(self.sections)}'),
            Help('name each section once'),
        )
