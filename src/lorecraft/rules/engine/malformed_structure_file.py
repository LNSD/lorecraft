"""`LC003`: a structure file does not follow the structure format."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import Help, Note, Subdiagnostic, WholeSubject

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MalformedStructureFile(EngineCondition):
    """A structure file does not follow the structure format.

    ## What it does

    Checks for structure files that are not JSON, or are JSON that does not follow the structure format: a key the
    format does not define, a value of the wrong type, or a count below one.
    Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
    coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
    the file does not govern is checked as if the file were fixed.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
    agent loads them unreviewed.

    ## Example

    `docs/__meta__/guide.structure.json`, with a key the format does not define:

    ```json
    {
      "max_tokens": 4000
    }
    ```

    ## Use instead

    Use the key the format defines:

    ```json
    {
      "tokens": 4000
    }
    ```

    Attributes:
        problems: Every problem found, as `<key path>: <message>`.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 3)
    NAME: ClassVar[RuleName] = RuleName('malformed-structure-file')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    problems: tuple[str, ...]

    def message(self) -> str:
        """Name the condition."""
        return 'structure file does not follow the structure format'

    def primary(self) -> WholeSubject:
        """The structure file as a whole: no line of it is at fault."""
        return WholeSubject()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """List every problem found, then say to fix them."""
        notes: list[Subdiagnostic] = [Note(problem) for problem in self.problems]
        notes.append(Help('fix each problem listed'))
        return tuple(notes)
