"""`LC002`: a path cannot be read."""

from dataclasses import dataclass
from typing import ClassVar, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import EntryCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import EntryHelp, EntryNote, EntrySubdiagnostic
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
class UnreadablePath(EntryCondition):
    """A path cannot be read.

    ## What it does

    Checks for paths the operating system refuses to let the check read, list or look up: a structure file, one of
    the `<name>.structure.json` files of `docs/__meta__/`, that it cannot read; a corpus directory, a skills
    directory or a skill entry that it cannot list; and a link on the way to a skill, a skill entry or a skill's
    `SKILL.md` that it cannot follow. A structure file the check expected, with no regular file standing in its
    place, is reported the same way, with nothing refused to name.
    It is reported once, at its path, and nothing under it is loaded. The message names the operation that was
    refused, the path it was refused at, which may be one on the way, and the reason the operating system gave.

    What the path held is then not checked. A structure file it cannot read governs documents, and each of them is
    listed as skipped in coverage, with no rule run over it: a document that was not checked is never reported as
    clean. A corpus directory, a skills directory or a skill entry it cannot list holds documents the check never
    learns of, so none is listed, and this diagnostic is the only sign of them. Every other corpus, skill and
    document is checked as if the path could be read.

    Four refusals are not reported under this code, and each stops the run with an error naming the path and exit
    status 2: a `docs/` or `docs/__meta__/` that cannot be listed, since with it nothing can be checked; a
    document, or any other file the check reads, that cannot be read, including a regular `SKILL.md`; a symlink
    whose target cannot be read; and a directory that nothing loads, such as one under `docs/` that no meta spec
    names or one inside a skill, that cannot be listed.

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
