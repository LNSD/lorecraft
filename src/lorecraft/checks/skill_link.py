"""Validate the links in one skill's ``SKILL.md``: the home of the skill check's link rules.

A skill is loaded from wherever an agent keeps it, so a link in its ``SKILL.md`` is followed from the skill's own
directory: one that starts at a filesystem root points at a file the skill does not carry, and is
``skill.link-absolute``. A fragment-only link, such as ``#usage``, stays in the ``SKILL.md`` itself, so the heading
it names must be one of that file's own, or it is ``skill.link-fragment``. The rules that follow a link to another
file join them later.

The check is pure: it takes the links and the heading anchors the parse tree holds and returns violations. Reading
and parsing the ``SKILL.md`` happen above it, in ``checks.run`` and the database. It is the sibling of the
frontmatter half in ``skill``, and reports in the same ``SkillCheckResult``.
"""

from urllib.parse import unquote

from lorecraft.project.syntax import Anchor, Link

from .reporting import Violation
from .skill import SkillCheckResult


def validate_skill_links(*, links: tuple[Link, ...], anchors: frozenset[Anchor]) -> SkillCheckResult:
    """Check the links of one skill's ``SKILL.md``, in the order given. Pure: raises nothing.

    A link whose destination starts with ``/`` is ``skill.link-absolute``, on the link's line. A URL with a
    scheme, such as ``https:``, never starts with ``/``, and neither does a fragment-only link, so neither is one.

    A link whose destination starts with ``#`` is ``skill.link-fragment``, on the link's line, when its fragment,
    percent-decoded and lowercased by ``Anchor.from_fragment``, is none of the anchors. A bare ``#`` names no
    heading, so it is not one, and neither is a fragment after a path, such as ``other.md#usage``: only a link into
    the ``SKILL.md`` itself is checked.

    Either message shows the destination percent-decoded, as the author wrote it, rather than as the parser
    encoded it: ``[x](#Straße)`` is reported as ``#Straße``, not ``#Stra%C3%9Fe``.

    Args:
        links: Every link and image of the skill's ``SKILL.md``, in document order.
        anchors: The heading anchors of that same ``SKILL.md``, as ``ParsedDocument.anchors`` holds them. Empty
            when the file has no heading, so that every fragment dangles.
    """
    violations: list[Violation] = []
    for link in links:
        if _is_absolute(link.url):
            violations.append(
                Violation(
                    line=link.line,
                    rule='skill.link-absolute',
                    message=f'`{unquote(link.url)}` is absolute; link relative to the skill root',
                )
            )
        elif _is_dangling_fragment(link.url, anchors):
            violations.append(
                Violation(
                    line=link.line,
                    rule='skill.link-fragment',
                    message=f'`{unquote(link.url)}` names a heading this file does not have',
                )
            )
    return SkillCheckResult(violations=tuple(violations))


def _is_absolute(url: str) -> bool:
    """Whether a link's destination starts at a filesystem root rather than at the file it is written in.

    Args:
        url: The link's destination as the parser encoded it.
    """
    return url.startswith('/')


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
