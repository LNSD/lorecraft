"""`FM005`: a top-level frontmatter key is written more than once."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.project.syntax import InvalidYamlFrontmatter, LineNumber, MissingFrontmatter, NonMappingFrontmatter
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import FrontmatterBlockInput, FrontmatterBlockRule, FrontmatterFields
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic

from .__ruleset__ import GROUP_ID, owner_spec, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class DuplicateKey(FrontmatterBlockRule):
    """A top-level frontmatter key is written more than once.

    ## What it does

    Checks for documents whose structure specification sets a `frontmatter` schema, and for skills, whose
    frontmatter writes a top-level key again. Each later occurrence is reported on its own line, pointing back at
    the first, whether the values are equal or differ.

    A key a `<<` merge supplies is not one the block writes, so it never repeats one. A document no `frontmatter`
    schema governs is not checked.

    ## Why is this bad?

    YAML keeps the value of the last occurrence without a word, so an agent reads whichever was written last, and
    one of the two lines says nothing the document means.

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
        spec: The structure specification whose frontmatter schema governs the document, or `None` for a skill,
            which the Agent Skills specification governs.
        key: The key written again, as decoded.
        first_line: The line the key's first occurrence is written on.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 5)
    NAME: ClassVar[RuleName] = RuleName('duplicate-key')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    key: str
    first_line: LineNumber

    def message(self) -> str:
        """Name the key, and the line of its first occurrence.

        The key is printed as its `repr`: a key holding a newline would otherwise split the message, and an escape
        sequence would vanish into the character it stands for.
        """
        return f'duplicate key {self.key!r}, already written on line {self.first_line}'

    def labels(self) -> tuple[Label, ...]:
        """Point at the key's first occurrence."""
        return (Label(Here(self.first_line), 'first written here'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Name the specification that governs the frontmatter, and the key to write once."""
        return (spec_note(self.spec), Help(f'write {self.key!r} once, with the value meant'))

    @classmethod
    def check(cls, subject: FrontmatterBlockInput) -> tuple[Self, ...]:
        """One occurrence per top-level key written after its first, on its own line, in document order.

        The third occurrence of a key points back at the first, not at the second.

        Args:
            subject: The subject's frontmatter block, and the subject it opens.
        """
        frontmatter = subject.frontmatter
        match frontmatter:
            case FrontmatterFields():
                spec = owner_spec(subject.owner)
                return tuple(
                    cls(spec=spec, line=repeated.line, key=repeated.key, first_line=repeated.first_line)
                    for repeated in frontmatter.repeated_keys
                )
            case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
                return ()
            case _:
                assert_never(frontmatter)
