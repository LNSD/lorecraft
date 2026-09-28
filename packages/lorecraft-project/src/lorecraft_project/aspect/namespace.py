"""Validated namespaces shared by document names."""

from dataclasses import dataclass
from string import ascii_lowercase, digits
from typing import Self

from lorecraft_core.error import Error


class AspectNamespaceError(Error):
    """A namespace does not satisfy its format."""

    namespace: str


class EmptyAspectNamespaceError(AspectNamespaceError):
    """A namespace is empty."""

    def __init__(self) -> None:
        self.namespace = ''
        super().__init__('namespace cannot be empty')


class InvalidAspectNamespaceCharacterError(AspectNamespaceError):
    """A namespace contains a character outside its format."""

    position: int
    character: str

    def __init__(self, namespace: str, position: int) -> None:
        self.namespace = namespace
        self.position = position
        self.character = namespace[position]
        super().__init__(f'invalid character {self.character!r} in namespace {namespace!r}')


@dataclass(frozen=True, slots=True)
class AspectNamespace:
    """A validated, possibly nested kebab-case namespace.

    A namespace matches ``[a-z][a-z0-9]*(?:-[a-z0-9]+)*``. It may contain any number of
    lowercase ASCII words, separated by single hyphens. A namespace matches a document name
    when the name is equal to it or begins with it followed by a hyphen.

    Attributes:
        value: The validated namespace, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated namespace.

        Raises:
            AspectNamespaceError: If the namespace is empty or is not kebab case.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing namespace validation."""
        _validate_namespace(self.value)

    def matches(self, document_name: str) -> bool:
        """Return whether this namespace is the whole name or its hyphen-delimited prefix."""
        return document_name == self.value or document_name.startswith(f'{self.value}-')

    def __str__(self) -> str:
        return self.value


def _validate_namespace(namespace: str) -> None:
    if not namespace:
        raise EmptyAspectNamespaceError()
    if namespace[0] not in ascii_lowercase:
        raise InvalidAspectNamespaceCharacterError(namespace, 0)

    previous_was_hyphen = False
    for position, character in enumerate(namespace[1:], start=1):
        if character == '-':
            if previous_was_hyphen:
                raise InvalidAspectNamespaceCharacterError(namespace, position)
            previous_was_hyphen = True
        elif character in ascii_lowercase or character in digits:
            previous_was_hyphen = False
        else:
            raise InvalidAspectNamespaceCharacterError(namespace, position)

    if previous_was_hyphen:
        raise InvalidAspectNamespaceCharacterError(namespace, len(namespace) - 1)
