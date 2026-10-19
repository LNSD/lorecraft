"""`OUT002`: a document a structure file governs carries more than one H1 title."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self

from lorecraft.project.item import ItemKind
from lorecraft.project.query import ItemQuery, SyntaxPrimitives, item_parse
from lorecraft.project.syntax import Heading
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import ByMetaSpec, Gate, MetaSpecPart, QueriedItemRule

from .__ruleset__ import GROUP_ID


def titles(primitives: SyntaxPrimitives) -> tuple[Heading, ...]:
    """The document's H1 headings, in document order. Raises nothing.

    A query: it reads the document's headings and nothing else.

    Args:
        primitives: The model state of the document.
    """
    return tuple(heading for heading in primitives.query(item_parse).headings if heading.level == 1)


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class ExtraTitle(QueriedItemRule[tuple[Heading, ...]]):
    """A document a structure file governs carries more than one H1 title.

    ## What it does

    Checks for documents with more than one `#` H1 heading, and reports each H1 after the first at its own heading,
    pointing back at the first: the first is the document's title, and every one after it is extra. Every document
    a structure file governs is held to it, with no key to state it: the meta spec need not mention
    the title at all. Only a heading at the top level of the document counts: one inside a list or a blockquote does
    not.

    A document that more than one meta spec governs, such as a corpus and a namespace, has each extra title
    reported once.

    ## Why is this bad?

    An agent reads the title to learn what the document is about; a second title reads as a second document, so the
    agent cannot tell which one the document is, nor that the sections under the second belong to the first.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "empty_sections": "forbidden"
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    # Setup

    ## Install

    Install the toolkit, then run it once over the repository.

    # Usage

    Run it over the repository's documents.
    ```

    ## Use instead

    Keep one title, and make the rest sections:

    ```markdown
    # Setup

    ## Install

    Install the toolkit, then run it once over the repository.

    ## Usage

    Run it over the repository's documents.
    ```

    Attributes:
        spec: Always `None`: the package states the rule.
        first_title: The document's first H1 heading, its own title.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 2)
    NAME: ClassVar[RuleName] = RuleName('extra-title')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.STRUCTURE),
            ItemKind.SKILL: ByMetaSpec(MetaSpecPart.STRUCTURE, requires_loaded_layer=True),
        }
    )

    spec: None = None
    first_title: Heading

    def message(self) -> str:
        """State that the document has a title already."""
        return 'extra H1 title'

    def labels(self) -> tuple[Label, ...]:
        """Point at the document's own title, and name it."""
        return (Label(Here(self.first_title.line), f'the document is titled `{self.first_title.text}` here'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the extra title belongs."""
        return (Help('make it an H2 section, or move it into a document of its own'),)

    @classmethod
    def query(cls) -> ItemQuery[tuple[Heading, ...]]:
        """The H1 headings of the document."""
        return titles

    @classmethod
    def judge(cls, facts: tuple[Heading, ...], /) -> tuple[Self, ...]:
        """One occurrence per H1 title after the first, at its heading.

        Args:
            facts: The document's H1 headings, in document order.
        """
        if not facts:
            return ()
        first = facts[0]
        return tuple(cls(line=extra.line, first_title=first) for extra in facts[1:])
