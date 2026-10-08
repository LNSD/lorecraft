"""`OUT002`: a document a structure specification governs carries more than one H1 title."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.context import DocumentContext
from lorecraft.project.syntax import Heading
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class ExtraTitle(DocumentRule):
    """A document a structure specification governs carries more than one H1 title.

    ## What it does

    Checks for documents with more than one `#` H1 heading, and reports each H1 after the first at its own heading,
    pointing back at the first: the first is the document's title, and every one after it is extra. Every document
    a structure specification governs is held to it, with no key to state it: the specification need not mention
    the title at all. Only a heading at the top level of the document counts: one inside a list or a blockquote does
    not.

    A document that more than one specification governs, such as a corpus and a namespace, has each extra title
    reported once.

    ## Why is this bad?

    An agent reads the title to learn what the document is about; a second title reads as a second document, so the
    agent cannot tell which one the document is, nor that the sections under the second belong to the first.

    ## Example

    `docs/__meta__/guide.structure.json`:

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
    GOVERNED_BY: ClassVar[Facet] = Facet.STRUCTURE

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
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence per H1 title after the first, at its heading.

        Args:
            subject: The document, governed by a structure specification.
        """
        titles: list[Heading] = []
        for heading in subject.parse().headings:
            if heading.level == 1:
                titles.append(heading)
        if not titles:
            return ()
        first = titles[0]
        occurrences: list[Self] = []
        for extra in titles[1:]:
            occurrences.append(cls(line=extra.line, first_title=first))
        return tuple(occurrences)
