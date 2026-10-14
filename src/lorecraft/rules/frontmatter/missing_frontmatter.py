"""`FM001`: a document or a skill does not open with a frontmatter block."""

from dataclasses import dataclass, field
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath

# The module, not its classes: this rule's own name is the syntax's `MissingFrontmatter`.
from lorecraft.project import syntax
from lorecraft.project.context import (
    DocumentFrontmatterOwner,
    FrontmatterContext,
    FrontmatterOwner,
    SkillFrontmatterOwner,
)
from lorecraft.project.schemas import FIRST_LINE
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Here, Label, Note, Subdiagnostic
from lorecraft.rules.subject import FrontmatterRule

from .__ruleset__ import GROUP_ID, owner_spec, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MissingFrontmatter(FrontmatterRule):
    """A document or a skill does not open with a frontmatter block.

    ## What it does

    Checks for documents whose structure specification sets a `frontmatter` schema, and for skills, whose
    `SKILL.md` the Agent Skills specification requires to open with frontmatter, that do not open with a block
    between two `---` lines. A file whose first line is not `---`, or whose block is never closed by a second
    `---` line, has none.

    A document no `frontmatter` schema governs is not checked.

    ## Why is this bad?

    An agent decides whether to load a document or a skill from its frontmatter, its `name` and `description`
    among them; without a block it has nothing to decide on, and loads the file blind or never.

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
    # Setup

    Install the toolkit, then run it once over the repository.
    ```

    ## Use instead

    Open the file with the block:

    ```markdown
    ---
    name: setup
    description: Install the toolkit and run it for the first time.
    ---

    # Setup

    Install the toolkit, then run it once over the repository.
    ```

    Attributes:
        spec: The specification file that governs the owner's frontmatter, derived from `owner`, so no caller states
            one that disagrees with it.
        owner: The document or the skill that opens with no block. It says which specification governs the subject,
            and for a skill the directory name its `name` must equal, which the example shows.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 1)
    NAME: ClassVar[RuleName] = RuleName('missing-frontmatter')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    # The specification file is derived from `owner`, so no caller can state one that disagrees with it.
    spec: RootRelativePath | None = field(init=False)
    owner: FrontmatterOwner

    def __post_init__(self) -> None:
        """Derive the specification file from the owner of the frontmatter."""
        # The dataclass is frozen, so the field a rule derives is set the one way a frozen dataclass allows.
        object.__setattr__(self, 'spec', owner_spec(self.owner))

    def message(self) -> str:
        """Name the block that is missing."""
        return 'no `---` delimited frontmatter block'

    def labels(self) -> tuple[Label, ...]:
        """Say where the block is expected: line 1, which an empty file does not have, so a renderer may clamp it.

        The wording holds for a file that never opens a block and for one that opens it and never closes it.
        """
        return (Label(Here(self.line), 'a `---` delimited block is expected here'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Name the specification, say how to open the block, and for a skill show the fields it opens with."""
        owner = self.owner
        parts: list[Subdiagnostic] = [
            spec_note(owner),
            Help('open the file with a `---` line, the fields, and a closing `---` line'),
        ]
        match owner:
            case DocumentFrontmatterOwner():
                pass  # a document's required fields are the schema's, not this rule's input
            case SkillFrontmatterOwner():
                parts.append(Note(f'for example:\n---\nname: {owner.directory_name}\ndescription: …\n---'))
            case _:
                assert_never(owner)
        return tuple(parts)

    @classmethod
    def check(cls, subject: FrontmatterContext) -> tuple[Self, ...]:
        """The one occurrence, on line 1, when the subject has no frontmatter block; none otherwise.

        Args:
            subject: The document or the skill whose frontmatter is judged.
        """
        frontmatter = subject.frontmatter()
        match frontmatter:
            case syntax.MissingFrontmatter():
                return (cls(owner=subject.frontmatter_owner(), line=FIRST_LINE),)
            case syntax.InvalidYamlFrontmatter() | syntax.NonMappingFrontmatter() | syntax.Frontmatter():
                return ()
            case _:
                assert_never(frontmatter)
