"""Where each relative link of a Markdown file leads, and what the snapshot holds there.

A relative link is read from a directory that depends on the file. In a file of a skill, the Agent Skills
specification reads it from the skill root, the skill directory where an agent reaches it, whichever file holds it. In
a document, it is read from the document's own directory, as Markdown renders it. `LinkBase` states which.

`find_link_targets` joins each link's relative path to that directory and looks the result up through a view: present,
missing, or in a directory the scan never read, so the snapshot cannot tell. Each entry keeps the root-relative path
it joined beside the lookup, so a reader says where a link really leads. It is a fact of the revision, never a
judgment: whether a missing target makes a link broken is a rule's to decide. A link spelling no relative path has no
entry, and neither has one that climbs past its bound: above the skill root in a file of a skill, which names nothing
the skill carries once it is installed elsewhere, or above the repository root in a document, which names nothing the
snapshot can hold.
"""

import posixpath
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import assert_never

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import RootRelativePath
from lorecraft.vfs import ScopeIndex, VirtualFileSystem

from .syntax import Link


@dataclass(frozen=True, slots=True)
class SkillRoot:
    """A file of a skill, whose relative links the Agent Skills specification reads from the skill root.

    A link names a file of the skill by its path from the root, whichever file holds it, so a link that climbs above
    the root names nothing the skill carries once it is installed elsewhere.

    Attributes:
        directory: The skill directory where an agent reaches it, never where a link there leads.
    """

    directory: RootRelativePath


@dataclass(frozen=True, slots=True)
class DocumentDirectory:
    """A document, whose relative links are read from the directory holding it, as Markdown renders them.

    Attributes:
        directory: The directory holding the document, such as `docs/guide`.
    """

    directory: RootRelativePath


# Where a Markdown file's relative links are read from: a skill's root, or a document's own directory. A union of two
# records rather than one with a flag, since the two differ in how far a link may climb and what it may name.
type LinkBase = SkillRoot | DocumentDirectory


class PathLookup(Enum):
    """What the snapshot holds at a root-relative path."""

    PRESENT = 'present'
    """A file or a directory the snapshot holds, reached through any symlink on the way."""
    MISSING = 'missing'
    """Nothing the snapshot holds, in a directory the scan read: no entry, or a symlink that dangles or leads to
    nothing it holds."""
    OUTSIDE_SCOPE = 'outside scope'
    """A path in a directory the scan never read, so the snapshot cannot tell what is there."""


@dataclass(frozen=True, slots=True)
class LinkTarget:
    """Where a relative link leads, read from its base, and what the snapshot holds there.

    Attributes:
        path: The root-relative path the link names once joined to its base, which differs from the path as written
            when the link is read from a directory other than its own file's.
        lookup: What the snapshot holds at `path`.
    """

    path: RootRelativePath
    lookup: PathLookup


def find_link_targets(
    links: tuple[Link, ...], base: LinkBase, view: VirtualFileSystem, scope: ScopeIndex
) -> Mapping[PurePosixPath, LinkTarget]:
    """Where each relative link leads and what the snapshot holds there, keyed by its normalised path. Raises nothing.

    The key is `Link.to_normalised_relative_path`'s, so a reader finds a link's entry from the link alone: two links
    spelling one path share an entry. A link spelling no relative path, or climbing past its bound, has none.

    Args:
        links: Every link and image of one Markdown file, as its parse tree holds them.
        base: Where the file's relative links are read from.
        view: The snapshot's view each target is looked up through, every recorded link on the way followed.
        scope: The scope the snapshot was taken of, which tells a path the scan never read.
    """
    targets: dict[PurePosixPath, LinkTarget] = {}
    for link in links:
        normalised = link.to_normalised_relative_path()
        if normalised is None:
            continue
        path = _joined_path(normalised, base)
        if path is None:
            continue
        targets[normalised] = LinkTarget(path=path, lookup=_look_up(path, view, scope))
    return FrozenMapping(targets)


def _joined_path(normalised: PurePosixPath, base: LinkBase) -> RootRelativePath | None:
    """The root-relative path a link's normalised relative path names, read from the base, or `None` past its bound.

    The path was normalised lexically, so a `..` cancels the component written before it, never one a symlink there
    would lead to.

    Args:
        normalised: The link's relative path, as `Link.to_normalised_relative_path` returns it.
        base: Where the file's relative links are read from.
    """
    match base:
        case SkillRoot():
            # Climbing above the skill root names nothing the skill carries once it is installed elsewhere.
            if _climbs_above(normalised):
                return None
            return base.directory / str(normalised)
        case DocumentDirectory():
            # Joined before normalising again, so a `..` may climb out of the document's directory, as Markdown
            # renders it, but a path climbing above the repository root names nothing the snapshot can hold.
            joined = PurePosixPath(posixpath.normpath(f'{base.directory}/{normalised}'))
            if _climbs_above(joined):
                return None
            return RootRelativePath(joined)
        case _:
            assert_never(base)


def _climbs_above(normalised: PurePosixPath) -> bool:
    """Whether a lexically normalised relative path climbs above the directory it is read from.

    Normalising leaves a `..` only at the start, so the first component alone decides.

    Args:
        normalised: A relative path with every `.` and every `..` it can cancel resolved.
    """
    # A slice, not `parts[0]`: the directory itself normalises to `.`, whose `parts` is empty.
    return normalised.parts[:1] == ('..',)


def _look_up(path: RootRelativePath, view: VirtualFileSystem, scope: ScopeIndex) -> PathLookup:
    """What the snapshot holds at a path, or that the scan never read the directory it sits in.

    Args:
        path: The path to look up, relative to the repository root.
        view: The view the path is looked up through.
        scope: The scope the snapshot was taken of.
    """
    # Scope first: a path in a directory the scan never read holds nothing in the snapshot whatever is on disk, so
    # the view alone would call it missing.
    if not scope.is_in_scope(path):
        return PathLookup.OUTSIDE_SCOPE
    if view.find_dir(path) is None and view.find_file(path) is None:
        return PathLookup.MISSING
    return PathLookup.PRESENT
