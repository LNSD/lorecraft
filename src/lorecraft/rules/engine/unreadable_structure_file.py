"""`LC002`: a structure file cannot be read."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import Help, Note, Subdiagnostic, WholeSubject
from lorecraft.vfs import OsRefusal

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class UnreadableStructureFile(EngineCondition):
    """A structure file cannot be read.

    ## What it does

    Checks for structure files, the `<name>.structure.json` files of `docs/__meta__/`, that the operating system
    refuses to let the check read, such as one whose permissions deny it. Such a file is reported once, at the file, and
    every document its meta spec governs is listed as skipped in coverage, with no rule run over it: a document that
    was not checked is never reported as clean. Every document the file does not govern is checked as if the file were
    fixed.

    `lorecraft check` reads the whole repository before it reports anything, and a refusal at that point stops the run
    with an error naming the path and exit status 2, so it does not report this code today: it is reported only where
    the workspace is read without that first read.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the file is fixed, the documents it governs are not checked, so a violation in them goes unreported and an
    agent loads them unreviewed.

    ## Example

    `docs/__meta__/guide.structure.json`, with its permissions removed:

    ```console
    $ ls -l docs/__meta__/guide.structure.json
    ---------- 1 dev dev 24 Oct 12 10:02 docs/__meta__/guide.structure.json
    ```

    ## Use instead

    Give the file back its read permission:

    ```console
    $ chmod 644 docs/__meta__/guide.structure.json
    $ ls -l docs/__meta__/guide.structure.json
    -rw-r--r-- 1 dev dev 24 Oct 12 10:02 docs/__meta__/guide.structure.json
    ```

    Attributes:
        refusal: Why the operating system refused the read; none when there is no regular file.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 2)
    NAME: ClassVar[RuleName] = RuleName('unreadable-structure-file')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    refusal: OsRefusal | None

    def message(self) -> str:
        """Name the condition."""
        return 'structure file cannot be read'

    def primary(self) -> WholeSubject:
        """The structure file as a whole: no line of it is at fault."""
        return WholeSubject()

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say why the file cannot be read, and how to fix it."""
        if self.refusal is None:
            return (
                Note('the file is not a regular file the check can find'),
                Help('restore the file as a regular file inside the repository'),
            )
        return (
            Note(f'the operating system refused the read: {self.refusal.value}'),
            Help('make the file readable by the process that runs the check'),
        )
