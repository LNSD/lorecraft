"""The specification filename grammar: the stem a file sits at, and the aspect it carries.

A specification file in ``docs/__meta__/`` is either ``<stem>.md``, the prose of a specification, or
``<stem>.<aspect>.json``, one machine-checkable aspect of it. The aspect is ``header``, ``structure`` or
``budget``. The stem is one of the three forms ``name.py`` describes, and a ``<corpus>.<type>`` stem carries the
structure aspect only.

``parse_spec_file`` is the one place this grammar is read, and ``schema_filename`` and
``type_selector_filename`` the one place it is written. Every other module takes the parsed records.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final

from lorecraft_core.error import Error
from lorecraft_project.aspect import AspectNameError, AspectNamespaceError
from lorecraft_project.corpus import CorpusName, CorpusNameError
from lorecraft_vfs import RootRelativePath

from .name import SchemaName, TypeSelectorName, parse_schema_name, schema_name_stem

_PROSE_SUFFIX: Final[str] = '.md'
_JSON_SUFFIX: Final[str] = '.json'


class SpecAspect(Enum):
    """The machine-checkable aspect a ``<stem>.<aspect>.json`` file carries; the value is the filename token."""

    HEADER = 'header'
    STRUCTURE = 'structure'
    BUDGET = 'budget'


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


@dataclass(frozen=True, slots=True)
class TypeSelectorFile:
    """A ``<corpus>.<type>.structure.json`` file.

    It has no aspect field: a type selector carries the structure aspect and no other, so the type says so.

    Attributes:
        path: Root-relative path of the file.
        name: The stem, parsed.
    """

    path: RootRelativePath
    name: TypeSelectorName

    @property
    def corpus(self) -> CorpusName:
        """The corpus this file's stem belongs to."""
        return self.name.corpus


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
        super().__init__(f'{path}: aspect {token!r} is not header, structure or budget')


class TypedAspectUnsupportedError(SpecFilenameError):
    """A ``<corpus>.<type>`` stem carries something other than the structure aspect."""

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'{path}: a <corpus>.<type> stem carries the structure aspect only')


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
        detail: The message of the corpus, namespace or type parser that rejected the token.
    """

    detail: str

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f'{path}: {detail}')


def parse_spec_file(path: RootRelativePath) -> SpecFile | TypeSelectorFile:
    """Parse the filename of one file in the specification directory.

    The rules apply in order, and the first one broken selects the error: the filename shape, the aspect
    token, a ``<corpus>.<type>`` stem on anything but structure, then the stem's tokens.

    Args:
        path: Root-relative path of the file; only its name is parsed.

    Raises:
        NotASpecFileError: If the name is neither ``<stem>.md`` nor ``<stem>.<token>.json``.
        UnknownSpecAspectError: If the JSON token is not a ``SpecAspect``.
        TypedAspectUnsupportedError: If a dotted stem is prose or carries a header or budget aspect.
        NotASpecStemError: If a prose file's stem does not start with a valid corpus name.
        InvalidSpecStemError: If any other stem token does not parse.
    """
    stem, aspect = _split_filename(path)

    if '.' in stem:
        # The dotted form alone makes a type selector, so the aspect is judged before the tokens are parsed.
        if aspect is not SpecAspect.STRUCTURE:
            raise TypedAspectUnsupportedError(path)
        try:
            return TypeSelectorFile(path=path, name=TypeSelectorName.parse(stem))
        except (CorpusNameError, AspectNameError) as exc:
            raise InvalidSpecStemError(path, str(exc)) from exc

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


def type_selector_filename(name: TypeSelectorName) -> str:
    """The filename of a type selector, which carries the structure aspect only; never raises."""
    return f'{name}.{SpecAspect.STRUCTURE.value}{_JSON_SUFFIX}'


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
        # `feat.feature.structure.json` splits at the last dot before the suffix: the stem keeps its own dot,
        # and only the final token is the aspect.
        stem, separator, token = filename.removesuffix(_JSON_SUFFIX).rpartition('.')
        if not separator or not stem or not token:
            raise NotASpecFileError(path)
        try:
            aspect = SpecAspect(token)
        except ValueError as exc:
            raise UnknownSpecAspectError(path, token) from exc
        return stem, aspect

    raise NotASpecFileError(path)
