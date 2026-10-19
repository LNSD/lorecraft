"""`OUT008`: a section the outline does not name, in a place the outline does not allow one."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.item import ItemType
from lorecraft.project.query import ItemQuery
from lorecraft.project.schemas import (
    AbsentSection,
    ExpectedSection,
    MisplacedSection,
    OutlineDivergenceSpec,
    OutlineEnd,
    UnlistedSection,
)
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import Gate, MetaSpecPart, QueriedItemRule, WhenMetaSpec

from .__ruleset__ import GROUP_ID, outline_divergences, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class UnexpectedSection(QueriedItemRule[tuple[OutlineDivergenceSpec, ...]]):
    """A section the outline does not name, in a place the outline does not allow one.

    ## What it does

    Checks for documents that write a section their structure file's `outline` does not name, in a place
    no `{"any": true}` entry of the outline covers. The section is reported where it stands, which is either where
    the outline expects a section the document only writes further down, or after the outline's end.

    Only the first place a document stops following its outline is reported, since every section after it is
    compared with an entry it was never meant to match. A document that more than one meta spec governs, such
    as a corpus and a namespace, must follow each outline, and is reported once for each it breaks.

    ## Why is this bad?

    An agent that loads the document expects every document of its kind to answer the same questions under the
    same headings; a section the outline does not name holds content no other document of the kind puts there, so
    an agent looking for it in its usual place does not find it.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "outline": [
        {"section": "Usage"},
        {"section": "Options"}
      ]
    }
    ```

    `docs/guide/check.md`:

    ```markdown
    # Check

    ## Usage

    Run `lorecraft check` from the repository root.

    ## Tips

    `--strict` fails on a warning.

    ## Options

    `--quiet` prints nothing on success.
    ```

    ## Use instead

    Move the content under a section the outline names:

    ```markdown
    # Check

    ## Usage

    Run `lorecraft check` from the repository root.

    ## Options

    `--strict` fails on a warning.

    `--quiet` prints nothing on success.
    ```

    Attributes:
        spec: The structure file whose outline does not allow the section.
        section: The heading text of the section the outline does not name, which the occurrence is reported at.
        placement: The section the outline places there instead, with the heading where the document writes it
            further down; or the end of the outline, with the last section it matched, when the section comes
            after it.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 8)
    NAME: ClassVar[RuleName] = RuleName('unexpected-section')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    APPLIES_TO: ClassVar[Mapping[ItemType, Gate]] = MappingProxyType(
        {
            ItemType.DOCUMENT: WhenMetaSpec(MetaSpecPart.OUTLINE),
            ItemType.SKILL_ENTRYPOINT: WhenMetaSpec(MetaSpecPart.OUTLINE),
        }
    )

    spec: RootRelativePath
    section: str
    placement: ExpectedSection | OutlineEnd

    def message(self) -> str:
        """Name the section the outline does not name."""
        return f'unexpected section `{self.section}`'

    def labels(self) -> tuple[Label, ...]:
        """Mark the section, and where the section the outline places there is written or where the outline ends.

        An outline that matched no section ends before the first one, so it has no section to mark.
        """
        placement = self.placement
        match placement:
            case ExpectedSection():
                return (
                    Label(Here(self.line), f'expected `{placement.name}` here'),
                    Label(Here(placement.written_at.line), f'`{placement.name}` is written here'),
                )
            case OutlineEnd():
                labels = [Label(Here(self.line), 'the outline ends before it')]
                if placement.last_matched is not None:
                    labels.append(Label(Here(placement.last_matched.line), 'the outline ends here'))
                return tuple(labels)
            case _:
                assert_never(placement)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the meta spec whose outline does not allow the section, and say where its content goes."""
        return (spec_note(self.spec), Help('move its content under a section the outline names, or remove it'))

    @classmethod
    def query(cls) -> ItemQuery[tuple[OutlineDivergenceSpec, ...]]:
        """The outline divergences of the document, one for each outline that governs it."""
        return outline_divergences

    @classmethod
    def judge(cls, facts: tuple[OutlineDivergenceSpec, ...], /) -> tuple[Self, ...]:
        """One occurrence for each outline whose first divergence is a section it does not name.

        Args:
            facts: The answer of the rule's query.
        """
        occurrences: list[Self] = []
        for outline_spec in facts:
            divergence = outline_spec.divergence
            match divergence:
                case UnlistedSection():
                    occurrences.append(
                        cls(
                            spec=outline_spec.spec,
                            line=divergence.section.line,
                            section=divergence.section.text,
                            placement=divergence.placement,
                        )
                    )
                case AbsentSection() | MisplacedSection() | None:
                    pass  # the document matches the outline, or diverges from it otherwise
                case _:
                    assert_never(divergence)
        return tuple(occurrences)
