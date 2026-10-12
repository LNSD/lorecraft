"""`LC009`: a structure file's title pattern is not a valid regular expression."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import Note, Subdiagnostic, WholeSubject

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidTitlePattern(EngineCondition):
    """A structure file's title pattern is not a valid regular expression.

    ## What it does

    Checks for structure files whose `title.pattern` does not compile as a regular expression.
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

    `docs/__meta__/guide.structure.json`, with an unclosed bracket:

    ```json
    {
      "title": {"pattern": "[A-Z"}
    }
    ```

    ## Use instead

    Write a pattern that compiles:

    ```json
    {
      "title": {"pattern": "^[A-Z]"}
    }
    ```

    Attributes:
        pattern: The pattern, exactly as written.
        problem: What the regular expression compiler rejected.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 9)
    NAME: ClassVar[RuleName] = RuleName('invalid-title-pattern')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    pattern: str
    problem: str

    def message(self) -> str:
        """Name the condition."""
        return 'title pattern is not a valid regular expression'

    def primary(self) -> WholeSubject:
        """The structure file as a whole: no line of it is at fault."""
        return WholeSubject()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Name the pattern and what was wrong with it."""
        return (Note(f'pattern {self.pattern!r}: {self.problem}'),)
