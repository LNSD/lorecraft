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


class EmptySchemaReferenceIdentityError(Error):
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


class EmptyBundledOriginIdentityError(Error):
    """A bundled schema origin has no stable identity.

    Attributes:
        identity: The rejected built-in identity.
    """

    identity: str

    def __init__(self, identity: str) -> None:
        self.identity = identity
        super().__init__('a bundled schema identity must not be empty')


@dataclass(frozen=True, slots=True, order=True)
class SchemaReference:
    """A stable, kind-scoped schema identity independent of paths and JSON Schema `$id`.

    Attributes:
        kind: The schema's role: structure or frontmatter.
        identity: A stable identity within `kind`; empty values raise `EmptySchemaReferenceIdentityError`.
    """

    kind: SchemaKind
    identity: str

    def __post_init__(self) -> None:
        """Reject an empty source identity.

        Raises:
            EmptySchemaReferenceIdentityError: If `identity` is empty.
        """
        if not self.identity:
            raise EmptySchemaReferenceIdentityError(self.kind, self.identity)


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
class BundledOrigin:
    """Stable identity for a schema shipped with Lorecraft, without a fabricated path.

    Attributes:
        identity: The built-in identity, which must match the schema reference identity and be non-empty.
            Empty values raise `EmptyBundledOriginIdentityError`.
    """

    identity: str

    def __post_init__(self) -> None:
        """Reject an empty bundled identity.

        Raises:
            EmptyBundledOriginIdentityError: If `identity` is empty.
        """
        if not self.identity:
            raise EmptyBundledOriginIdentityError(self.identity)


type SchemaOrigin = RepositoryOrigin | BundledOrigin


class SchemaOriginMismatchError(Error):
    """A bundled origin identity differs from its schema reference identity.

    Attributes:
        reference: The schema reference whose bundled origin is inconsistent.
        origin: The bundled origin whose identity differs from the reference.
    """

    reference: SchemaReference
    origin: SchemaOrigin

    def __init__(self, reference: SchemaReference, origin: SchemaOrigin) -> None:
        self.reference = reference
        self.origin = origin
        super().__init__(f'origin does not match schema reference {reference.kind.value}:{reference.identity}')


@dataclass(frozen=True, slots=True)
class SchemaInput:
    """An immutable schema document and its typed identity and provenance.

    A bundled input's payload for validator-backed entries remains an open question for the skills-floor part.

    Attributes:
        reference: The typed schema identity.
        origin: Repository or bundled provenance, independent of schema kind; bundled identity must match
            the reference identity or `SchemaOriginMismatchError` is raised.
        document: The immutable JSON mapping used by schema-backed entries.
    """

    reference: SchemaReference
    origin: SchemaOrigin
    document: FrozenMapping[str, Frozen]

    def __post_init__(self) -> None:
        """Keep bundled provenance tied to its schema reference.

        Raises:
            SchemaOriginMismatchError: If bundled origin identity differs from the reference identity.
        """
        if isinstance(self.origin, BundledOrigin) and self.origin.identity != self.reference.identity:
            raise SchemaOriginMismatchError(self.reference, self.origin)
