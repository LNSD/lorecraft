"""`LEN004`: a document's title holds more words than its word cap allows."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.item import ItemKind
from lorecraft.project.query import ItemQuery
from lorecraft.project.schemas import TitleFacts, title_facts
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Here, Label, Subdiagnostic
from lorecraft.rules.overrun import Overrun, find_overrun
from lorecraft.rules.subject import ByMetaSpec, Gate, MetaSpecPart, QueriedItemRule

from .__ruleset__ import GROUP_ID, TITLE_HELP, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TitleTooManyWords(QueriedItemRule[TitleFacts]):
    """A document's title is longer than its word cap allows.

    ## What it does

    Checks for an H1 title longer than the `words` cap its structure file sets on `title`. The words are
    those of the title's own text, counted as a section's prose words are: each whitespace-delimited token is one.
    Only the document's first H1 is its title, and a document with no title is not reported here.

    A document that more than one meta spec governs, such as a corpus and a namespace, must keep its title
    within every cap they set, and is reported once for each cap the title exceeds.

    ## Why is this bad?

    A title is what an agent reads to decide whether the document is the one it needs; a long one says less, not
    more, and costs context in every listing that shows it.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "title": { "words": 4 }
    }
    ```

    `docs/guide/setup.md`, with a title of ten words:

    ```markdown
    # How to set up the toolkit on a new machine
    ```

    ## Use instead

    Name what the document is about, and leave the rest to its first paragraph:

    ```markdown
    # Setting up the toolkit
    ```

    Attributes:
        spec: The structure file that sets the exceeded cap.
        overrun: The words of the title's text against the cap they exceed.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 4)
    NAME: ClassVar[RuleName] = RuleName('title-too-many-words')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.STRUCTURE),
            ItemKind.SKILL_ENTRYPOINT: ByMetaSpec(MetaSpecPart.STRUCTURE, requires_loaded_layer=True),
        }
    )

    spec: RootRelativePath
    overrun: Overrun

    def message(self) -> str:
        """Name the title's words against the cap they exceed."""
        return f'too many words in the title ({self.overrun.count} > {self.overrun.cap})'

    def labels(self) -> tuple[Label, ...]:
        """Say how many words the title runs past its cap, at the title."""
        return (Label(Here(self.line), f'words over the cap: {self.overrun.excess}'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the meta spec that sets the cap, then say what a title holds."""
        return (spec_note(self.spec), TITLE_HELP)

    @classmethod
    def query(cls) -> ItemQuery[TitleFacts]:
        """The title and the title checks of the document."""
        return title_facts

    @classmethod
    def judge(cls, facts: TitleFacts, /) -> tuple[Self, ...]:
        """One occurrence, at the title's heading, for each cap on the title that it exceeds.

        The caps are taken in the order their meta specs apply; a document with no title is held to none.

        Args:
            facts: The document's title and the title checks each governing specification states.
        """
        title = facts.title
        if title is None:
            return ()
        occurrences: list[Self] = []
        for constraint in facts.constraints:
            if constraint.checks.words is None:
                continue
            overrun = find_overrun(title.words, constraint.checks.words)
            if overrun is not None:
                occurrences.append(cls(spec=constraint.spec, line=title.heading.line, overrun=overrun))
        return tuple(occurrences)
