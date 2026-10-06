"""`OUT003`: a document a structure specification governs opens with a heading other than its H1 title."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import DocumentContext
from lorecraft.project.syntax import HeadingLevel
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TitleNotFirst(DocumentRule):
    """A document a structure specification governs opens with a heading that is not its H1 title.

    ## What it does

    Checks for documents whose first heading is not a `#` H1, and reports that first heading. Every document a
    structure specification governs is held to it, with no key to state it: the specification need not mention the
    title at all. Only a heading at the top level of the document counts: one inside a list or a blockquote does
    not.

    A document with no heading at all is not reported here: it is missing its title, and adding one fixes both.

    A document that more than one specification governs, such as a corpus and a namespace, is reported once, under
    its corpus's structure specification.

    ## Why is this bad?

    An agent reads the title to learn what the document is about before it reads the rest; a section above the title
    is read before the agent knows what it belongs to.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "empty_sections": "forbidden"
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    ## Install

    Install the toolkit, then run it once over the repository.

    # Setup
    ```

    ## Use instead

    Move the title above every section:

    ```markdown
    # Setup

    ## Install

    Install the toolkit, then run it once over the repository.
    ```

    Attributes:
        spec: The corpus's structure specification, which governs the document.
        level: The level of the heading the document opens with.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 3)
    NAME: ClassVar[RuleName] = RuleName('title-not-first')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.STRUCTURE

    spec: RootRelativePath
    level: HeadingLevel

    def message(self) -> str:
        """Name the level of the heading found where the title belongs."""
        return f'first heading is not the H1 title (found H{self.level})'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the corpus's structure specification."""
        return (spec_note(self.spec),)

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence, at the first heading, under the corpus's structure specification, when it is not an H1.

        Args:
            subject: The document, governed by its corpus's structure specification.
        """
        headings = subject.parse().headings
        if not headings:
            return ()
        first = headings[0]
        if first.level == 1:
            return ()
        return (cls(spec=subject.corpus_structure().path, line=first.line, level=first.level),)
