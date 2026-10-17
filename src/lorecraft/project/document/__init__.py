"""Document identity and the repository that lists corpora and reads document text."""

from .ref import DocumentRef, InvalidSpecificationNameError, MisplacedSpecificationError, SpecRef
from .repo import (
    CorpusListError,
    Document,
    DocumentDecodeError,
    DocumentFile,
    DocumentReadError,
    Repository,
)

__all__: list[str] = [
    'DocumentRef',
    'SpecRef',
    'InvalidSpecificationNameError',
    'MisplacedSpecificationError',
    'Document',
    'DocumentFile',
    'Repository',
    'CorpusListError',
    'DocumentReadError',
    'DocumentDecodeError',
]
