"""Validate the links in one skill's Markdown files: the home of the skill check's link rules.

A skill is loaded from wherever an agent keeps it, and the Agent Skills specification has it name its files by
paths relative to the skill root, in every Markdown file it carries: a link in `references/guide.md` to
`SKILL.md` is `SKILL.md`, not `../SKILL.md`. So a relative link that, read from the skill root, climbs above it
points at a file the skill does not carry once it is installed elsewhere, and is `skill.link-escapes`. One that
stays inside must name a file or a directory the skill holds, or a file its `metadata` links in, or it is
`skill.link-broken`; when the `metadata` cannot be read, which files it links in is unknown, and that rule is
not judged. A link that starts at a filesystem root points at a file the skill does not carry either, and is
`skill.link-absolute`. A fragment-only link, such as `#usage`, stays in the file that holds it, so the heading it
names must be one of that file's own, or it is `skill.link-fragment`. All four rules hold in the `SKILL.md` and in
each resource alike, so one validator checks the links of either.

The check is pure: it takes one file's links and the heading anchors its parse tree holds, what the snapshot holds at
each path inside the skill a link names, and the paths `metadata` links files in at, and returns violations.
Reading and parsing the files, and looking each path up in the snapshot, happen above it, in `checks.run` and the
database. It is the sibling of the frontmatter half in `skill`, and reports in the same `SkillCheckResult`.
"""

from collections.abc import Mapping
from enum import Enum
from pathlib import PurePosixPath
from typing import assert_never
from urllib.parse import unquote

from lorecraft.project.syntax import Anchor, Link

from .reporting import Note, NoteKind, Violation
from .skill import SkillCheckResult


class LinkTargetState(Enum):
    """What the snapshot holds at one path inside a skill that a link names."""

    PRESENT = 'present'
    """A file or a directory the snapshot holds, reached through any symlink on the way."""
    MISSING = 'missing'
    """Nothing the snapshot holds: no entry, or a symlink that dangles or leads to nothing it holds."""


def validate_skill_links(
    *,
    links: tuple[Link, ...],
    anchors: frozenset[Anchor],
    targets: Mapping[PurePosixPath, LinkTargetState],
    linked_in: frozenset[PurePosixPath] | None,
) -> SkillCheckResult:
    """Check the links of one file of a skill, its `SKILL.md` or a resource, in order. Pure: raises nothing.

    A link whose destination starts with `/` is `skill.link-absolute`, on the link's line. A URL with a scheme,
    such as `https:`, never starts with `/`, and neither does a fragment-only link, so neither is one.

    A link whose destination starts with `#` is `skill.link-fragment`, on the link's line, when its fragment,
    percent-decoded and lowercased by `Anchor.from_fragment`, is none of the anchors. A bare `#` names no
    heading, so it is not one, and neither is a fragment after a path, such as `other.md#usage`: only a link into
    the file itself is checked.

    A relative link is `skill.link-escapes`, on the link's line, when its path, normalised lexically, climbs
    above the skill root. The path is read from the skill root, not from the file that holds it: `../SKILL.md`
    climbs out from any file of the skill, and `references/../SKILL.md` does not. One that stays inside is
    `skill.link-broken`, on the link's line, when `targets` has it missing and it is not in `linked_in`; when
    `linked_in` is `None`, no link is.

    A link breaks at most one of these rules, so each link gives at most one violation, and the violations come
    in the order of the links. The rules exclude one another: an absolute or a fragment-only link names no
    relative path, and a path that climbs above the skill root names nothing inside it.

    Each message states the problem alone and shows the destination percent-decoded, as the author wrote it,
    rather than as the parser encoded it: `[x](#Straße)` is reported as `#Straße`, not `#Stra%C3%9Fe`. An
    absolute, an escaping and a broken link carry a help note on how to fix it; a dangling fragment carries none.

    Args:
        links: Every link and image of the file, the skill's `SKILL.md` or one of its resources, in document order.
        anchors: The heading anchors of that same file, as `ParsedDocument.anchors` holds them. Empty when the file
            has no heading, so that every fragment dangles.
        targets: What the snapshot holds at each path inside the skill a link names, keyed by the path
            `link_path_in_skill` reads from the link; every such path of `links` is a key.
        linked_in: Every path inside the skill a `metadata` subkey of the skill's `SKILL.md` links a file in at, such as
            `references/logging.md`; a link to one is not broken, whatever the snapshot holds there. `None` when
            the skill's `metadata` is unknown, because its frontmatter cannot be read: any path might then be
            linked in, so `skill.link-broken` is not judged.
    """
    violations: list[Violation] = []
    for link in links:
        if _is_absolute(link.url):
            violations.append(_absolute_violation(link))
        elif _is_dangling_fragment(link.url, anchors):
            violations.append(_fragment_violation(link))
        elif _is_escaping(link):
            violations.append(_escape_violation(link))
        elif _is_broken(link, targets, linked_in):
            violations.append(_broken_violation(link))
    return SkillCheckResult(violations=tuple(violations))


def link_path_in_skill(link: Link) -> PurePosixPath | None:
    """The path inside the skill a link names, read from the skill root, or `None` when it names none.

    The path is `Link.to_normalised_relative_path`'s: `references/./a%20b.md#usage` is `references/a b.md`, and
    `references/..` is `.`, the skill root itself. `None` for a link that spells no relative path, such as a URL
    with a scheme, an absolute or a fragment-only link, and for one that climbs above the skill root.

    Args:
        link: The link whose destination is read.
    """
    normalised = link.to_normalised_relative_path()
    if normalised is None or _climbs_above_root(normalised):
        return None
    return normalised


def _absolute_violation(link: Link) -> Violation:
    """The violation of a link that starts at a filesystem root, on the link's line, with help to fix it.

    Args:
        link: The absolute link.
    """
    return Violation(
        line=link.line,
        rule='skill.link-absolute',
        message=f'`{unquote(link.url)}` is absolute',
        notes=(Note(NoteKind.HELP, 'link relative to the skill root'),),
    )


def _fragment_violation(link: Link) -> Violation:
    """The violation of a fragment-only link naming no heading of its file, on the link's line.

    Args:
        link: The dangling fragment link.
    """
    return Violation(
        line=link.line,
        rule='skill.link-fragment',
        message=f'`{unquote(link.url)}` names a heading this file does not have',
    )


def _escape_violation(link: Link) -> Violation:
    """The violation of a link that climbs above the skill root, on the link's line, with help to fix it.

    Args:
        link: The escaping link.
    """
    return Violation(
        line=link.line,
        rule='skill.link-escapes',
        message=f'`{unquote(link.url)}` leaves the skill directory',
        notes=(Note(NoteKind.HELP, 'link a file inside the skill, relative to the skill root'),),
    )


def _broken_violation(link: Link) -> Violation:
    """The violation of a link inside the skill that names nothing there, on the link's line, with help to fix it.

    Args:
        link: The broken link.
    """
    return Violation(
        line=link.line,
        rule='skill.link-broken',
        message=f'`{unquote(link.url)}` names nothing in the skill',
        notes=(Note(NoteKind.HELP, 'link a file or a directory the skill holds, relative to the skill root'),),
    )


def _is_absolute(url: str) -> bool:
    """Whether a link's destination starts at a filesystem root rather than at the skill root.

    Args:
        url: The link's destination as the parser encoded it.
    """
    return url.startswith('/')


def _is_escaping(link: Link) -> bool:
    """Whether a link's relative path, read from the skill root, climbs above it.

    A link that spells no relative path, such as a URL with a scheme, an absolute or a fragment-only link,
    never escapes.

    Args:
        link: The link whose destination is read.
    """
    # Lexical on purpose, rather than a containment check of resolved paths: a check performs no I/O, and the
    # link is text read from the skill root, not a filesystem path. The path alone decides, never joined to
    # the skill's directory first: a link that climbs out and back in by the repository's own path, such as
    # `../../skills/review/SKILL.md`, depends on where the skill is installed, so it escapes too.
    normalised = link.to_normalised_relative_path()
    if normalised is None:
        return False
    return _climbs_above_root(normalised)


def _is_broken(
    link: Link, targets: Mapping[PurePosixPath, LinkTargetState], linked_in: frozenset[PurePosixPath] | None
) -> bool:
    """Whether a link names a path inside the skill that holds nothing, and that `metadata` links nothing in at.

    A link that names no path inside the skill, such as a URL or an escaping link, is never broken, and no link
    is when `linked_in` is `None`.

    Args:
        link: The link whose destination is read.
        targets: What the snapshot holds at each path inside the skill a link names.
        linked_in: Every path inside the skill a `metadata` subkey links a file in at, or `None` when unknown.
    """
    if linked_in is None:
        # The skill's `metadata` could not be read, so any path might be one it links in: not judged at all.
        return False
    path = link_path_in_skill(link)
    if path is None:
        return False
    # A file `metadata` links in is the `skill.metadata-*` rules' to check, present or not, so a link to it is
    # never reported here too.
    if path in linked_in:
        return False
    # The run keys `targets` by every path `link_path_in_skill` yields for these links, so the lookup cannot miss.
    state = targets[path]
    match state:
        case LinkTargetState.PRESENT:
            return False
        case LinkTargetState.MISSING:
            return True
        case _:
            assert_never(state)


def _climbs_above_root(normalised: PurePosixPath) -> bool:
    """Whether a lexically normalised relative path climbs above the directory it is read from.

    Normalising leaves a `..` only at the start, so the first component alone decides.

    Args:
        normalised: A relative path, as `Link.to_normalised_relative_path` returns it.
    """
    # A slice, not `parts[0]`: `references/..` normalises to `.`, whose `parts` is empty.
    return normalised.parts[:1] == ('..',)


def _is_dangling_fragment(url: str, anchors: frozenset[Anchor]) -> bool:
    """Whether a link is fragment-only and its fragment names a heading the file does not have.

    A bare `#` names no heading at all, so it does not dangle. A fragment no heading can have, such as one
    holding a space, dangles whatever the anchors are.

    Args:
        url: The link's destination as the parser encoded it; one not starting with `#` never dangles.
        anchors: The heading anchors of the file the link is written in.
    """
    if not url.startswith('#'):
        return False
    fragment = url.removeprefix('#')
    if fragment == '':
        return False
    anchor = Anchor.from_fragment(fragment)
    if anchor is None:
        return True
    return anchor not in anchors
