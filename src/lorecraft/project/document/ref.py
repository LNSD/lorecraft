"""A document's identity in the workspace model, separate from its content.

The model lists which documents exist; their text stays behind the document repository and is read on
demand. A `DocumentRef` is the key that ties the two together, and its `path` is the root-relative
location every finding reports.
"""

from dataclasses import dataclass

from lorecraft.core.error import Error
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.layout import DOCS_DIR, DOCUMENT_SUFFIX, SPECS_DIR
from lorecraft.project.schemas import (
    DottedSpecStemError,
    InvalidSpecStemError,
    NotASpecFileError,
    NotASpecStemError,
    UnknownSpecFileTypeError,
    parse_spec_file,
)


@dataclass(frozen=True, slots=True)
class DocumentRef:
    """A document's identity in the workspace model; carries no content.

    Attributes:
        corpus: The corpus directory name under docs/.
        filename: The Markdown filename stem; the frontmatter `name` must equal it.
    """

    corpus: CorpusName
    filename: AspectFilename

    @property
    def path(self) -> RootRelativePath:
        """Root-relative `docs/<corpus>/<filename>.md`; the report path in findings."""
        # A corpus name is validated snake case and a filename stem a validated aspect name, so both are components.
        return (
            DOCS_DIR / PathComponent.parse(str(self.corpus)) / PathComponent.parse(f'{self.filename}{DOCUMENT_SUFFIX}')
        )


class MisplacedSpecificationError(Error):
    """A path is no Markdown file directly inside the specification directory, so it names no specification.

    Attributes:
        path: Root-relative path that was refused.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'{path} is no Markdown file directly inside {SPECS_DIR}')


type ParseSpecFileError = (
    NotASpecFileError | UnknownSpecFileTypeError | NotASpecStemError | DottedSpecStemError | InvalidSpecStemError
)
"""Every way `parse_spec_file` refuses the name of a file."""


class InvalidSpecificationNameError(Error):
    """A Markdown file of the specification directory has a name no specification can take.

    Attributes:
        path: Root-relative path that was refused, such as `docs/__meta__/README.md`.
        source: Why the specification filename parser refuses the name.
    """

    path: RootRelativePath
    source: ParseSpecFileError

    def __init__(self, path: RootRelativePath, *, source: ParseSpecFileError) -> None:
        self.path = path
        self.source = source
        super().__init__(f'{path} is no specification name')
        self.__cause__ = source


@dataclass(frozen=True, slots=True, order=True)
class SpecRef:
    """A meta specification's identity in the workspace model: a Markdown file of `docs/__meta__/`.

    Attributes:
        path: Root-relative `docs/__meta__/<specification name>.md`; the report path in findings.
    """

    path: RootRelativePath

    def __post_init__(self) -> None:
        """Refuse a path that is no prose specification directly inside `docs/__meta__/`.

        The filename is held to the one parser of specification filenames, so `README.md` or `code.bad.md` is no
        specification here, as it is none to the model.

        Raises:
            MisplacedSpecificationError: If the path is elsewhere or is not a `.md` file.
            InvalidSpecificationNameError: If the file's name is no specification name.
        """
        if self.path.parent != SPECS_DIR or not self.path.value.name.endswith(DOCUMENT_SUFFIX):
            raise MisplacedSpecificationError(self.path)
        try:
            parse_spec_file(self.path)
        except (
            NotASpecFileError,
            UnknownSpecFileTypeError,
            NotASpecStemError,
            DottedSpecStemError,
            InvalidSpecStemError,
        ) as exc:
            raise InvalidSpecificationNameError(self.path, source=exc) from exc

    @property
    def name(self) -> str:
        """The specification name: the file's stem, such as `feat-cli`."""
        return self.path.value.name.removesuffix(DOCUMENT_SUFFIX)

    @property
    def corpus(self) -> str:
        """The corpus the specification belongs to: the first hyphen-delimited segment of its name."""
        return self.name.split('-', 1)[0]
