"""The contexts of `lorecraft.project.context`, answered by the database's queries for one decoded subject.

`DatabaseItemContext` implements `DocumentContext`, `SkillContext` and `SkillResourceContext`. It holds the database
and the decode query's witness, and nothing it computed: every fact, a document's governance included, is the matching
memoized query of the database, so a fact nobody asks for is never computed, and one asked for twice is computed once.
An identity value, such as a document's filename or a skill's directory name, is read from the descriptor's origin.

A context is built only from a witness, so no fact of a file that does not decode can be asked for. The item context
answers for a document, a skill entry and a skill's resource alike; a fact only one kind has, or a document's
governance when none governs it, is a defect of the caller to ask for, and raises `WrongItemKindError`. The rule bases
name the kinds they apply to and the facet they read, so a rule that runs never asks.

`DatabaseSymlinkContext` and `DatabaseCorpusDirectoryContext` implement `SymlinkContext` and
`CorpusDirectoryContext`. A layout entry has no text, so it has no witness and no per-file query: the context holds the
record the model or a skill's `skill_resources` listing returned, the memoized query value itself, and reads every fact
from it.
"""

from collections.abc import Mapping
from typing import assert_never

from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName, ReservedCorpusDirectory
from lorecraft.project.document import SpecRef
from lorecraft.project.item import (
    DocumentOrigin,
    MarkdownItemRef,
    SkillEntryOrigin,
    SkillResourceOrigin,
    SpecificationOrigin,
)
from lorecraft.project.link_target import DocumentLink, LinkBase, LinkTargetEntry
from lorecraft.project.schemas import (
    DocumentFrontmatterOwner,
    Query,
    SkillFields,
    SkillFrontmatterOwner,
    StructureSpec,
)
from lorecraft.project.skill import OutsideSymlink
from lorecraft.project.syntax import FrontmatterNode, NormalisedLinkPath, ParsedDocument, TokenCount
from lorecraft.project.workspace import Governance
from lorecraft.vfs import ResolvedPath, RootExit

from .database import Database
from .text import ItemText


class WrongItemKindError(TypeError):
    """A fact of one kind of item was asked of another, which a rule that applies to its kind never does."""

    def __init__(self, ref: MarkdownItemRef, asked: str) -> None:
        super().__init__(f'{ref.path} is not {asked}')


class DatabaseItemContext:
    """One decoded document or skill entry, as the database answers for it; a `DocumentContext` and a `SkillContext`.

    The context is keyed by the item's text, and every fact is the matching memoized query of the database for that
    item, so a rule over what both kinds share reads one context whichever kind it judges. A fact only one kind has,
    such as a document's governance or a skill's directory name, is read from the descriptor's origin; asking it of the
    other kind is a defect of the caller, since the rule bases name the kind they apply to.
    """

    def __init__(self, database: Database, source: ItemText) -> None:
        """Bind the context to one decoded item.

        Args:
            database: The revision the item is read from.
            source: The item's text, as `Database.item_text` returns it: the witness every per-file query takes.
        """
        self._database = database
        self._source = source

    def _document(self) -> DocumentOrigin:
        """The origin of the document this context is bound to.

        Raises:
            WrongItemKindError: If the item is a skill entry.
        """
        origin = self._source.descriptor.origin
        match origin:
            case DocumentOrigin():
                return origin
            case SkillEntryOrigin() | SkillResourceOrigin() | SpecificationOrigin():
                raise WrongItemKindError(self._source.ref, 'a document')
            case _:
                assert_never(origin)

    def _skill(self) -> SkillEntryOrigin:
        """The origin of the skill entry this context is bound to.

        Raises:
            WrongItemKindError: If the item is a document.
        """
        origin = self._source.descriptor.origin
        match origin:
            case SkillEntryOrigin():
                return origin
            case DocumentOrigin() | SkillResourceOrigin() | SpecificationOrigin():
                raise WrongItemKindError(self._source.ref, 'a skill entry')
            case _:
                assert_never(origin)

    def filename(self) -> AspectFilename:
        """The filename of a document or meta specification, without its extension, read from its origin.

        Raises:
            WrongItemKindError: If the item is a skill entry or a skill resource.
        """
        origin = self._source.descriptor.origin
        match origin:
            case DocumentOrigin() | SpecificationOrigin():
                return AspectFilename.parse(origin.expected_name)
            case SkillEntryOrigin() | SkillResourceOrigin():
                raise WrongItemKindError(self._source.ref, 'a document or a specification')
            case _:
                assert_never(origin)

    def name(self) -> str:
        """The stem of a document or meta specification, read from its origin.

        Raises:
            WrongItemKindError: If the item is a skill entry or a skill resource.
        """
        origin = self._source.descriptor.origin
        match origin:
            case DocumentOrigin() | SpecificationOrigin():
                return origin.expected_name
            case SkillEntryOrigin() | SkillResourceOrigin():
                raise WrongItemKindError(self._source.ref, 'a document or a specification')
            case _:
                assert_never(origin)

    def base(self) -> str | None:
        """The stem of the document or specification this one extends, from the names the model lists.

        A document's base is looked for among the documents of its corpus, a specification's among the specifications.

        Raises:
            WrongItemKindError: If the item is a skill entry or a skill resource.
        """
        origin = self._source.descriptor.origin
        match origin:
            case DocumentOrigin():
                corpus = self._database.model().find_corpus(CorpusName.parse(origin.corpus))
                if corpus is None:
                    return None
                base = corpus.document_base(AspectFilename.parse(origin.expected_name))
                return None if base is None else str(base.filename)
            case SpecificationOrigin():
                base_spec = self._database.model().find_specification_base(SpecRef(self._source.ref.path))
                return None if base_spec is None else base_spec.name
            case SkillEntryOrigin() | SkillResourceOrigin():
                raise WrongItemKindError(self._source.ref, 'a document or a specification')
            case _:
                assert_never(origin)

    def directory_name(self) -> PathComponent:
        """The name of the skill's directory as an agent lists it, read from its origin.

        Raises:
            WrongItemKindError: If the item is a document.
        """
        return PathComponent.parse(self._skill().expected_name)

    def link_target(self) -> ResolvedPath | None:
        """The resolved directory the listed directory leads to when it is a link, or `None` when it is not.

        Raises:
            WrongItemKindError: If the item is a document.
        """
        return self._skill().link_target

    def frontmatter(self) -> FrontmatterNode:
        """The item's frontmatter block, from the `item_frontmatter` query."""
        return self._database.item_frontmatter(self._source)

    def skill_fields(self) -> SkillFields:
        """The fields of the skill's frontmatter that parse, from the `item_skill_fields` query.

        Raises:
            WrongItemKindError: If the item is a document.
        """
        self._skill()
        return self._database.item_skill_fields(self._source)

    def frontmatter_owner(self) -> DocumentFrontmatterOwner | SkillFrontmatterOwner:
        """The item, with the name its frontmatter `name` must equal and the facts the rules read of its origin.

        Raises:
            WrongItemKindError: If the item is a document no specification governs, or whose corpus states no
                structure specification.
        """
        origin = self._source.descriptor.origin
        match origin:
            case SkillEntryOrigin():
                return SkillFrontmatterOwner(directory_name=self.directory_name(), link_target=self.link_target())
            case DocumentOrigin():
                # A schema governs a document only through its corpus's structure specification, which a namespace's
                # schema merely narrows; so that specification states every rule over the block.
                return DocumentFrontmatterOwner(filename=self.filename(), spec=self.corpus_structure().path)
            case SkillResourceOrigin() | SpecificationOrigin():
                raise WrongItemKindError(self._source.ref, 'a document or a skill entry')
            case _:
                assert_never(origin)

    def parse(self) -> ParsedDocument:
        """The item's parse tree, from the `item_parse` query."""
        return self._database.item_parse(self._source)

    def link_base(self) -> LinkBase:
        """Where the item's relative links are read from, as its descriptor carries it."""
        return self._source.descriptor.link_base

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """Where each relative link leads and what the snapshot holds there, from the `item_link_targets` query."""
        return self._database.item_link_targets(self._source)

    def token_count(self) -> TokenCount:
        """The tokens in the document's whole file, from the `item_token_count` query.

        Raises:
            WrongItemKindError: If the item is a skill entry.
        """
        self._document()
        return self._database.item_token_count(self._source)

    def specifications(self) -> Governance:
        """The specifications that govern the document, from the `item_governance` query.

        Raises:
            WrongItemKindError: If the item is a skill, or no specification governs the document, which no rule
                that applies to a governed document asks.
        """
        self._document()
        governance = self._database.item_governance(self._source.ref)
        if governance is None:
            raise WrongItemKindError(self._source.ref, 'a governed document')
        return governance

    def corpus_structure(self) -> StructureSpec:
        """The structure specification of the document's corpus, which the specifications state.

        Raises:
            WrongItemKindError: If the item is a skill entry, or no specification governs the document, or its corpus
                states no structure specification.
        """
        structure = self.specifications().corpus_structure()
        if structure is None:
            raise WrongItemKindError(self._source.ref, 'a document whose corpus states a structure specification')
        return structure

    def query[T](self, query: Query[T]) -> T:
        """The answer of a declared query, from the database's memoized `query`.

        Raises:
            WrongItemKindError: If the item is a skill resource.
        """
        if isinstance(self._source.descriptor.origin, SkillResourceOrigin):
            raise WrongItemKindError(self._source.ref, 'a document or a skill entry')
        return self._database.query(query, self._source.ref)

    def document_links(self) -> tuple[DocumentLink, ...]:
        """The links to another document, from the `item_document_links` query.

        Raises:
            WrongItemKindError: If the item is a skill entry.
        """
        self._document()
        return self._database.item_document_links(self._source)


class DatabaseSymlinkContext:
    """One symlink of the skill layout whose chain leaves the repository, as recorded; a `SymlinkContext`."""

    def __init__(self, outside: OutsideSymlink) -> None:
        """Bind the context to one symlink whose chain leaves the repository.

        Args:
            outside: The symlink, as the model's `outside_symlinks` or a skill's resource listing holds it.
        """
        self._outside = outside

    def path(self) -> RootRelativePath:
        """Where an agent reaches the symlink, read from the record."""
        return self._outside.path

    def leaves_at(self) -> RootExit:
        """The link the chain leaves the repository through, and its target, read from the record."""
        return self._outside.leaves_at


class DatabaseCorpusDirectoryContext:
    """One directory under `docs/` that takes a reserved corpus's name, as recorded; a `CorpusDirectoryContext`."""

    def __init__(self, directory: ReservedCorpusDirectory) -> None:
        """Bind the context to one directory the model set aside.

        Args:
            directory: The directory, as the model's `overlapping_directories` holds it.
        """
        self._directory = directory

    def path(self) -> RootRelativePath:
        """The directory, read from the record."""
        return self._directory.path

    def reserved_corpus(self) -> CorpusName:
        """The reserved corpus whose name the directory takes, read from the record."""
        return self._directory.corpus
