"""`LC205`: a frontmatter key is written more than once in one mapping."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.item import ItemType
from lorecraft.project.query import ItemQuery
from lorecraft.project.schemas import FrontmatterOwner
from lorecraft.project.syntax import (
    Frontmatter,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
)
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Note, Subdiagnostic
from lorecraft.rules.subject import Gate, QueriedItemRule, SpecPart, WhenSpec

from .__ruleset__ import GROUP_ID, FrontmatterFacts, frontmatter_facts, owner_spec, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class DuplicateKey(QueriedItemRule[FrontmatterFacts]):
    """A frontmatter key is written more than once in one mapping.

    ## What it does

    Checks for documents whose structure file sets a `frontmatter` schema, and for skills, whose
    frontmatter writes a key again in the same mapping, at any depth, block or flow. Each later occurrence is
    reported on its own line, pointing back at the first, whether the values are equal or differ. The same key
    under two different mappings is not a repeat.

    A document no `frontmatter` schema governs is not checked.

    ## Why is this bad?

    YAML does not say which value of a repeated key wins, and the reader keeps the last without a word, so an
    agent reads whichever was written last, and one of the two lines says nothing the document means.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "required": ["name", "description"]
      }
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    ---
    name: setup
    description: Install the toolkit.
    description: Install the toolkit and run it for the first time.
    ---

    # Setup
    ```

    ## Use instead

    Keep the one value meant:

    ```markdown
    ---
    name: setup
    description: Install the toolkit and run it for the first time.
    ---

    # Setup
    ```

    Attributes:
        spec: The structure file that governs the owner's frontmatter, derived from `owner`, so no caller states
            one that disagrees with it.
        owner: The document or the skill whose frontmatter repeats the key, and so which spec governs it.
        key: The key written again, as decoded.
        first_line: The line the key's first occurrence in its mapping is written on.
        kept_line: The line of the key's last occurrence in its mapping, whose value the reader keeps.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 205)
    NAME: ClassVar[RuleName] = RuleName('duplicate-key')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    APPLIES_TO: ClassVar[Mapping[ItemType, Gate]] = MappingProxyType(
        {
            ItemType.DOCUMENT: WhenSpec(SpecPart.FRONTMATTER),
            ItemType.SPEC: WhenSpec(SpecPart.FRONTMATTER),
            ItemType.SKILL_ENTRYPOINT: WhenSpec(SpecPart.FRONTMATTER),
        }
    )

    # The specification file is derived from `owner`, so no caller can state one that disagrees with it.
    spec: RootRelativePath | None = field(init=False)
    owner: FrontmatterOwner
    key: str
    first_line: LineNumber
    kept_line: LineNumber

    def __post_init__(self) -> None:
        """Derive the structure file from the owner of the frontmatter."""
        # The dataclass is frozen, so the field a rule derives is set the one way a frozen dataclass allows.
        object.__setattr__(self, 'spec', owner_spec(self.owner))

    def message(self) -> str:
        """Name the key.

        The key is printed as its `repr`: a key holding a newline would otherwise split the message, and an escape
        sequence would vanish into the character it stands for.
        """
        return f'duplicate key {self.key!r}'

    def labels(self) -> tuple[Label, ...]:
        """Mark this occurrence, and point at the key's first, unless the two are on one line."""
        # Two keys of one flow mapping share a span, so a second label would say nothing more.
        if self.first_line == self.line:
            return (Label(Here(self.line), 'written again here'),)
        return (
            Label(Here(self.line), 'written again here'),
            Label(Here(self.first_line), 'first written here'),
        )

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Name the spec, the key to write once, and the line whose value is read, unless it is this one."""
        parts: list[Subdiagnostic] = [
            spec_note(self.owner),
            Help(f'write {self.key!r} once, with the value meant'),
        ]
        if self.kept_line != self.line:
            parts.append(Note('the value written last is the one read', at=Here(self.kept_line)))
        return tuple(parts)

    @classmethod
    def query(cls) -> ItemQuery[FrontmatterFacts]:
        """The frontmatter block and whose it is."""
        return frontmatter_facts

    @classmethod
    def judge(cls, facts: FrontmatterFacts, /) -> tuple[Self, ...]:
        """One occurrence per key written after its first in a mapping, at any depth, in document order.

        The third occurrence of a key points back at the first, not at the second. The same key in two mappings is
        written once in each, so it repeats none.

        Args:
            facts: The block the subject opens with, and whose it is.
        """
        frontmatter = facts.frontmatter
        match frontmatter:
            case Frontmatter():
                pass  # the repeats are listed below
            case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
                return ()
            case _:
                assert_never(frontmatter)

        owner = facts.owner
        occurrences: list[Self] = []
        for repeat in frontmatter.repeats:
            occurrences.append(
                cls(
                    owner=owner,
                    line=repeat.line,
                    key=repeat.name,
                    first_line=repeat.first_line,
                    kept_line=repeat.kept_line,
                )
            )
        return tuple(occurrences)
