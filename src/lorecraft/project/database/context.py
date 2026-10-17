"""The contexts of `lorecraft.project.context`, answered by the database's queries for one decoded subject.

`DatabaseItemContext` and `DatabaseSkillResourceContext` implement `DocumentContext` and `SkillContext`, and
`SkillResourceContext`. Each holds the database and the decode query's witness, and nothing it computed: every fact,
a document's governance included, is the matching memoized query of the database, so a fact nobody asks for is never
computed, and one asked for twice is computed once. An identity value, such as a document's filename or a skill's
directory name, is read from the descriptor's origin.

A context is built only from a witness, so no fact of a file that does not decode can be asked for. The item context
answers for a document and for a skill entry alike; a fact only one kind has, or a document's governance when none
governs it, is a defect of the caller to ask for, and raises `WrongItemKindError`. The rule bases name the kinds they
apply to and the facet they read, so a rule that runs never asks.

`DatabaseLayoutContext` implements `LayoutContext`. A layout entry has no text, so it has no witness and no per-file
query: the context holds the `OutsideSymlink` record the model's `outside_symlinks` or a skill's `skill_resources`
listing returned, the memoized query value itself, and reads every fact from it.
"""

from collections.abc import Mapping
from typing import assert_never

from lorecraft.core.path import PathComponent
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.context import DocumentFrontmatterOwner, SkillFrontmatterOwner
from lorecraft.project.item import DocumentOrigin, MarkdownItemRef, SkillEntryOrigin, SkillResourceOrigin
from lorecraft.project.link_target import LinkBase, LinkTargetEntry, SkillRoot
from lorecraft.project.schemas import (
    OutlineAlignmentSpec,
    OutlineDivergenceSpec,
    SchemaProblems,
    SkillFields,
    StructureSpec,
)
from lorecraft.project.skill import OutsideSymlink
from lorecraft.project.syntax import FrontmatterNode, LineCount, NormalisedLinkPath, ParsedDocument, TokenCount
from lorecraft.project.workspace import Governance
from lorecraft.vfs import ResolvedPath, RootExit

from .database import Database
from .text import ItemText, SkillResourceText


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
            case SkillEntryOrigin() | SkillResourceOrigin():
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
            case DocumentOrigin() | SkillResourceOrigin():
                raise WrongItemKindError(self._source.ref, 'a skill entry')
            case _:
                assert_never(origin)

    def filename(self) -> AspectFilename:
        """The document's filename, without its extension, read from its origin.

        Raises:
            WrongItemKindError: If the item is a skill entry.
        """
        return AspectFilename.parse(self._document().expected_name)

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

    def schema_problems(self) -> tuple[SchemaProblems, ...]:
        """What each schema that governs the item rejects in its frontmatter, from the matching schema query."""
        origin = self._source.descriptor.origin
        match origin:
            case SkillEntryOrigin():
                return self._database.item_skill_schema_problems(self._source)
            case DocumentOrigin():
                return self._database.item_schema_problems(self._source)
            case SkillResourceOrigin():
                raise WrongItemKindError(self._source.ref, 'a document or a skill entry')
            case _:
                assert_never(origin)

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
            case SkillResourceOrigin():
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

    def line_count(self) -> LineCount:
        """The lines in the item's whole file, from the `item_line_count` query."""
        return self._database.item_line_count(self._source)

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

    def outline_alignment(self) -> tuple[OutlineAlignmentSpec, ...]:
        """Which outline entry each of the document's sections falls in, from the `item_outline_alignment` query.

        Raises:
            WrongItemKindError: If the item is a skill entry.
        """
        self._document()
        return self._database.item_outline_alignment(self._source)

    def outline_divergences(self) -> tuple[OutlineDivergenceSpec, ...]:
        """Where the document's sections stop matching each outline, from the `item_outline_divergences` query.

        Raises:
            WrongItemKindError: If the item is a skill entry.
        """
        self._document()
        return self._database.item_outline_divergences(self._source)


class DatabaseSkillResourceContext:
    """One resource of a skill whose file decoded, as the database answers for it; a `SkillResourceContext`."""

    def __init__(self, database: Database, source: SkillResourceText) -> None:
        """Bind the context to one decoded resource.

        Args:
            database: The revision the resource is read from.
            source: The resource's text, as `Database.skill_resource_text` returns it: the witness every per-file
                query takes.
        """
        self._database = database
        self._source = source

    def parse(self) -> ParsedDocument:
        """The resource's parse tree, from the `skill_resource_parse` query."""
        return self._database.skill_resource_parse(self._source)

    def link_base(self) -> SkillRoot:
        """The directory of the resource's skill where an agent reaches it, read from its ref."""
        return SkillRoot(self._source.ref.skill.directory)

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """Where each relative link leads and what the snapshot holds there, from `skill_resource_link_targets`."""
        return self._database.skill_resource_link_targets(self._source)


class DatabaseLayoutContext:
    """One symlink of the skill layout whose chain leaves the repository, as recorded; a `LayoutContext`."""

    def __init__(self, outside: OutsideSymlink) -> None:
        """Bind the context to one symlink whose chain leaves the repository.

        Args:
            outside: The symlink, as the model's `outside_symlinks` or a skill's resource listing holds it.
        """
        self._outside = outside

    def leaves_at(self) -> RootExit:
        """The link the chain leaves the repository through, and its target, read from the record."""
        return self._outside.leaves_at
