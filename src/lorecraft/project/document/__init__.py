"""Document identity and the repository that lists corpora and reads document text."""

from .ref import DocumentRef
from .repo import (
    Document,
    DocumentDecodeError,
    DocumentFile,
    GetDocumentError,
    ListCorpusDirectoriesError,
    ListDocumentsError,
    Repository,
)

__all__ = [
    'DocumentRef',
    'Document',
    'DocumentFile',
    'Repository',
    'ListCorpusDirectoriesError',
    'ListDocumentsError',
    'GetDocumentError',
    'DocumentDecodeError',
]
