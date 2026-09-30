"""Document specification aspect names and namespaces."""

from .filename import AspectFilename
from .name import AspectName, EmptyAspectNameError, InvalidAspectNameCharacterError
from .namespace import (
    AspectNamespace,
    EmptyAspectNamespaceError,
    InvalidAspectNamespaceCharacterError,
)

__all__ = [
    'AspectName',
    'EmptyAspectNameError',
    'InvalidAspectNameCharacterError',
    'AspectFilename',
    'AspectNamespace',
    'EmptyAspectNamespaceError',
    'InvalidAspectNamespaceCharacterError',
]
