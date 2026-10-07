"""`FM005`: a top-level frontmatter key is written more than once."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.project.context import FrontmatterContext
from lorecraft.project.syntax import (
    Frontmatter,
    FrontmatterKey,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
)
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Here, Label, Note, Subdiagnostic
from lorecraft.rules.subject import FrontmatterRule

from .__ruleset__ import GROUP_ID, owner_spec, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class DuplicateKey(FrontmatterRule):
    """A top-level frontmatter key is written more than once.

    ## What it does

    Checks for documents whose structure specification sets a `frontmatter` schema, and for skills, whose
    frontmatter writes a top-level key again. Each later occurrence is reported on its own line, pointing back at
    the first, whether the values are equal or differ.

    A document no `frontmatter` schema governs is not checked.

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
        kept_line: The line of the key's last occurrence, whose value YAML keeps.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 5)
    NAME: ClassVar[RuleName] = RuleName('duplicate-key')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    key: str
    first_line: LineNumber
    kept_line: LineNumber

    def message(self) -> str:
        """Name the key.

        The key is printed as its `repr`: a key holding a newline would otherwise split the message, and an escape
        sequence would vanish into the character it stands for.
        """
        return f'duplicate key {self.key!r}'

    def labels(self) -> tuple[Label, ...]:
        """Mark this occurrence, and point at the key's first."""
        return (
            Label(Here(self.line), 'written again here'),
            Label(Here(self.first_line), 'first written here'),
        )

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Name the specification, the key to write once, and the line whose value YAML keeps, unless it is this one."""
        parts: list[Subdiagnostic] = [
            spec_note(self.spec),
            Help(f'write {self.key!r} once, with the value meant'),
        ]
        if self.kept_line != self.line:
            parts.append(Note('the value written last is the one YAML keeps', at=Here(self.kept_line)))
        return tuple(parts)

    @classmethod
    def check(cls, subject: FrontmatterContext) -> tuple[Self, ...]:
        """One occurrence per top-level key written after its first, on its own line, in document order.

        The third occurrence of a key points back at the first, not at the second. A key nested in a value is not a
        top-level key, so it repeats none.

        Args:
            subject: The document or the skill whose frontmatter is judged.
        """
        frontmatter = subject.frontmatter()
        match frontmatter:
            case Frontmatter():
                pass  # the keys are walked below
            case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
                return ()
            case _:
                assert_never(frontmatter)

        spec = owner_spec(subject.frontmatter_owner())
        first_lines: dict[str, LineNumber] = {}
        last_lines: dict[str, LineNumber] = {}
        repeats: list[FrontmatterKey] = []
        for key in frontmatter.keys:
            if key.name in first_lines:
                repeats.append(key)
            else:
                first_lines[key.name] = key.line
            last_lines[key.name] = key.line

        occurrences: list[Self] = []
        for key in repeats:
            occurrences.append(
                cls(
                    spec=spec,
                    line=key.line,
                    key=key.name,
                    first_line=first_lines[key.name],
                    kept_line=last_lines[key.name],
                )
            )
        return tuple(occurrences)
