"""Validate the repository files a skill links in through its frontmatter ``metadata``.

A skill installed into other repositories has no file of this one beside it, so it depends on a repository file by
listing it under a ``metadata`` subkey: ``references``, ``scripts`` or ``assets``, each a whitespace-separated list
of root-relative paths. Writing such a list is the skill choosing that convention; a skill without one is not
checked here. A listed file is linked into the skill directory the subkey names, under its file name alone:
``references: docs/code/logging.md`` is ``references/logging.md`` in the skill. So two paths under one subkey may
not share a file name.

This module is the home of the skill's ``metadata`` rules. The check is pure: it takes the skill's frontmatter and
returns violations. It is the sibling of the frontmatter half in ``skill``, and reports in the same
``SkillCheckResult``.
"""

from pathlib import PurePosixPath
from typing import Final

from lorecraft.project.syntax import Frontmatter

from .frontmatter_problem import field_line
from .reporting import Violation
from .skill import SkillCheckResult

_LINKED_SUBKEYS: Final[tuple[str, ...]] = ('references', 'scripts', 'assets')
"""The ``metadata`` subkeys that link a repository file in, each named after the skill directory it lands in."""


def validate_skill_metadata(*, frontmatter: Frontmatter) -> SkillCheckResult:
    """Check the files a skill lists under ``metadata``, subkey by subkey. Pure: raises nothing.

    Every violation is on the line of the ``metadata`` key, the one line the frontmatter records for the whole
    mapping. A path whose file name an earlier path under the same subkey already has is
    ``skill.metadata-duplicate-name``, naming both: they would link in at the same path. Each later repeat is
    reported against the first, in the order written. The same name under two subkeys lands in two skill
    directories, so it is not one.

    A ``metadata`` that is not a mapping, or a subkey whose value is not a string, is not checked here: the Agent
    Skills specification reports either.

    Args:
        frontmatter: The frontmatter of any skill's ``SKILL.md``; one whose ``metadata`` lists no file has no
            violation.
    """
    line = field_line(frontmatter, 'metadata')
    violations: list[Violation] = []
    for subkey, written_paths in _listed_by_subkey(frontmatter):
        for first, repeat in _repeated_names(written_paths):
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
    return SkillCheckResult(violations=tuple(violations))


def _repeated_names(written_paths: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    """Each path whose file name an earlier path already has, as ``(first, repeat)``, in the order written.

    ``first`` is the earliest path with that file name, so every later repeat is paired with the same one.
    """
    first_by_name: dict[str, str] = {}
    repeats: list[tuple[str, str]] = []
    for written in written_paths:
        file_name = PurePosixPath(written).name
        first = first_by_name.get(file_name)
        if first is None:
            first_by_name[file_name] = written
        else:
            repeats.append((first, written))
    return tuple(repeats)


def _listed_by_subkey(frontmatter: Frontmatter) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Each linking subkey written as a string, with the paths it lists in the order written.

    The one place the ``metadata`` convention is read.
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
