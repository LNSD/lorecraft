"""What each frontmatter schema rejects in one frontmatter, each problem placed on the line it is reported on.

Every frontmatter is parsed from text by the real parser, and every schema decoded from a structure specification's
JSON by the real decoder, so no case holds a fact a real document could not produce.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import Frontmatter, LineNumber, parse_frontmatter

from ..frontmatter_problem import FieldGuidance, JsonType, MissingFieldProblem, UnknownFieldProblem, WrongTypeProblem
from ..name import parse_spec_name
from ..schema_problems import (
    AgentSkillsSchema,
    LocatedProblem,
    SchemaProblems,
    StructureSpecSchema,
    field_line,
    locate_schema_problems,
    locate_skill_schema_problems,
)
from ..spec_file import SpecFileType, StructureSpecFile, spec_filename
from ..structure import FrontmatterSchema, StructureSchema, StructureSpec

SPECS_DIR: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__')

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code-python.structure.json')
"""The `python` namespace structure specification."""

REQUIRE_STATUS: Final[str] = '{"frontmatter": {"type": "object", "required": ["status"]}}'
"""A structure specification whose frontmatter schema requires `status`."""

REQUIRE_OWNER: Final[str] = '{"frontmatter": {"type": "object", "required": ["owner"]}}'
"""A structure specification whose frontmatter schema requires `owner`."""

STRING_DESCRIPTION: Final[str] = (
    '{"frontmatter": {"type": "object", "properties": {"description": {"type": "string"}}}}'
)
"""A structure specification whose frontmatter schema requires `description` to be a string."""


def _frontmatter_schema(spec_name: str, text: str) -> FrontmatterSchema:
    """The frontmatter schema a structure specification states, decoded from its JSON.

    Args:
        spec_name: The specification's name, such as `code` or `code-python`.
        text: The structure specification's JSON; it states a frontmatter schema.
    """
    name = parse_spec_name(spec_name)
    file = StructureSpecFile(path=SPECS_DIR / spec_filename(name, SpecFileType.STRUCTURE), name=name)
    frontmatter = StructureSpec.parse(file, StructureSchema(text)).frontmatter
    assert frontmatter is not None, f'{file.path} states a frontmatter schema'
    return frontmatter


def _mapping(text: str) -> Frontmatter:
    """The frontmatter mapping the parser reads from a document's text.

    Args:
        text: A document's text, opening with a block that decodes to a mapping.
    """
    frontmatter = parse_frontmatter(text)
    assert isinstance(frontmatter, Frontmatter), 'the block decodes to a mapping'
    return frontmatter


@pytest.mark.unit
class TestFieldLine:
    def test_field_line_of_a_written_field_returns_the_line_its_key_is_on(self) -> None:
        #: Given
        frontmatter = _mapping('---\nname: typing\nstatus: stable\n---\n')

        #: When
        line = field_line(frontmatter, 'status')

        #: Then
        assert line == LineNumber.from_int(3), 'a field is on the line its key is written on'

    def test_field_line_of_a_field_not_written_returns_line_1(self) -> None:
        #: Given
        frontmatter = _mapping('---\nname: typing\n---\n')

        #: When
        line = field_line(frontmatter, 'status')

        #: Then
        assert line == LineNumber.from_int(1), 'a field the mapping does not hold is placed on the first line'


@pytest.mark.unit
class TestLocateSchemaProblems:
    def test_locate_with_two_schemas_holds_each_schema_problems_in_the_order_given(self) -> None:
        #: Given
        # each schema requires a field the frontmatter lacks, so each finds one problem on line 1
        frontmatter = parse_frontmatter('---\nname: python-typing\n---\n# Typing\n')
        schemas = (_frontmatter_schema('code', REQUIRE_STATUS), _frontmatter_schema('code-python', REQUIRE_OWNER))

        #: When
        found = locate_schema_problems(frontmatter, schemas)

        #: Then
        assert found == (
            SchemaProblems(
                source=StructureSpecSchema(spec=CORPUS_SPEC),
                problems=(
                    LocatedProblem(
                        problem=MissingFieldProblem('status', "'status' is a required property"),
                        line=LineNumber.from_int(1),
                    ),
                ),
            ),
            SchemaProblems(
                source=StructureSpecSchema(spec=NAMESPACE_SPEC),
                problems=(
                    LocatedProblem(
                        problem=MissingFieldProblem('owner', "'owner' is a required property"),
                        line=LineNumber.from_int(1),
                    ),
                ),
            ),
        ), 'the corpus schema comes first, then the namespace one, each naming the specification that states it'

    def test_locate_with_problems_on_written_fields_places_each_on_its_field_line(self) -> None:
        #: Given
        # `description` is on line 3 and of the wrong type; `status` is missing, so it is on no line
        frontmatter = parse_frontmatter('---\nname: python-typing\ndescription: 3\n---\n# Typing\n')
        schemas = (
            _frontmatter_schema('code', REQUIRE_STATUS),
            _frontmatter_schema('code-python', STRING_DESCRIPTION),
        )

        #: When
        found = locate_schema_problems(frontmatter, schemas)

        #: Then
        assert found == (
            SchemaProblems(
                source=StructureSpecSchema(spec=CORPUS_SPEC),
                problems=(
                    LocatedProblem(
                        problem=MissingFieldProblem('status', "'status' is a required property"),
                        line=LineNumber.from_int(1),
                    ),
                ),
            ),
            SchemaProblems(
                source=StructureSpecSchema(spec=NAMESPACE_SPEC),
                problems=(
                    LocatedProblem(
                        problem=WrongTypeProblem(
                            'description', "3 is not of type 'string'", (JsonType.STRING,), JsonType.INTEGER
                        ),
                        line=LineNumber.from_int(3),
                    ),
                ),
            ),
        ), 'a problem on a written field is on that field line, and a missing field, written nowhere, on line 1'

    def test_locate_with_a_conforming_frontmatter_holds_each_schema_with_no_problem(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nstatus: stable\ndescription: Annotate.\n---\n# Typing\n')
        schemas = (
            _frontmatter_schema('code', REQUIRE_STATUS),
            _frontmatter_schema('code-python', STRING_DESCRIPTION),
        )

        #: When
        found = locate_schema_problems(frontmatter, schemas)

        #: Then
        assert found == (
            SchemaProblems(source=StructureSpecSchema(spec=CORPUS_SPEC), problems=()),
            SchemaProblems(source=StructureSpecSchema(spec=NAMESPACE_SPEC), problems=()),
        ), 'a frontmatter both schemas accept is still held to each, with nothing found'

    def test_locate_with_no_block_holds_no_schema(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('# Typing\n')

        #: When
        found = locate_schema_problems(frontmatter, (_frontmatter_schema('code', REQUIRE_STATUS),))

        #: Then
        assert found == (), 'no schema can hold a missing block: the block rules report it'

    def test_locate_with_a_block_that_is_not_yaml_holds_no_schema(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: [unclosed\n---\n# Typing\n')

        #: When
        found = locate_schema_problems(frontmatter, (_frontmatter_schema('code', REQUIRE_STATUS),))

        #: Then
        assert found == (), 'no schema can hold a block that is not YAML: the block rules report it'

    def test_locate_with_a_block_that_is_a_list_holds_no_schema(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\n- status\n---\n# Typing\n')

        #: When
        found = locate_schema_problems(frontmatter, (_frontmatter_schema('code', REQUIRE_STATUS),))

        #: Then
        assert found == (), 'no schema can hold a block that is not a mapping: the block rules report it'


@pytest.mark.unit
class TestLocateSkillSchemaProblems:
    def test_locate_with_a_skill_holds_the_agent_skills_problems_on_their_lines(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('---\nname: review\ndescription: [a]\nextra: y\n---\n# Review\n')

        #: When
        found = locate_skill_schema_problems(frontmatter)

        #: Then
        assert found == (
            SchemaProblems(
                source=AgentSkillsSchema(),
                problems=(
                    LocatedProblem(
                        problem=WrongTypeProblem(
                            'description',
                            '`description` must be a string',
                            (JsonType.STRING,),
                            JsonType.ARRAY,
                            guidance=FieldGuidance(
                                description=(
                                    'What the skill does and when to use it, with the keywords that let an agent '
                                    'match it to a task.'
                                ),
                                example=(
                                    'Extracts text and tables from PDF files, fills PDF forms, and merges multiple '
                                    'PDFs. Use when working with PDF documents or when the user mentions PDFs, '
                                    'forms, or document extraction.'
                                ),
                            ),
                        ),
                        line=LineNumber.from_int(3),
                    ),
                    LocatedProblem(
                        problem=UnknownFieldProblem(
                            'extra',
                            '`extra` is not a field of the Agent Skills specification',
                            ('name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools'),
                        ),
                        line=LineNumber.from_int(4),
                    ),
                ),
            ),
        ), 'a skill is held to the Agent Skills specification alone, each problem on its field line'

    def test_locate_with_a_skill_with_no_frontmatter_holds_no_schema(self) -> None:
        #: Given
        frontmatter = parse_frontmatter('# Review\n')

        #: When
        found = locate_skill_schema_problems(frontmatter)

        #: Then
        assert found == (), 'no schema can hold a missing block: the block rules report it'
