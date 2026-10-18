"""Typed inputs and pure lookup for validation schemas."""

from .registry import DuplicateSchemaReferenceError, SchemaReferenceError, SchemaRegistry
from .types import (
    BundledOrigin,
    EmptyBundledOriginIdentityError,
    EmptyRepositoryLayerError,
    EmptySchemaReferenceIdentityError,
    RepositoryOrigin,
    SchemaInput,
    SchemaKind,
    SchemaOrigin,
    SchemaOriginMismatchError,
    SchemaReference,
)

__all__: list[str] = [
    'BundledOrigin',
    'DuplicateSchemaReferenceError',
    'EmptyBundledOriginIdentityError',
    'EmptyRepositoryLayerError',
    'EmptySchemaReferenceIdentityError',
    'RepositoryOrigin',
    'SchemaInput',
    'SchemaKind',
    'SchemaOriginMismatchError',
    'SchemaOrigin',
    'SchemaReference',
    'SchemaReferenceError',
    'SchemaRegistry',
]
