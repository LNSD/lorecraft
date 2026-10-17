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

from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import CorpusName, ReservedCorpusDirectory
from lorecraft.project.item import (
    DocumentOrigin,
    SkillEntryOrigin,
    SkillResourceOrigin,
    SpecificationOrigin,
)
from lorecraft.project.schemas import (
    Query,
    StructureSpec,
)
from lorecraft.project.skill import OutsideSymlink
from lorecraft.project.syntax import FrontmatterNode, TokenCount
from lorecraft.project.workspace import Governance
from lorecraft.vfs import RootExit

from .database import Database
from .text import ItemText
from .wrong_kind import WrongItemKindError


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

    def frontmatter(self) -> FrontmatterNode:
        """The skill's frontmatter block, from the `item_frontmatter` query."""
        return self._database.item_frontmatter(self._source)

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
        """The answer of a declared query, from the database's memoized `query`."""
        return self._database.query(query, self._source.ref)


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
