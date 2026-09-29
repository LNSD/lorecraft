"""The specification filename grammar: the stem a file sits at, and the aspect it carries.

A specification file in ``docs/__meta__/`` is either ``<stem>.md``, the prose of a specification, or
``<stem>.<aspect>.json``, one machine-checkable aspect of it. The aspect is ``header`` or ``structure``. The
stem is one of the two forms ``name.py`` describes, and holds no dot.

``parse_spec_file`` is the one place this grammar is read, and ``schema_filename`` and ``prose_filename`` the
only places it is written. Every other module takes the parsed records.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final

from lorecraft.core.error import Error
from lorecraft.project.aspect import AspectNamespaceError
from lorecraft.project.corpus import CorpusName, CorpusNameError
from lorecraft.vfs import RootRelativePath

from .name import SchemaName, parse_schema_name, schema_name_stem

_PROSE_SUFFIX: Final[str] = '.md'
_JSON_SUFFIX: Final[str] = '.json'


class SpecAspect(Enum):
    """The machine-checkable aspect a ``<stem>.<aspect>.json`` file carries; the value is the filename token."""

    HEADER = 'header'
    STRUCTURE = 'structure'


@dataclass(frozen=True, slots=True)
class SpecFile:
    """A file at a ``<corpus>`` or ``<corpus>-<namespace>`` stem.

    Attributes:
        path: Root-relative path of the file.
        name: The stem, parsed.
        aspect: The aspect of a JSON file, or None for the ``.md`` prose.
    """

    path: RootRelativePath
    name: SchemaName
    aspect: SpecAspect | None

    @property
    def corpus(self) -> CorpusName:
        """The corpus this file's stem belongs to."""
        return self.name[0]


class SpecFilenameError(Error):
    """A file in the specification directory does not have a specification filename.

    Attributes:
        path: Root-relative path of the rejected file.
    """

    path: RootRelativePath


class NotASpecFileError(SpecFilenameError):
    """The filename is neither ``<stem>.md`` nor ``<stem>.<token>.json``."""

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'{path} is neither <stem>.md nor <stem>.<aspect>.json')


class UnknownSpecAspectError(SpecFilenameError):
    """The token of a ``<stem>.<token>.json`` file is not a known aspect.

    Attributes:
        token: The rejected token.
    """

    token: str

    def __init__(self, path: RootRelativePath, token: str) -> None:
        self.path = path
        self.token = token
        super().__init__(f'{path}: aspect {token!r} is not header or structure')


class NotASpecStemError(SpecFilenameError):
    """A prose file whose stem does not start with a corpus name, such as ``README.md``.

    It is prose kept beside the specifications, not a misnamed specification, so it carries no parser detail.
    """

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'{path} is not at a specification stem')


class InvalidSpecStemError(SpecFilenameError):
    """A stem has a specification form but a token that does not parse.

    Attributes:
        detail: Why the stem was rejected: the corpus or namespace parser's message, or the dot it holds.
    """

    detail: str

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f'{path}: {detail}')


def parse_spec_file(path: RootRelativePath) -> SpecFile:
    """Parse the filename of one file in the specification directory.

    The rules apply in order, and the first one broken selects the error: the filename shape, the aspect
    token, a dot left in the stem, then the stem's tokens.

    Args:
        path: Root-relative path of the file; only its name is parsed.

    Raises:
        NotASpecFileError: If the name is neither ``<stem>.md`` nor ``<stem>.<token>.json``.
        UnknownSpecAspectError: If the JSON token is not a ``SpecAspect``.
        NotASpecStemError: If a prose file's stem does not start with a valid corpus name.
        InvalidSpecStemError: If the stem holds a dot, or any other stem token does not parse.
    """
    stem, aspect = _split_filename(path)

    if '.' in stem:
        # `feat.component.structure.json` is not a stem with a type in it: a stem is `<corpus>` or
        # `<corpus>-<namespace>`, and the only dots in a specification filename set off the aspect and the suffix.
        raise InvalidSpecStemError(path, f'stem {stem!r} holds a dot; a stem is <corpus> or <corpus>-<namespace>')

    try:
        name = parse_schema_name(stem)
    except CorpusNameError as exc:
        # A prose file whose first token is not a corpus name (README.md) is not a misnamed spec, it is simply
        # not a spec; a JSON file at such a stem can only be a misnaming.
        if aspect is None:
            raise NotASpecStemError(path) from exc
        raise InvalidSpecStemError(path, str(exc)) from exc
    except AspectNamespaceError as exc:
        raise InvalidSpecStemError(path, str(exc)) from exc
    return SpecFile(path=path, name=name, aspect=aspect)


def schema_filename(name: SchemaName, aspect: SpecAspect) -> str:
    """The filename of one aspect at a ``<corpus>`` or ``<corpus>-<namespace>`` stem; never raises."""
    return f'{schema_name_stem(name)}.{aspect.value}{_JSON_SUFFIX}'


def prose_filename(name: SchemaName) -> str:
    """The filename of the prose at a ``<corpus>`` or ``<corpus>-<namespace>`` stem; never raises."""
    return f'{schema_name_stem(name)}{_PROSE_SUFFIX}'


def _split_filename(path: RootRelativePath) -> tuple[str, SpecAspect | None]:
    """Split a filename into its stem text and its aspect, None for prose.

    Raises:
        NotASpecFileError: If the name is neither ``<stem>.md`` nor ``<stem>.<token>.json``.
        UnknownSpecAspectError: If the JSON token is not a ``SpecAspect``.
    """
    filename = path.name

    if filename.endswith(_PROSE_SUFFIX):
        stem = filename.removesuffix(_PROSE_SUFFIX)
        if not stem:
            raise NotASpecFileError(path)
        return stem, None

    if filename.endswith(_JSON_SUFFIX):
        # Split at the last dot before the suffix, so only the final token is the aspect; a dot left in the stem
        # is rejected by the caller.
        stem, separator, token = filename.removesuffix(_JSON_SUFFIX).rpartition('.')
        if not separator or not stem or not token:
            raise NotASpecFileError(path)
        try:
            aspect = SpecAspect(token)
        except ValueError as exc:
            raise UnknownSpecAspectError(path, token) from exc
        return stem, aspect

    raise NotASpecFileError(path)
