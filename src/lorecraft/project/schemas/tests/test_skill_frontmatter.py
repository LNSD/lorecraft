"""The skill frontmatter's string fields: each value object keeps valid text as written and refuses every rule it
checks, and as a pydantic type parses a field, refuses an invalid one as a validation error, serializes it back and
renders its rules as JSON Schema."""

import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from ..skill_frontmatter import (
    EmptySkillCompatibilityError,
    EmptySkillDescriptionError,
    EmptySkillNameError,
    InvalidSkillNameFormatError,
    OverlongSkillCompatibilityError,
    OverlongSkillDescriptionError,
    OverlongSkillNameError,
    SkillAllowedTools,
    SkillCompatibility,
    SkillDescription,
    SkillLicense,
    SkillName,
)


class _Named(BaseModel):
    """A model with one skill name field, standing in for any model that uses a value object."""

    model_config = ConfigDict(strict=True)

    name: SkillName


@pytest.mark.unit
class TestSkillName:
    @pytest.mark.parametrize(
        'raw',
        [
            pytest.param('pdf-processing', id='hyphenated'),
            pytest.param('v2', id='letters-and-digits'),
            pytest.param('a' * 64, id='at-the-limit'),
        ],
    )
    def test_parse_with_a_valid_name_keeps_it_as_written(self, raw: str) -> None:
        #: Given
        expected = raw

        #: When
        name = SkillName.parse(raw)

        #: Then
        assert name.value == expected, 'the spelling is kept'

    def test_parse_with_an_empty_name_raises_empty_skill_name(self) -> None:
        #: Given
        raw = ''

        #: When
        with pytest.raises(EmptySkillNameError) as exc_info:
            SkillName.parse(raw)

        #: Then
        assert isinstance(exc_info.value.source, ValidationError), 'the broken rule is kept as the source'

    def test_parse_with_a_name_over_the_limit_raises_skill_name_too_long(self) -> None:
        #: Given
        raw = 'a' * 65

        #: When
        with pytest.raises(OverlongSkillNameError) as exc_info:
            SkillName.parse(raw)

        #: Then
        assert exc_info.value.name == raw, 'the error keeps the rejected name'

    @pytest.mark.parametrize(
        'raw',
        [
            pytest.param('PDF-Processing', id='uppercase'),
            pytest.param('-pdf', id='leading-hyphen'),
            pytest.param('pdf-', id='trailing-hyphen'),
            pytest.param('pdf--processing', id='consecutive-hyphens'),
            pytest.param('pdf_processing', id='underscore'),
            pytest.param('café', id='non-ascii'),
        ],
    )
    def test_parse_with_a_misformed_name_raises_invalid_skill_name_format(self, raw: str) -> None:
        #: Given
        rejected = raw

        #: When
        with pytest.raises(InvalidSkillNameFormatError) as exc_info:
            SkillName.parse(raw)

        #: Then
        assert exc_info.value.name == rejected, 'the error keeps the rejected name'

    def test_json_schema_states_the_name_rules(self) -> None:
        #: Given
        adapter = TypeAdapter(SkillName)

        #: When
        schema = adapter.json_schema()

        #: Then
        assert schema == {
            'type': 'string',
            'minLength': 1,
            'maxLength': 64,
            'pattern': '^[a-z0-9]+(-[a-z0-9]+)*$',
        }, 'the schema states the rules the parser checks'


@pytest.mark.unit
class TestSkillDescription:
    def test_parse_with_a_description_at_the_limit_keeps_it_as_written(self) -> None:
        #: Given
        raw = 'x' * 1024

        #: When
        description = SkillDescription.parse(raw)

        #: Then
        assert description.value == raw, 'the text is kept'

    @pytest.mark.parametrize('raw', [pytest.param('', id='empty'), pytest.param('  \n', id='whitespace')])
    def test_parse_with_a_blank_description_raises_empty_skill_description(self, raw: str) -> None:
        #: Given
        blank = raw

        #: When
        with pytest.raises(EmptySkillDescriptionError) as exc_info:
            SkillDescription.parse(blank)

        #: Then
        assert 'empty' in str(exc_info.value), f'the blank description is reported, got {exc_info.value}'

    def test_parse_with_a_description_over_the_limit_raises_skill_description_too_long(self) -> None:
        #: Given
        raw = 'x' * 1025

        #: When
        with pytest.raises(OverlongSkillDescriptionError) as exc_info:
            SkillDescription.parse(raw)

        #: Then
        assert '1025 characters' in str(exc_info.value), f'the length is reported, got {exc_info.value}'

    def test_json_schema_states_the_description_rules(self) -> None:
        #: Given
        adapter = TypeAdapter(SkillDescription)

        #: When
        schema = adapter.json_schema()

        #: Then
        assert schema == {'type': 'string', 'minLength': 1, 'maxLength': 1024, 'pattern': r'\S'}, (
            'the schema states the rules the parser checks'
        )


@pytest.mark.unit
class TestSkillLicense:
    def test_parse_with_any_text_keeps_it_as_written(self) -> None:
        #: Given
        raw = 'Proprietary. LICENSE.txt has complete terms'

        #: When
        license_ = SkillLicense.parse(raw)

        #: Then
        assert license_.value == raw, 'the text is kept'

    def test_json_schema_is_any_string(self) -> None:
        #: Given
        adapter = TypeAdapter(SkillLicense)

        #: When
        schema = adapter.json_schema()

        #: Then
        assert schema == {'type': 'string'}, 'the specification sets no rule on a license'


@pytest.mark.unit
class TestSkillCompatibility:
    def test_parse_with_a_note_keeps_it_as_written(self) -> None:
        #: Given
        raw = 'Requires Python 3.14+ and uv'

        #: When
        compatibility = SkillCompatibility.parse(raw)

        #: Then
        assert compatibility.value == raw, 'the text is kept'

    def test_parse_with_a_blank_note_raises_empty_skill_compatibility(self) -> None:
        #: Given
        raw = ' \n'

        #: When
        with pytest.raises(EmptySkillCompatibilityError) as exc_info:
            SkillCompatibility.parse(raw)

        #: Then
        assert 'empty' in str(exc_info.value), f'the blank note is reported, got {exc_info.value}'

    def test_parse_with_a_note_over_the_limit_raises_skill_compatibility_too_long(self) -> None:
        #: Given
        raw = 'x' * 501

        #: When
        with pytest.raises(OverlongSkillCompatibilityError) as exc_info:
            SkillCompatibility.parse(raw)

        #: Then
        assert '501 characters' in str(exc_info.value), f'the length is reported, got {exc_info.value}'

    def test_json_schema_states_the_compatibility_rules(self) -> None:
        #: Given
        adapter = TypeAdapter(SkillCompatibility)

        #: When
        schema = adapter.json_schema()

        #: Then
        assert schema == {'type': 'string', 'minLength': 1, 'maxLength': 500, 'pattern': r'\S'}, (
            'the schema states the rules the parser checks'
        )


@pytest.mark.unit
class TestSkillAllowedTools:
    def test_parse_with_rules_holding_spaces_keeps_them_whole(self) -> None:
        #: Given
        raw = 'Bash(git add *) Read'

        #: When
        allowed_tools = SkillAllowedTools.parse(raw)

        #: Then
        assert allowed_tools.value == raw, 'the text is kept whole'

    def test_json_schema_is_any_string(self) -> None:
        #: Given
        adapter = TypeAdapter(SkillAllowedTools)

        #: When
        schema = adapter.json_schema()

        #: Then
        assert schema == {'type': 'string'}, 'the specification sets no rule on allowed-tools'


@pytest.mark.unit
class TestSkillValuePydanticType:
    def test_model_validate_with_a_valid_string_returns_the_value_object(self) -> None:
        #: Given
        data = {'name': 'pdf-processing'}

        #: When
        model = _Named.model_validate(data)

        #: Then
        assert model.name == SkillName('pdf-processing'), 'the string is parsed into a skill name'

    def test_model_validate_with_an_invalid_string_raises_one_validation_error_with_its_message(self) -> None:
        #: Given
        # braces in the rejected name must reach the message as written, not be read as a template
        data = {'name': '{pdf}'}

        #: When
        with pytest.raises(ValidationError) as exc_info:
            _Named.model_validate(data)

        #: Then
        messages = [error['msg'] for error in exc_info.value.errors()]
        assert messages == [
            "skill name '{pdf}' must be lowercase letters, digits and single hyphens, "
            'neither starting nor ending with a hyphen'
        ], 'one error, the name message, braces kept'

    def test_model_validate_with_a_non_string_raises_a_validation_error(self) -> None:
        #: Given
        data = {'name': 42}

        #: When
        with pytest.raises(ValidationError) as exc_info:
            _Named.model_validate(data)

        #: Then
        assert [error['type'] for error in exc_info.value.errors()] == ['string_type'], 'a number is not text'

    def test_model_dump_serializes_the_value_object_as_its_string(self) -> None:
        #: Given
        model = _Named(name=SkillName('pdf-processing'))

        #: When
        dumped = model.model_dump(mode='json')

        #: Then
        assert dumped == {'name': 'pdf-processing'}, 'the value object serializes back to its string'
