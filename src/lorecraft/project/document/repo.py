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
from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import CorpusName
from lorecraft.project.layout import DOCS_DIR, DOCUMENT_SUFFIX
from lorecraft.vfs import (
    DecodeTextError,
    EntryKind,
    FileSystem,
    ListDirError,
    ReadTextError,
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


class CorpusListError(Error):
    """A corpus directory exists but cannot be listed.

    Attributes:
        corpus: The corpus whose documents were being listed.
        source: The failure to list its directory.
    """

    corpus: CorpusName
    source: ListDirError

    def __init__(self, corpus: CorpusName, *, source: ListDirError) -> None:
        self.corpus = corpus
        self.source = source
        super().__init__(f'cannot list the documents of corpus {corpus}')
        self.__cause__ = source


class DocumentReadError(Error):
    """A document listed in the model cannot be read: the file is missing or unreadable.

    Attributes:
        ref: The document that could not be read.
        source: The failure to read its file.
    """

    ref: DocumentRef
    source: ReadTextError

    def __init__(self, ref: DocumentRef, *, source: ReadTextError) -> None:
        self.ref = ref
        self.source = source
        super().__init__(f'cannot read document {ref.path}')
        self.__cause__ = source


class DocumentDecodeError(Error):
    """A document's bytes are not UTF-8; a check reports this as a finding.

    Attributes:
        ref: The document that could not be decoded.
        source: The failure to decode its file.
    """

    ref: DocumentRef
    source: DecodeTextError

    def __init__(self, ref: DocumentRef, *, source: DecodeTextError) -> None:
        self.ref = ref
        self.source = source
        super().__init__(f'document {ref.path} is not UTF-8')
        self.__cause__ = source


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
            ListDirError: If docs/ cannot be listed.
        """
        # A failure to list docs/ is the listing's own, with docs/ as its path: this layer adds nothing to it.
        entries = self._fs.list_dir(DOCS_DIR)

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
            CorpusListError: If the directory cannot be listed.
        """
        corpus_dir = DOCS_DIR / str(corpus)
        try:
            entries = self._fs.list_dir(corpus_dir)
        except ListDirError as exc:
            raise CorpusListError(corpus, source=exc) from exc

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
            DocumentReadError: If the file is missing or unreadable.
        """
        # DecodeTextError is a ReadTextError, so the narrower clause must come first.
        try:
            text = self._fs.read_text(ref.path)
        except DecodeTextError as exc:
            raise DocumentDecodeError(ref, source=exc) from exc
        except ReadTextError as exc:
            raise DocumentReadError(ref, source=exc) from exc
        return Document(ref, text)
