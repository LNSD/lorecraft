"""`OUT005`: a section a structure file forbids appears in the document."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.item import ItemKind
from lorecraft.project.query import ItemQuery
from lorecraft.project.schemas import (
    AnyRunAlignment,
    NamedAlignment,
    OutlineAlignmentSpec,
    UnalignedSection,
    outline_alignment,
)
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Subdiagnostic
from lorecraft.rules.subject import ByMetaSpec, Gate, MetaSpecPart, QueriedItemRule

from .__ruleset__ import GROUP_ID, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class ForbiddenSection(QueriedItemRule[tuple[OutlineAlignmentSpec, ...]]):
    """A section a structure file forbids appears in the document.

    ## What it does

    Checks for H2 sections whose heading text is one of the names a document's structure file lists under
    `forbidden`. Only H2 headings are sections: a title or a deeper heading of the same text is not reported. Every
    occurrence is reported, so a forbidden section written twice is reported twice.

    A document that more than one meta spec governs, such as a corpus and a namespace, is reported once for
    each meta spec that forbids the section.

    ## Why is this bad?

    A meta spec forbids a section because what it would hold belongs elsewhere, or nowhere: a changelog kept in
    the version history, or a history of the document that an agent reads as a current rule. Written anyway, the
    section is read as part of the document.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "forbidden": ["Changelog"]
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    # Setup

    ## Run

    Run the toolkit once over the repository.

    ## Changelog

    Added the run step.
    ```

    ## Use instead

    Remove the section:

    ```markdown
    # Setup

    ## Run

    Run the toolkit once over the repository.
    ```

    Attributes:
        spec: The structure file that forbids the section.
        section: The text of the forbidden section's heading.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 5)
    NAME: ClassVar[RuleName] = RuleName('forbidden-section')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.STRUCTURE),
            ItemKind.SKILL_ENTRY: ByMetaSpec(MetaSpecPart.STRUCTURE, requires_loaded_layer=True),
        }
    )

    spec: RootRelativePath
    section: str

    def message(self) -> str:
        """Name the forbidden section."""
        return f'section `{self.section}` is forbidden'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the meta spec that forbids the section, and say to remove it."""
        return (spec_note(self.spec), Help('remove the section'))

    @classmethod
    def query(cls) -> ItemQuery[tuple[OutlineAlignmentSpec, ...]]:
        """The alignment of the document's sections to each outline that governs it."""
        return outline_alignment

    @classmethod
    def judge(cls, facts: tuple[OutlineAlignmentSpec, ...], /) -> tuple[Self, ...]:
        """One occurrence, at its heading, for each forbidden H2 section under each meta spec that forbids it.

        The meta specs are taken in the order they apply, and the headings of each in document order.

        Args:
            facts: The answer of the rule's query.
        """
        occurrences: list[Self] = []
        for alignment in facts:
            for aligned in alignment.sections:
                match aligned:
                    case NamedAlignment():
                        pass  # an outline never names a forbidden section
                    case AnyRunAlignment() | UnalignedSection():
                        if aligned.forbidden:
                            section = aligned.section
                            occurrences.append(cls(spec=alignment.spec, line=section.line, section=section.text))
                    case _:
                        assert_never(aligned)
        return tuple(occurrences)
