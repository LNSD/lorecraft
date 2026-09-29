"""Specification stems: the part of a specification filename that names what it governs.

A stem on disk takes one of two forms, both a ``SchemaName``:

- ``<corpus>``, a corpus spec;
- ``<corpus>-<namespace>``, a namespace spec narrowing it. The corpus token ends at the first hyphen because a
  corpus name never contains one; everything after it is one namespace, however many hyphens it carries.
"""

from lorecraft.project.aspect import AspectNamespace
from lorecraft.project.corpus import CorpusName

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
    return corpus, AspectNamespace.parse(namespace_token)


def schema_name_stem(name: SchemaName) -> str:
    """Join the parts back into the on-disk stem; never raises."""
    if len(name) == 1:
        return str(name[0])
    return f'{name[0]}-{name[1]}'
