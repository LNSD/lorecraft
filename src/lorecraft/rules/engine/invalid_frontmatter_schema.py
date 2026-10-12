"""`LC010`: a structure file's frontmatter schema is not a valid JSON Schema."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import Note, Subdiagnostic, WholeSubject

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidFrontmatterSchema(EngineCondition):
    """A structure file's frontmatter schema is not a valid JSON Schema.

    ## What it does

    Checks for structure files whose `frontmatter` key is not a valid JSON Schema of the 2020-12 dialect.
    Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
    coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
    the file does not govern is checked as if the file were fixed.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
    agent loads them unreviewed.

    ## Example

    `docs/__meta__/guide.structure.json`, with `required` holding a string where a list is due:

    ```json
    {
      "frontmatter": {"type": "object", "required": "name"}
    }
    ```

    ## Use instead

    Write the keyword as the dialect defines it:

    ```json
    {
      "frontmatter": {"type": "object", "required": ["name"]}
    }
    ```

    Attributes:
        problem: What the JSON Schema meta-schema rejected.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 10)
    NAME: ClassVar[RuleName] = RuleName('invalid-frontmatter-schema')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    problem: str

    def message(self) -> str:
        """Name the condition."""
        return 'frontmatter schema is not a valid JSON Schema'

    def primary(self) -> WholeSubject:
        """The structure file as a whole: no line of it is at fault."""
        return WholeSubject()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say what the meta-schema rejected."""
        return (Note(self.problem),)
