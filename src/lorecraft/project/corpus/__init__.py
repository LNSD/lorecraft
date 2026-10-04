"""Validated names for documentation corpora."""

from .name import (
    CorpusName,
    EmptyCorpusNameError,
    InvalidCorpusNameCharacterError,
)

__all__: list[str] = [
    'CorpusName',
    'EmptyCorpusNameError',
    'InvalidCorpusNameCharacterError',
]
