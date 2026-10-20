"""`OUT001`: a document a structure file governs carries no H1 title."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self

from lorecraft.project.item import ItemType
from lorecraft.project.query import ItemQuery
from lorecraft.project.schemas import TitleFacts, title_facts
from lorecraft.project.syntax import FIRST_LINE
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Subdiagnostic
from lorecraft.rules.subject import Gate, MetaSpecPart, QueriedItemRule, WhenMetaSpec

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MissingTitle(QueriedItemRule[TitleFacts]):
    """A document a structure file governs carries no H1 title.

    ## What it does

    Checks for documents with no `#` H1 heading. Every document a structure file governs is held to it,
    with no key to state it: the meta spec need not mention the title at all. Only a heading at the top level
    of the document counts: one inside a list or a blockquote does not.

    A document that more than one meta spec governs, such as a corpus and a namespace, is reported once.

    ## Why is this bad?

    An agent reads the title to learn what the document is about before it reads the rest; without one it has to
    guess from the first section, and a link or a listing that shows the title shows nothing.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "empty_sections": "forbidden"
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    ## Install

    Install the toolkit, then run it once over the repository.
    ```

    ## Use instead

    Open the document with its title:

    ```markdown
    # Setup

    ## Install

    Install the toolkit, then run it once over the repository.
    ```

    Attributes:
        spec: Always `None`: the package states the rule.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 1)
    NAME: ClassVar[RuleName] = RuleName('missing-title')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    APPLIES_TO: ClassVar[Mapping[ItemType, Gate]] = MappingProxyType(
        {
            ItemType.DOCUMENT: WhenMetaSpec(MetaSpecPart.STRUCTURE),
            ItemType.META_SPEC: WhenMetaSpec(MetaSpecPart.STRUCTURE),
            ItemType.SKILL_ENTRYPOINT: WhenMetaSpec(MetaSpecPart.STRUCTURE),
        }
    )

    spec: None = None

    def message(self) -> str:
        """State that the title is missing."""
        return 'missing H1 title'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say how to write the title."""
        return (Help('open the document with an H1 title, `# <title>`'),)

    @classmethod
    def query(cls) -> ItemQuery[TitleFacts]:
        """The title and the title checks of the document."""
        return title_facts

    @classmethod
    def judge(cls, facts: TitleFacts, /) -> tuple[Self, ...]:
        """One occurrence, on line 1, when the document has no H1 title.

        Args:
            facts: The document's title and the title checks each governing specification states.
        """
        if facts.title is not None:
            return ()
        return (cls(line=FIRST_LINE),)
