"""`LC002`: a path cannot be read."""

from dataclasses import dataclass
from typing import ClassVar, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import EntryHelp, EntryNote, EntrySubdiagnostic, WholeSubject
from lorecraft.vfs import OsRefusal

from .__ruleset__ import GROUP_ID, RefusedOperation


@dataclass(frozen=True, slots=True)
class Refused:
    """The operating system refused an operation on the path.

    Attributes:
        operation: What was refused: reading a file, resolving a link, inspecting an entry or listing a directory.
        refusal: Why the operating system refused it.
    """

    operation: RefusedOperation
    refusal: OsRefusal


@dataclass(frozen=True, slots=True)
class NotARegularFile:
    """No regular file stands where a structure file should: nothing was refused, there is nothing to read."""


type Cause = Refused | NotARegularFile
"""Why the path cannot be read."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class UnreadablePath(EngineCondition):
    """A path cannot be read.

    ## What it does

    Checks for paths the operating system refuses to let the check read, list or look up, such as a structure file,
    the `<name>.structure.json` files of `docs/__meta__/`, a corpus directory, a skills directory, a skill entry or a
    skill's `SKILL.md`, whose permissions deny it, or a link on the way to it that cannot be followed. A structure
    file that is not a regular file, such as a directory or a missing file where one was found, is reported the same
    way, with nothing refused to name.
    It is reported once, at its path, and nothing under it is loaded. The message names the operation that was
    refused, the path it was refused at, which may be one on the way, and the reason the operating system gave.

    What the path held is then not checked, and every document it governs is listed as skipped in coverage, with no
    rule run over it: a document that was not checked is never reported as clean. A structure file governs the
    documents of its meta spec; a corpus directory, a skills directory and a skill entry hold the documents under
    them. Every other corpus, skill and document is checked as if the path could be read.

    `lorecraft check` reads the whole repository before it reports anything, and a refusal at that point stops the run
    with an error naming the path and exit status 2, so it does not report this code today: it is reported only where
    the workspace is read without that first read.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the path can be reached, what it holds is not checked, so a violation there goes unreported and an agent
    loads it unreviewed.

    ## Example

    `docs/__meta__/guide.structure.json`, with its permissions removed:

    ```console
    $ ls -l docs/__meta__/guide.structure.json
    ---------- 1 dev dev 24 Oct 12 10:02 docs/__meta__/guide.structure.json
    ```

    ## Use instead

    Give the path back its permissions:

    ```console
    $ chmod 644 docs/__meta__/guide.structure.json
    $ ls -l docs/__meta__/guide.structure.json
    -rw-r--r-- 1 dev dev 24 Oct 12 10:02 docs/__meta__/guide.structure.json
    ```

    A directory needs its listing permission back instead, such as `chmod 755 docs/guide`. Where no regular file
    stands, restore the structure file as a regular file inside the repository.

    Attributes:
        failed_at: The path the operation was refused at, which may be one on the way to the path that failed.
        cause: What was refused and why, or that no regular file stands where a structure file should.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 2)
    NAME: ClassVar[RuleName] = RuleName('unreadable-path')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    failed_at: RootRelativePath
    cause: Cause

    def message(self) -> str:
        """Name the condition."""
        return 'path cannot be read'

    def primary(self) -> WholeSubject:
        """The path as a whole: no line of it is at fault."""
        return WholeSubject()

    def children(self) -> tuple[EntrySubdiagnostic, ...]:
        """Say which operation was refused where, and why, then say how to fix it."""
        match self.cause:
            case Refused(operation=operation, refusal=refusal):
                return (
                    EntryNote(f'cannot {operation.value} {self.failed_at}: {refusal.value}'),
                    EntryHelp('make the path, and what it links to, accessible to the process that runs the check'),
                )
            case NotARegularFile():
                return (
                    EntryNote(f'cannot read {self.failed_at}: no regular file the check can find'),
                    EntryHelp('restore the file as a regular file inside the repository'),
                )
            case _:
                assert_never(self.cause)
