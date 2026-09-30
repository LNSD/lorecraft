"""Parsing a ``SKILL.md`` into its frontmatter: the specification's fields are kept, and every way a document
falls short of them is refused with an error naming the file."""

from textwrap import dedent
from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath

from ..skill import (
    InvalidSkillFrontmatterError,
    MissingSkillFrontmatterError,
    NonMappingSkillFrontmatterError,
    parse_skill_frontmatter,
)
from ..skill_frontmatter import (
    SkillAllowedTools,
    SkillCompatibility,
    SkillDescription,
    SkillFrontmatter,
    SkillLicense,
    SkillName,
)

SKILL_PATH: Final[RootRelativePath] = RootRelativePath.parse('skills/pdf-processing/SKILL.md')


@pytest.mark.unit
class TestParseSkillFrontmatter:
    def test_parse_skill_frontmatter_with_the_required_fields_returns_them(self) -> None:
        #: Given
        text = dedent(
            """\
            ---
            name: skill-name
            description: A description of what this skill does and when to use it.
            ---

            # Skill
            """
        )

        #: When
        frontmatter = parse_skill_frontmatter(SKILL_PATH, text)

        #: Then
        assert frontmatter == SkillFrontmatter(
            name=SkillName('skill-name'),
            description=SkillDescription('A description of what this skill does and when to use it.'),
        )

    def test_parse_skill_frontmatter_with_every_field_returns_them(self) -> None:
        #: Given
        text = dedent(
            """\
            ---
            name: pdf-processing
            description: Extract PDF text, fill forms, merge files. Use when handling PDFs.
            license: Apache-2.0
            compatibility: Requires Python 3.14+ and uv
            metadata:
              author: example-org
              version: "1.0"
            allowed-tools: Bash(git add *) Read
            ---
            """
        )

        #: When
        frontmatter = parse_skill_frontmatter(SKILL_PATH, text)

        #: Then
        assert frontmatter.license == SkillLicense('Apache-2.0'), 'license is kept'
        assert frontmatter.compatibility == SkillCompatibility('Requires Python 3.14+ and uv'), 'compatibility is kept'
        assert frontmatter.metadata == {'author': 'example-org', 'version': '1.0'}, 'metadata is kept'
        assert frontmatter.allowed_tools == SkillAllowedTools('Bash(git add *) Read'), 'allowed-tools is read by alias'

    def test_parse_skill_frontmatter_without_a_block_raises_missing_skill_frontmatter(self) -> None:
        #: Given
        text = '# Skill\n'

        #: When
        with pytest.raises(MissingSkillFrontmatterError) as exc_info:
            parse_skill_frontmatter(SKILL_PATH, text)

        #: Then
        assert exc_info.value.path == SKILL_PATH, 'the error names the file'
        assert type(exc_info.value) is MissingSkillFrontmatterError, 'the missing block is its own failure'

    def test_parse_skill_frontmatter_with_a_non_mapping_block_raises_non_mapping_skill_frontmatter(self) -> None:
        #: Given
        text = '---\n- name\n---\n'

        #: When
        with pytest.raises(NonMappingSkillFrontmatterError) as exc_info:
            parse_skill_frontmatter(SKILL_PATH, text)

        #: Then
        assert exc_info.value.path == SKILL_PATH, 'the error names the file whose block is not a mapping'

    @pytest.mark.parametrize(
        'name',
        [
            pytest.param('PDF-Processing', id='uppercase'),
            pytest.param('-pdf', id='leading-hyphen'),
            pytest.param('pdf-', id='trailing-hyphen'),
            pytest.param('pdf--processing', id='consecutive-hyphens'),
            pytest.param('a' * 65, id='too-long'),
        ],
    )
    def test_parse_skill_frontmatter_with_an_invalid_name_raises_invalid_skill_frontmatter(self, name: str) -> None:
        #: Given
        text = f'---\nname: {name}\ndescription: Does a thing.\n---\n'

        #: When
        with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
            parse_skill_frontmatter(SKILL_PATH, text)

        #: Then
        assert any(problem.startswith('name:') for problem in exc_info.value.problems), (
            f'the name field is reported, got {exc_info.value}'
        )

    def test_parse_skill_frontmatter_without_a_description_raises_invalid_skill_frontmatter(self) -> None:
        #: Given
        text = '---\nname: pdf-processing\n---\n'

        #: When
        with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
            parse_skill_frontmatter(SKILL_PATH, text)

        #: Then
        assert any(problem.startswith('description:') for problem in exc_info.value.problems), (
            f'the missing description is reported, got {exc_info.value}'
        )

    def test_parse_skill_frontmatter_with_a_description_over_the_limit_raises_invalid_skill_frontmatter(self) -> None:
        #: Given
        text = f'---\nname: pdf-processing\ndescription: {"x" * 1025}\n---\n'

        #: When
        with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
            parse_skill_frontmatter(SKILL_PATH, text)

        #: Then
        assert any(problem.startswith('description:') for problem in exc_info.value.problems), (
            f'the long description is reported, got {exc_info.value}'
        )

    def test_parse_skill_frontmatter_with_an_unquoted_metadata_number_raises_invalid_skill_frontmatter(self) -> None:
        #: Given
        text = '---\nname: pdf-processing\ndescription: Does a thing.\nmetadata:\n  version: 1.0\n---\n'

        #: When
        with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
            parse_skill_frontmatter(SKILL_PATH, text)

        #: Then
        assert any(problem.startswith('metadata.version:') for problem in exc_info.value.problems), (
            f'a YAML float is not coerced, got {exc_info.value}'
        )

    def test_parse_skill_frontmatter_with_a_field_outside_the_specification_raises_invalid_skill_frontmatter(
        self,
    ) -> None:
        #: Given
        text = '---\nname: pdf-processing\ndescription: Does a thing.\nargument-hint: <file>\n---\n'

        #: When
        with pytest.raises(InvalidSkillFrontmatterError) as exc_info:
            parse_skill_frontmatter(SKILL_PATH, text)

        #: Then
        assert any(problem.startswith('argument-hint:') for problem in exc_info.value.problems), (
            f'the unknown field is reported, got {exc_info.value}'
        )
