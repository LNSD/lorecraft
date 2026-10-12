"""`LC003`: a structure file does not parse as the structure format, or states no rule."""

from dataclasses import dataclass
from typing import ClassVar, assert_never

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import Help, Note, Subdiagnostic, WholeSubject

from .__ruleset__ import GROUP_ID


@dataclass(frozen=True, slots=True)
class FormatViolated:
    """The file is not JSON, or is JSON that does not follow the structure format.

    Attributes:
        problems: Every problem found, as `<key path>: <message>`.
    """

    problems: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NoRuleStated:
    """The file follows the structure format and states no rule, so it would check nothing."""


type Cause = FormatViolated | NoRuleStated
"""What makes the structure file malformed."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MalformedStructureFile(EngineCondition):
    """A structure file does not follow the structure format, or states no rule.

    ## What it does

    Checks for structure files that are not a usable statement of the structure format, in one of two ways: the file
    is not JSON, or is JSON that holds a key the format does not define, a value of the wrong type or a count below
    one; or the file is in the format and states no rule, so it would check nothing.
    Such a file is reported once, at the file, and every document its meta spec governs is listed as skipped in
    coverage, with no rule run over it: a document that was not checked is never reported as clean. Every document
    the file does not govern is checked as if the file were fixed.

    The message says which of the two it is, and for the first, lists every problem found.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
    agent loads them unreviewed.

    ## A file that does not follow the format

    `docs/__meta__/guide.structure.json`, with a key the format does not define:

    ```json
    {
      "max_tokens": 4000
    }
    ```

    Use the key the format defines:

    ```json
    {
      "tokens": 4000
    }
    ```

    ## A file that states no rule

    `docs/__meta__/guide.structure.json`, stating nothing. The file would check no title, no empty section, no
    outline, no forbidden section, no token budget and no frontmatter schema:

    ```json
    {}
    ```

    State the rules the corpus is held to, or delete the file:

    ```json
    {
      "tokens": 4000
    }
    ```

    Attributes:
        cause: How the file is malformed: the problems found in it, or that it states no rule.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 3)
    NAME: ClassVar[RuleName] = RuleName('malformed-structure-file')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    cause: Cause

    def message(self) -> str:
        """Name the way the file is malformed."""
        match self.cause:
            case FormatViolated():
                return 'structure file does not follow the structure format'
            case NoRuleStated():
                return 'structure file states no rule'
            case _:
                assert_never(self.cause)

    def primary(self) -> WholeSubject:
        """The structure file as a whole: no line of it is at fault."""
        return WholeSubject()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """List every problem found and say to fix them, or say to state a rule or delete the file."""
        match self.cause:
            case FormatViolated(problems=problems):
                notes: list[Subdiagnostic] = [Note(problem) for problem in problems]
                notes.append(Help('fix each problem listed'))
                return tuple(notes)
            case NoRuleStated():
                return (Help('state a rule, or delete the file'),)
            case _:
                assert_never(self.cause)
