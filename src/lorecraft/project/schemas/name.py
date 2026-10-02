"""Specification names: the part of a specification filename that names what it governs.

A specification name on disk takes one of two forms, together a `SpecName`:

- `<corpus>`, a `CorpusSpecName`, naming a corpus spec;
- `<corpus>-<namespace>`, a `NamespaceSpecName`, naming a namespace spec narrowing it. The corpus token ends
  at the first hyphen because a corpus name never contains one; everything after it is one namespace, however
  many hyphens it carries.
"""

from dataclasses import dataclass

from lorecraft.project.aspect import AspectNamespace
from lorecraft.project.corpus import CorpusName


@dataclass(frozen=True, slots=True)
class CorpusSpecName:
    """The name of a corpus spec, `<corpus>`, such as `code`.

    Attributes:
        corpus: The corpus the spec governs every document of.
    """

    corpus: CorpusName

    def __str__(self) -> str:
        """The name as the specification filenames spell it before their pattern's suffix: the corpus alone."""
        return str(self.corpus)


@dataclass(frozen=True, slots=True)
class NamespaceSpecName:
    """The name of a namespace spec, `<corpus>-<namespace>`, such as `code-python`.

    Attributes:
        corpus: The corpus whose spec this one narrows.
        namespace: The namespace whose documents the spec governs, however many hyphens it carries.
    """

    corpus: CorpusName
    namespace: AspectNamespace

    def __str__(self) -> str:
        """The name as the specification filenames spell it before their pattern's suffix: corpus, hyphen, namespace."""
        return f'{self.corpus}-{self.namespace}'


type SpecName = CorpusSpecName | NamespaceSpecName


def parse_spec_name(raw: str) -> SpecName:
    """Read the token before the first hyphen as the corpus and the rest as one namespace.

    Args:
        raw: Specification filename with its file type's pattern suffix stripped, such as `code` or `code-python`.

    Raises:
        EmptyCorpusNameError: If the corpus token is empty.
        InvalidCorpusNameCharacterError: If a character of the corpus token falls outside lowercase snake case.
        EmptyAspectNamespaceError: If a hyphen is followed by no namespace.
        InvalidAspectNamespaceCharacterError: If a character of the namespace token falls outside kebab case.
    """
    corpus_token, separator, namespace_token = raw.partition('-')
    corpus = CorpusName.parse(corpus_token)
    if not separator:
        return CorpusSpecName(corpus)
    return NamespaceSpecName(corpus, AspectNamespace.parse(namespace_token))
