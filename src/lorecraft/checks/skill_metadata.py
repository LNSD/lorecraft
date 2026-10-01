"""Validate the repository files a skill links in through its frontmatter ``metadata``.

A skill installed into other repositories has no file of this one beside it, so it depends on a repository file by
listing it under a ``metadata`` subkey: ``references``, ``scripts`` or ``assets``, each a whitespace-separated list
of root-relative paths. Writing such a list is the skill choosing that convention; a skill without one is not
checked here. A listed file is linked into the skill directory the subkey names, under its file name alone:
``references: docs/code/logging.md`` is ``references/logging.md`` in the skill. So two paths under one subkey may
not share a file name, and each must lie in what the snapshot read.

The check is pure: it takes the skill's frontmatter and the files it lists, each with what the snapshot can tell
about it, and returns violations. Reading the lists is ``listed_by_subkey``; locating each path in the snapshot
happens above the check, in ``checks.run``. It is the sibling of the frontmatter half in ``skill``, and reports in
the same ``SkillCheckResult``.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import Final, assert_never

from lorecraft.project.syntax import Frontmatter

from .frontmatter_problem import field_line
from .reporting import Violation
from .skill import SkillCheckResult

_LINKED_SUBKEYS: Final[tuple[str, ...]] = ('references', 'scripts', 'assets')
"""The ``metadata`` subkeys that link a repository file in, each named after the skill directory it lands in."""


class ListedFileState(Enum):
    """What the snapshot can tell about one path a skill lists under ``metadata``."""

    IN_SCOPE = 'in-scope'
    """A regular file the snapshot holds, reached through any link on the way, or a path in a directory it listed."""
    OUTSIDE_SCOPE = 'outside-scope'
    """Nothing the snapshot can tell about: the path is in a directory it never listed, or is not root-relative."""


@dataclass(frozen=True, slots=True)
class ListedFile:
    """One path a linking subkey lists, with what the snapshot can tell about it.

    Attributes:
        written: The path exactly as the subkey writes it, which is how a finding names it.
        state: Whether the snapshot read where the path leads.
    """

    written: str
    state: ListedFileState


@dataclass(frozen=True, slots=True)
class ListedFiles:
    """The files one linking subkey lists, each with its state.

    Attributes:
        subkey: ``references``, ``scripts`` or ``assets``: the skill directory the files land in.
        files: In the order written, a path written twice included twice.
    """

    subkey: str
    files: tuple[ListedFile, ...]


def listed_by_subkey(frontmatter: Frontmatter) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Each linking subkey written as a string, with the paths it lists in the order written.

    The one place the ``metadata`` convention is read. The subkeys come as references, then scripts, then assets,
    whatever order the mapping writes them in. A ``metadata`` that is not a mapping, or a subkey whose value is not
    a string, lists none: the Agent Skills specification already reports either.
    """
    metadata = frontmatter.data.get('metadata')
    if not isinstance(metadata, dict):
        return ()
    listed: list[tuple[str, tuple[str, ...]]] = []
    for subkey in _LINKED_SUBKEYS:
        value = metadata.get(subkey)
        if isinstance(value, str):
            listed.append((subkey, tuple(value.split())))
    return tuple(listed)


def validate_skill_metadata(*, frontmatter: Frontmatter, listed: tuple[ListedFiles, ...]) -> SkillCheckResult:
    """Check the files a skill lists under ``metadata``, subkey by subkey. Pure: raises nothing.

    Every violation is on the line of the ``metadata`` key, the one line the frontmatter records for the whole
    mapping. Within each subkey, the repeated names come first, then the paths outside the scope, each in the order
    written:

    - A path whose file name an earlier path under the same subkey already has is
      ``skill.metadata-duplicate-name``, naming both: they would link in at the same path. Each later repeat is
      reported against the first. The same name under two subkeys lands in two skill directories, so it is not one.
    - A path the snapshot never read is ``skill.metadata-outside-scope``, once for every time it is written.

    Args:
        frontmatter: The frontmatter of the skill's ``SKILL.md``, read here only for the line of its ``metadata``.
        listed: What ``listed_by_subkey`` reads from this frontmatter, each path with its state, in the same order;
            empty when the ``metadata`` lists no file.
    """
    line = field_line(frontmatter, 'metadata')
    violations: list[Violation] = []
    for subkey_files in listed:
        subkey = subkey_files.subkey
        for first, repeat in _repeated_names(subkey_files.files):
            violations.append(
                Violation(
                    line=line,
                    rule='skill.metadata-duplicate-name',
                    message=(
                        f'`metadata.{subkey}` lists `{first}` and `{repeat}`, '
                        f'which both link in as `{subkey}/{PurePosixPath(repeat).name}`'
                    ),
                )
            )
        for written in _outside_scope(subkey_files.files):
            violations.append(
                Violation(
                    line=line,
                    rule='skill.metadata-outside-scope',
                    message=(
                        f'`metadata.{subkey}` lists `{written}`, which lorecraft does not read; list a file directly '
                        f'in docs/, in a real directory directly in docs/, or directly in a skill directory'
                    ),
                )
            )
    return SkillCheckResult(violations=tuple(violations))


def _repeated_names(files: tuple[ListedFile, ...]) -> tuple[tuple[str, str], ...]:
    """Each path whose file name an earlier path already has, as ``(first, repeat)``, in the order written.

    ``first`` is the earliest path with that file name, so every later repeat is paired with the same one.
    """
    first_by_name: dict[str, str] = {}
    repeats: list[tuple[str, str]] = []
    for file in files:
        file_name = PurePosixPath(file.written).name
        first = first_by_name.get(file_name)
        if first is None:
            first_by_name[file_name] = file.written
        else:
            repeats.append((first, file.written))
    return tuple(repeats)


def _outside_scope(files: tuple[ListedFile, ...]) -> tuple[str, ...]:
    """Each path the snapshot never read, as written, in the order written; a path written twice comes twice."""
    outside: list[str] = []
    for file in files:
        state = file.state
        match state:
            case ListedFileState.IN_SCOPE:
                pass  # the snapshot read where the path leads
            case ListedFileState.OUTSIDE_SCOPE:
                outside.append(file.written)
            case _:
                assert_never(state)
    return tuple(outside)
