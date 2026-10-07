"""`OUT003`: a document a structure specification governs opens with a heading other than its H1 title."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.project.context import DocumentContext
from lorecraft.project.syntax import HeadingLevel, LineNumber, find_title
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TitleNotFirst(DocumentRule):
    """A document a structure specification governs opens with a heading that is not its H1 title.

    ## What it does

    Checks for documents whose first heading is not a `#` H1, and reports that first heading. Every document a
    structure specification governs is held to it, with no key to state it: the specification need not mention the
    title at all. Only a heading at the top level of the document counts: one inside a list or a blockquote does
    not.

    A document with no H1 title is not reported here, whatever its headings: it is missing its title, which
    `missing-title` reports, and adding one fixes both.

    A document that more than one specification governs, such as a corpus and a namespace, is reported once.

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
        spec: Always `None`: the package states the rule.
        level: The level of the heading the document opens with.
        title_line: The line of the document's H1 title, which the heading above it should follow.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 3)
    NAME: ClassVar[RuleName] = RuleName('title-not-first')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.STRUCTURE

    spec: None = None
    level: HeadingLevel
    title_line: LineNumber

    def message(self) -> str:
        """Name the level of the heading found where the title belongs."""
        return f'first heading is not the H1 title (found H{self.level})'

    def labels(self) -> tuple[Label, ...]:
        """Point at the document's title."""
        return (Label(Here(self.title_line), 'the title is written here'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say where the title belongs."""
        return (Help('move the title above every section'),)

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence, at the first heading, when the document has an H1 title and the first heading is not it.

        Args:
            subject: The document, governed by a structure specification.
        """
        headings = subject.parse().headings
        title = find_title(headings)
        if title is None:
            return ()
        first = headings[0]
        if first.level == 1:
            return ()
        return (cls(line=first.line, level=first.level, title_line=title.line),)
