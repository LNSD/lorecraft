"""What each frontmatter schema rejects in one frontmatter, each problem placed on the line it is reported on.

A schema reports a problem by the field it concerns, as `FrontmatterProblem` states; this module places it on the
line that field is written on, through `field_line`, the one place a field's line, or line 1 in its absence, is
decided. A document is held to each frontmatter schema that governs it, and a skill to the Agent Skills
specification's, so each set of problems names the schema it was found against.
"""

from dataclasses import dataclass
from typing import Final, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import (
    Frontmatter,
    FrontmatterNode,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
)

from .frontmatter_problem import (
    BlockProblem,
    FrontmatterProblem,
    InvalidValueProblem,
    MissingFieldProblem,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from .skill import SKILL_FRONTMATTER_SCHEMA
from .structure import FrontmatterSchema

FIRST_LINE: Final[LineNumber] = LineNumber.from_int(1)
"""Where an occurrence with no more precise line is reported: the subject's first line, which opens the block."""


@dataclass(frozen=True, slots=True)
class StructureSpecSchema:
    """A frontmatter schema a structure specification states under its `frontmatter` key.

    Attributes:
        spec: The structure specification file that states the schema.
    """

    spec: RootRelativePath


@dataclass(frozen=True, slots=True)
class AgentSkillsSchema:
    """The Agent Skills specification's frontmatter schema: the package states it, and no repository file sets it."""


# The schema a set of problems was found against: one a structure specification file states, for a document, or
# the Agent Skills specification's, for a skill.
type SchemaSource = StructureSpecSchema | AgentSkillsSchema


@dataclass(frozen=True, slots=True)
class LocatedProblem:
    """One thing a frontmatter schema rejects, with the line it is reported on.

    Attributes:
        problem: What the schema rejects.
        line: The line of the field it concerns, or line 1 when it concerns no field or a field not written.
    """

    problem: FrontmatterProblem
    line: LineNumber


@dataclass(frozen=True, slots=True)
class SchemaProblems:
    """Every problem one frontmatter schema found in a frontmatter.

    Attributes:
        source: The schema the problems were found against.
        problems: In the order the schema reports them; empty when the frontmatter conforms to it.
    """

    source: SchemaSource
    problems: tuple[LocatedProblem, ...]


def locate_schema_problems(
    frontmatter: FrontmatterNode, schemas: tuple[FrontmatterSchema, ...]
) -> tuple[SchemaProblems, ...]:
    """What each frontmatter schema rejects in a document's frontmatter, each problem on its line. Raises nothing.

    Every schema is applied on its own: a document governed by a corpus and a namespace schema must conform to both.

    Args:
        frontmatter: The document's frontmatter, as parsed; a block that is missing, not YAML or not a mapping is held
            to no schema.
        schemas: The frontmatter schemas that govern the document, in the order they apply.

    Returns:
        One entry per schema, in the order given, each naming the structure specification that states it; none when
        the block is missing, not YAML or not a mapping, which no schema can hold.
    """
    match frontmatter:
        case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
            return ()
        case Frontmatter():
            pass  # the mapping is held to each schema below
        case _:
            assert_never(frontmatter)

    found: list[SchemaProblems] = []
    for schema in schemas:
        found.append(
            SchemaProblems(
                source=StructureSpecSchema(spec=schema.path),
                problems=_located_problems(frontmatter, schema.validate(frontmatter.data)),
            )
        )
    return tuple(found)


def locate_skill_schema_problems(frontmatter: FrontmatterNode) -> tuple[SchemaProblems, ...]:
    """What the Agent Skills specification rejects in a skill's frontmatter, each problem on its line. Raises nothing.

    Args:
        frontmatter: The frontmatter of the skill's `SKILL.md`, as parsed; a block that is missing, not YAML or not a
            mapping is held to no schema.

    Returns:
        One entry, for the Agent Skills specification; none when the block is missing, not YAML or not a mapping,
        which no schema can hold.
    """
    match frontmatter:
        case MissingFrontmatter() | InvalidYamlFrontmatter() | NonMappingFrontmatter():
            return ()
        case Frontmatter():
            pass  # the mapping is held to the specification below
        case _:
            assert_never(frontmatter)

    problems = _located_problems(frontmatter, SKILL_FRONTMATTER_SCHEMA.validate(frontmatter.data))
    return (SchemaProblems(source=AgentSkillsSchema(), problems=problems),)


def field_line(frontmatter: Frontmatter, field: str) -> LineNumber:
    """The line a top-level field is written on, or line 1 when the mapping does not hold it. Raises nothing.

    Args:
        frontmatter: The decoded frontmatter, whose top-level keys carry the line each is written on.
        field: Name of the top-level key to find.
    """
    line = frontmatter.find_key_line(field)
    if line is None:
        return FIRST_LINE
    return line


def _located_problems(frontmatter: Frontmatter, problems: tuple[FrontmatterProblem, ...]) -> tuple[LocatedProblem, ...]:
    """Each problem a schema found, with the line it is reported on, in the order given. Raises nothing.

    Args:
        frontmatter: The frontmatter the problems were found in.
        problems: What the schema rejected in it.
    """
    located: list[LocatedProblem] = []
    for problem in problems:
        located.append(LocatedProblem(problem=problem, line=_problem_line(frontmatter, problem)))
    return tuple(located)


def _problem_line(frontmatter: Frontmatter, problem: FrontmatterProblem) -> LineNumber:
    """The line a schema problem is reported on: its field's, or line 1 when it has no written field. Raises nothing.

    Args:
        frontmatter: The frontmatter the problem was found in; searched for the line its field is written on.
        problem: What the schema rejected; a problem on a written field is placed on that field's line.
    """
    match problem:
        # A missing field is not written, and a block constraint concerns none.
        case MissingFieldProblem() | BlockProblem():
            return FIRST_LINE
        case UnknownFieldProblem() | WrongTypeProblem() | InvalidValueProblem():
            return field_line(frontmatter, problem.field)
        case _:
            assert_never(problem)
