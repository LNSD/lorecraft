"""Where each relative link of a Markdown file leads, and what the snapshot holds there.

A relative link is read from a directory that depends on the file. In a file of a skill, the Agent Skills
specification reads it from the skill root, the skill directory where an agent reaches it, whichever file holds it. In
a document, it is read from the document's own directory, as Markdown renders it. `LinkBase` states which.

`link_targets_of` joins each link's relative path to that directory and looks the result up through a view: a file, a
directory, missing, or in a directory the scan never read, so the snapshot cannot tell. Each entry keeps the
root-relative path
it joined beside the lookup, so a reader says where a link really leads. It is a fact of the revision, never a
judgment: whether a missing target makes a link broken is a rule's to decide. A link spelling no relative path has no
entry. One that climbs past its bound has an `EscapingTarget` instead of a `LinkTarget`: above the skill root in a
file of a skill, which names nothing the skill carries once it is installed elsewhere, or above the repository root in
a document, which names nothing the snapshot can hold.
"""

import posixpath
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, assert_never

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.layout import DOCUMENT_SUFFIX
from lorecraft.project.syntax import (
    AbsoluteDestination,
    ExternalDestination,
    FragmentDestination,
    LineNumber,
    Link,
    NormalisedLinkPath,
    RelativeDestination,
)
from lorecraft.vfs import FileSystem, ScopeIndex

if TYPE_CHECKING:
    # Avoid the project.schemas -> project.item -> project.link_target import cycle.
    from lorecraft.project.schemas import SpecName


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

    FILE = 'file'
    """A file the snapshot holds, reached through any symlink on the way."""
    DIRECTORY = 'directory'
    """A directory the snapshot holds, reached through any symlink on the way."""
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


@dataclass(frozen=True, slots=True)
class EscapingTarget:
    """A link that climbs past its bound, so it names no path of the snapshot.

    The bound is the skill root in a file of a skill and the repository root in a document, which only the base
    knows, so a link's destination alone cannot say it.
    """


# What a relative link leads to: a path the snapshot can be asked about, or none at all. A union of two records rather
# than one with a flag, so an escaping link can never carry a path or a lookup.
type LinkTargetEntry = LinkTarget | EscapingTarget


def link_targets_of(
    links: tuple[Link, ...], base: LinkBase, view: FileSystem, scope: ScopeIndex
) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
    """Where each relative link leads and what the snapshot holds there, keyed by its normalised path. Raises nothing.

    The key is the `NormalisedLinkPath` of the link's `RelativeDestination`, so a reader finds a link's entry from the
    link alone: two links spelling one path share an entry. A link spelling no relative path has none, and one
    climbing past its bound has an `EscapingTarget`.

    Args:
        links: Every link and image of one Markdown file, as its parse tree holds them.
        base: Where the file's relative links are read from.
        view: The snapshot's view each target is looked up through, every recorded link on the way followed.
        scope: The scope the snapshot was taken of, which tells a path the scan never read.
    """
    targets: dict[NormalisedLinkPath, LinkTargetEntry] = {}
    for link in links:
        destination = link.to_destination()
        match destination:
            case RelativeDestination():
                normalised = destination.path
            case ExternalDestination() | AbsoluteDestination() | FragmentDestination():
                continue
            case _:
                assert_never(destination)
        path = _joined_path(normalised.path, base)
        if path is None:
            targets[normalised] = EscapingTarget()
        else:
            targets[normalised] = LinkTarget(path=path, lookup=_look_up(path, view, scope))
    return FrozenMapping(targets)


def _joined_path(normalised: PurePosixPath, base: LinkBase) -> RootRelativePath | None:
    """The root-relative path a link's normalised relative path names, read from the base, or `None` past its bound.

    The path was normalised lexically, so a `..` cancels the component written before it, never one a symlink there
    would lead to.

    Args:
        normalised: The link's relative path, as its `NormalisedLinkPath` holds it.
        base: Where the file's relative links are read from.
    """
    match base:
        case SkillRoot():
            # Climbing above the skill root names nothing the skill carries once it is installed elsewhere. Lexical
            # on purpose, rather than a containment check of resolved paths: nothing here performs I/O, and the link
            # is text read from the skill root, not a filesystem path. The path alone decides, never joined to the
            # skill's directory first: a link that climbs out and back in by the repository's own path, such as
            # `../../skills/review/SKILL.md`, depends on where the skill is installed, so it escapes too.
            if _climbs_above(normalised):
                return None
            return base.directory / RootRelativePath(normalised)
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


def _look_up(path: RootRelativePath, view: FileSystem, scope: ScopeIndex) -> PathLookup:
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
    if view.find_dir(path) is not None:
        return PathLookup.DIRECTORY
    if view.find_file(path) is not None:
        return PathLookup.FILE
    return PathLookup.MISSING


@dataclass(frozen=True, slots=True)
class ExtensionLink:
    """A link from a document to an existing document in its directory that extends it.

    Attributes:
        line: The line the link is on.
        url: The link's destination as written.
        extension: The filename of the document it leads to, such as `guide-extra.md`.
    """

    line: LineNumber
    url: str
    extension: str


def extension_links_of(
    links: tuple[Link, ...],
    targets: Mapping[NormalisedLinkPath, LinkTargetEntry],
    base: LinkBase,
    filename: 'AspectFilename | SpecName',
) -> tuple[ExtensionLink, ...]:
    """The links to an existing Markdown file beside the document whose name starts with `<filename>-`. Raises nothing.

    A document in a skill has no such links: its relative links are read from the skill root.

    Args:
        links: The document's links, in document order.
        targets: Where each relative link leads, as `link_targets_of` returns it.
        base: Where the document's relative links are read from.
        filename: The typed filename stem of a document or specification.
    """
    if not isinstance(base, DocumentDirectory):
        return ()
    prefix = f'{filename}-'
    found: list[ExtensionLink] = []
    for link in links:
        destination = link.to_destination()
        if not isinstance(destination, RelativeDestination):
            continue
        entry = targets.get(destination.path)
        if not isinstance(entry, LinkTarget) or entry.lookup is not PathLookup.FILE:
            continue
        name = entry.path.name
        if entry.path.parent == base.directory and name is not None and name.has_suffix(DOCUMENT_SUFFIX):
            if str(name).startswith(prefix):
                found.append(ExtensionLink(line=link.line, url=link.url, extension=str(name)))
    return tuple(found)


@dataclass(frozen=True, slots=True)
class LinkedDocument:
    """A link from a document to an existing Markdown file in the `docs/` tree, to be read as a document.

    Attributes:
        line: The line the link is on.
        url: The link's destination as written.
        path: The root-relative path of the file it leads to.
    """

    line: LineNumber
    url: str
    path: RootRelativePath


def linked_files_of(
    links: tuple[Link, ...], targets: Mapping[NormalisedLinkPath, LinkTargetEntry], base: LinkBase
) -> tuple[LinkedDocument, ...]:
    """The links to an existing Markdown file, with the path each leads to. Raises nothing.

    A file in a skill has none: its relative links are read from the skill root, and no document is its destination.

    Args:
        links: The document's links, in document order.
        targets: Where each relative link leads, as `link_targets_of` returns it.
        base: Where the document's relative links are read from.
    """
    if not isinstance(base, DocumentDirectory):
        return ()
    found: list[LinkedDocument] = []
    for link in links:
        destination = link.to_destination()
        if not isinstance(destination, RelativeDestination):
            continue
        entry = targets.get(destination.path)
        if not isinstance(entry, LinkTarget) or entry.lookup is not PathLookup.FILE:
            continue
        name = entry.path.name
        if name is not None and name.has_suffix('.md'):
            found.append(LinkedDocument(line=link.line, url=link.url, path=entry.path))
    return tuple(found)


@dataclass(frozen=True, slots=True)
class DocumentLink:
    """A link from a document to another document of the `docs/<corpus>/<name>.md` layout.

    Attributes:
        line: The line the link is on.
        url: The link's destination as written.
        corpus: The typed corpus directory of the document it leads to.
        filename: The typed filename of the document it leads to, without its extension.
        has_back_link: Whether that document links to this one.
    """

    line: LineNumber
    url: str
    corpus: CorpusName
    filename: AspectFilename
    has_back_link: bool


def has_link_to(targets: Mapping[NormalisedLinkPath, LinkTargetEntry], path: RootRelativePath) -> bool:
    """Whether any relative link of a file leads to an existing file at a path.

    Args:
        targets: Where each relative link of the file leads, as `link_targets_of` returns it.
        path: The root-relative path to look for.
    """
    return any(
        isinstance(entry, LinkTarget) and entry.lookup is PathLookup.FILE and entry.path == path
        for entry in targets.values()
    )


def document_links_of(
    linked: tuple[LinkedDocument, ...],
    source: RootRelativePath,
    documents: Mapping[RootRelativePath, tuple[CorpusName, AspectFilename]],
    back_links: Mapping[RootRelativePath, bool],
) -> tuple[DocumentLink, ...]:
    """The links to another document of the `docs/<corpus>/<name>.md` layout, with its back link. Raises nothing.

    A link to the document itself, or to a file that is no such document, is left out.

    Args:
        linked: The links to an existing Markdown file, as `linked_files_of` returns them.
        source: The root-relative path of the document that holds the links.
        documents: The typed corpus and filename of each path that is a document of the layout.
        back_links: For each such path, whether that document links to the source.
    """
    return tuple(
        DocumentLink(
            line=link.line,
            url=link.url,
            corpus=documents[link.path][0],
            filename=documents[link.path][1],
            has_back_link=back_links.get(link.path, False),
        )
        for link in linked
        if link.path in documents and link.path != source
    )
