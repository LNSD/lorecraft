"""`OUT009`: a document's title does not match the pattern its structure file holds it to."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.item import ItemKind
from lorecraft.project.query import ItemQuery
from lorecraft.project.schemas import TitleFacts, TitlePattern, title_facts
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Here, Label, Subdiagnostic
from lorecraft.rules.subject import BySpec, Facet, Gate, QueriedItemRule

from .__ruleset__ import GROUP_ID, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidTitle(QueriedItemRule[TitleFacts]):
    """A document's title does not match the pattern its structure file sets on `title`.

    ## What it does

    Checks for an H1 title whose text does not match the `pattern` its structure file sets on `title`. The
    pattern is matched as JSON Schema's `pattern` is: it is searched for anywhere in the title's text, so a pattern
    that must hold the whole title anchors itself with `^` and `$`. Only the document's first H1 is its title, and a
    document with no title is not reported here.

    A document that more than one meta spec governs, such as a corpus and a namespace, must keep its title to
    every pattern they set, and is reported once for each pattern the title does not match.

    ## Why is this bad?

    A pattern states how every title of a corpus reads, so an agent scanning a listing of titles can tell what each
    document is; a title that breaks it reads apart from the rest, or hides what the document is about.

    ## Example

    `docs/__meta__/guide.spec.json`:

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
        spec: The structure file that sets the pattern.
        title: The text of the title's heading.
        pattern: The pattern the title does not match, which prints exactly as written.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 9)
    NAME: ClassVar[RuleName] = RuleName('invalid-title')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: BySpec(Facet.STRUCTURE),
            ItemKind.SKILL_ENTRY: BySpec(Facet.STRUCTURE, requires_loaded_layer=True),
        }
    )
    GOVERNED_BY: ClassVar[Facet] = Facet.STRUCTURE

    spec: RootRelativePath
    title: str
    pattern: TitlePattern

    def message(self) -> str:
        """Name the title that does not match; the label gives the pattern."""
        return f'title `{self.title}` does not match the pattern'

    def labels(self) -> tuple[Label, ...]:
        """Mark the title with the pattern it misses."""
        return (Label(Here(self.line), f'does not match `{self.pattern}`'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the meta spec that sets the pattern."""
        return (spec_note(self.spec),)

    @classmethod
    def query(cls) -> ItemQuery[TitleFacts]:
        """The title and the title checks of the document."""
        return title_facts

    @classmethod
    def judge(cls, facts: TitleFacts, /) -> tuple[Self, ...]:
        """One occurrence, at the title's heading, for each pattern on the title that it does not match.

        The patterns are taken in the order their meta specs apply; a document with no title is held to none.

        Args:
            facts: The document's title and the title checks each governing specification states.
        """
        title = facts.title
        if title is None:
            return ()
        heading = title.heading
        occurrences: list[Self] = []
        for constraint in facts.constraints:
            pattern = constraint.checks.pattern
            if pattern is None or pattern.is_found_in(heading.text):
                continue
            occurrences.append(cls(spec=constraint.spec, line=heading.line, title=heading.text, pattern=pattern))
        return tuple(occurrences)
