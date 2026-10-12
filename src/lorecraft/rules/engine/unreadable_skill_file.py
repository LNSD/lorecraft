"""`LC017`: a skill's `SKILL.md` cannot be resolved."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import EntryHelp, EntryNote, EntrySubdiagnostic, WholeSubject
from lorecraft.vfs import OsRefusal

from .__ruleset__ import GROUP_ID, RefusedOperation


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class UnreadableSkillFile(EngineCondition):
    """A skill's `SKILL.md` cannot be resolved.

    ## What it does

    Checks for skills whose `SKILL.md`, or a link on the way to it, the operating system refuses to resolve or inspect,
    such as a link into a directory whose permissions deny it.
    It is reported once, at its path, and nothing under it is loaded. Every other corpus, skill and document is
    checked as if it could be read.

    `lorecraft check` reads the whole repository before it reports anything, and a refusal at that point stops the run
    with an error naming the path and exit status 2, so it does not report this code today: it is reported only where
    the workspace is read without that first read.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the skill's `SKILL.md` can be reached, nothing under it is checked, so a violation there goes unreported and
    an agent loads it unreviewed.

    ## Example

    `.agents/skills/review/SKILL.md`, a link into a directory with its permissions removed:

    ```console
    $ ln -s ../../../shared/review.md .agents/skills/review/SKILL.md
    $ chmod 000 shared
    ```

    ## Use instead

    Give the directory its permissions back:

    ```console
    $ chmod 755 shared
    ```

    Attributes:
        operation: What was refused: resolving a link, or inspecting an entry on the way to the file.
        failed_at: The path the operation was refused at, which may be one on the way.
        refusal: Why the operating system refused it.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 17)
    NAME: ClassVar[RuleName] = RuleName('unreadable-skill-file')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    operation: RefusedOperation
    failed_at: RootRelativePath
    refusal: OsRefusal

    def message(self) -> str:
        """Name the condition."""
        return 'skill file cannot be resolved'

    def primary(self) -> WholeSubject:
        """The entry as a whole, which has no line."""
        return WholeSubject()

    def children(self) -> tuple[EntrySubdiagnostic, ...]:
        """Say which operation was refused where, and why, then say how to fix it."""
        return (
            EntryNote(f'cannot {self.operation.value} {self.failed_at}: {self.refusal.value}'),
            EntryHelp('make the `SKILL.md`, and what it links to, readable by the process that runs the check'),
        )
