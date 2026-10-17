"""`COR001`: a directory under `docs/` has the name of a reserved corpus."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.context import CorpusDirectoryContext
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import EntryHelp, EntryNote, EntrySubdiagnostic
from lorecraft.rules.subject import CorpusDirectoryRule

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class ReservedCorpusOverlap(CorpusDirectoryRule):
    """A directory under `docs/` has the name of a reserved corpus.

    ## What it does

    Checks for a directory directly under `docs/` named like a reserved corpus, such as `docs/skills/` beside a
    `skills` meta spec. The `skills` corpus has no directory: its documents are the skills of the agents' skills
    directories, governed by the `skills` and `skills-<namespace>` meta specs of `docs/__meta__/`. The directory is
    reported once, at its path, and ignored: none of the documents inside it is checked. The package states the rule;
    no meta spec sets or changes it.

    ## Why is this bad?

    The documents in the directory look governed, since a meta spec carries their corpus name, yet no rule is run
    over them, so a violation there goes unreported.

    ## Example

    `docs/skills/notes.md`, beside `docs/__meta__/skills.md`.

    ## Use instead

    Move the documents to a corpus with another name, such as `docs/guides/`, and give that corpus a meta spec:

    ```console
    $ mv docs/skills docs/guides
    ```

    Attributes:
        spec: Always `None`: the package states the rule.
        corpus: The reserved corpus name the directory takes.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 1)
    NAME: ClassVar[RuleName] = RuleName('reserved-corpus-overlap')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('0.4.0')

    spec: None = None
    corpus: str

    def message(self) -> str:
        """Name the condition."""
        return 'directory overlaps a reserved corpus'

    def children(self) -> tuple[EntrySubdiagnostic, ...]:
        """Say how to fix it, then which corpus is reserved and what is ignored."""
        return (
            EntryHelp('move its documents to a corpus with another name'),
            EntryNote(f'`{self.corpus}` is a reserved corpus, so the documents in this directory are not checked'),
        )

    @classmethod
    def check(cls, subject: CorpusDirectoryContext) -> tuple[Self, ...]:
        """The one occurrence, at the directory, naming the reserved corpus it takes.

        Args:
            subject: The directory judged; the model lists only directories that take a reserved name.
        """
        return (cls(corpus=str(subject.reserved_corpus())),)
