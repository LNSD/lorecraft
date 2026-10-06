"""`OUT009`: a document's title does not match the pattern its structure specification holds it to."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import DocumentContext
from lorecraft.project.syntax import find_title
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Note, Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidTitle(DocumentRule):
    """A document's title does not match the pattern its structure specification sets on `title`.

    ## What it does

    Checks for an H1 title whose text does not match the `pattern` its structure specification sets on `title`. The
    pattern is matched as JSON Schema's `pattern` is: it is searched for anywhere in the title's text, so a pattern
    that must hold the whole title anchors itself with `^` and `$`. Only the document's first H1 is its title, and a
    document with no title is not reported here.

    A document that more than one specification governs, such as a corpus and a namespace, must keep its title to
    every pattern they set, and is reported once for each pattern the title does not match.

    ## Why is this bad?

    A pattern states how every title of a corpus reads, so an agent scanning a listing of titles can tell what each
    document is; a title that breaks it reads apart from the rest, or hides what the document is about.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "title": { "pattern": "^[A-Z][^:]*$" }
    }
    ```

    `docs/guide/setup.md`, with a title holding a colon:

    ```markdown
    # Setup: the toolkit on a new machine
    ```

    ## Use instead

    Write the title the way the pattern states:

    ```markdown
    # Setting up the toolkit
    ```

    Attributes:
        spec: The structure specification that sets the pattern.
        title: The text of the title's heading.
        pattern: The pattern the title does not match, exactly as written.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 9)
    NAME: ClassVar[RuleName] = RuleName('invalid-title')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.STRUCTURE

    spec: RootRelativePath
    title: str
    pattern: str

    def message(self) -> str:
        """Name the title that does not match; the pattern is a note."""
        return f'title `{self.title}` does not match the pattern'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that sets the pattern, and give the pattern."""
        return (spec_note(self.spec), Note(f'the title must match `{self.pattern}`'))

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence, at the title's heading, for each pattern on the title that it does not match.

        The patterns are taken in the order their specifications apply; a document with no title is held to none.

        Args:
            subject: The document, governed by a structure specification.
        """
        title = find_title(subject.parse().headings)
        if title is None:
            return ()
        occurrences: list[Self] = []
        for structure_spec in subject.specifications().structure_specs():
            title_checks = structure_spec.title
            if title_checks is None or title_checks.pattern is None:
                continue
            if title_checks.pattern.is_found_in(title.text):
                continue
            occurrences.append(
                cls(spec=structure_spec.path, line=title.line, title=title.text, pattern=str(title_checks.pattern))
            )
        return tuple(occurrences)
