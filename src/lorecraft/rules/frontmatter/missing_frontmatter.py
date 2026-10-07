"""`FM001`: a document or a skill does not open with a frontmatter block."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

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

    `docs/__meta__/guide.structure.json`:

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
        spec: The structure specification whose frontmatter schema governs the document, or `None` for a skill,
            which the Agent Skills specification governs.
        directory_name: The name of the skill's directory, as an agent lists it, which its `name` must equal; or
            `None` for a document, whose required fields are the schema's and not this rule's input.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 1)
    NAME: ClassVar[RuleName] = RuleName('missing-frontmatter')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    directory_name: str | None

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
        parts: list[Subdiagnostic] = [
            spec_note(self.spec),
            Help('open the file with a `---` line, the fields, and a closing `---` line'),
        ]
        if self.directory_name is not None:
            parts.append(Note(f'for example:\n---\nname: {self.directory_name}\ndescription: …\n---'))
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
                owner = subject.frontmatter_owner()
                return (cls(spec=owner_spec(owner), line=FIRST_LINE, directory_name=_directory_name(owner)),)
            case syntax.InvalidYamlFrontmatter() | syntax.NonMappingFrontmatter() | syntax.Frontmatter():
                return ()
            case _:
                assert_never(frontmatter)


def _directory_name(owner: FrontmatterOwner) -> str | None:
    """The name of a skill's directory, which its `name` must equal; `None` for a document.

    Args:
        owner: The document or the skill whose frontmatter is missing.
    """
    match owner:
        case DocumentFrontmatterOwner():
            return None
        case SkillFrontmatterOwner():
            return owner.directory_name
        case _:
            assert_never(owner)
