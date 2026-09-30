"""Discover and read documents in the flat ``docs/<corpus>/`` directories through the filesystem boundary.

Every path the repository takes or returns is root-relative: ``docs/`` is joined to the workspace root only
inside ``FileSystem``. The repository lists entries and reads text; whether a listed stem is a valid document
name, and whether the text is a valid document, is decided above it. The repository decides what kind an entry
is: a corpus is a regular directory and a document a regular file, so a symlink under ``docs/`` is never listed,
and no ``EntryKind`` leaves the repository.

Nothing here logs: the command that loads the model catches every ``Error`` that escapes it and reports it,
so every handler below re-raises without logging.
"""

from dataclasses import dataclass

from lorecraft.core.error import Error
from lorecraft.project.corpus import CorpusName
from lorecraft.project.layout import DOCS_DIR, DOCUMENT_SUFFIX
from lorecraft.vfs import (
    DecodeTextError,
    EntryKind,
    FileSystem,
    ListDirError,
    ReadTextError,
    RootRelativePath,
)

from .ref import DocumentRef


@dataclass(frozen=True, slots=True)
class DocumentFile:
    """A regular ``.md`` file directly inside a corpus directory, before name validation.

    Attributes:
        path: Root-relative path.
        stem: Filename without ``.md``; may fail ``AspectFilename.parse`` (the loader records that).
    """

    path: RootRelativePath
    stem: str


@dataclass(frozen=True, slots=True)
class Document:
    """A document's text at the moment it was read.

    Attributes:
        ref: The document's identity in the workspace model.
        text: The whole file decoded as UTF-8.
    """

    ref: DocumentRef
    text: str


class ListCorpusDirectoriesError(Error):
    """The docs/ directory exists but cannot be listed."""


class ListDocumentsError(Error):
    """A corpus directory exists but cannot be listed."""


class GetDocumentError(Error):
    """A document listed in the model cannot be read.

    Attributes:
        ref: The document that could not be read.
    """

    ref: DocumentRef

    def __init__(self, ref: DocumentRef, detail: str) -> None:
        self.ref = ref
        super().__init__(f'cannot read document {ref.path}: {detail}')


class DocumentDecodeError(GetDocumentError):
    """The document is not UTF-8; the CLI reports this as a finding."""


class Repository:
    """Discover and read documents in the flat ``docs/<corpus>/`` directories."""

    def __init__(self, fs: FileSystem) -> None:
        """Remember the seam; performs no I/O."""
        self._fs = fs

    def list_corpus_directories(self) -> tuple[str, ...]:
        """The names of the regular directories directly under docs/, sorted; a missing docs/ is ``()``.

        Files are dropped silently: a Markdown file directly under docs/ belongs to no corpus. So are symlinks:
        a corpus is a regular directory.

        Raises:
            ListCorpusDirectoriesError: If docs/ cannot be listed.
        """
        try:
            entries = self._fs.list_dir(DOCS_DIR)
        except ListDirError as exc:
            raise ListCorpusDirectoriesError(f'cannot list corpus directories in {DOCS_DIR}: {exc.detail}') from exc

        names: list[str] = []
        for entry in entries:
            if entry.kind is EntryKind.DIRECTORY:
                names.append(entry.name)
        return tuple(names)

    def list_documents(self, corpus: CorpusName) -> tuple[DocumentFile, ...]:
        """Regular ``.md`` files directly inside docs/<corpus>/, sorted by name.

        Subdirectories, non-``.md`` entries and symlinks are dropped silently: a document is a regular file.
        A missing directory lists as nothing.

        Raises:
            ListDocumentsError: If the directory cannot be listed.
        """
        corpus_dir = DOCS_DIR / str(corpus)
        try:
            entries = self._fs.list_dir(corpus_dir)
        except ListDirError as exc:
            raise ListDocumentsError(f'cannot list documents for {corpus} in {corpus_dir}: {exc.detail}') from exc

        documents: list[DocumentFile] = []
        for entry in entries:
            if entry.kind is not EntryKind.FILE:
                continue
            if not entry.name.endswith(DOCUMENT_SUFFIX):
                continue
            stem = entry.name.removesuffix(DOCUMENT_SUFFIX)
            documents.append(DocumentFile(corpus_dir / entry.name, stem))
        return tuple(documents)

    def get_document(self, ref: DocumentRef) -> Document:
        """Read one document's text.

        Raises:
            DocumentDecodeError: If the file is not UTF-8.
            GetDocumentError: If the file is missing or unreadable.
        """
        # DecodeTextError is a ReadTextError, so the narrower clause must come first.
        try:
            text = self._fs.read_text(ref.path)
        except DecodeTextError as exc:
            raise DocumentDecodeError(ref, exc.detail) from exc
        except ReadTextError as exc:
            raise GetDocumentError(ref, exc.detail) from exc
        return Document(ref, text)
