"""What a JSON Schema states that tells a reader how to write a field, read defensively from plain data."""

import pytest

from ..frontmatter_problem import FieldGuidance, JsonType
from ..schema_guidance import json_type_of, known_fields, property_guidance, schema_guidance, schema_reason, value_text


@pytest.mark.unit
class TestValueText:
    def test_value_text_with_a_plain_string_returns_it_as_it_is(self) -> None:
        #: Given
        value = 'pdf'

        #: When
        text = value_text(value)

        #: Then
        assert text == 'pdf', 'a string the reader decodes as itself needs no quotes'

    def test_value_text_with_a_string_read_as_a_float_returns_it_quoted(self) -> None:
        #: Given
        value = '1.0'

        #: When
        text = value_text(value)

        #: Then
        assert text == '"1.0"', 'unquoted, the reader would decode the string as a number, which the schema rejects'

    def test_value_text_with_a_string_read_as_a_boolean_returns_it_quoted(self) -> None:
        #: Given
        value = 'true'

        #: When
        text = value_text(value)

        #: Then
        assert text == '"true"', 'unquoted, the reader would decode the string as a boolean, which the schema rejects'

    def test_value_text_with_an_octal_string_returns_it_quoted(self) -> None:
        #: Given
        value = '0o17'

        #: When
        text = value_text(value)

        #: Then
        assert text == '"0o17"', 'unquoted, the reader would decode the string as the integer 15'

    def test_value_text_with_an_exponent_string_returns_it_quoted(self) -> None:
        #: Given
        value = '1e3'

        #: When
        text = value_text(value)

        #: Then
        assert text == '"1e3"', 'unquoted, the reader would decode the string as the float 1000.0'

    def test_value_text_with_an_empty_string_returns_it_quoted(self) -> None:
        #: Given
        value = ''

        #: When
        text = value_text(value)

        #: Then
        assert text == '""', 'unquoted, an empty string would decode as nothing at all'

    def test_value_text_with_a_string_that_is_not_yaml_returns_it_quoted(self) -> None:
        #: Given
        value = '[unclosed'

        #: When
        text = value_text(value)

        #: Then
        assert text == '"[unclosed"', 'unquoted, the text would make the frontmatter invalid YAML'

    def test_value_text_with_a_list_returns_it_as_json(self) -> None:
        #: Given
        value = ['a', 1, None]

        #: When
        text = value_text(value)

        #: Then
        assert text == '["a", 1, null]', 'any value but a string is written as JSON, which YAML reads as itself'

    def test_value_text_with_a_non_ascii_character_keeps_it(self) -> None:
        #: Given
        value = {'k': 'é'}

        #: When
        text = value_text(value)

        #: Then
        assert text == '{"k": "é"}', 'the text is for a reader, so a character is not escaped'


@pytest.mark.unit
class TestJsonTypeOf:
    def test_json_type_of_with_none_returns_null(self) -> None:
        #: Given
        value = None

        #: When
        json_type = json_type_of(value)

        #: Then
        assert json_type is JsonType.NULL, 'None is JSON null'

    def test_json_type_of_with_a_bool_returns_boolean(self) -> None:
        #: Given
        value = True

        #: When
        json_type = json_type_of(value)

        #: Then
        assert json_type is JsonType.BOOLEAN, 'a bool is checked before an int, which it is in Python'

    def test_json_type_of_with_an_int_returns_integer(self) -> None:
        #: Given
        value = 3

        #: When
        json_type = json_type_of(value)

        #: Then
        assert json_type is JsonType.INTEGER, 'an int is a JSON integer'

    def test_json_type_of_with_a_float_returns_number(self) -> None:
        #: Given
        value = 1.5

        #: When
        json_type = json_type_of(value)

        #: Then
        assert json_type is JsonType.NUMBER, 'a float is a JSON number'

    def test_json_type_of_with_a_str_returns_string(self) -> None:
        #: Given
        value = 'text'

        #: When
        json_type = json_type_of(value)

        #: Then
        assert json_type is JsonType.STRING, 'a str is a JSON string'

    def test_json_type_of_with_a_list_returns_array(self) -> None:
        #: Given
        value = [1]

        #: When
        json_type = json_type_of(value)

        #: Then
        assert json_type is JsonType.ARRAY, 'a list is a JSON array'

    def test_json_type_of_with_a_tuple_returns_array(self) -> None:
        #: Given
        value = (1,)

        #: When
        json_type = json_type_of(value)

        #: Then
        assert json_type is JsonType.ARRAY, 'a tuple is a JSON array'

    def test_json_type_of_with_a_mapping_returns_object(self) -> None:
        #: Given
        value = {'k': 'v'}

        #: When
        json_type = json_type_of(value)

        #: Then
        assert json_type is JsonType.OBJECT, 'a mapping is a JSON object'

    def test_json_type_of_with_a_value_json_cannot_hold_raises_assertion_error(self) -> None:
        #: Given
        value = object()

        #: When
        with pytest.raises(AssertionError):
            json_type_of(value)


@pytest.mark.unit
class TestSchemaGuidance:
    def test_schema_guidance_with_a_schema_that_is_not_an_object_states_nothing(self) -> None:
        #: Given
        schema = True

        #: When
        guidance = schema_guidance(schema)

        #: Then
        assert guidance == FieldGuidance(), 'a boolean schema states nothing'

    def test_schema_guidance_with_a_schema_without_keywords_states_nothing(self) -> None:
        #: Given
        schema: dict[str, object] = {}

        #: When
        guidance = schema_guidance(schema)

        #: Then
        assert guidance == FieldGuidance(), 'a keyword left out reads as nothing stated'

    def test_schema_guidance_with_description_examples_and_enum_reads_them(self) -> None:
        #: Given
        schema = {'description': 'What it is', 'examples': ['a', 'b'], 'enum': ['a', 'b']}

        #: When
        guidance = schema_guidance(schema)

        #: Then
        assert guidance == FieldGuidance(description='What it is', example='a', allowed=('a', 'b')), (
            'the first example is the example, and the enum is the allowed values'
        )

    def test_schema_guidance_with_a_const_returns_it_as_the_allowed_value_and_the_example(self) -> None:
        #: Given
        schema = {'const': 'x'}

        #: When
        guidance = schema_guidance(schema)

        #: Then
        assert guidance == FieldGuidance(example='x', allowed=('x',)), 'the one value allowed is also a sample of it'

    def test_schema_guidance_with_a_const_and_examples_prefers_the_first_example(self) -> None:
        #: Given
        schema = {'const': 'x', 'examples': ['y']}

        #: When
        guidance = schema_guidance(schema)

        #: Then
        assert guidance == FieldGuidance(example='y', allowed=('x',)), 'the schema states its example'

    def test_schema_guidance_with_a_description_that_is_not_a_string_ignores_it(self) -> None:
        #: Given
        schema = {'description': 3}

        #: When
        guidance = schema_guidance(schema)

        #: Then
        assert guidance == FieldGuidance(), 'a description that is not text states nothing'

    def test_schema_guidance_with_an_enum_that_is_not_a_list_ignores_it(self) -> None:
        #: Given
        schema = {'enum': 'ab'}

        #: When
        guidance = schema_guidance(schema)

        #: Then
        assert guidance == FieldGuidance(), 'an enum that is not a list allows nothing in particular'

    def test_schema_guidance_with_empty_examples_gives_no_example(self) -> None:
        #: Given
        schema: dict[str, object] = {'examples': []}

        #: When
        guidance = schema_guidance(schema)

        #: Then
        assert guidance == FieldGuidance(), 'an empty list holds no first example'


@pytest.mark.unit
class TestPropertyGuidance:
    def test_property_guidance_with_a_named_property_reads_it(self) -> None:
        #: Given
        schema = {'properties': {'name': {'description': 'The name'}}}

        #: When
        guidance = property_guidance(schema, 'name')

        #: Then
        assert guidance == FieldGuidance(description='The name'), 'the property is read as a schema'

    def test_property_guidance_with_a_missing_property_states_nothing(self) -> None:
        #: Given
        schema: dict[str, object] = {'properties': {}}

        #: When
        guidance = property_guidance(schema, 'name')

        #: Then
        assert guidance == FieldGuidance(), 'a property the schema lacks states nothing'

    def test_property_guidance_with_a_schema_that_is_not_an_object_states_nothing(self) -> None:
        #: Given
        schema = ['properties']

        #: When
        guidance = property_guidance(schema, 'name')

        #: Then
        assert guidance == FieldGuidance(), 'a schema that is not an object has no properties'


@pytest.mark.unit
class TestKnownFields:
    def test_known_fields_with_properties_lists_them_in_the_order_stated(self) -> None:
        #: Given
        schema = {'properties': {'b': {}, 'a': {}}}

        #: When
        fields = known_fields(schema)

        #: Then
        assert fields == ('b', 'a'), 'the order the schema states them is kept'

    def test_known_fields_with_a_schema_without_properties_names_none(self) -> None:
        #: Given
        schema = {'type': 'object'}

        #: When
        fields = known_fields(schema)

        #: Then
        assert fields == (), 'a schema without properties names no field'

    def test_known_fields_with_properties_that_are_not_an_object_names_none(self) -> None:
        #: Given
        schema = {'properties': ['a']}

        #: When
        fields = known_fields(schema)

        #: Then
        assert fields == (), 'properties that are not an object name no field'

    def test_known_fields_with_a_schema_that_is_not_an_object_names_none(self) -> None:
        #: Given
        schema = False

        #: When
        fields = known_fields(schema)

        #: Then
        assert fields == (), 'a boolean schema names no field'


@pytest.mark.unit
class TestSchemaReason:
    def test_schema_reason_with_a_comment_returns_it(self) -> None:
        #: Given
        schema = {'$comment': 'because'}

        #: When
        reason = schema_reason(schema)

        #: Then
        assert reason == 'because', 'the comment is the reason, as written'

    def test_schema_reason_with_a_comment_that_is_not_a_string_ignores_it(self) -> None:
        #: Given
        schema = {'$comment': 3}

        #: When
        reason = schema_reason(schema)

        #: Then
        assert reason is None, 'a comment that is not text states no reason'

    def test_schema_reason_with_a_schema_without_a_comment_states_none(self) -> None:
        #: Given
        schema: dict[str, object] = {}

        #: When
        reason = schema_reason(schema)

        #: Then
        assert reason is None, 'a schema owes a reader no reason'

    def test_schema_reason_with_a_schema_that_is_not_an_object_states_none(self) -> None:
        #: Given
        schema = True

        #: When
        reason = schema_reason(schema)

        #: Then
        assert reason is None, 'a boolean schema states no reason'
