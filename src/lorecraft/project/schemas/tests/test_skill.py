"""The Agent Skills specification as a frontmatter schema: each way a decoded frontmatter falls short of it is one
problem, in Lorecraft's words, on the field it concerns."""

import pytest

from ..frontmatter_problem import (
    InvalidValueProblem,
    MissingFieldProblem,
    NonStringKeyProblem,
    NotAStringMappingProblem,
    NotAStringProblem,
    UnknownFieldProblem,
)
from ..skill import SKILL_FRONTMATTER_SCHEMA


@pytest.mark.unit
class TestSkillFrontmatterSchemaValidate:
    def test_validate_with_every_field_returns_no_problems(self) -> None:
        #: Given
        data: dict[object, object] = {
            'name': 'pdf-processing',
            'description': 'Extract PDF text, fill forms, merge files. Use when handling PDFs.',
            'license': 'Apache-2.0',
            'compatibility': 'Requires Python 3.14+ and uv',
            'metadata': {'author': 'example-org', 'version': '1.0'},
            'allowed-tools': 'Bash(git add *) Read',
        }

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (), 'a frontmatter with every field, each valid, conforms'

    def test_validate_without_the_required_fields_returns_one_missing_problem_each(self) -> None:
        #: Given
        data: dict[object, object] = {}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (
            MissingFieldProblem('name', '`name` is required'),
            MissingFieldProblem('description', '`description` is required'),
        ), 'each required field is its own problem, in the order the specification declares them'

    def test_validate_with_a_field_outside_the_specification_returns_an_unknown_field_problem(self) -> None:
        #: Given
        data: dict[object, object] = {'name': 'review', 'description': 'Review code.', 'model': 'opus'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (
            UnknownFieldProblem(
                'model',
                '`model` is not a field of the Agent Skills specification',
            ),
        ), 'a field the specification does not define is named'

    def test_validate_with_a_key_that_is_not_a_string_returns_a_non_string_key_problem(self) -> None:
        #: Given
        data: dict[object, object] = {'name': 'review', 'description': 'Review code.', 123: 'x'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (
            NonStringKeyProblem('a key that is not a string is not a field of the Agent Skills specification'),
        ), 'a key that is not a string names no field'

    def test_validate_with_a_name_that_is_not_a_string_returns_a_not_a_string_problem(self) -> None:
        #: Given
        data: dict[object, object] = {'name': None, 'description': 'Review code.'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (NotAStringProblem('name'),), (
            'a field written with no value is null, which a required string field does not accept'
        )

    def test_validate_with_metadata_that_is_not_a_mapping_returns_a_not_a_string_mapping_problem(self) -> None:
        #: Given
        data: dict[object, object] = {'name': 'review', 'description': 'Review code.', 'metadata': 'author'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (NotAStringMappingProblem('metadata'),), 'metadata is a mapping, not a string'

    def test_validate_with_an_unquoted_metadata_number_returns_an_invalid_value_problem(self) -> None:
        #: Given
        data: dict[object, object] = {'name': 'review', 'description': 'Review code.', 'metadata': {'version': 1.0}}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (InvalidValueProblem('metadata', '`metadata.version` must be a string'),), (
            'a value inside metadata is named by its path, and makes the metadata field invalid'
        )

    def test_validate_with_a_metadata_key_that_is_not_a_string_returns_an_invalid_value_problem(self) -> None:
        #: Given
        data: dict[object, object] = {'name': 'review', 'description': 'Review code.', 'metadata': {1: 'one'}}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (InvalidValueProblem('metadata', '`metadata` keys must be strings'),), (
            'a key inside metadata is at fault, not a value'
        )

    def test_validate_with_an_empty_name_returns_the_value_objects_own_message(self) -> None:
        #: Given
        data: dict[object, object] = {'name': '', 'description': 'Review code.'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (InvalidValueProblem('name', 'skill name cannot be empty'),), (
            'an empty name is worded by SkillName, not by pydantic'
        )

    def test_validate_with_a_name_over_64_characters_returns_the_value_objects_own_message(self) -> None:
        #: Given
        name = 'a' * 65
        data: dict[object, object] = {'name': name, 'description': 'Review code.'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (
            InvalidValueProblem(
                'name',
                f'skill name {name!r} is 65 characters; the limit is 64',
            ),
        ), 'a name over the length limit is worded by SkillName, not by pydantic'

    def test_validate_with_an_uppercase_name_returns_the_value_objects_own_message(self) -> None:
        #: Given
        data: dict[object, object] = {'name': 'PDF', 'description': 'Review code.'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (
            InvalidValueProblem(
                'name',
                "skill name 'PDF' must be lowercase letters, digits and single hyphens, "
                'neither starting nor ending with a hyphen',
            ),
        ), 'a name outside the allowed format is worded by SkillName, not by pydantic'

    def test_validate_with_braces_in_a_rejected_name_returns_the_braces_unformatted(self) -> None:
        #: Given
        data: dict[object, object] = {'name': '{reason}', 'description': 'Review code.'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (
            InvalidValueProblem(
                'name',
                "skill name '{reason}' must be lowercase letters, digits and single hyphens, "
                'neither starting nor ending with a hyphen',
            ),
        ), 'pydantic formats the template once, so braces in the rejected text reach the reader as written'

    def test_validate_with_a_description_over_the_limit_returns_an_invalid_value_problem(self) -> None:
        #: Given
        data: dict[object, object] = {'name': 'review', 'description': 'x' * 1025}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (
            InvalidValueProblem(
                'description',
                'skill description is 1025 characters; the limit is 1024',
            ),
        ), 'the length limit is worded by SkillDescription'

    def test_validate_with_a_blank_compatibility_returns_an_invalid_value_problem(self) -> None:
        #: Given
        data: dict[object, object] = {'name': 'review', 'description': 'Review code.', 'compatibility': ' '}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (
            InvalidValueProblem(
                'compatibility',
                'skill compatibility cannot be empty; leave the field out instead',
            ),
        ), 'a blank note is worded by SkillCompatibility'

    def test_validate_with_allowed_tools_spelt_with_an_underscore_returns_an_unknown_field_problem(self) -> None:
        #: Given
        data: dict[object, object] = {'name': 'review', 'description': 'Review code.', 'allowed_tools': 'Read'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(data)

        #: Then
        assert problems == (
            UnknownFieldProblem(
                'allowed_tools',
                '`allowed_tools` is not a field of the Agent Skills specification',
            ),
        ), 'the field is read by its alias only, as the specification spells it'
