"""Document identity and the repository that lists corpora and reads document text."""

from .ref import DocumentRef, InvalidSpecificationNameError, MetaSpecRef, MisplacedSpecificationError
from .repo import (
    CorpusListError,
    Document,
    DocumentDecodeError,
    DocumentFile,
    Repository,
)

__all__: list[str] = [
    'DocumentRef',
    'MetaSpecRef',
    'InvalidSpecificationNameError',
    'MisplacedSpecificationError',
    'Document',
    'DocumentFile',
    'Repository',
    'CorpusListError',
    'DocumentDecodeError',
]
