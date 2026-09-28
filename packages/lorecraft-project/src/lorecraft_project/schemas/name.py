"""Specification stems: the part of a specification filename that names what it governs.

A stem on disk takes one of three forms:

- ``<corpus>``, a corpus spec;
- ``<corpus>-<namespace>``, a namespace spec narrowing it. The corpus token ends at the first hyphen because a
  corpus name never contains one; everything after it is one namespace, however many hyphens it carries;
- ``<corpus>.<type>``, a type selector: the structure layer for documents whose frontmatter ``type`` is
  ``<type>``. The corpus token ends at the first dot; everything after it is the type.

The first two are a ``SchemaName``, the third a ``TypeSelectorName``.
"""

from dataclasses import dataclass
from typing import Self

from lorecraft_project.aspect import AspectName, AspectNamespace
from lorecraft_project.corpus import CorpusName

type SchemaName = tuple[CorpusName] | tuple[CorpusName, AspectNamespace]


def parse_schema_name(stem: str) -> SchemaName:
    """Read the token before the first hyphen as the corpus and the rest as one namespace.

    Raises:
        CorpusNameError: If the corpus token is invalid.
        AspectNamespaceError: If the namespace token is invalid.
    """
    corpus_token, separator, namespace_token = stem.partition('-')
    corpus = CorpusName.parse(corpus_token)
    if not separator:
        return (corpus,)
    return (corpus, AspectNamespace.parse(namespace_token))


def schema_name_stem(name: SchemaName) -> str:
    """Join the parts back into the on-disk stem; never raises."""
    if len(name) == 1:
        return str(name[0])
    return f'{name[0]}-{name[1]}'


@dataclass(frozen=True, slots=True)
class TypeSelectorName:
    """A ``<corpus>.<type>`` stem, such as ``feat.component``.

    Each part is validated by its own type, so the pair carries no check of its own.

    Attributes:
        corpus: The corpus it narrows.
        document_type: The frontmatter ``type`` value it selects on.
    """

    corpus: CorpusName
    document_type: AspectName

    @classmethod
    def parse(cls, stem: str) -> Self:
        """Read the token before the first dot as the corpus and the rest as the document type.

        Raises:
            CorpusNameError: If the corpus token is invalid.
            AspectNameError: If the type token is invalid, including a stem with no dot at all.
        """
        corpus_token, _, type_token = stem.partition('.')
        return cls(CorpusName.parse(corpus_token), AspectName.parse(type_token))

    def __str__(self) -> str:
        return f'{self.corpus}.{self.document_type}'
