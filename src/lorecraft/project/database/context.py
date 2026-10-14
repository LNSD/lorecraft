"""The contexts of `lorecraft.project.context`, answered by the database's queries for one decoded subject.

`DatabaseDocumentContext`, `DatabaseSkillContext` and `DatabaseSkillResourceContext` implement `DocumentContext`,
`SkillContext` and `SkillResourceContext`. Each holds the database, the decode query's witness and, for a skill, what
the model says about it, and nothing it computed: every fact, a document's governance included, is the matching
memoized query of the database, so a fact nobody asks for is never computed, and one asked for twice is computed
once. An identity value, such as a document's filename or a skill's directory name, is read from the subject's ref or
its location.

A context is built only from a witness, so no fact of a file that does not decode can be asked for, and a document's
context only from a `GovernedDocument`, the decoded text with the governance of a corpus that states a structure
specification: no facet governs a document whose corpus states none. The governance is held, so no method raises.

`DatabaseLayoutContext` implements `LayoutContext`. A layout entry has no text, so it has no witness and no per-file
query: the context holds the `OutsideSymlink` record the model's `outside_symlinks` or a skill's `skill_resources`
listing returned, the memoized query value itself, and reads every fact from it.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from lorecraft.core.path import PathComponent
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.context import DocumentFrontmatterOwner, SkillFrontmatterOwner
from lorecraft.project.link_target import DocumentDirectory, LinkTargetEntry, SkillRoot
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
from .text import DocumentText, SkillResourceText, SkillText


@dataclass(frozen=True, slots=True)
class GovernedDocument:
    """A decoded document whose corpus states a structure specification: the witness of a document's context.

    Without a structure specification of its corpus no facet governs a document, so no value of this type holds one.
    Built only by `GovernedDocument.find`, which pairs the text with the governance and structure it asked the database
    for.

    Attributes:
        text: The document's text, as `Database.text` returns it: the witness every per-file query takes.
        governance: The specifications that govern the document, as `Database.governance` returns them.
        corpus_structure: The structure specification of the document's corpus, which `governance` states.
    """

    text: DocumentText
    governance: Governance
    corpus_structure: StructureSpec

    @classmethod
    def find(cls, database: Database, text: DocumentText) -> 'GovernedDocument | None':
        """The governed document, or `None` when no facet can govern it. Raises nothing.

        No facet governs a document in no corpus the database's model holds, nor one whose corpus has no structure
        specification that loaded: without the corpus's, a namespace's governs nothing.

        Args:
            database: The revision the document is read from; its model decides which specifications govern it.
            text: The document's text, the witness every per-file query takes.
        """
        governance = database.governance(text.ref)
        if governance is None:
            return None
        corpus_structure = governance.corpus_structure()
        if corpus_structure is None:
            return None
        return cls(text, governance, corpus_structure)


class DatabaseDocumentContext:
    """One decoded document of a corpus, as the database answers for it; a `DocumentContext`."""

    def __init__(self, database: Database, governed: GovernedDocument) -> None:
        """Bind the context to one decoded document of a corpus that states a structure specification.

        Args:
            database: The revision the document is read from.
            governed: The document's text and the specifications that govern it.
        """
        self._database = database
        self._governed = governed
        self._source = governed.text

    def filename(self) -> AspectFilename:
        """The document's filename, without its extension, read from its ref."""
        return self._source.ref.filename

    def frontmatter(self) -> FrontmatterNode:
        """The document's frontmatter block, from the `frontmatter` query."""
        return self._database.frontmatter(self._source)

    def schema_problems(self) -> tuple[SchemaProblems, ...]:
        """What each frontmatter schema that governs the document rejects, from the `schema_problems` query."""
        return self._database.schema_problems(self._source)

    def frontmatter_owner(self) -> DocumentFrontmatterOwner:
        """The document, with the filename its frontmatter `name` must equal and its corpus's structure spec."""
        # A schema governs a document only through its corpus's structure specification, which a namespace's schema
        # merely narrows; so that specification states every rule over the block.
        return DocumentFrontmatterOwner(filename=self._source.ref.filename, spec=self.corpus_structure().path)

    def parse(self) -> ParsedDocument:
        """The document's parse tree, from the `parse` query."""
        return self._database.parse(self._source)

    def link_base(self) -> DocumentDirectory:
        """The directory holding the document, read from its ref."""
        return DocumentDirectory(self._source.ref.path.parent)

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """Where each relative link leads and what the snapshot holds there, from the `link_targets` query."""
        return self._database.link_targets(self._source)

    def tokens(self) -> TokenCount:
        """The tokens in the document's whole file, from the `tokens` query."""
        return self._database.tokens(self._source)

    def lines(self) -> LineCount:
        """The lines in the document's whole file, from the `document_lines` query."""
        return self._database.document_lines(self._source)

    def specifications(self) -> Governance:
        """The specifications that govern the document, as `Database.governance` returned them."""
        return self._governed.governance

    def corpus_structure(self) -> StructureSpec:
        """The structure specification of the document's corpus, which the specifications state."""
        return self._governed.corpus_structure

    def outline_alignment(self) -> tuple[OutlineAlignmentSpec, ...]:
        """Which outline entry each of the document's sections falls in, from the `outline_alignment` query."""
        return self._database.outline_alignment(self._source)

    def outline_divergences(self) -> tuple[OutlineDivergenceSpec, ...]:
        """Where the document's sections stop matching each outline, from the `outline_divergences` query."""
        return self._database.outline_divergences(self._source)


class DatabaseSkillContext:
    """One skill whose `SKILL.md` decoded, as the database answers for it; a `SkillContext`."""

    def __init__(self, database: Database, source: SkillText) -> None:
        """Bind the context to one decoded skill.

        The skill's location is the one the witness carries, so the text and the location cannot name different
        skills.

        Args:
            database: The revision the skill is read from.
            source: The skill's `SKILL.md` text, as `Database.skill_text` returns it: the witness every per-file
                query takes.
        """
        self._database = database
        self._source = source

    def directory_name(self) -> PathComponent:
        """The name of the skill's directory as an agent lists it, read from its ref."""
        return self._source.ref.entry

    def link_target(self) -> ResolvedPath | None:
        """The resolved directory the listed directory leads to when it is a link, or `None` when it is not.

        Read from the location the model hands out, never from the disk.
        """
        location = self._source.location
        if location.resolves_to == location.ref.directory:
            return None
        return location.resolves_to

    def frontmatter(self) -> FrontmatterNode:
        """The skill's frontmatter block, from the `skill_frontmatter` query."""
        return self._database.skill_frontmatter(self._source)

    def schema_problems(self) -> tuple[SchemaProblems, ...]:
        """What the Agent Skills specification rejects in the frontmatter, from the `skill_schema_problems` query."""
        return self._database.skill_schema_problems(self._source)

    def skill_fields(self) -> SkillFields:
        """The fields of the frontmatter that parse, from the `skill_fields` query."""
        return self._database.skill_fields(self._source)

    def frontmatter_owner(self) -> SkillFrontmatterOwner:
        """The skill, with the directory name its frontmatter `name` must equal and where a link there leads."""
        return SkillFrontmatterOwner(directory_name=self.directory_name(), link_target=self.link_target())

    def parse(self) -> ParsedDocument:
        """The parse tree of the skill's `SKILL.md`, from the `skill_parse` query."""
        return self._database.skill_parse(self._source)

    def link_base(self) -> SkillRoot:
        """The skill directory where an agent reaches it, read from its ref, never where a link there leads."""
        return SkillRoot(self._source.ref.directory)

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """Where each relative link leads and what the snapshot holds there, from the `skill_link_targets` query."""
        return self._database.skill_link_targets(self._source)

    def lines(self) -> LineCount:
        """The lines in the skill's whole `SKILL.md`, from the `skill_lines` query."""
        return self._database.skill_lines(self._source)


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
