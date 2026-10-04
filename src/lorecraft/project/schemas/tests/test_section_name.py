"""The section name: what it keeps, what it refuses and how it prints, and how pydantic reads one."""

from typing import Final

import pytest
from pydantic import TypeAdapter, ValidationError

from ..section_name import EmptySectionNameError, MultilineSectionNameError, PaddedSectionNameError, SectionName

ADAPTER: Final[TypeAdapter[SectionName]] = TypeAdapter(SectionName)


@pytest.mark.unit
class TestSectionName:
    def test_parse_with_heading_text_keeps_it_with_its_inner_spaces(self) -> None:
        #: Given
        raw = 'Table of Contents'

        #: When
        name = SectionName.parse(raw)

        #: Then
        assert name.value == raw, f'whitespace inside a name is part of the heading text, got {name.value!r}'

    def test_parse_with_one_character_keeps_it(self) -> None:
        #: Given
        raw = 'A'

        #: When
        name = SectionName.parse(raw)

        #: Then
        assert name.value == raw, f'a single character starts and ends the name, got {name.value!r}'

    def test_parse_with_an_empty_name_raises_empty_section_name_error(self) -> None:
        #: Given
        raw = ''

        #: When
        with pytest.raises(EmptySectionNameError) as exc_info:
            SectionName.parse(raw)

        #: Then
        assert str(exc_info.value) == 'must not be empty', f'the message names the rule, got {exc_info.value}'

    def test_parse_with_a_leading_space_raises_padded_section_name_error(self) -> None:
        #: Given
        raw = ' Checklist'

        #: When
        with pytest.raises(PaddedSectionNameError) as exc_info:
            SectionName.parse(raw)

        #: Then
        assert exc_info.value.name == raw, 'the error keeps the rejected name'
        assert repr(raw) in str(exc_info.value), f'the message quotes the name, padding visible, got {exc_info.value}'

    def test_parse_with_a_trailing_tab_raises_padded_section_name_error(self) -> None:
        #: Given
        raw = 'Changelog\t'

        #: When
        with pytest.raises(PaddedSectionNameError) as exc_info:
            SectionName.parse(raw)

        #: Then
        assert exc_info.value.name == raw, 'a heading never ends in whitespace, so no name may'

    def test_parse_with_a_trailing_line_feed_raises_padded_section_name_error(self) -> None:
        #: Given
        raw = 'Checklist\n'

        #: When
        with pytest.raises(PaddedSectionNameError) as exc_info:
            SectionName.parse(raw)

        #: Then
        assert exc_info.value.name == raw, 'a final line feed is whitespace at the end'

    def test_parse_with_a_line_feed_inside_raises_multiline_section_name_error(self) -> None:
        #: Given
        raw = 'Check\nlist'

        #: When
        with pytest.raises(MultilineSectionNameError) as exc_info:
            SectionName.parse(raw)

        #: Then
        assert exc_info.value.name == raw, 'a name is one line, as the JSON Schema pattern states'

    def test_parse_with_a_carriage_return_inside_raises_multiline_section_name_error(self) -> None:
        #: Given
        # the Markdown parser ends a heading at a carriage return, so the name could match only its first line
        raw = 'Change\rlog'

        #: When
        with pytest.raises(MultilineSectionNameError) as exc_info:
            SectionName.parse(raw)

        #: Then
        assert exc_info.value.name == raw, 'a carriage return breaks a line as a line feed does'

    def test_parse_with_a_form_feed_inside_raises_multiline_section_name_error(self) -> None:
        #: Given
        # the JSON Schema pattern lets a form feed through, but the Markdown parser ends a heading at it
        raw = 'Change\x0clog'

        #: When
        with pytest.raises(MultilineSectionNameError) as exc_info:
            SectionName.parse(raw)

        #: Then
        assert exc_info.value.name == raw, 'every line break the parser splits on is refused, not just the common ones'

    def test_parse_with_only_spaces_raises_padded_section_name_error(self) -> None:
        #: Given
        raw = '   '

        #: When
        with pytest.raises(PaddedSectionNameError) as exc_info:
            SectionName.parse(raw)

        #: Then
        assert exc_info.value.name == raw, 'a name of whitespace alone is padding around nothing'

    def test_construction_with_a_padded_name_raises_padded_section_name_error(self) -> None:
        #: Given
        raw = 'Checklist '

        #: When
        with pytest.raises(PaddedSectionNameError) as exc_info:
            SectionName(raw)

        #: Then
        assert exc_info.value.name == raw, 'direct construction checks the name as parsing does'

    def test_str_with_inner_spaces_returns_the_name_exactly(self) -> None:
        #: Given
        name = SectionName('Code References')

        #: When
        text = str(name)

        #: Then
        assert text == 'Code References', f'a name interpolates as its heading text, got {text!r}'


@pytest.mark.unit
class TestSectionNameAsPydanticType:
    def test_validate_json_with_a_number_raises_pydantics_string_type_error(self) -> None:
        #: Given
        text = '1'

        #: When
        with pytest.raises(ValidationError) as exc_info:
            ADAPTER.validate_json(text)

        #: Then
        errors = exc_info.value.errors()
        assert len(errors) == 1, f'one error is reported, got {errors}'
        assert errors[0]['type'] == 'string_type', 'a number is not a name'
        assert errors[0]['msg'] == 'Input should be a valid string', 'the message is the one pydantic gives'

    def test_validate_json_with_a_padded_name_raises_the_value_objects_rejection_as_a_validation_error(self) -> None:
        #: Given
        text = '" Checklist"'

        #: When
        with pytest.raises(ValidationError) as exc_info:
            ADAPTER.validate_json(text)

        #: Then
        errors = exc_info.value.errors()
        assert len(errors) == 1, f'one error is reported, got {errors}'
        assert errors[0]['type'] == 'section_name', 'the rejection is reported under its own error type'
        assert errors[0]['msg'] == str(PaddedSectionNameError(' Checklist')), 'the message is the rejection exactly'

    def test_validate_json_with_braces_in_a_rejected_name_keeps_them_in_the_message(self) -> None:
        #: Given
        text = '"{name} "'

        #: When
        with pytest.raises(ValidationError) as exc_info:
            ADAPTER.validate_json(text)

        #: Then
        errors = exc_info.value.errors()
        assert len(errors) == 1, f'one error is reported, got {errors}'
        assert errors[0]['msg'] == str(PaddedSectionNameError('{name} ')), (
            f'the name sits in the context, not the template, so pydantic leaves its braces alone, got {errors}'
        )

    def test_validate_json_with_a_name_returns_the_value_object(self) -> None:
        #: Given
        text = '"Checklist"'

        #: When
        name = ADAPTER.validate_json(text)

        #: Then
        assert name == SectionName('Checklist'), 'the string is parsed into the value object'

    def test_validate_python_with_an_instance_returns_it_unchanged(self) -> None:
        #: Given
        name = SectionName('Checklist')

        #: When
        validated = ADAPTER.validate_python(name)

        #: Then
        assert validated is name, 'an instance is taken as it is'

    def test_dump_python_in_json_mode_returns_the_string(self) -> None:
        #: Given
        name = SectionName('Checklist')

        #: When
        dumped = ADAPTER.dump_python(name, mode='json')

        #: Then
        assert dumped == 'Checklist', f'the value object serializes back to its string, got {dumped!r}'

    def test_json_schema_of_the_type_states_its_rule(self) -> None:
        #: Given
        expected = {'type': 'string', 'minLength': 1, 'pattern': SectionName.PATTERN}

        #: When
        schema = ADAPTER.json_schema()

        #: Then
        assert schema == expected, f'the schema states the rule the value object checks, got {schema}'
