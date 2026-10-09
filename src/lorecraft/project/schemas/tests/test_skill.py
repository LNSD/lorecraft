"""The Agent Skills specification as a frontmatter schema.

Each way a decoded frontmatter falls short of it is one problem, in Lorecraft's words, on the field it concerns.
"""

from typing import Final

import pytest

from lorecraft.core.mapping import FrozenMapping

from ..frontmatter_problem import (
    FieldGuidance,
    InvalidValueProblem,
    JsonType,
    MissingFieldProblem,
    OtherValueConstraint,
    PatternMismatch,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from ..skill import SKILL_FRONTMATTER_SCHEMA
from ..skill_frontmatter import SKILL_NAME_PATTERN

NAME_GUIDANCE: Final[FieldGuidance] = FieldGuidance(
    description=(
        "The skill's name: lowercase letters, digits and hyphens, neither starting nor ending with a hyphen and "
        'never two in a row. It must match the name of the directory the skill sits in.'
    ),
    example='pdf-processing',
)
"""What the specification states about `name`, unwrapped into one line."""

DESCRIPTION_GUIDANCE: Final[FieldGuidance] = FieldGuidance(
    description='What the skill does and when to use it, with the keywords that let an agent match it to a task.',
    example=(
        'Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working'
        ' with PDF documents or when the user mentions PDFs, forms, or document extraction.'
    ),
)
"""What the specification states about `description`."""

COMPATIBILITY_GUIDANCE: Final[FieldGuidance] = FieldGuidance(
    description=(
        'The environment the skill needs: the product it is meant for, the system packages it runs, or network '
        'access. Most skills need none, and leave it out.'
    ),
    example='Designed for Claude Code (or similar products)',
)
"""What the specification states about `compatibility`."""

METADATA_GUIDANCE: Final[FieldGuidance] = FieldGuidance(
    description=(
        'Properties the specification does not define, for clients to read: string keys to string values, so a '
        "number is quoted. Keys are best made unique enough not to collide with another client's."
    ),
    example='{"author": "example-org", "version": "1.0"}',
)
"""What the specification states about `metadata`; its example is a mapping, written as JSON."""

SPECIFIED_FIELDS: Final[tuple[str, ...]] = (
    'name',
    'description',
    'license',
    'compatibility',
    'metadata',
    'allowed-tools',
)
"""The fields the specification defines, in the order it declares them."""


@pytest.mark.unit
class TestSkillFrontmatterSchemaValidate:
    def test_validate_with_every_field_returns_no_problems(self) -> None:
        #: Given
        data: dict[str, object] = {
            'name': 'pdf-processing',
            'description': 'Extract PDF text, fill forms, merge files. Use when handling PDFs.',
            'license': 'Apache-2.0',
            'compatibility': 'Requires Python 3.14+ and uv',
            'metadata': {'author': 'example-org', 'version': '1.0'},
            'allowed-tools': 'Bash(git add *) Read',
        }

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (), 'a frontmatter with every field, each valid, conforms'

    def test_validate_without_the_required_fields_returns_one_missing_problem_each(self) -> None:
        #: Given
        data: dict[str, object] = {}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            MissingFieldProblem('name', '`name` is required', guidance=NAME_GUIDANCE),
            MissingFieldProblem('description', '`description` is required', guidance=DESCRIPTION_GUIDANCE),
        ), 'each required field is its own problem, in the order the specification declares them'

    def test_validate_with_a_field_outside_the_specification_returns_an_unknown_field_problem(self) -> None:
        #: Given
        data: dict[str, object] = {'name': 'review', 'description': 'Review code.', 'model': 'opus'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            UnknownFieldProblem(
                'model',
                '`model` is not a field of the Agent Skills specification',
                SPECIFIED_FIELDS,
            ),
        ), 'a field the specification does not define is named, with the fields it defines'

    def test_validate_with_a_name_that_is_not_a_string_returns_a_wrong_type_problem(self) -> None:
        #: Given
        data: dict[str, object] = {'name': None, 'description': 'Review code.'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            WrongTypeProblem(
                'name', '`name` must be a string', (JsonType.STRING,), JsonType.NULL, guidance=NAME_GUIDANCE
            ),
        ), 'a field written with no value is null, which a required string field does not accept'

    def test_validate_with_metadata_that_is_not_a_mapping_returns_a_wrong_type_problem(self) -> None:
        #: Given
        data: dict[str, object] = {'name': 'review', 'description': 'Review code.', 'metadata': 'author'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            WrongTypeProblem(
                'metadata',
                '`metadata` must be a mapping of strings to strings',
                (JsonType.OBJECT,),
                JsonType.STRING,
                guidance=METADATA_GUIDANCE,
            ),
        ), 'metadata is a mapping, not a string'

    def test_validate_with_an_unquoted_metadata_number_returns_an_invalid_value_problem(self) -> None:
        #: Given
        data: dict[str, object] = {'name': 'review', 'description': 'Review code.', 'metadata': {'version': 1.0}}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            InvalidValueProblem(
                'metadata', '`metadata.version` must be a string', OtherValueConstraint(), guidance=METADATA_GUIDANCE
            ),
        ), 'a value inside metadata is named by its path, and makes the metadata field invalid'

    def test_validate_with_an_empty_name_returns_the_value_objects_own_message(self) -> None:
        #: Given
        data: dict[str, object] = {'name': '', 'description': 'Review code.'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            InvalidValueProblem('name', 'skill name cannot be empty', OtherValueConstraint(), guidance=NAME_GUIDANCE),
        ), 'an empty name is worded by SkillName, not by pydantic'

    def test_validate_with_a_name_over_64_characters_returns_the_value_objects_own_message(self) -> None:
        #: Given
        name = 'a' * 65
        data: dict[str, object] = {'name': name, 'description': 'Review code.'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            InvalidValueProblem(
                'name',
                f'skill name {name!r} is 65 characters; the limit is 64',
                OtherValueConstraint(),
                guidance=NAME_GUIDANCE,
            ),
        ), 'a name over the length limit is worded by SkillName, not by pydantic'

    def test_validate_with_an_uppercase_name_returns_the_value_objects_own_message(self) -> None:
        #: Given
        data: dict[str, object] = {'name': 'PDF', 'description': 'Review code.'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            InvalidValueProblem(
                'name',
                "skill name 'PDF' must be lowercase letters, digits and single hyphens, "
                'neither starting nor ending with a hyphen',
                PatternMismatch(SKILL_NAME_PATTERN),
                guidance=NAME_GUIDANCE,
            ),
        ), 'a name outside the allowed format is worded by SkillName and carries the pattern it breaks'

    def test_validate_with_braces_in_a_rejected_name_returns_the_braces_unformatted(self) -> None:
        #: Given
        data: dict[str, object] = {'name': '{reason}', 'description': 'Review code.'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            InvalidValueProblem(
                'name',
                "skill name '{reason}' must be lowercase letters, digits and single hyphens, "
                'neither starting nor ending with a hyphen',
                PatternMismatch(SKILL_NAME_PATTERN),
                guidance=NAME_GUIDANCE,
            ),
        ), 'pydantic formats the template once, so braces in the rejected text reach the reader as written'

    def test_validate_with_a_description_over_the_limit_returns_an_invalid_value_problem(self) -> None:
        #: Given
        data: dict[str, object] = {'name': 'review', 'description': 'x' * 1025}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            InvalidValueProblem(
                'description',
                'skill description is 1025 characters; the limit is 1024',
                OtherValueConstraint(),
                guidance=DESCRIPTION_GUIDANCE,
            ),
        ), 'the length limit is worded by SkillDescription'

    def test_validate_with_a_blank_compatibility_returns_an_invalid_value_problem(self) -> None:
        #: Given
        data: dict[str, object] = {'name': 'review', 'description': 'Review code.', 'compatibility': ' '}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            InvalidValueProblem(
                'compatibility',
                'skill compatibility cannot be empty; leave the field out instead',
                OtherValueConstraint(),
                guidance=COMPATIBILITY_GUIDANCE,
            ),
        ), 'a blank note is worded by SkillCompatibility'

    def test_validate_with_allowed_tools_spelt_with_an_underscore_returns_an_unknown_field_problem(self) -> None:
        #: Given
        data: dict[str, object] = {'name': 'review', 'description': 'Review code.', 'allowed_tools': 'Read'}

        #: When
        problems = SKILL_FRONTMATTER_SCHEMA.validate(FrozenMapping.from_plain(data))

        #: Then
        assert problems == (
            UnknownFieldProblem(
                'allowed_tools',
                '`allowed_tools` is not a field of the Agent Skills specification',
                SPECIFIED_FIELDS,
            ),
        ), 'the field is read by its alias only, as the specification spells it'
