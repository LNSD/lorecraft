"""The specification filename grammar: the specification name a file sits at, and the file type that claims it.

A file's extension is what follows its last dot. What a specification file is comes from its file type, which a
file name pattern claims: `*.md` claims the prose of a specification, and `*.structure.json` its structure
specification, the machine-checkable rules, which also hold the frontmatter schema. A `<name>.<token>.json` that
no pattern claims, such as a `header` file where that schema was once kept, is of no file type and is left out.
The specification name is what is left of the filename once the pattern's suffix is stripped: one of the two forms
`name.py` describes, and it holds no dot. Until it parses, that text is only the filename's stem, which is what
the errors below carry.

`parse_spec_file` is the one place this grammar is read, and `spec_filename` the only place it is written.
Every other module takes the parsed records.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final, assert_never

from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import EmptyAspectNamespaceError, InvalidAspectNamespaceCharacterError
from lorecraft.project.corpus import CorpusName, EmptyCorpusNameError, InvalidCorpusNameCharacterError

from .name import SpecName, parse_spec_name

_JSON_SUFFIX: Final[str] = '.json'


class SpecFileType(Enum):
    """What a specification file is; the value is the file name pattern that claims it."""

    PROSE = '*.md'
    """The specification in prose, written for a reader."""
    STRUCTURE = '*.structure.json'
    """The structure specification: the rules a check can decide, the frontmatter schema among them."""

    @property
    def suffix(self) -> str:
        """What a filename this type claims ends with: the pattern without its leading `*`."""
        return self.value.removeprefix('*')


@dataclass(frozen=True, slots=True)
class SpecFile:
    """A file at a `<corpus>` or `<corpus>-<namespace>` specification name.

    Attributes:
        path: Root-relative path of the file.
        name: The specification name, parsed.
        type: The file type whose pattern claims the filename.
    """

    path: RootRelativePath
    name: SpecName
    type: SpecFileType

    @property
    def corpus(self) -> CorpusName:
        """The corpus this file's specification name belongs to."""
        return self.name.corpus


class NotASpecFileError(Error):
    """No file type's pattern claims the filename at a non-empty stem, and it is not a `<stem>.<token>.json` either.

    Attributes:
        path: Root-relative path of the rejected file.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'{path}: no file type claims it at a stem; the patterns are {_pattern_list()}')


class UnknownSpecFileTypeError(Error):
    """No specification file type claims a `<stem>.<token>.json` file.

    Attributes:
        path: Root-relative path of the rejected file.
        token: The text between the stem and `.json`, such as `header`.
    """

    path: RootRelativePath
    token: str

    def __init__(self, path: RootRelativePath, token: str) -> None:
        self.path = path
        self.token = token
        super().__init__(f'{path}: no file type claims *.{token}.json; the patterns are {_pattern_list()}')


class NotASpecStemError(Error):
    """A prose file whose stem does not start with a corpus name, such as `README.md`.

    It is prose kept beside the specifications, not a misnamed specification.

    Attributes:
        path: Root-relative path of the prose file.
        source: Why the stem's first token is not a corpus name.
    """

    path: RootRelativePath
    source: EmptyCorpusNameError | InvalidCorpusNameCharacterError

    def __init__(
        self, path: RootRelativePath, *, source: EmptyCorpusNameError | InvalidCorpusNameCharacterError
    ) -> None:
        self.path = path
        self.source = source
        super().__init__(f'{path} is not at a specification name')
        self.__cause__ = source


class DottedSpecStemError(Error):
    """A stem holds a dot, where a specification name is `<corpus>` or `<corpus>-<namespace>`.

    Attributes:
        path: Root-relative path of the rejected file.
        stem: The stem that holds the dot.
    """

    path: RootRelativePath
    stem: str

    def __init__(self, path: RootRelativePath, stem: str) -> None:
        self.path = path
        self.stem = stem
        super().__init__(f'{path}: stem {stem!r} holds a dot; a specification name is <corpus> or <corpus>-<namespace>')


class InvalidSpecStemError(Error):
    """A stem has the form of a specification name but a token that does not parse.

    Attributes:
        path: Root-relative path of the rejected file.
        source: Why the corpus or the namespace token does not parse.
    """

    path: RootRelativePath
    source: (
        EmptyCorpusNameError
        | InvalidCorpusNameCharacterError
        | EmptyAspectNamespaceError
        | InvalidAspectNamespaceCharacterError
    )

    def __init__(
        self,
        path: RootRelativePath,
        *,
        source: (
            EmptyCorpusNameError
            | InvalidCorpusNameCharacterError
            | EmptyAspectNamespaceError
            | InvalidAspectNamespaceCharacterError
        ),
    ) -> None:
        self.path = path
        self.source = source
        super().__init__(f'{path} is not at a valid specification name')
        self.__cause__ = source


def parse_spec_file(path: RootRelativePath) -> SpecFile:
    """Parse the filename of one file in the specification directory.

    The rules apply in order, and the first one broken selects the error: the filename shape, the file type, a
    dot left in the stem, then the stem's tokens.

    Args:
        path: Root-relative path of the file; only its name is parsed.

    Raises:
        NotASpecFileError: If no pattern claims the name at a non-empty stem and it is not `<stem>.<token>.json`.
        UnknownSpecFileTypeError: If no `SpecFileType` claims a `<stem>.<token>.json` name.
        NotASpecStemError: If a prose file's stem does not start with a valid corpus name.
        DottedSpecStemError: If the stem holds a dot.
        InvalidSpecStemError: If any other stem token does not parse.
    """
    stem, file_type = _split_filename(path)

    if '.' in stem:
        # `feat.component.structure.json` is not a name with a type in it: a specification name is `<corpus>` or
        # `<corpus>-<namespace>`, and the only dots in a specification filename are its pattern's.
        raise DottedSpecStemError(path, stem)

    try:
        name = parse_spec_name(stem)
    except (EmptyCorpusNameError, InvalidCorpusNameCharacterError) as exc:
        # A prose file whose first token is not a corpus name (README.md) is not a misnamed spec, it is simply
        # not a spec; a JSON file at such a stem can only be a misnaming.
        match file_type:
            case SpecFileType.PROSE:
                raise NotASpecStemError(path, source=exc) from exc
            case SpecFileType.STRUCTURE:
                raise InvalidSpecStemError(path, source=exc) from exc
            case _:
                assert_never(file_type)
    except (EmptyAspectNamespaceError, InvalidAspectNamespaceCharacterError) as exc:
        raise InvalidSpecStemError(path, source=exc) from exc
    return SpecFile(path=path, name=name, type=file_type)


def spec_filename(name: SpecName, file_type: SpecFileType) -> str:
    """The filename of one file type at a `<corpus>` or `<corpus>-<namespace>` specification name; never raises.

    Args:
        name: Specification name the filename starts with.
        file_type: Type whose pattern the filename matches, such as `*.structure.json`.
    """
    return f'{name}{file_type.suffix}'


def _split_filename(path: RootRelativePath) -> tuple[str, SpecFileType]:
    """Split a filename into its stem text and the file type whose pattern claims it.

    Args:
        path: Root-relative path of the file; only its final name is read, and `path` is carried into any error.

    Raises:
        NotASpecFileError: If no pattern claims the name at a non-empty stem and it is not `<stem>.<token>.json`.
        UnknownSpecFileTypeError: If no `SpecFileType` claims a `<stem>.<token>.json` name.
    """
    filename = path.name

    # The first type whose pattern matches claims the file, so no pattern's suffix may end another's: a `*.json`
    # declared before `*.structure.json` would claim every structure specification at a dotted stem.
    for file_type in SpecFileType:
        if filename.endswith(file_type.suffix):
            stem = filename.removesuffix(file_type.suffix)
            if not stem:
                raise NotASpecFileError(path)
            return stem, file_type

    if filename.endswith(_JSON_SUFFIX):
        # Split at the last dot before `.json`, so only the final token is the one no pattern claims; a name no
        # type claims is rejected here, before the caller looks for a dot left in its stem.
        stem, separator, token = filename.removesuffix(_JSON_SUFFIX).rpartition('.')
        if separator and stem and token:
            raise UnknownSpecFileTypeError(path, token)

    raise NotASpecFileError(path)


def _pattern_list() -> str:
    """Every file type's pattern, in declaration order, for an error message: `*.md, *.structure.json`."""
    return ', '.join(file_type.value for file_type in SpecFileType)
