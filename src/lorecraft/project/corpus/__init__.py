"""Validated names for documentation corpora."""

from .directory import ReservedCorpusDirectory, ReservedCorpusDirectoryRef
from .name import (
    META_CORPUS_NAME,
    RESERVED_CORPUS_NAME,
    SKILLS_CORPUS_NAME,
    CorpusName,
    EmptyCorpusNameError,
    InvalidCorpusNameCharacterError,
    ReservedCorpusNameError,
)

__all__: list[str] = [
    'RESERVED_CORPUS_NAME',
    'META_CORPUS_NAME',
    'SKILLS_CORPUS_NAME',
    'CorpusName',
    'EmptyCorpusNameError',
    'InvalidCorpusNameCharacterError',
    'ReservedCorpusNameError',
    'ReservedCorpusDirectory',
    'ReservedCorpusDirectoryRef',
]
