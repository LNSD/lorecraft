"""The committed skill frontmatter schema is a JSON Schema every skill this repository carries passes.

``docs/schemas/skill-frontmatter.spec.json`` is rendered by ``just gen`` from ``SkillFrontmatter``, the pydantic model
``parse_skill_frontmatter`` deserializes each ``SKILL.md`` with, so the schema and the parser cannot disagree about
a shape; CI's ``gen-check`` job keeps the committed file current. What is left to hold is the file an editor reads:
that it is a well-formed schema, and that it accepts every skill this repository writes, as the parser does.
"""

import json
from pathlib import Path
from typing import Final

import pytest
from jsonschema import Draft202012Validator

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import parse_skill_frontmatter
from lorecraft.project.syntax import Frontmatter, parse_frontmatter

REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SCHEMA_FILE: Final[Path] = REPOSITORY_ROOT / 'docs' / 'schemas' / 'skill-frontmatter.spec.json'


def repository_skills() -> list[Path]:
    """Every `SKILL.md` this repository carries, workspace and project skills alike, each once."""
    workspace_skills = (REPOSITORY_ROOT / '.agents' / 'skills').glob('*/SKILL.md')
    project_skills = (REPOSITORY_ROOT / 'skills').glob('*/SKILL.md')
    # A project skill is linked into the workspace by symlink; resolving it counts it once.
    return sorted({skill.resolve() for skill in [*workspace_skills, *project_skills]})


@pytest.fixture(scope='module')
def validator() -> Draft202012Validator:
    """A validator for the committed skill frontmatter schema."""
    return Draft202012Validator(json.loads(SCHEMA_FILE.read_text(encoding='utf-8')))


@pytest.mark.it
class TestSkillFrontmatterSchema:
    def test_skill_frontmatter_schema_is_a_well_formed_json_schema(self) -> None:
        #: Given
        schema = json.loads(SCHEMA_FILE.read_text(encoding='utf-8'))

        #: When
        Draft202012Validator.check_schema(schema)

        #: Then
        assert schema['$schema'] == 'https://json-schema.org/draft/2020-12/schema', 'the schema names its dialect'

    def test_every_repository_skill_passes_the_schema(self, validator: Draft202012Validator) -> None:
        #: Given
        frontmatters = {
            skill.parent.name: parse_frontmatter(skill.read_text(encoding='utf-8')) for skill in repository_skills()
        }
        assert all(isinstance(node, Frontmatter) for node in frontmatters.values()), 'every skill opens with a mapping'
        data = {name: node.data for name, node in frontmatters.items() if isinstance(node, Frontmatter)}

        #: When
        schema_errors = {
            name: [error.message for error in validator.iter_errors(value)] for name, value in data.items()
        }

        #: Then
        assert data, 'the repository carries skills, so the comparison is not vacuous'
        assert all(not errors for errors in schema_errors.values()), (
            f'every skill follows the specification, so the schema must accept them: {schema_errors}'
        )

    def test_every_repository_skill_parses(self) -> None:
        #: Given
        skills = repository_skills()

        #: When
        names = [
            parse_skill_frontmatter(
                RootRelativePath.parse(skill.relative_to(REPOSITORY_ROOT).as_posix()), skill.read_text(encoding='utf-8')
            ).name.value
            for skill in skills
        ]

        #: Then
        assert names == [skill.parent.name for skill in skills], 'each skill is named after its directory'
