"""`LEN005`: a document's title holds more characters than its character cap allows."""

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
from lorecraft.rules.location import Here, Label, Note, Subdiagnostic
from lorecraft.rules.overrun import Overrun, find_overrun
from lorecraft.rules.subject import BySpec, Facet, Gate, QueriedItemRule

from .__ruleset__ import GROUP_ID, TITLE_HELP, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TitleTooLong(QueriedItemRule[TitleFacts]):
    """A document's title is longer than its character cap allows.

    ## What it does

    Checks for an H1 title longer than the `chars` cap its structure file sets on `title`. The characters
    are those of the title's own text, without its `#` marker or inline markup, counted as Unicode code points: a
    space is one, and so is each code point of an emoji built of several. Only the document's first H1 is its title,
    and a document with no title is not reported here.

    A document that more than one meta spec governs, such as a corpus and a namespace, must keep its title
    within every cap they set, and is reported once for each cap the title exceeds.

    ## Why is this bad?

    A title is what an agent or a reader scans when documents are listed by title; a wide one overflows the
    listing, and a word cap alone does not bound it when a few of its words are long, such as a command or a path.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "title": { "chars": 24 }
    }
    ```

    `docs/guide/setup.md`, with a title of 36 characters, its backticks not counted:

    ```markdown
    # Setting up `lorecraft check structure`
    ```

    ## Use instead

    Name what the document is about, and leave the rest to its first paragraph:

    ```markdown
    # Setting up the checks
    ```

    Attributes:
        spec: The structure file that sets the exceeded cap.
        overrun: The characters of the title's text against the cap they exceed.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 5)
    NAME: ClassVar[RuleName] = RuleName('title-too-long')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: BySpec(Facet.STRUCTURE),
            ItemKind.SKILL_ENTRY: BySpec(Facet.STRUCTURE, requires_loaded_layer=True),
        }
    )

    spec: RootRelativePath
    overrun: Overrun

    def message(self) -> str:
        """Name the title's characters against the cap they exceed."""
        return f'too many characters in the title ({self.overrun.count} > {self.overrun.cap})'

    def labels(self) -> tuple[Label, ...]:
        """Say how many characters the title runs past its cap, at the title."""
        return (Label(Here(self.line), f'characters over the cap: {self.overrun.excess}'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the meta spec that sets the cap, say what a title holds, and how its characters are counted."""
        return (
            spec_note(self.spec),
            TITLE_HELP,
            Note(
                "characters are counted as the code points of the title's text, without its # marker or inline markup"
            ),
        )

    @classmethod
    def query(cls) -> ItemQuery[TitleFacts]:
        """The title and the title checks of the document."""
        return title_facts

    @classmethod
    def judge(cls, facts: TitleFacts, /) -> tuple[Self, ...]:
        """One occurrence, at the title's heading, for each cap on the title's characters that it exceeds.

        The caps are taken in the order their meta specs apply; a document with no title is held to none.

        Args:
            facts: The document's title and the title checks each governing specification states.
        """
        title = facts.title
        if title is None:
            return ()
        # The count is of the Unicode code points of the title's text with its inline markup stripped: neither its
        # bytes nor the letters a reader sees, so an emoji built of several counts each of them.
        occurrences: list[Self] = []
        for constraint in facts.constraints:
            if constraint.checks.chars is None:
                continue
            overrun = find_overrun(title.chars, constraint.checks.chars)
            if overrun is not None:
                occurrences.append(cls(spec=constraint.spec, line=title.heading.line, overrun=overrun))
        return tuple(occurrences)
