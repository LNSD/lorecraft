"""`LC101`: a directory under `docs/` has the name of a reserved corpus."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.corpus import CorpusName
from lorecraft.project.query import CorpusDirectoryPrimitives, Query
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import EntryHelp, EntryNote, EntrySubdiagnostic
from lorecraft.rules.subject import QueriedCorpusDirectoryRule

from .__ruleset__ import GROUP_ID


def reserved_corpus(primitives: CorpusDirectoryPrimitives) -> CorpusName:
    """The reserved corpus whose name the directory takes.

    A query: it reads the directory's reserved corpus and nothing else.

    Args:
        primitives: The model state of the directory.
    """
    return primitives.reserved_corpus()


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class ReservedCorpusOverlap(QueriedCorpusDirectoryRule[CorpusName]):
    """A directory under `docs/` has the name of a reserved corpus.

    ## What it does

    Checks for a directory directly under `docs/` named like a reserved corpus, such as `docs/skills/` beside a
    `skills` spec. The `skills` corpus has no directory: its documents are the skills of the agents' skills
    directories, governed by the `skills` and `skills-<namespace>` specs of `docs/__meta__/`. The directory is
    reported once, at its path, and ignored: none of the documents inside it is checked. The package states the rule;
    no spec sets or changes it.

    ## Why is this bad?

    The documents in the directory look governed, since a spec carries their corpus name, yet no rule is run
    over them, so a violation there goes unreported.

    ## Example

    `docs/skills/notes.md`, beside `docs/__meta__/skills.md`.

    ## Use instead

    Move the documents to a corpus with another name, such as `docs/guides/`, and give that corpus a spec:

    ```console
    $ mv docs/skills docs/guides
    ```

    Attributes:
        spec: Always `None`: the package states the rule.
        corpus: The reserved corpus name the directory takes.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 101)
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
    def query(cls) -> Query[CorpusDirectoryPrimitives, CorpusName]:
        """The reserved corpus the directory takes."""
        return reserved_corpus

    @classmethod
    def judge(cls, facts: CorpusName, /) -> tuple[Self, ...]:
        """The one occurrence, at the directory, naming the reserved corpus it takes.

        Args:
            facts: The reserved corpus whose name the directory takes; the model lists only such directories.
        """
        return (cls(corpus=str(facts)),)
