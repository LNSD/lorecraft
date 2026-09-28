"""Document specification aspect names and namespaces."""

from .filename import (
    AspectFilename,
    AspectFilenameError,
    InvalidAspectFilenameError,
)
from .name import AspectName, AspectNameError, EmptyAspectNameError, InvalidAspectNameCharacterError
from .namespace import (
    AspectNamespace,
    AspectNamespaceError,
    EmptyAspectNamespaceError,
    InvalidAspectNamespaceCharacterError,
)

__all__ = [
    'AspectName',
    'AspectNameError',
    'EmptyAspectNameError',
    'InvalidAspectNameCharacterError',
    'AspectFilename',
    'AspectFilenameError',
    'InvalidAspectFilenameError',
    'AspectNamespace',
    'AspectNamespaceError',
    'EmptyAspectNamespaceError',
    'InvalidAspectNamespaceCharacterError',
]
