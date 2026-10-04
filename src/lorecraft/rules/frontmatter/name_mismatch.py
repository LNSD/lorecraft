"""`FM004`: a frontmatter `name` differs from the name its document or skill is found under."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import ROOT
from lorecraft.project.syntax import InvalidYamlFrontmatter, MissingFrontmatter, NonMappingFrontmatter
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import (
    DocumentFrontmatterOwner,
    FrontmatterBlockInput,
    FrontmatterBlockRule,
    FrontmatterFields,
    SkillFrontmatterOwner,
)
from lorecraft.rules.location import Help, Note, Subdiagnostic
from lorecraft.vfs import ResolvedPath

from .__ruleset__ import GROUP_ID, owner_spec, spec_note


@dataclass(frozen=True, slots=True)
class FilenameExpected:
    """A document's `name` is held to its filename.

    Attributes:
        filename: The document's filename, without its extension.
    """

    filename: str


@dataclass(frozen=True, slots=True)
class DirectoryNameExpected:
    """A skill's `name` is held to the name of its directory, as an agent lists it.

    Attributes:
        directory_name: The name of the skill directory as an agent lists it in its skills directory.
        link_target: The resolved directory the listed directory leads to when it is a link, or `None` when it is
            not; it only words a note.
    """

    directory_name: str
    link_target: ResolvedPath | None


# What a `name` is held to: a document's filename, or a skill's listed directory name. A union of two records, so a
# document's occurrence can never carry a link target.
type NameExpectation = FilenameExpected | DirectoryNameExpected


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class NameMismatch(FrontmatterBlockRule):
    """A frontmatter `name` differs from the name its document or skill is found under.

    ## What it does

    Checks for documents whose structure specification sets a `frontmatter` schema and whose `name` differs from
    their filename without its extension, and for skills whose `name` differs from the name of their directory,
    as the Agent Skills specification requires. A skill's directory is named as an agent lists it in its skills
    directory: when that directory is a link to a directory named otherwise, the listed name is the one expected.

    Only a `name` written as a string is compared. A `name` that is missing or of another type is the schema's to
    report, so a document whose schema does not require `name` may leave it out.

    ## Why is this bad?

    An agent knows a document or a skill by the name it finds it under, and by the `name` it reads; when the two
    differ, a reference by one name does not reach the file known by the other.

    ## Example

    `docs/__meta__/guide.structure.json`:

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
        spec: The structure specification whose frontmatter schema governs the document, or `None` for a skill,
            whose frontmatter the package governs after the Agent Skills specification.
        name: The `name` the frontmatter writes.
        expectation: What the name is held to: the document's filename, or the skill's directory name with where
            a linked directory leads.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 4)
    NAME: ClassVar[RuleName] = RuleName('name-mismatch')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    name: str
    expectation: NameExpectation

    def message(self) -> str:
        """Name the `name` written against the one expected."""
        return f'`name` is {self.name!r}, expected {_expected_name(self.expectation)!r}'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say which name is expected and why, where a linked skill directory leads, and the name to write."""
        expectation = self.expectation
        match expectation:
            case FilenameExpected():
                return (
                    Note("a document's `name` must be its filename"),
                    spec_note(self.spec),
                    Help(f'set `name` to {expectation.filename!r}'),
                )
            case DirectoryNameExpected():
                return (
                    Note('the Agent Skills specification requires `name` to match the skill directory name'),
                    *_link_notes(expectation),
                    Help(f'set `name` to {expectation.directory_name!r}'),
                )
            case _:
                assert_never(expectation)

    @classmethod
    def check(cls, subject: FrontmatterBlockInput) -> tuple[Self, ...]:
        """The one occurrence, on the `name` line, when a string `name` differs from the expected name.

        Args:
            subject: The subject's frontmatter block, and the subject it opens.
        """
        frontmatter = subject.frontmatter
        match frontmatter:
            case FrontmatterFields():
                pass  # the `name` is compared below
            case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
                return ()
            case _:
                assert_never(frontmatter)

        name = frontmatter.name
        # A missing `name`, or one of another type, is the schema's to report, never this rule's.
        if name is None or not isinstance(name.value, str):
            return ()

        owner = subject.owner
        expectation: NameExpectation
        match owner:
            case DocumentFrontmatterOwner():
                expectation = FilenameExpected(filename=str(owner.filename))
            case SkillFrontmatterOwner():
                expectation = DirectoryNameExpected(directory_name=owner.directory_name, link_target=owner.link_target)
            case _:
                assert_never(owner)

        if name.value == _expected_name(expectation):
            return ()
        return (cls(spec=owner_spec(owner), line=name.line, name=name.value, expectation=expectation),)


def _expected_name(expectation: NameExpectation) -> str:
    """The name a `name` must equal: the document's filename, or the skill's listed directory name.

    Args:
        expectation: What the `name` is held to.
    """
    match expectation:
        case FilenameExpected():
            return expectation.filename
        case DirectoryNameExpected():
            return expectation.directory_name
        case _:
            assert_never(expectation)


def _link_notes(expectation: DirectoryNameExpected) -> tuple[Note, ...]:
    """The note naming where a listed skill directory leads, when it is a link to a directory named otherwise.

    The target is named by its root-relative path, so the root, whose own name is empty, reads as such.

    Args:
        expectation: The skill's listed directory name, and where it leads when it is a link.
    """
    link_target = expectation.link_target
    if link_target is None or link_target.name == expectation.directory_name:
        return ()
    if link_target == ROOT:
        return (Note(f'{expectation.directory_name!r} is a link to the repository root'),)
    return (Note(f'{expectation.directory_name!r} is a link to {str(link_target)!r}'),)
