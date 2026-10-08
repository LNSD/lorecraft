"""The contexts of `lorecraft.project.context`, answered by the database's queries for one decoded subject.

`DatabaseDocumentContext`, `DatabaseSkillContext` and `DatabaseSkillResourceContext` implement `DocumentContext`,
`SkillContext` and `SkillResourceContext`. Each holds the database, the decode query's witness and, for a document or
a skill, what the model says about it, and nothing it computed: every fact is the matching memoized query of the
database, so a fact nobody asks for is never computed, and one asked for twice is computed once. An identity value,
such as a document's filename or a skill's directory name, is read from the subject's ref or its location.

A context is built only from a witness, so no fact of a file that does not decode can be asked for, and a document's
context only for a document whose corpus states a structure specification, with the specifications that govern it: no
facet governs a document whose corpus states none. The model is loaded by then, so no method raises.

`DatabaseLayoutContext` implements `LayoutContext`. A layout entry has no text, so it has no witness and no per-file
query: the context holds the `OutsideSymlink` record the model's `outside_symlinks` or a skill's `skill_resources`
listing returned, the memoized query value itself, and reads every fact from it.
"""

from collections.abc import Mapping
from pathlib import PurePosixPath

from lorecraft.core.num import UnsignedInt
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.context import DocumentFrontmatterOwner, SkillFrontmatterOwner
from lorecraft.project.link_target import DocumentDirectory, LinkTarget, SkillRoot
from lorecraft.project.schemas import OutlineDivergenceSpec, SchemaProblems, StructureSpec
from lorecraft.project.skill import OutsideSymlink, SkillLocation
from lorecraft.project.syntax import FrontmatterNode, ParsedDocument
from lorecraft.project.workspace import Governance
from lorecraft.vfs import ResolvedPath, RootExit

from .database import Database
from .text import DocumentText, SkillResourceText, SkillText


class DatabaseDocumentContext:
    """One decoded document of a corpus, as the database answers for it; a `DocumentContext`."""

    def __init__(
        self, database: Database, source: DocumentText, governance: Governance, corpus_structure: StructureSpec
    ) -> None:
        """Bind the context to one decoded document and the specifications that govern it.

        Args:
            database: The revision the document is read from.
            source: The document's text, as `Database.text` returns it: the witness every per-file query takes.
            governance: The specifications that govern the document, as the database's model finds them.
            corpus_structure: The structure specification of the document's corpus, `governance.corpus_spec.structure`
                once the caller has found it stated; without it no facet governs the document.
        """
        self._database = database
        self._source = source
        self._governance = governance
        self._corpus_structure = corpus_structure

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
        return DocumentFrontmatterOwner(filename=self._source.ref.filename, spec=self._corpus_structure.path)

    def parse(self) -> ParsedDocument:
        """The document's parse tree, from the `parse` query."""
        return self._database.parse(self._source)

    def link_base(self) -> DocumentDirectory:
        """The directory holding the document, read from its ref."""
        return DocumentDirectory(self._source.ref.path.parent)

    def link_targets(self) -> Mapping[PurePosixPath, LinkTarget]:
        """Where each relative link leads and what the snapshot holds there, from the `link_targets` query."""
        return self._database.link_targets(self._source)

    def tokens(self) -> UnsignedInt:
        """The tokens in the document's whole file, from the `tokens` query."""
        # A count is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
        return UnsignedInt(self._database.tokens(self._source))

    def lines(self) -> UnsignedInt:
        """The lines in the document's whole file, from the `document_lines` query."""
        # A count is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
        return UnsignedInt(self._database.document_lines(self._source))

    def specifications(self) -> Governance:
        """The specifications that govern the document, as the model found them when the context was built."""
        return self._governance

    def corpus_structure(self) -> StructureSpec:
        """The structure specification of the document's corpus, as the caller found it stated."""
        return self._corpus_structure

    def outline_divergences(self) -> tuple[OutlineDivergenceSpec, ...]:
        """Where the document's sections stop matching each outline, from the `outline_divergences` query."""
        return self._database.outline_divergences(self._source)


class DatabaseSkillContext:
    """One skill whose `SKILL.md` decoded, as the database answers for it; a `SkillContext`."""

    def __init__(self, database: Database, source: SkillText, location: SkillLocation) -> None:
        """Bind the context to one decoded skill and where the model locates it.

        Args:
            database: The revision the skill is read from.
            source: The skill's `SKILL.md` text, as `Database.skill_text` returns it: the witness every per-file
                query takes.
            location: The skill, and where its files live, as the model hands it out.
        """
        self._database = database
        self._source = source
        self._location = location

    def directory_name(self) -> str:
        """The name of the skill's directory as an agent lists it, read from its ref."""
        return self._source.ref.directory.name

    def link_target(self) -> ResolvedPath | None:
        """The resolved directory the listed directory leads to when it is a link, or `None` when it is not.

        Read from the location the model hands out, never from the disk.
        """
        if self._location.resolves_to == self._location.ref.directory:
            return None
        return self._location.resolves_to

    def frontmatter(self) -> FrontmatterNode:
        """The skill's frontmatter block, from the `skill_frontmatter` query."""
        return self._database.skill_frontmatter(self._source)

    def schema_problems(self) -> tuple[SchemaProblems, ...]:
        """What the Agent Skills specification rejects in the frontmatter, from the `skill_schema_problems` query."""
        return self._database.skill_schema_problems(self._source)

    def frontmatter_owner(self) -> SkillFrontmatterOwner:
        """The skill, with the directory name its frontmatter `name` must equal and where a link there leads."""
        return SkillFrontmatterOwner(directory_name=self.directory_name(), link_target=self.link_target())

    def parse(self) -> ParsedDocument:
        """The parse tree of the skill's `SKILL.md`, from the `skill_parse` query."""
        return self._database.skill_parse(self._source)

    def link_base(self) -> SkillRoot:
        """The skill directory where an agent reaches it, read from its ref, never where a link there leads."""
        return SkillRoot(self._source.ref.directory)

    def link_targets(self) -> Mapping[PurePosixPath, LinkTarget]:
        """Where each relative link leads and what the snapshot holds there, from the `skill_link_targets` query."""
        return self._database.skill_link_targets(self._source)

    def lines(self) -> UnsignedInt:
        """The lines in the skill's whole `SKILL.md`, from the `skill_lines` query."""
        # A count is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
        return UnsignedInt(self._database.skill_lines(self._source))


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

    def link_targets(self) -> Mapping[PurePosixPath, LinkTarget]:
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
