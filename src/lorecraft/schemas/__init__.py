"""Typed schema identities, provenance, immutable inputs and pure registry lookup."""

from .registry import DuplicateSchemaRefError, SchemaRefError, SchemaRegistry
from .types import (
    BuiltinOrigin,
    BuiltinSchemaInput,
    EmptyBuiltinOriginIdentityError,
    EmptyRepositoryLayerError,
    EmptySchemaRefIdentityError,
    FrontmatterSchemaInput,
    RepositoryOrigin,
    RepositorySchemaInput,
    SchemaInput,
    SchemaKind,
    SchemaOrigin,
    SchemaRef,
)

__all__: list[str] = [
    'BuiltinOrigin',
    'BuiltinSchemaInput',
    'DuplicateSchemaRefError',
    'EmptyBuiltinOriginIdentityError',
    'EmptyRepositoryLayerError',
    'EmptySchemaRefIdentityError',
    'FrontmatterSchemaInput',
    'RepositoryOrigin',
    'RepositorySchemaInput',
    'SchemaInput',
    'SchemaKind',
    'SchemaOrigin',
    'SchemaRef',
    'SchemaRefError',
    'SchemaRegistry',
]
