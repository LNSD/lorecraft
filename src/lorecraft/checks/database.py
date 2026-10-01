"""One frozen state of a workspace: its snapshot, and the cached data every check, and every command, reads through.

The layering follows the IntelliJ Platform's. The ``Snapshot`` plays the virtual file system: every byte a
check can see, and never changed once built. Above it sit two kinds of cached data, each computed on first
use and kept for as long as the database lives (pattern-memoization):

- ``model()``: the workspace model, like the IDE's project model. It reads the structure of the snapshot, the
  specifications, the corpus directories and the skills directories, and no document's contents.
- ``frontmatter(ref)``: one document's frontmatter node, like a stub: the part of a file the IDE reads without
  building its full syntax tree. It reads that document's bytes and nothing else.
- ``parse(ref)``: one document's parse tree, like a PSI file or a per-file index entry. It reads that
  document's bytes and nothing else.
- ``skill_frontmatter(ref)``: one skill's frontmatter node, the same stub for a ``SKILL.md``. It reads that
  skill's bytes and nothing else.
- ``skill_parse(ref)``: one skill's parse tree, the same PSI file for a ``SKILL.md``. It reads that skill's bytes
  and nothing else.
- ``tokens(ref)``: what one document's whole file costs an agent that loads it, like another per-file index
  entry: counted from the raw text, frontmatter and code included, without a parse. It reads that document's
  bytes and nothing else.

Checks are plain functions of a database and a ref, like an inspection run over one file. Each asks for the
cheapest query that holds what it reads, so a check that needs only the frontmatter never pays for the full
parse, and every check reading the same query shares one computation of it. Their results are not cached; a
check runs again every time.

Nothing here records what a cached value read, so no dependency is tracked. Invalidation is written by hand instead,
the way the IDE drops per-file index entries on a file change event and resets structural caches on a project model
change. Reserved, not implemented: ``advance(snapshot) -> Database``, the next state. It would ``diff`` the two
snapshots and carry over each cached value the change set leaves valid: the frontmatter, the parse and the token
count of every document whose bytes did not change, the frontmatter and the parse of every skill whose bytes did
not, and the model unless an entry was added or deleted under ``docs/``, a skills directory or a directory a skill
is linked to, a link on the way to a skill changed its target, or a specification changed. That rule holds only
while the frontmatter, the parse and the token count each read their own document or skill and the model reads no
document, so keep them that way: data drawn from several documents belongs in a new cache with its own rule.

A change names a real path, while a ref may name a path through a link: a skill's ``SKILL.md`` under a linked
skill entry changes at the path the link leads to, not at the ref's. A snapshot maps a linked path to its real
one and not back, so the model records each skill's ``SkillLocation``, the real ``SKILL.md`` its ref leads to,
and ``advance`` would look that path up in the change set. A link retargeted to another skill leaves every file's
bytes as they were and the ref as it was, like a file's identity in the IDE, while its location changes. So a
skill's frontmatter and its parse carry over only when the two models locate its ref at the same real file and that
file's bytes did not change.
"""

from lorecraft.core.path import RootRelativePath
from lorecraft.project.document import DocumentRef
from lorecraft.project.document import Repository as DocumentRepository
from lorecraft.project.layout import require_real_layout
from lorecraft.project.skill import Repository as SkillRepository
from lorecraft.project.skill import SkillRef
from lorecraft.project.syntax import FrontmatterNode, ParsedDocument, count_tokens, parse_document, parse_frontmatter
from lorecraft.project.workspace import WorkspaceModel, load_model
from lorecraft.vfs import Snapshot, VirtualFileSystem


class Database:
    """The workspace model, the frontmatter, the parse trees and the token counts of the documents, and the
    frontmatter and the parse trees of the skills, of one snapshot, each cached for its lifetime."""

    def __init__(self, snapshot: Snapshot) -> None:
        """Index the snapshot for reading; performs no I/O and computes nothing yet."""
        self._fs = VirtualFileSystem(snapshot)
        self._documents = DocumentRepository(self._fs)
        self._skills = SkillRepository(self._fs)
        # `None` until the first `model()` call; a loaded model is never `None`, so the two cannot be confused.
        self._model: WorkspaceModel | None = None
        self._frontmatters: dict[DocumentRef, FrontmatterNode] = {}
        self._parses: dict[DocumentRef, ParsedDocument] = {}
        self._token_counts: dict[DocumentRef, int] = {}
        self._skill_frontmatters: dict[SkillRef, FrontmatterNode] = {}
        self._skill_parses: dict[SkillRef, ParsedDocument] = {}

    def model(self) -> WorkspaceModel:
        """The workspace model the snapshot declares, loaded on the first call.

        A load that fails is not cached, so each call raises the same error again.

        Raises:
            DirListError: If the specification directory or docs/ cannot be listed.
            CorpusListError: If a corpus directory cannot be listed.
            StructureSchemaReadError: If any structure specification cannot be read.
            StructureSpecDecodeError: If a structure specification is not JSON in the dialect's shape.
            StructureSpecFilenameError: If a structure specification is not at a specification filename.
            EmptyStructureSpecError: If a structure specification states no rule.
            InvalidTitleCountError: If a title count is below 1.
            InvalidTokenBudgetError: If a token budget is below 1.
            InvalidWordCapError: If an outline word cap is below 1.
            RepeatedOutlineSectionError: If an outline names a section twice.
            ForbiddenOutlineSectionError: If a specification forbids a section its outline names.
            AdjacentAnyRunsError: If an outline places two ``any`` runs side by side.
            InvalidFrontmatterSchemaError: If a frontmatter schema is rejected by the meta-schema.
            FrontmatterSchemaIdError: If a schema in a frontmatter schema carries ``$id``.
            ForeignFrontmatterDialectError: If a schema in a frontmatter schema names another dialect.
            UntypedFrontmatterSchemaError: If a frontmatter schema's root does not state an object.
            DirResolveError: If a skills directory cannot be resolved.
            SkillsDirListError: If a skills directory cannot be listed.
            SkillEntryResolveError: If a symlinked skill entry cannot be resolved.
            SkillDirListError: If a skill directory cannot be listed.
            SkillFileResolveError: If a symlinked SKILL.md cannot be resolved.
        """
        if self._model is None:
            self._model = load_model(self._fs)
        return self._model

    def require_real_layout(self) -> None:
        """Refuse a snapshot in which ``docs/`` or ``docs/__meta__/`` is a symlink; never cached.

        Behind a linked ``docs/`` or ``docs/__meta__/`` the snapshot holds no specification, so the model has no
        corpus, and a run over its documents would report success over nothing. Kept apart from ``model()``, which
        also lists the skills: a caller that reads only skills has no reason to refuse a linked ``docs/``.

        Raises:
            LinkedLayoutError: If ``docs/`` is a symlink, or else if ``docs/__meta__/`` is one.
        """
        require_real_layout(self._fs)

    def resolve(self, path: RootRelativePath) -> RootRelativePath | None:
        """Where ``path`` leads in the snapshot, every recorded link on the way followed; never cached.

        Like the IDE's lookup of a path in its virtual file system: a path handed in from outside, such as a
        command line argument, is interpreted in the same frozen tree every check reads, not on the live disk.

        Returns:
            The real directory or the real file, root-relative, or ``None`` when the snapshot holds neither there.
        """
        directory = self._fs.resolve_dir(path)
        if directory is not None:
            return directory
        return self._fs.resolve_file(path)

    def resolve_file(self, path: RootRelativePath) -> RootRelativePath | None:
        """The file ``path`` leads to in the snapshot, every recorded link on the way followed; never cached.

        Returns:
            The real file, root-relative, or ``None`` when the snapshot holds no file there: nothing, a
            directory, or a link it did not follow.
        """
        return self._fs.resolve_file(path)

    def is_listed(self, path: RootRelativePath) -> bool:
        """Whether the snapshot holds a listing of the directory ``path`` leads to, links followed; never cached.

        It tells a file that is missing from one the snapshot never read: in a listed directory the snapshot
        holds every entry, so a name it lacks was not there when the scan ran, while outside one it cannot say.

        Returns:
            True for a directory the scan listed, an empty one included; False for one it did not enter, and for a
            path that leads to no directory.
        """
        return self._fs.is_listed(path)

    def frontmatter(self, ref: DocumentRef) -> FrontmatterNode:
        """The frontmatter of one document, parsed from the snapshot on the first call for its ref.

        Cached apart from ``parse(ref)`` and never read from it, so the answer does not depend on which of the two
        was asked first; ``parse_frontmatter`` guarantees the two agree.

        A document that cannot be read is not cached, so each call raises the same error again.

        Raises:
            DocumentDecodeError: If the document's bytes are not UTF-8.
            DocumentReadError: If the snapshot holds no regular file at the document's path.
        """
        decoded = self._frontmatters.get(ref)
        if decoded is None:
            text = self._documents.get_document(ref).text
            decoded = parse_frontmatter(text)
            self._frontmatters[ref] = decoded
        return decoded

    def parse(self, ref: DocumentRef) -> ParsedDocument:
        """The parse tree of one document, parsed from the snapshot on the first call for its ref.

        A document that cannot be read is not cached, so each call raises the same error again.

        Raises:
            DocumentDecodeError: If the document's bytes are not UTF-8.
            DocumentReadError: If the snapshot holds no regular file at the document's path.
        """
        parsed = self._parses.get(ref)
        if parsed is None:
            text = self._documents.get_document(ref).text
            parsed = parse_document(text)
            self._parses[ref] = parsed
        return parsed

    def tokens(self, ref: DocumentRef) -> int:
        """The tokens in one document's whole file, counted from the snapshot on the first call for its ref.

        Cached apart from ``parse(ref)`` and never read from it: the count needs the raw text, not the tree, so
        a check that needs only one of the two never pays for the other.

        A document that cannot be read is not cached, so each call raises the same error again.

        Raises:
            DocumentDecodeError: If the document's bytes are not UTF-8.
            DocumentReadError: If the snapshot holds no regular file at the document's path.
        """
        count = self._token_counts.get(ref)
        if count is None:
            text = self._documents.get_document(ref).text
            count = count_tokens(text)
            self._token_counts[ref] = count
        return count

    def skill_frontmatter(self, ref: SkillRef) -> FrontmatterNode:
        """The frontmatter of one skill's ``SKILL.md``, parsed from the snapshot on the first call for its ref.

        A skill that cannot be read is not cached, so each call raises the same error again.

        Raises:
            SkillDecodeError: If the skill's bytes are not UTF-8.
            SkillReadError: If the snapshot holds no regular file at the skill's path.
        """
        decoded = self._skill_frontmatters.get(ref)
        if decoded is None:
            text = self._skills.get_skill(ref).text
            decoded = parse_frontmatter(text)
            self._skill_frontmatters[ref] = decoded
        return decoded

    def skill_parse(self, ref: SkillRef) -> ParsedDocument:
        """The parse tree of one skill's ``SKILL.md``, parsed from the snapshot on the first call for its ref.

        Cached apart from ``skill_frontmatter(ref)`` and never read from it, as a document's parse is from its
        frontmatter.

        A skill that cannot be read is not cached, so each call raises the same error again.

        Raises:
            SkillDecodeError: If the skill's bytes are not UTF-8.
            SkillReadError: If the snapshot holds no regular file at the skill's path.
        """
        parsed = self._skill_parses.get(ref)
        if parsed is None:
            text = self._skills.get_skill(ref).text
            parsed = parse_document(text)
            self._skill_parses[ref] = parsed
        return parsed
