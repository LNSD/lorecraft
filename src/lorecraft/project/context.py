"""What can be asked of one decoded subject: a context per subject kind, and whose frontmatter a subject opens with.

A context is a read-only view of one document or one skill whose file decoded. Each method names one fact of the
subject, such as its frontmatter, its parse tree or the specifications that govern it, and every type a method
returns is this package's own or a layer below's, so the contexts import nothing from above. The contexts are
interfaces only: nothing here computes or caches a fact. The implementations that answer them from a revision's
memoized queries live in `lorecraft.checks`, beside the database they read.

`FrontmatterContext` holds what a document and a skill share, the frontmatter they open with; `DocumentContext` and
`SkillContext` extend it with what each kind adds.
"""

from dataclasses import dataclass
from typing import Protocol

from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.vfs import ResolvedPath

from .aspect import AspectFilename
from .schemas import OutlineDivergenceSpec, SchemaProblems
from .syntax import FrontmatterNode, ParsedDocument
from .workspace import Governance


@dataclass(frozen=True, slots=True)
class DocumentFrontmatterOwner:
    """A document whose frontmatter a schema governs: the name its frontmatter must carry, and where it is governed.

    Attributes:
        filename: The document's filename, without its extension, which its frontmatter `name` must equal.
        spec: The structure specification of the document's corpus, whose frontmatter schema makes the document
            governed for its frontmatter. A namespace's schema only narrows the corpus's, so this one file is
            always the specification that states every rule over the block.
    """

    filename: AspectFilename
    spec: RootRelativePath


@dataclass(frozen=True, slots=True)
class SkillFrontmatterOwner:
    """A skill, whose frontmatter the package governs after the Agent Skills specification.

    Attributes:
        directory_name: The name of the skill directory as an agent lists it in its skills directory, which the
            frontmatter `name` must equal. An agent never resolves a link itself, so where a link leads plays no
            part in it.
        link_target: The resolved directory the listed directory leads to when it is a link, or `None` when it is
            not; it only words a note, so a reader sees why the name they know is not the one expected.
    """

    directory_name: str
    link_target: ResolvedPath | None


# Whose frontmatter block it is: a document a frontmatter schema governs, or a skill. A union of two records rather
# than one with a flag, so a document can never carry a link target, nor a skill a specification.
type FrontmatterOwner = DocumentFrontmatterOwner | SkillFrontmatterOwner


class FrontmatterContext(Protocol):
    """The frontmatter a document or a skill opens with, and whose it is."""

    def frontmatter(self) -> FrontmatterNode:
        """The subject's frontmatter block as parsed: missing, not YAML, not a mapping, or the mapping."""
        ...

    def schema_problems(self) -> tuple[SchemaProblems, ...]:
        """What each frontmatter schema that governs the subject rejects in its frontmatter, each problem on its line.

        One entry per schema, in the order the schemas apply; a skill's one schema is the Agent Skills
        specification's. None when no schema governs the subject, or when its block is missing, not YAML or not a
        mapping, which no schema can hold.
        """
        ...

    def frontmatter_owner(self) -> FrontmatterOwner:
        """The document or the skill the block opens, with the name its frontmatter must carry.

        A document's context exists only for a document whose corpus states a structure specification, so every
        subject has an owner.
        """
        ...


class DocumentContext(FrontmatterContext, Protocol):
    """One decoded document of a corpus, and the specifications that govern it."""

    def filename(self) -> AspectFilename:
        """The document's filename, without its extension."""
        ...

    def parse(self) -> ParsedDocument:
        """The document's parse tree: its headings, their anchors and its links."""
        ...

    def tokens(self) -> UnsignedInt:
        """The `o200k_base` tokens in the document's whole file, frontmatter, code and tables included."""
        ...

    def lines(self) -> UnsignedInt:
        """The lines in the document's whole file, frontmatter included."""
        ...

    def specifications(self) -> Governance:
        """The specifications that govern the document: its corpus's first, then each matching namespace's.

        Never absent: a document in no corpus is governed by nothing, so no context is built for it.
        """
        ...

    def outline_divergences(self) -> tuple[OutlineDivergenceSpec, ...]:
        """Where the document's sections first stop matching each outline that governs it.

        One entry per structure specification that governs the document and states an outline, in the order the
        specifications apply; none when no outline governs it.
        """
        ...


class SkillContext(FrontmatterContext, Protocol):
    """One skill whose `SKILL.md` decoded; the package governs it, after the Agent Skills specification."""

    def directory_name(self) -> str:
        """The name of the skill's directory as an agent lists it, whatever a link there leads to."""
        ...

    def link_target(self) -> ResolvedPath | None:
        """The resolved directory the listed directory leads to when it is a link, or `None` when it is not."""
        ...

    def parse(self) -> ParsedDocument:
        """The parse tree of the skill's `SKILL.md`."""
        ...

    def lines(self) -> UnsignedInt:
        """The lines in the skill's whole `SKILL.md`, frontmatter, code and blank lines included."""
        ...
