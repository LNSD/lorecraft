"""Typed schema identities, provenance, immutable inputs and pure registry lookup."""

from .registry import DuplicateSchemaRefError, SchemaRefError, SchemaRegistry
from .types import (
    BundledOrigin,
    EmptyBundledOriginIdentityError,
    EmptyRepositoryLayerError,
    EmptySchemaRefIdentityError,
    RepositoryOrigin,
    SchemaInput,
    SchemaKind,
    SchemaOrigin,
    SchemaOriginMismatchError,
    SchemaRef,
)

__all__: list[str] = [
    'BundledOrigin',
    'DuplicateSchemaRefError',
    'EmptyBundledOriginIdentityError',
    'EmptyRepositoryLayerError',
    'EmptySchemaRefIdentityError',
    'RepositoryOrigin',
    'SchemaInput',
    'SchemaKind',
    'SchemaOriginMismatchError',
    'SchemaOrigin',
    'SchemaRef',
    'SchemaRefError',
    'SchemaRegistry',
]
