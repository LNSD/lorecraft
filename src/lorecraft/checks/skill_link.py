"""Validate the links in one skill's Markdown files: the home of the skill check's link rules.

A skill is loaded from wherever an agent keeps it, and the Agent Skills specification has it name its files by
paths relative to the skill root, in every Markdown file it carries: a link in `references/guide.md` to
`SKILL.md` is `SKILL.md`, not `../SKILL.md`. So a relative link that, read from the skill root, climbs above it
points at a file the skill does not carry once it is installed elsewhere, and is `skill.link-escapes`, in the
`SKILL.md` and in each resource alike.

Two rules hold for the `SKILL.md` only. A link that starts at a filesystem root points at a file the skill does
not carry either, and is `skill.link-absolute`. A fragment-only link, such as `#usage`, stays in the `SKILL.md`
itself, so the heading it names must be one of that file's own, or it is `skill.link-fragment`.

The check is pure: it takes the links and the heading anchors the parse tree holds, and returns violations.
Reading and parsing the files happen above it, in `checks.run` and the database. It is the sibling of the
frontmatter half in `skill`, and reports in the same `SkillCheckResult`.
"""

import posixpath
from urllib.parse import unquote

from lorecraft.project.syntax import Anchor, Link

from .reporting import Violation
from .skill import SkillCheckResult


def validate_skill_links(*, links: tuple[Link, ...], anchors: frozenset[Anchor]) -> SkillCheckResult:
    """Check the links of one skill's `SKILL.md`, in the order given. Pure: raises nothing.

    A link whose destination starts with `/` is `skill.link-absolute`, on the link's line. A URL with a scheme,
    such as `https:`, never starts with `/`, and neither does a fragment-only link, so neither is one.

    A link whose destination starts with `#` is `skill.link-fragment`, on the link's line, when its fragment,
    percent-decoded and lowercased by `Anchor.from_fragment`, is none of the anchors. A bare `#` names no
    heading, so it is not one, and neither is a fragment after a path, such as `other.md#usage`: only a link into
    the `SKILL.md` itself is checked.

    A relative link is `skill.link-escapes`, on the link's line, when its path, normalised lexically, climbs
    above the skill root: `../SKILL.md` does, and `references/../SKILL.md` does not.

    Each message shows the destination percent-decoded, as the author wrote it, rather than as the parser
    encoded it: `[x](#Straße)` is reported as `#Straße`, not `#Stra%C3%9Fe`.

    Args:
        links: Every link and image of the skill's `SKILL.md`, in document order.
        anchors: The heading anchors of that same `SKILL.md`, as `ParsedDocument.anchors` holds them. Empty
            when the file has no heading, so that every fragment dangles.
    """
    violations: list[Violation] = []
    for link in links:
        if _is_absolute(link.url):
            violations.append(_absolute_violation(link))
        elif _is_dangling_fragment(link.url, anchors):
            violations.append(_fragment_violation(link))
        elif _is_escaping(link):
            violations.append(_escape_violation(link))
    return SkillCheckResult(violations=tuple(violations))


def validate_skill_resource_links(*, links: tuple[Link, ...]) -> SkillCheckResult:
    """Check the links of one resource of a skill, in the order given. Pure: raises nothing.

    A relative link is `skill.link-escapes`, on the link's line, when its path, normalised lexically, climbs
    above the skill root. The path is read from the skill root, not from the resource: `../SKILL.md` climbs out
    from any file of the skill, and `references/../SKILL.md` does not.

    The message shows the destination percent-decoded, as the author wrote it.

    Args:
        links: Every link and image of the resource, in document order.
    """
    violations: list[Violation] = []
    for link in links:
        if _is_escaping(link):
            violations.append(_escape_violation(link))
    return SkillCheckResult(violations=tuple(violations))


def _absolute_violation(link: Link) -> Violation:
    """The violation of a link that starts at a filesystem root, on the link's line.

    Args:
        link: The absolute link.
    """
    return Violation(
        line=link.line,
        rule='skill.link-absolute',
        message=f'`{unquote(link.url)}` is absolute; link relative to the skill root',
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
    """The violation of a link that climbs above the skill root, on the link's line.

    Args:
        link: The escaping link.
    """
    return Violation(
        line=link.line,
        rule='skill.link-escapes',
        message=(
            f'`{unquote(link.url)}` leaves the skill directory; link a file inside the skill, relative to the '
            'skill root'
        ),
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
    path = link.to_relative_path()
    if path is None:
        return False
    # Lexical on purpose, rather than a containment check of resolved paths: a check performs no I/O, and the
    # link is text read from the skill root, not a filesystem path. The path alone decides, never joined to
    # the skill's directory first: a link that climbs out and back in by the repository's own path, such as
    # `../../skills/review/SKILL.md`, depends on where the skill is installed, so it escapes too.
    normalised = posixpath.normpath(str(path))
    return normalised == '..' or normalised.startswith('../')


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
