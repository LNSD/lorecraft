"""A directory under docs/ that takes a reserved corpus's name, as the workspace model sets it aside."""

from dataclasses import dataclass

from lorecraft.core.path import RootRelativePath

from .name import CorpusName


@dataclass(frozen=True, slots=True, order=True)
class ReservedCorpusDirectoryRef:
    """The path identifying one reserved-corpus directory subject in the workspace model.

    Attributes:
        path: Root-relative path of the directory, also used in reports.
    """

    path: RootRelativePath


# order=True so a collection of directories sorts by path, as the root-relative paths they wrap do.
@dataclass(frozen=True, slots=True, order=True)
class ReservedCorpusDirectory:
    """One directory directly under `docs/` named like a reserved corpus, such as `docs/skills/`.

    The model ignores it: none of the documents inside is listed.

    Attributes:
        path: The directory, root-relative, where the layout reports it.
        corpus: The reserved corpus whose name the directory takes.
    """

    path: RootRelativePath
    corpus: CorpusName
