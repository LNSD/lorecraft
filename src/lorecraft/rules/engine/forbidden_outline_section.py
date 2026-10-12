"""`LC007`: a structure file forbids a section its own outline names."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import Help, Note, Subdiagnostic, WholeSubject

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class ForbiddenOutlineSection(EngineCondition):
    """A structure file forbids a section its own outline names.

    ## What it does

    Checks for structure files whose `forbidden` list names a section that the same file's `outline` names, so no
    document could hold to both.
    Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
    coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
    the file does not govern is checked as if the file were fixed.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
    agent loads them unreviewed.

    ## Example

    `docs/__meta__/guide.structure.json`, requiring and forbidding `Overview`:

    ```json
    {
      "outline": [{"section": "Overview"}],
      "forbidden": ["Overview"]
    }
    ```

    ## Use instead

    Keep the section in one of the two:

    ```json
    {
      "outline": [{"section": "Overview"}],
      "forbidden": ["Draft"]
    }
    ```

    Attributes:
        sections: The section names both in the outline and forbidden, sorted.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 7)
    NAME: ClassVar[RuleName] = RuleName('forbidden-outline-section')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    sections: tuple[str, ...]

    def message(self) -> str:
        """Name the condition."""
        return 'outline names a section the file also forbids'

    def primary(self) -> WholeSubject:
        """The structure file as a whole: no line of it is at fault."""
        return WholeSubject()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Name the contradicted sections, then say to keep each in one place."""
        return (
            Note(f'named and forbidden: {", ".join(self.sections)}'),
            Help('keep each section in the outline or in the forbidden list, not both'),
        )
