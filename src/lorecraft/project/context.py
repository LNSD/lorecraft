"""What can be asked of one decoded subject: a context per subject kind, and whose frontmatter a subject opens with.

A context is a read-only view of one document, one skill or one skill resource whose file decoded. Each method
names one fact of the subject, such as its frontmatter, its parse tree or the specifications that govern it, and
every type a method returns is this package's own or a layer below's, so the contexts import nothing from above. The
contexts are interfaces only: nothing here computes or caches a fact. The implementations that answer them from a
revision's memoized queries live in `lorecraft.project.database`, beside the database they read.

Three contexts hold what several kinds share. `MarkdownContext` holds what any one Markdown file has, the queries
a rule declares over it; `DocumentContext`, `SkillContext` and `SkillResourceContext` all extend it, a skill being its
`SKILL.md`.
`SkillFileContext` holds what one of a skill's Markdown files has, its `SKILL.md` or a resource, and `SkillContext`
and `SkillResourceContext` extend it; a document is no file of a skill, so `DocumentContext` does not.
`FrontmatterContext` holds the frontmatter a document and a skill open with, and `DocumentContext` and
`SkillContext` extend it too; a resource opens with no frontmatter the package governs, so `SkillResourceContext`
does not.

`LayoutContext` is the context of a subject with no text: a layout entry, of one of the kinds its sub-protocols name.
A symlink of the skill layout whose chain leaves the repository, as the model or a skill's resource listing records it,
is a `SymlinkContext`, and a directory under `docs/` named like a reserved corpus a `CorpusDirectoryContext`. An entry
is never decoded, so its context is built from its record alone, and it states a fact, never that it is a finding.
"""

from typing import Protocol

from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import CorpusName
from lorecraft.project.schemas import (
    Query,
    StructureSpec,
)
from lorecraft.project.syntax import FrontmatterNode, ParsedDocument, TokenCount
from lorecraft.project.workspace import Governance
from lorecraft.vfs import RootExit

from .link_target import DocumentLink


class MarkdownContext(Protocol):
    """One decoded Markdown file: a document, a skill's `SKILL.md` or a skill's resource."""

    def query[T](self, query: Query[T]) -> T:
        """The answer of a declared query over this file, memoized by the query and the file."""
        ...


class SkillFileContext(MarkdownContext, Protocol):
    """One decoded Markdown file of a skill, its `SKILL.md` or a resource, whose relative links the skill root reads.

    The Agent Skills specification has every file of a skill name another by its path from the skill root, wherever
    the file lies inside the skill. It is asked only what any Markdown file can be asked, so far.
    """


class FrontmatterContext(Protocol):
    """The frontmatter a document or a skill opens with, read through the queries a rule declares."""

    def query[T](self, query: Query[T]) -> T:
        """The answer of a declared query over this subject, memoized by the query and the subject."""
        ...


class DocumentContext(FrontmatterContext, MarkdownContext, Protocol):
    """One decoded document of a corpus, and the specifications that govern it."""

    def parse(self) -> ParsedDocument:
        """The document's parse tree: its headings, their anchors and its links."""
        ...

    def token_count(self) -> TokenCount:
        """The `o200k_base` tokens in the document's whole file, frontmatter, code and tables included."""
        ...

    def specifications(self) -> Governance:
        """The specifications that govern the document: its corpus's first, then each matching namespace's.

        Never absent: a document in no corpus is governed by nothing, so no context is built for it.
        """
        ...

    def corpus_structure(self) -> StructureSpec:
        """The structure specification of the document's corpus.

        It is the one the document's corpus states, which every rule over the document's structure is gated on.

        Never absent: a document's context exists only for a document whose corpus states one.
        """
        ...

    def document_links(self) -> tuple[DocumentLink, ...]:
        """The links to another document, with its corpus and filename and whether it links back, in document order."""
        ...


class SkillContext(FrontmatterContext, SkillFileContext, Protocol):
    """One skill whose `SKILL.md` decoded; the package governs it, after the Agent Skills specification.

    Its Markdown file is its `SKILL.md` alone, so its parse tree is that file's: each of its resources is a subject of
    its own.
    """

    def frontmatter(self) -> FrontmatterNode:
        """The skill's frontmatter block as parsed: missing, not YAML, not a mapping, or the mapping."""
        ...

    def query[T](self, query: Query[T]) -> T:
        """The answer of a declared query over this skill, memoized by the query and the skill."""
        ...


class SkillResourceContext(SkillFileContext, Protocol):
    """One resource of a skill whose file decoded; the package governs it, after the Agent Skills specification.

    A resource is a Markdown file inside the skill other than its own top-level `SKILL.md`, at any depth, named where
    an agent reaches it. It is asked only what any Markdown file can be asked.
    """


class LayoutContext(Protocol):
    """One layout entry, the subject of a rule over the layout: what every kind of entry has, its reported path.

    An entry has a kind, and each kind has the context that asks what only it has: a symlink, `SymlinkContext`, and a
    directory under `docs/` named like a reserved corpus, `CorpusDirectoryContext`. A rule is over one kind, so it
    asks the context of that kind. An entry has no text, so nothing about it is decoded.
    """

    def path(self) -> RootRelativePath:
        """Where the entry is reached, the path its diagnostics are reported at."""
        ...


class SymlinkContext(LayoutContext, Protocol):
    """One symlink an agent follows in the skill layout whose chain leaves the repository.

    The entry is a skills directory as an agent declares it, an entry in a skills directory, that entry's `SKILL.md`,
    or a path inside a skill; the run supplies the path an agent reaches it by.
    """

    def leaves_at(self) -> RootExit:
        """The link the entry's chain leaves the repository through, and that link's target, as the scan recorded it.

        The link is the entry itself when it links straight out, or one on the way to it or further along its chain.
        """
        ...


class CorpusDirectoryContext(LayoutContext, Protocol):
    """One directory directly under `docs/` that takes a reserved corpus's name, which the model ignores."""

    def reserved_corpus(self) -> CorpusName:
        """The reserved corpus whose name the directory takes."""
        ...
