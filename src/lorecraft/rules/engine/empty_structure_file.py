"""`LC004`: a structure file states no rule."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import Help, Subdiagnostic, WholeSubject

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class EmptyStructureFile(EngineCondition):
    """A structure file states no rule.

    ## What it does

    Checks for structure files that follow the structure format and state no rule: no title check, no empty-section
    ban, no outline, no forbidden sections, no token budget and no frontmatter schema, so the file would check nothing.
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

    `docs/__meta__/guide.structure.json`, stating nothing:

    ```json
    {}
    ```

    ## Use instead

    State the rules the corpus is held to:

    ```json
    {
      "tokens": 4000
    }
    ```
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 4)
    NAME: ClassVar[RuleName] = RuleName('empty-structure-file')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    def message(self) -> str:
        """Name the condition."""
        return 'structure file states no rule'

    def primary(self) -> WholeSubject:
        """The structure file as a whole: no line of it is at fault."""
        return WholeSubject()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say how to fix the file."""
        return (Help('state a rule, or delete the file'),)
