"""Validate the links in one skill's ``SKILL.md``: the home of the skill check's link rules.

A skill is loaded from wherever an agent keeps it, so a link in its ``SKILL.md`` is followed from the skill's own
directory: one that starts at a filesystem root points at a file the skill does not carry. Only that rule,
``skill.link-absolute``, is checked here so far; the rules that follow a link to its target join it later.

The check is pure: it takes the links the parse tree holds and returns violations. Reading and parsing the
``SKILL.md`` happen above it, in ``checks.run`` and the database. It is the sibling of the frontmatter half in
``skill``, and reports in the same ``SkillCheckResult``.
"""

from lorecraft.project.syntax import Link

from .reporting import Violation
from .skill import SkillCheckResult


def validate_skill_links(*, links: tuple[Link, ...]) -> SkillCheckResult:
    """Check the links of one skill's ``SKILL.md``, in the order given. Pure: raises nothing.

    A link whose destination starts with ``/`` is ``skill.link-absolute``, on the link's line. A URL with a
    scheme, such as ``https:``, never starts with ``/``, and neither does a fragment-only link, so neither is one.

    Args:
        links: Every link and image of the skill's ``SKILL.md``, in document order.
    """
    violations: list[Violation] = []
    for link in links:
        if link.url.startswith('/'):
            violations.append(
                Violation(
                    line=link.line,
                    rule='skill.link-absolute',
                    message=f'`{link.url}` is absolute; link relative to the skill root',
                )
            )
    return SkillCheckResult(violations=tuple(violations))
