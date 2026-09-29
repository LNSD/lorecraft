"""One frozen state of a workspace: its snapshot, and the cached data every check reads through.

The layering follows the IntelliJ Platform's. The ``Snapshot`` plays the virtual file system: every byte a
check can see, and never changed once built. Above it sit two kinds of cached data, each computed on first
use and kept for as long as the database lives (pattern-memoization):

- ``model()``: the workspace model, like the IDE's project model. It reads the structure of the snapshot, the
  specifications and the corpus directories, and no document's contents.
- ``frontmatter(ref)``: one document's frontmatter node, like a stub: the part of a file the IDE reads without
  building its full syntax tree. It reads that document's bytes and nothing else.
- ``parse(ref)``: one document's parse tree, like a PSI file or a per-file index entry. It reads that
  document's bytes and nothing else.

Checks are plain functions of a database and a ref, like an inspection run over one file. Each asks for the
cheapest query that holds what it reads, so a check that needs only the frontmatter never pays for the full
parse, and every check reading the same query shares one computation of it. Their results are not cached; a
check runs again every time.

Nothing here records what a cached value read, so no dependency is tracked. Invalidation is written by hand
instead, the way the IDE drops per-file index entries on a file change event and resets structural caches on
a project model change. Reserved, not implemented: ``advance(snapshot) -> Database``, the next state. It would
``diff`` the two snapshots and carry over each cached value the change set leaves valid: the frontmatter and
the parse of every document whose bytes did not change, and the model unless an entry under ``docs/`` was added
or deleted or a specification changed. That rule holds only while the frontmatter and the parse each read their
own document and the model reads no document, so keep them that way: data drawn from several documents belongs
in a new cache with its own rule.
"""

from lorecraft_project.document import DocumentRef
from lorecraft_project.document import Repository as DocumentRepository
from lorecraft_project.syntax import FrontmatterNode, ParsedDocument, parse_document, parse_frontmatter
from lorecraft_project.workspace import WorkspaceModel, load_model
from lorecraft_vfs import Snapshot, VirtualFileSystem


class Database:
    """The workspace model, the frontmatter and the parse trees of one snapshot, each cached for its lifetime."""

    def __init__(self, snapshot: Snapshot) -> None:
        """Index the snapshot for reading; performs no I/O and computes nothing yet."""
        self._fs = VirtualFileSystem(snapshot)
        self._documents = DocumentRepository(self._fs)
        # `None` until the first `model()` call; a loaded model is never `None`, so the two cannot be confused.
        self._model: WorkspaceModel | None = None
        self._frontmatters: dict[DocumentRef, FrontmatterNode] = {}
        self._parses: dict[DocumentRef, ParsedDocument] = {}

    def model(self) -> WorkspaceModel:
        """The workspace model the snapshot declares, loaded on the first call.

        A load that fails is not cached, so each call raises the same error again.

        Raises:
            ListSpecsError: If the specification directory cannot be listed.
            ListCorpusDirectoriesError: If docs/ cannot be listed.
            ListDocumentsError: If a corpus directory cannot be listed.
            GetHeaderSchemaError: If any header schema cannot be read or decoded.
            InvalidHeaderSchemaError: If any header schema is not a well-formed JSON Schema.
            GetStructureSchemaError: If any structure specification cannot be read.
            InvalidStructureSchemaError: If any structure specification is not JSON in the dialect, or states no
                usable rules.
        """
        if self._model is None:
            self._model = load_model(self._fs)
        return self._model

    def frontmatter(self, ref: DocumentRef) -> FrontmatterNode:
        """The frontmatter of one document, parsed from the snapshot on the first call for its ref.

        Cached apart from ``parse(ref)`` and never read from it, so the answer does not depend on which of the two
        was asked first; ``parse_frontmatter`` guarantees the two agree.

        A document that cannot be read is not cached, so each call raises the same error again.

        Raises:
            DocumentDecodeError: If the document's bytes are not UTF-8.
            GetDocumentError: If the snapshot holds no regular file at the document's path.
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
            GetDocumentError: If the snapshot holds no regular file at the document's path.
        """
        parsed = self._parses.get(ref)
        if parsed is None:
            text = self._documents.get_document(ref).text
            parsed = parse_document(text)
            self._parses[ref] = parsed
        return parsed
