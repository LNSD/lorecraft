"""Parsing a skill's ``SKILL.md`` into its frontmatter, the fields the Agent Skills specification defines.

A ``SKILL.md`` is a document like any other up to its frontmatter block, so the block is found and decoded by
``syntax.parse_frontmatter``. What sets a skill apart is the shape the decoded mapping must have, which
``SkillFrontmatter`` declares; ``parse_skill_frontmatter`` holds the mapping to it with pydantic. The body after
the block is free Markdown, which the specification puts no rule on, and is not read here.

Nothing here logs: the command that parses a skill catches every ``Error`` that escapes it and reports it.
"""

from typing import assert_never

from pydantic import ValidationError

from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import (
    Frontmatter,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
    parse_frontmatter,
)

from .skill_frontmatter import SkillFrontmatter


class MissingSkillFrontmatterError(Error):
    """A ``SKILL.md`` does not open with a ``---`` delimited frontmatter block.

    Attributes:
        path: Root-relative path of the rejected ``SKILL.md``.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(
            f'invalid skill frontmatter {path}: it must open with a `---` delimited YAML frontmatter block'
        )


class UnparseableSkillFrontmatterError(Error):
    """A ``SKILL.md``'s frontmatter block is not valid YAML.

    The parse reports the failure as a value, not an exception, so there is no source to chain: its facts are
    held here instead.

    Attributes:
        path: Root-relative path of the rejected ``SKILL.md``.
        problem: What the YAML parser found wrong, in its own words.
        line: The line of the ``SKILL.md`` the problem is on, or None when the parser does not say.
    """

    path: RootRelativePath
    problem: str
    line: LineNumber | None

    def __init__(self, path: RootRelativePath, problem: str, line: LineNumber | None) -> None:
        self.path = path
        self.problem = problem
        self.line = line
        super().__init__(f'invalid skill frontmatter {path}: the frontmatter is not valid YAML: {problem}')


class NonMappingSkillFrontmatterError(Error):
    """A ``SKILL.md``'s frontmatter block is valid YAML but not a mapping.

    Attributes:
        path: Root-relative path of the rejected ``SKILL.md``.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'invalid skill frontmatter {path}: the frontmatter must be a YAML mapping')


class InvalidSkillFrontmatterError(Error):
    """A ``SKILL.md``'s frontmatter mapping does not have the shape the Agent Skills specification defines.

    Attributes:
        path: Root-relative path of the rejected ``SKILL.md``.
        problems: Every problem found, as ``<field path>: <message>``, read from the validation error.
        source: The validation error.
    """

    path: RootRelativePath
    problems: tuple[str, ...]
    source: ValidationError

    def __init__(self, path: RootRelativePath, problems: tuple[str, ...], *, source: ValidationError) -> None:
        self.path = path
        self.problems = problems
        self.source = source
        super().__init__(f'invalid skill frontmatter {path}: {"; ".join(problems)}')
        self.__cause__ = source


def parse_skill_frontmatter(path: RootRelativePath, text: str) -> SkillFrontmatter:
    """Parse a ``SKILL.md``'s text into its frontmatter.

    Args:
        path: Where the text was read from; every rejection names it.
        text: The whole ``SKILL.md``, frontmatter and body.

    Raises:
        MissingSkillFrontmatterError: If the text has no frontmatter block.
        UnparseableSkillFrontmatterError: If the block is not valid YAML.
        NonMappingSkillFrontmatterError: If the block is valid YAML but not a mapping.
        InvalidSkillFrontmatterError: If the mapping does not have the specification's shape.
    """
    node = parse_frontmatter(text)
    match node:
        case MissingFrontmatter():
            raise MissingSkillFrontmatterError(path)
        case InvalidYamlFrontmatter(problem=problem, line=line):
            raise UnparseableSkillFrontmatterError(path, problem, line)
        case NonMappingFrontmatter():
            raise NonMappingSkillFrontmatterError(path)
        case Frontmatter(data=data):
            try:
                return SkillFrontmatter.model_validate(data)
            except ValidationError as exc:
                raise InvalidSkillFrontmatterError(path, _problems(exc), source=exc) from exc
        case _:
            assert_never(node)


def _problems(error: ValidationError) -> tuple[str, ...]:
    """Every problem pydantic found in one frontmatter, each as ``<field path>: <message>``."""
    problems: list[str] = []
    for detail in error.errors(include_url=False):
        location = '.'.join(str(part) for part in detail['loc'])
        if location:
            problems.append(f'{location}: {detail["msg"]}')
        else:
            problems.append(detail['msg'])
    return tuple(problems)
