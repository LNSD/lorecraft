"""Typed schema identities, provenance, immutable inputs and pure registry lookup."""

from .registry import DuplicateSchemaRefError, SchemaRefError, SchemaRegistry
from .types import (
    BuiltinOrigin,
    EmptyBuiltinOriginIdentityError,
    EmptyRepositoryLayerError,
    EmptySchemaRefIdentityError,
    RepositoryOrigin,
    RepositorySchemaInput,
    SchemaInput,
    SchemaKind,
    SchemaOrigin,
    SchemaOriginMismatchError,
    SchemaRef,
)

__all__: list[str] = [
    'BuiltinOrigin',
    'DuplicateSchemaRefError',
    'EmptyBuiltinOriginIdentityError',
    'EmptyRepositoryLayerError',
    'EmptySchemaRefIdentityError',
    'RepositoryOrigin',
    'RepositorySchemaInput',
    'SchemaInput',
    'SchemaKind',
    'SchemaOriginMismatchError',
    'SchemaOrigin',
    'SchemaRef',
    'SchemaRefError',
    'SchemaRegistry',
]
