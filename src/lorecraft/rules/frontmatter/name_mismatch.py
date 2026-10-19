"""`FM004`: a frontmatter `name` differs from the name its document or skill is found under."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import ROOT, RootRelativePath
from lorecraft.project.item import ItemKind
from lorecraft.project.layout import DOCUMENT_SUFFIX
from lorecraft.project.query import ItemQuery
from lorecraft.project.schemas import (
    DocumentFrontmatterOwner,
    FrontmatterOwner,
    SkillFrontmatterOwner,
    field_line,
)
from lorecraft.project.syntax import Frontmatter, InvalidYamlFrontmatter, MissingFrontmatter, NonMappingFrontmatter
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Note, Subdiagnostic
from lorecraft.rules.subject import ByMetaSpec, BySchema, Gate, MetaSpecPart, QueriedItemRule
from lorecraft.schemas.agent_skills_frontmatter import (
    EmptySkillNameError,
    InvalidSkillNameFormatError,
    OverlongSkillNameError,
    SkillName,
)
from lorecraft.schemas.builtin import AGENT_SKILLS_SCHEMA_REFERENCE

from .__ruleset__ import GROUP_ID, FrontmatterFacts, frontmatter_facts, owner_spec


def _expected_name(owner: FrontmatterOwner) -> str:
    """The name a `name` must equal: the document's filename, or the skill's listed directory name.

    Args:
        owner: The document or the skill whose `name` is compared.
    """
    match owner:
        case DocumentFrontmatterOwner():
            return str(owner.filename)
        case SkillFrontmatterOwner():
            return str(owner.directory_name)
        case _:
            assert_never(owner)


def _is_skill_name(name: str) -> bool:
    """Whether the Agent Skills specification accepts `name` as a skill's `name`, its length included.

    Args:
        name: The `name` the frontmatter writes.
    """
    try:
        SkillName.parse(name)
    except EmptySkillNameError, OverlongSkillNameError, InvalidSkillNameFormatError:
        return False
    return True


def _link_notes(owner: SkillFrontmatterOwner) -> tuple[Note, ...]:
    """The note naming where a listed skill directory leads, when it is a link to a directory named otherwise.

    The target is named by its root-relative path, so the root, which has no name, reads as such.

    Args:
        owner: The skill, with its listed directory name and where it leads when it is a link.
    """
    link_target = owner.link_target
    if link_target is None:
        return ()
    name = link_target.name
    if name == owner.directory_name:
        return ()
    if link_target == ROOT:
        return (Note(f'{str(owner.directory_name)!r} is a link to the repository root'),)
    return (Note(f'{str(owner.directory_name)!r} is a link to {str(link_target)!r}'),)


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class NameMismatch(QueriedItemRule[FrontmatterFacts]):
    """A frontmatter `name` differs from the name its document or skill is found under.

    ## What it does

    Checks for documents whose structure file sets a `frontmatter` schema and whose `name` differs from
    their filename without its extension, and for skills whose `name` differs from the name of their directory,
    as the Agent Skills specification requires. A skill's directory is named as an agent lists it in its skills
    directory: when that directory is a link to a directory named otherwise, the listed name is the one expected.

    Only a `name` written as a string is compared. A `name` that is missing or of another type is the schema's to
    report, so a document whose schema does not require `name` may leave it out.

    No schema key states the rule: the package holds a document's `name` to its filename, and the Agent Skills
    specification holds a skill's to its directory name. The rename of a skill's directory is offered only for a
    `name` that specification accepts.

    ## Why is this bad?

    An agent knows a document or a skill by the name it finds it under, and by the `name` it reads; when the two
    differ, a reference by one name does not reach the file known by the other.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "frontmatter": {
        "type": "object",
        "required": ["name"]
      }
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    ---
    name: installation
    ---

    # Setup
    ```

    ## Use instead

    Set `name` to the filename, or rename the file:

    ```markdown
    ---
    name: setup
    ---

    # Setup
    ```

    Attributes:
        spec: The structure file that governs the owner's frontmatter, derived from `owner`, so no caller states
            one that disagrees with it.
        owner: The document or the skill whose `name` is compared. It says what the name is held to, the document's
            filename or the skill's directory name with where a linked directory leads, and which kind of subject
            is governed; no note renders the meta spec, since no schema states this rule.
        name: The `name` the frontmatter writes.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 4)
    NAME: ClassVar[RuleName] = RuleName('name-mismatch')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.FRONTMATTER),
            ItemKind.SKILL_ENTRYPOINT: BySchema(AGENT_SKILLS_SCHEMA_REFERENCE),
        }
    )

    # The specification file is derived from `owner`, so no caller can state one that disagrees with it.
    spec: RootRelativePath | None = field(init=False)
    owner: FrontmatterOwner
    name: str

    def __post_init__(self) -> None:
        """Derive the structure file from the owner of the frontmatter."""
        # The dataclass is frozen, so the field a rule derives is set the one way a frozen dataclass allows.
        object.__setattr__(self, 'spec', owner_spec(self.owner))

    def message(self) -> str:
        """Name the `name` written; the name expected is the label's."""
        return f'`name` is {self.name!r}, which is not the name it is found under'

    def labels(self) -> tuple[Label, ...]:
        """Say the name expected, on the `name` line."""
        return (Label(Here(self.line), f'expected `{_expected_name(self.owner)}`'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say which name is expected and why, the two ways to make the names agree, and where a link leads.

        No schema states this rule, so no note points at the structure file: the document's `name` is held to its
        filename by the package, and a skill's to its directory by the Agent Skills specification.
        """
        owner = self.owner
        match owner:
            case DocumentFrontmatterOwner():
                parts: list[Subdiagnostic] = [
                    Note("a document's `name` must be its filename"),
                    Help(f'set `name` to {str(owner.filename)!r}'),
                ]
                # A `name` with a path separator cannot be a filename.
                if '/' not in self.name:
                    parts.append(Help(f'or rename the file to {self.name + DOCUMENT_SUFFIX!r}'))
                return tuple(parts)
            case SkillFrontmatterOwner():
                parts = [
                    Note('the Agent Skills specification requires `name` to match the skill directory name'),
                    Help(f'set `name` to {str(owner.directory_name)!r}'),
                ]
                # Renaming the directory to a `name` the specification rejects would trade this finding for another.
                if _is_skill_name(self.name):
                    parts.append(Help(f'or rename the skill directory to {self.name!r}'))
                parts.extend(_link_notes(owner))
                return tuple(parts)
            case _:
                assert_never(owner)

    @classmethod
    def query(cls) -> ItemQuery[FrontmatterFacts]:
        """The frontmatter block and whose it is."""
        return frontmatter_facts

    @classmethod
    def judge(cls, facts: FrontmatterFacts, /) -> tuple[Self, ...]:
        """The one occurrence, on the `name` line, when a string `name` differs from the expected name.

        A `name` written more than once holds its last value, so it is reported on the last line it is written on.

        Args:
            facts: The block the subject opens with, and whose it is.
        """
        frontmatter = facts.frontmatter
        match frontmatter:
            case Frontmatter():
                pass  # the `name` is compared below
            case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
                return ()
            case _:
                assert_never(frontmatter)

        name = frontmatter.data.get('name')
        # A missing `name`, or one of another type, is the schema's to report, never this rule's.
        if not isinstance(name, str):
            return ()

        owner = facts.owner
        if name == _expected_name(owner):
            return ()
        return (cls(owner=owner, line=field_line(frontmatter, 'name'), name=name),)
