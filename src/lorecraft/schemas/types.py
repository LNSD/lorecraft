"""Schema identities, provenance and immutable source values."""

from dataclasses import dataclass
from enum import StrEnum

from lorecraft.core.error import Error
from lorecraft.core.mapping import Frozen, FrozenMapping
from lorecraft.core.path import RootRelativePath


class SchemaKind(StrEnum):
    """The role an input has in schema validation."""

    STRUCTURE = 'structure'
    FRONTMATTER = 'frontmatter'


class EmptySchemaRefIdentityError(Error):
    """A schema reference has no stable identity.

    Attributes:
        kind: The kind whose reference identity was empty.
        identity: The rejected identity.
    """

    kind: SchemaKind
    identity: str

    def __init__(self, kind: SchemaKind, identity: str) -> None:
        self.kind = kind
        self.identity = identity
        super().__init__(f'a {kind.value} schema reference identity must not be empty')


class EmptyRepositoryLayerError(Error):
    """A repository schema origin has no governing layer.

    Attributes:
        path: The repository path whose origin omitted its layer.
        layer: The rejected layer identity.
    """

    path: RootRelativePath
    layer: str

    def __init__(self, path: RootRelativePath, layer: str) -> None:
        self.path = path
        self.layer = layer
        super().__init__(f'repository schema layer for {path} must not be empty')


class EmptyBuiltinOriginIdentityError(Error):
    """A builtin schema origin has no stable identity.

    Attributes:
        identity: The rejected built-in identity.
    """

    identity: str

    def __init__(self, identity: str) -> None:
        self.identity = identity
        super().__init__('a builtin schema identity must not be empty')


@dataclass(frozen=True, slots=True, order=True)
class SchemaRef:
    """A stable, kind-scoped schema identity independent of paths and JSON Schema `$id`.

    Attributes:
        kind: The schema's role: structure or frontmatter.
        identity: A stable identity within `kind`; empty values raise `EmptySchemaRefIdentityError`.
    """

    kind: SchemaKind
    identity: str

    def __post_init__(self) -> None:
        """Reject an empty source identity.

        Raises:
            EmptySchemaRefIdentityError: If `identity` is empty.
        """
        if not self.identity:
            raise EmptySchemaRefIdentityError(self.kind, self.identity)


@dataclass(frozen=True, slots=True)
class RepositoryOrigin:
    """Repository provenance for an input already acquired by the workspace loader.

    Attributes:
        path: The repository-relative path from which the input was acquired.
        layer: The governance layer that owns the input; empty values raise `EmptyRepositoryLayerError`.
    """

    path: RootRelativePath
    layer: str

    def __post_init__(self) -> None:
        """Reject missing repository-layer provenance.

        Raises:
            EmptyRepositoryLayerError: If `layer` is empty.
        """
        if not self.layer:
            raise EmptyRepositoryLayerError(self.path, self.layer)


@dataclass(frozen=True, slots=True)
class BuiltinOrigin:
    """Stable identity for a builtin schema or layer, without a fabricated path.

    Attributes:
        identity: The builtin identity; schema inputs derive their reference from it. Empty values raise
            `EmptyBuiltinOriginIdentityError`.
    """

    identity: str

    def __post_init__(self) -> None:
        """Reject an empty builtin identity.

        Raises:
            EmptyBuiltinOriginIdentityError: If `identity` is empty.
        """
        if not self.identity:
            raise EmptyBuiltinOriginIdentityError(self.identity)


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


type SchemaInput = RepositorySchemaInput | BuiltinSchemaInput
