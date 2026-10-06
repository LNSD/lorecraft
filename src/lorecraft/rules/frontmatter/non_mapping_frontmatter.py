"""`FM003`: a frontmatter block is valid YAML, but not a mapping."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

# The module, not its classes: this rule's own name is the syntax's `NonMappingFrontmatter`.
from lorecraft.project import syntax
from lorecraft.project.schemas import FIRST_LINE
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import FrontmatterBlockInput, FrontmatterBlockRule, FrontmatterFields
from lorecraft.rules.location import Subdiagnostic

from .__ruleset__ import GROUP_ID, owner_spec, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class NonMappingFrontmatter(FrontmatterBlockRule):
    """A frontmatter block is valid YAML, but not a mapping of fields.

    ## What it does

    Checks for documents whose structure specification sets a `frontmatter` schema, and for skills, whose
    frontmatter block reads as YAML but holds something other than `key: value` fields: a list, a single value,
    or nothing at all.

    A document no `frontmatter` schema governs is not checked.

    ## Why is this bad?

    An agent looks a field such as `name` or `description` up by its key, and a block that is not a mapping has
    no keys to look up.

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
        spec: The structure specification whose frontmatter schema governs the document, or `None` for a skill,
            which the Agent Skills specification governs.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 3)
    NAME: ClassVar[RuleName] = RuleName('non-mapping-frontmatter')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    def message(self) -> str:
        """Name what the block is not."""
        return 'frontmatter is not a YAML mapping'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Name the specification that governs the frontmatter."""
        return (spec_note(self.spec),)

    @classmethod
    def check(cls, subject: FrontmatterBlockInput) -> tuple[Self, ...]:
        """The one occurrence, on line 1, when the block is YAML but not a mapping; none otherwise.

        Args:
            subject: The subject's frontmatter block, and the subject it opens.
        """
        frontmatter = subject.frontmatter
        match frontmatter:
            case syntax.NonMappingFrontmatter():
                return (cls(spec=owner_spec(subject.owner), line=FIRST_LINE),)
            case syntax.MissingFrontmatter() | syntax.InvalidYamlFrontmatter() | FrontmatterFields():
                return ()
            case _:
                assert_never(frontmatter)
