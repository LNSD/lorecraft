"""`LC015`: a skills directory cannot be resolved or listed."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import EntryHelp, EntryNote, EntrySubdiagnostic, WholeSubject
from lorecraft.vfs import OsRefusal

from .__ruleset__ import GROUP_ID, RefusedOperation


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class UnreadableSkillsDirectory(EngineCondition):
    """A skills directory cannot be resolved or listed.

    ## What it does

    Checks for skills directories an agent reads, such as `.agents/skills/`, that the operating system refuses to
    resolve, inspect or list, such as one whose permissions deny it, or a link on the way to it that cannot be followed.
    It is reported once, at its path, and nothing under it is loaded. Every other corpus, skill and document is
    checked as if it could be read.

    `lorecraft check` reads the whole repository before it reports anything, and a refusal at that point stops the run
    with an error naming the path and exit status 2, so it does not report this code today: it is reported only where
    the workspace is read without that first read.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the skills directory can be reached, nothing under it is checked, so a violation there goes unreported and
    an agent loads it unreviewed.

    ## Example

    `.agents/skills/`, with its permissions removed:

    ```console
    $ chmod 000 .agents/skills
    ```

    ## Use instead

    Give the directory its permissions back:

    ```console
    $ chmod 755 .agents/skills
    ```

    Attributes:
        operation: What was refused: resolving a link, inspecting an entry or listing a directory.
        failed_at: The path the operation was refused at, which may be one on the way.
        refusal: Why the operating system refused it.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 15)
    NAME: ClassVar[RuleName] = RuleName('unreadable-skills-directory')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    operation: RefusedOperation
    failed_at: RootRelativePath
    refusal: OsRefusal

    def message(self) -> str:
        """Name the condition."""
        return 'skills directory cannot be listed or resolved'

    def primary(self) -> WholeSubject:
        """The entry as a whole, which has no line."""
        return WholeSubject()

    def children(self) -> tuple[EntrySubdiagnostic, ...]:
        """Say which operation was refused where, and why, then say how to fix it."""
        return (
            EntryNote(f'cannot {self.operation.value} {self.failed_at}: {self.refusal.value}'),
            EntryHelp('make the skills directory listable by the process that runs the check'),
        )
