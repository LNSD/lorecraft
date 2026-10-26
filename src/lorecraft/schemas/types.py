"""Schema identities, provenance and immutable source values."""

from dataclasses import dataclass
from enum import StrEnum

from lorecraft.core.mapping import Frozen, FrozenMapping
from lorecraft.core.path import RootRelativePath
from lorecraft.core.text import NonEmptyStr


class SchemaKind(StrEnum):
    """The role an input has in schema validation."""

    STRUCTURE = 'structure'
    FRONTMATTER = 'frontmatter'


@dataclass(frozen=True, slots=True, order=True)
class SchemaRef:
    """A stable, kind-scoped schema identity independent of paths and JSON Schema `$id`.

    Attributes:
        kind: The schema's role: structure or frontmatter.
        identity: A stable, non-empty identity within `kind`.
    """

    kind: SchemaKind
    identity: NonEmptyStr


@dataclass(frozen=True, slots=True)
class RepositoryOrigin:
    """Repository provenance for an input already acquired by the workspace loader.

    Attributes:
        path: The repository-relative path from which the input was acquired.
        layer: The non-empty governance layer that owns the input.
    """

    path: RootRelativePath
    layer: NonEmptyStr


@dataclass(frozen=True, slots=True)
class BuiltinOrigin:
    """Stable identity for a builtin schema or layer, without a fabricated path.

    Attributes:
        identity: The non-empty builtin identity; schema inputs derive their reference from it.
    """

    identity: NonEmptyStr


type SchemaOrigin = RepositoryOrigin | BuiltinOrigin


@dataclass(frozen=True, slots=True)
class RepositorySchemaInput:
    """A schema input acquired from a repository, whose provenance is repository-only.

    Attributes:
        reference: The typed schema identity.
        origin: Repository path and governing layer that supplied the input.
        document: The immutable JSON mapping used by schema-backed entries.
    """

    reference: SchemaRef
    origin: RepositoryOrigin
    document: FrozenMapping[str, Frozen]

    @property
    def kind(self) -> SchemaKind:
        """The role carried by the input's reference."""
        return self.reference.kind


@dataclass(frozen=True, slots=True)
class BuiltinSchemaInput:
    """A builtin schema document whose stable identity is held by its origin exactly once.

    Attributes:
        kind: The schema's role: structure or frontmatter.
        origin: Stable builtin identity, used to derive the typed reference.
        document: The immutable JSON mapping used by schema-backed entries.
    """

    kind: SchemaKind
    origin: BuiltinOrigin
    document: FrozenMapping[str, Frozen]

    @property
    def reference(self) -> SchemaRef:
        """The typed schema identity derived from its kind and builtin origin."""
        return SchemaRef(self.kind, self.origin.identity)


@dataclass(frozen=True, slots=True)
class FrontmatterSchemaInput:
    """A builtin schema input whose kind is fixed to frontmatter."""

    origin: BuiltinOrigin
    document: FrozenMapping[str, Frozen]

    @property
    def kind(self) -> SchemaKind:
        """The schema's fixed role."""
        return SchemaKind.FRONTMATTER

    @property
    def reference(self) -> SchemaRef:
        """The typed frontmatter identity derived from its builtin origin."""
        return SchemaRef(SchemaKind.FRONTMATTER, self.origin.identity)


type SchemaInput = RepositorySchemaInput | BuiltinSchemaInput | FrontmatterSchemaInput
