"""`LC014`: a corpus directory cannot be listed."""

from dataclasses import dataclass
from typing import ClassVar

from lorecraft.project.corpus import CorpusName
from lorecraft.rules.declaration import EngineCondition, Release, RuleCode, RuleName, Severity, rule
from lorecraft.rules.location import EntryHelp, EntryNote, EntrySubdiagnostic, WholeSubject
from lorecraft.vfs import OsRefusal

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class UnlistableCorpusDirectory(EngineCondition):
    """A corpus directory cannot be listed.

    ## What it does

    Checks for corpus directories, the `docs/<corpus>/` directories that a structure file in `docs/__meta__/` names,
    that the operating system refuses to list, such as one whose permissions deny it. The corpus holds no document
    the check can know.
    It is reported once, at its path, and nothing under it is loaded. Every other corpus, skill and document is
    checked as if it could be read.

    `lorecraft check` reads the whole repository before it reports anything, and a refusal at that point stops the run
    with an error naming the path and exit status 2, so it does not report this code today: it is reported only where
    the workspace is read without that first read.

    It has no level, so no configuration turns it off, and it is always reported as an error.

    ## Why is this bad?

    Until the directory can be listed, none of the corpus's documents is checked, so a violation in them goes
    unreported.

    ## Example

    `docs/guide/`, with its permissions removed:

    ```console
    $ chmod 000 docs/guide
    ```

    ## Use instead

    Give the directory its permissions back:

    ```console
    $ chmod 755 docs/guide
    ```

    Attributes:
        corpus: The corpus whose documents were being listed.
        refusal: Why the operating system refused the listing.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 14)
    NAME: ClassVar[RuleName] = RuleName('unlistable-corpus-directory')
    SINCE: ClassVar[Release] = Release('0.3.0')
    SEVERITY: ClassVar[Severity] = Severity.ERROR

    corpus: CorpusName
    refusal: OsRefusal

    def message(self) -> str:
        """Name the condition."""
        return 'corpus directory cannot be listed'

    def primary(self) -> WholeSubject:
        """The entry as a whole, which has no line."""
        return WholeSubject()

    def children(self) -> tuple[EntrySubdiagnostic, ...]:
        """Name the corpus and why the listing was refused, then say how to fix the directory."""
        return (
            EntryNote(f'the documents of corpus {self.corpus} cannot be listed: {self.refusal.value}'),
            EntryHelp('make the directory listable by the process that runs the check'),
        )
