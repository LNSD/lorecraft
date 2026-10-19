"""`FM003`: a frontmatter block is valid YAML, but not a mapping."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath

# The module, not its classes: this rule's own name is the syntax's `NonMappingFrontmatter`.
from lorecraft.project import syntax
from lorecraft.project.item import ItemKind
from lorecraft.project.query import ItemQuery
from lorecraft.project.schemas import FrontmatterOwner
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Subdiagnostic
from lorecraft.rules.subject import ByMetaSpec, Gate, MetaSpecPart, QueriedItemRule

from .__ruleset__ import GROUP_ID, FrontmatterFacts, frontmatter_facts, owner_spec, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class NonMappingFrontmatter(QueriedItemRule[FrontmatterFacts]):
    """A frontmatter block is valid YAML, but not a mapping of fields.

    ## What it does

    Checks for documents whose structure file sets a `frontmatter` schema, and for skills, whose
    frontmatter block reads as YAML but holds something other than `key: value` fields: a list, a single value,
    or nothing at all.

    A document no `frontmatter` schema governs is not checked.

    ## Why is this bad?

    An agent looks a field such as `name` or `description` up by its key, and a block that is not a mapping has
    no keys to look up.

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
    - setup
    - Install the toolkit and run it for the first time.
    ---

    # Setup
    ```

    ## Use instead

    Write each field as a key and its value:

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
        owner: The document or the skill whose frontmatter is not a mapping, and so which meta spec governs it.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 3)
    NAME: ClassVar[RuleName] = RuleName('non-mapping-frontmatter')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.FRONTMATTER),
            ItemKind.SKILL: ByMetaSpec(MetaSpecPart.FRONTMATTER),
        }
    )

    # The specification file is derived from `owner`, so no caller can state one that disagrees with it.
    spec: RootRelativePath | None = field(init=False)
    owner: FrontmatterOwner

    def __post_init__(self) -> None:
        """Derive the structure file from the owner of the frontmatter."""
        # The dataclass is frozen, so the field a rule derives is set the one way a frozen dataclass allows.
        object.__setattr__(self, 'spec', owner_spec(self.owner))

    def message(self) -> str:
        """Name what the block is not."""
        return 'frontmatter is not a YAML mapping'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Name the meta spec that governs the frontmatter, and say what a mapping looks like."""
        return (spec_note(self.owner), Help('write the block as `key: value` lines'))

    @classmethod
    def query(cls) -> ItemQuery[FrontmatterFacts]:
        """The frontmatter block and whose it is."""
        return frontmatter_facts

    @classmethod
    def judge(cls, facts: FrontmatterFacts, /) -> tuple[Self, ...]:
        """The one occurrence, on line 1, when the block is YAML but not a mapping; none otherwise.

        Args:
            facts: The block the subject opens with, and whose it is.
        """
        frontmatter = facts.frontmatter
        match frontmatter:
            case syntax.NonMappingFrontmatter():
                return (cls(owner=facts.owner, line=syntax.FIRST_LINE),)
            case syntax.MissingFrontmatter() | syntax.InvalidYamlFrontmatter() | syntax.Frontmatter():
                return ()
            case _:
                assert_never(frontmatter)
