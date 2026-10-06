"""Establish the workspace root: the directory whose `docs/__meta__/` the checks read.

Two ways in. An explicit `--root` is resolved and required to be a directory; without one, the nearest of
the working directory and its parents holding `docs/__meta__/` is the root. `establish_root` takes either.
Either way the result is an absolute path with symlinks followed, and it is the only `Path` a command keeps:
everything below reads root-relative through `FileSystem`.
"""

from pathlib import Path

from lorecraft.core.error import Error
from lorecraft.project.layout import SPECS_DIR
from lorecraft.vfs import OsRefusal, disk_location


class WorkingDirectoryReadError(Error):
    """The current working directory cannot be read, so no root can be searched for from it.

    That happens, for one, after the directory was deleted.

    Attributes:
        refusal: Why the operating system refused to report it.
        source: The operating system's failure.
    """

    refusal: OsRefusal
    source: OSError

    def __init__(self, refusal: OsRefusal, *, source: OSError) -> None:
        self.refusal = refusal
        self.source = source
        super().__init__(f'cannot read the current directory: {refusal.value}')
        self.__cause__ = source


class RootNotFoundError(Error):
    """Neither `start` nor any of its parents holds `docs/__meta__/`.

    Attributes:
        start: The directory the search began at, as given.
    """

    start: Path

    def __init__(self, start: Path) -> None:
        self.start = start
        super().__init__('cannot find repository root: no parent contains docs/__meta__/')


class RootCandidateInspectError(Error):
    """A directory on the way up from the start cannot be inspected for `docs/__meta__/`.

    Attributes:
        candidate: The directory whose `docs/__meta__/` could not be inspected.
        refusal: Why the operating system refused the inspection.
        source: The operating system's failure.
    """

    candidate: Path
    refusal: OsRefusal
    source: OSError

    def __init__(self, candidate: Path, refusal: OsRefusal, *, source: OSError) -> None:
        self.candidate = candidate
        self.refusal = refusal
        self.source = source
        super().__init__(f'cannot find repository root: cannot inspect {candidate}: {refusal.value}')
        self.__cause__ = source


class InvalidRootError(Error):
    """An explicit root is not an existing directory.

    Attributes:
        path: The rejected root, resolved.
    """

    path: Path

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f'{path} is not an existing directory')


class RootInspectError(Error):
    """An explicit root cannot be inspected to learn whether it is a directory.

    Attributes:
        path: The root, resolved.
        refusal: Why the operating system refused the inspection.
        source: The operating system's failure.
    """

    path: Path
    refusal: OsRefusal
    source: OSError

    def __init__(self, path: Path, refusal: OsRefusal, *, source: OSError) -> None:
        self.path = path
        self.refusal = refusal
        self.source = source
        super().__init__(f'cannot inspect root {path}: {refusal.value}')
        self.__cause__ = source


def get_root(start: Path) -> Path:
    """The first of `start` and its parents holding `docs/__meta__/` as a directory, resolved.

    Args:
        start: Directory the search begins at, then climbs from. A relative path is resolved first.

    Raises:
        RootNotFoundError: If no directory from `start` upward holds `docs/__meta__/`.
        RootCandidateInspectError: If the operating system refuses to inspect a directory on the way up.
    """
    # A relative start has parents that stop at `.`, so resolve first to climb the resolved directory tree.
    resolved = start.resolve()
    for candidate in (resolved, *resolved.parents):
        try:
            holds_specs = disk_location(candidate, SPECS_DIR).is_dir()
        except OSError as exc:
            # Through Python 3.13, `is_dir` answers False only for ENOENT, ENOTDIR, EBADF and ELOOP and raises any
            # other failure, a PermissionError under an unsearchable parent for one; 3.14 answers False for every
            # failure. Raised here, it is a failure of this search, not a bare OSError for the command.
            raise RootCandidateInspectError(candidate, OsRefusal.from_error(exc), source=exc) from exc
        if holds_specs:
            return candidate
    raise RootNotFoundError(start)


def resolve_root(path: Path) -> Path:
    """Resolve an explicit root (symlinks followed) and require it to be a directory.

    Args:
        path: The root as given, such as the `--root` option. Symlinks are followed; it need not be absolute.

    Raises:
        InvalidRootError: If the resolved path is not an existing directory.
        RootInspectError: If the operating system refuses to inspect it.
    """
    resolved = path.resolve()
    try:
        is_directory = resolved.is_dir()
    except OSError as exc:
        # As in `get_root`: through Python 3.13 `is_dir` raises a failure other than absence, where 3.14 answers False.
        raise RootInspectError(resolved, OsRefusal.from_error(exc), source=exc) from exc
    if not is_directory:
        raise InvalidRootError(resolved)
    return resolved


def establish_root(root: Path | None) -> Path:
    """The root a command reads: the one given, resolved, or the nearest found upward from the working directory.

    Args:
        root: The `--root` option; `None` searches upward from the working directory.

    Raises:
        WorkingDirectoryReadError: If no root is given and the working directory cannot be read.
        RootNotFoundError: If no root is given and no directory upward holds docs/__meta__/.
        RootCandidateInspectError: If no root is given and a directory upward cannot be inspected.
        InvalidRootError: If the given root is not an existing directory.
        RootInspectError: If the given root cannot be inspected.
    """
    if root is not None:
        return resolve_root(root)
    try:
        working_directory = Path.cwd()
    except OSError as exc:
        # The operating system cannot report a deleted working directory, for one.
        raise WorkingDirectoryReadError(OsRefusal.from_error(exc), source=exc) from exc
    return get_root(working_directory)
