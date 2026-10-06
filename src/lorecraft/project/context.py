"""What can be asked of one decoded subject: a context per subject kind, and whose frontmatter a subject opens with.

A context is a read-only view of one document, one skill or one skill resource whose file decoded. Each method
names one fact of the subject, such as its frontmatter, its parse tree or the specifications that govern it, and
every type a method returns is this package's own or a layer below's, so the contexts import nothing from above. The
contexts are interfaces only: nothing here computes or caches a fact. The implementations that answer them from a
revision's memoized queries live in `lorecraft.project.database`, beside the database they read.

Three contexts hold what several kinds share. `MarkdownContext` holds what any one Markdown file has, its parse
tree; `DocumentContext`, `SkillContext` and `SkillResourceContext` all extend it, a skill being its `SKILL.md`.
`SkillFileContext` holds what one of a skill's Markdown files has, its `SKILL.md` or a resource, and `SkillContext`
and `SkillResourceContext` extend it; a document is no file of a skill, so `DocumentContext` does not.
`FrontmatterContext` holds the frontmatter a document and a skill open with, and `DocumentContext` and
`SkillContext` extend it too; a resource opens with no frontmatter the package governs, so `SkillResourceContext`
does not.

A Markdown file also states two facts beyond its own text, for a rule that follows its links: the directory its
relative links are read from, a `LinkBase`, and what the snapshot holds at each link's target, a `PathLookup`. Both
are facts of the revision, never a judgment of a link.

`LayoutContext` is the one context of a subject with no text: a layout entry, one symlink of the skill layout whose
chain leaves the repository, as the model or a skill's resource listing records it. A symlink is never decoded, so
its context is built from that record alone, and it states where the chain leaves, a fact, never that it is a
finding.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol

from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.vfs import ResolvedPath, RootExit

from .aspect import AspectFilename
from .link_target import LinkBase, PathLookup
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


class MarkdownContext(Protocol):
    """One decoded Markdown file: a document, a skill's `SKILL.md` or a skill's resource."""

    def parse(self) -> ParsedDocument:
        """The file's parse tree: its headings, their anchors and its links."""
        ...

    def link_base(self) -> LinkBase:
        """Where the file's relative links are read from: its skill's root, or the document's own directory."""
        ...

    def link_targets(self) -> Mapping[PurePosixPath, PathLookup]:
        """What the snapshot holds at the target of each relative link, keyed by the link's normalised relative path.

        A link spelling no relative path has no entry, and neither has one climbing past its bound: above the skill
        root in a file of a skill, above the repository root in a document.
        """
        ...


class SkillFileContext(MarkdownContext, Protocol):
    """One decoded Markdown file of a skill, its `SKILL.md` or a resource, whose relative links the skill root reads.

    The Agent Skills specification has every file of a skill name another by its path from the skill root, wherever
    the file lies inside the skill. It is asked only what any Markdown file can be asked, so far.
    """


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


class DocumentContext(FrontmatterContext, MarkdownContext, Protocol):
    """One decoded document of a corpus, and the specifications that govern it."""

    def filename(self) -> AspectFilename:
        """The document's filename, without its extension."""
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


class SkillContext(FrontmatterContext, SkillFileContext, Protocol):
    """One skill whose `SKILL.md` decoded; the package governs it, after the Agent Skills specification.

    Its Markdown file is its `SKILL.md` alone, so its parse tree is that file's: each of its resources is a subject of
    its own.
    """

    def directory_name(self) -> str:
        """The name of the skill's directory as an agent lists it, whatever a link there leads to."""
        ...

    def link_target(self) -> ResolvedPath | None:
        """The resolved directory the listed directory leads to when it is a link, or `None` when it is not."""
        ...

    def lines(self) -> UnsignedInt:
        """The lines in the skill's whole `SKILL.md`, frontmatter, code and blank lines included."""
        ...


class SkillResourceContext(SkillFileContext, Protocol):
    """One resource of a skill whose file decoded; the package governs it, after the Agent Skills specification.

    A resource is a Markdown file inside the skill other than its own top-level `SKILL.md`, at any depth, named where
    an agent reaches it. It is asked only what any Markdown file can be asked.
    """


class LayoutContext(Protocol):
    """One layout entry: a symlink an agent follows in the skill layout whose chain leaves the repository.

    The entry is a skills directory as an agent declares it, an entry in a skills directory, that entry's `SKILL.md`,
    or a path inside a skill; the run supplies the path an agent reaches it by. It has no text, so nothing about it
    is decoded.
    """

    def leaves_at(self) -> RootExit:
        """The link the entry's chain leaves the repository through, and that link's target, as the scan recorded it.

        The link is the entry itself when it links straight out, or one on the way to it or further along its chain.
        """
        ...
