"""The contexts of `lorecraft.project.context`, answered by the database's queries for one decoded subject.

`DatabaseDocumentContext` and `DatabaseSkillContext` implement `DocumentContext` and `SkillContext`. Each holds the
database, the decode query's witness and what the model says about the subject, and nothing it computed: every fact
is the matching memoized query of the database, so a fact nobody asks for is never computed, and one asked for twice
is computed once. An identity value, such as a document's filename or a skill's directory name, is read from the
subject's ref or its location.

A context is built only from a witness, so no fact of a file that does not decode can be asked for, and a document's
context only for a document whose corpus states a structure specification, with the specifications that govern it: no
facet governs a document whose corpus states none. The model is loaded by then, so no method raises.
"""

from lorecraft.core.num import UnsignedInt
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.context import DocumentFrontmatterOwner, SkillFrontmatterOwner
from lorecraft.project.schemas import OutlineDivergenceSpec, SchemaProblems, StructureSpec
from lorecraft.project.skill import SkillLocation
from lorecraft.project.syntax import FrontmatterNode, ParsedDocument
from lorecraft.project.workspace import Governance
from lorecraft.vfs import ResolvedPath

from .database import Database
from .text import DocumentText, SkillText


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

    def lines(self) -> UnsignedInt:
        """The lines in the skill's whole `SKILL.md`, from the `skill_lines` query."""
        # A count is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
        return UnsignedInt(self._database.skill_lines(self._source))
