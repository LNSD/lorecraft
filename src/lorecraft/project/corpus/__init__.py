"""Validated names for documentation corpora."""

from .name import (
    RESERVED_CORPUS_NAME,
    CorpusName,
    EmptyCorpusNameError,
    InvalidCorpusNameCharacterError,
    ReservedCorpusNameError,
)

__all__: list[str] = [
    'RESERVED_CORPUS_NAME',
    'CorpusName',
    'EmptyCorpusNameError',
    'InvalidCorpusNameCharacterError',
    'ReservedCorpusNameError',
]
