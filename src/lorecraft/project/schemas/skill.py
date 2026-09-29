"""Parsing a skill's ``SKILL.md`` into its frontmatter, the fields the Agent Skills specification defines.

A ``SKILL.md`` is a document like any other up to its frontmatter block, so the block is found and decoded by
``syntax.parse_frontmatter``. What sets a skill apart is the shape the decoded mapping must have, which
``SkillFrontmatter`` declares; ``parse_skill_frontmatter`` holds the mapping to it with pydantic. The body after
the block is free Markdown, which the specification puts no rule on, and is not read here.

Nothing here logs: the command that parses a skill catches every ``Error`` that escapes it and reports it.
"""

from pydantic import ValidationError

from lorecraft.core.error import Error
from lorecraft.project.syntax import (
    Frontmatter,
    InvalidYamlFrontmatter,
    MissingFrontmatter,
    NonMappingFrontmatter,
    parse_frontmatter,
)
from lorecraft.vfs import RootRelativePath

from .skill_frontmatter import SkillFrontmatter


class InvalidSkillFrontmatterError(Error):
    """A ``SKILL.md`` does not open with frontmatter of the shape the Agent Skills specification defines.

    Attributes:
        path: Root-relative path of the rejected ``SKILL.md``.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        super().__init__(f'invalid skill frontmatter {path}: {detail}')


def parse_skill_frontmatter(path: RootRelativePath, text: str) -> SkillFrontmatter:
    """Parse a ``SKILL.md``'s text into its frontmatter.

    Args:
        path: Where the text was read from; every rejection names it.
        text: The whole ``SKILL.md``, frontmatter and body.

    Raises:
        InvalidSkillFrontmatterError: If the text has no frontmatter block, the block is not a YAML mapping, or
            the mapping does not have the specification's shape.
    """
    node = parse_frontmatter(text)
    match node:
        case MissingFrontmatter():
            raise InvalidSkillFrontmatterError(path, 'it must open with a `---` delimited YAML frontmatter block')
        case InvalidYamlFrontmatter(detail=detail):
            raise InvalidSkillFrontmatterError(path, f'the frontmatter is not valid YAML: {detail}')
        case NonMappingFrontmatter():
            raise InvalidSkillFrontmatterError(path, 'the frontmatter must be a YAML mapping')
        case Frontmatter(data=data):
            try:
                return SkillFrontmatter.model_validate(data)
            except ValidationError as exc:
                raise InvalidSkillFrontmatterError(path, _describe(exc)) from exc


def _describe(error: ValidationError) -> str:
    """Every problem pydantic found in one frontmatter, as ``<field path>: <message>``, joined into one line."""
    problems: list[str] = []
    for detail in error.errors(include_url=False):
        location = '.'.join(str(part) for part in detail['loc'])
        if location:
            problems.append(f'{location}: {detail["msg"]}')
        else:
            problems.append(detail['msg'])
    return '; '.join(problems)
