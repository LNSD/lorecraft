"""The number values: what each keeps, what it refuses and how it prints, and how pydantic reads a non-zero one."""

from typing import Final

import pytest
from pydantic import TypeAdapter, ValidationError

from ..num import NegativeIntError, NonPositiveIntError, NonZeroUnsignedInt, UnsignedInt

ADAPTER: Final[TypeAdapter[NonZeroUnsignedInt]] = TypeAdapter(NonZeroUnsignedInt)


@pytest.mark.unit
class TestNonZeroUnsignedInt:
    def test_parse_with_one_keeps_it(self) -> None:
        #: Given
        raw = 1

        #: When
        number = NonZeroUnsignedInt.parse(raw)

        #: Then
        assert number.value == 1, f'1 is the smallest number the type holds, got {number.value}'

    def test_parse_with_zero_raises_non_non_zero_unsigned_int(self) -> None:
        #: Given
        raw = 0

        #: When
        with pytest.raises(NonPositiveIntError) as exc_info:
            NonZeroUnsignedInt.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the rejected zero'
        assert str(raw) in str(exc_info.value), f'the message names the rejected zero, got {exc_info.value}'
        assert str(NonZeroUnsignedInt.MINIMUM) in str(exc_info.value), (
            f'the message names the bound, got {exc_info.value}'
        )

    def test_parse_with_a_negative_number_raises_non_non_zero_unsigned_int(self) -> None:
        #: Given
        raw = -1

        #: When
        with pytest.raises(NonPositiveIntError) as exc_info:
            NonZeroUnsignedInt.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the rejected negative number'
        assert str(raw) in str(exc_info.value), f'the message names the rejected number, got {exc_info.value}'

    def test_construction_with_zero_raises_non_non_zero_unsigned_int(self) -> None:
        #: Given
        raw = 0

        #: When
        with pytest.raises(NonPositiveIntError) as exc_info:
            NonZeroUnsignedInt(raw)

        #: Then
        assert exc_info.value.value == raw, 'direct construction checks the number as parsing does'

    def test_minimum_of_the_type_is_one(self) -> None:
        #: Given
        smallest = NonZeroUnsignedInt.MINIMUM

        #: When
        number = NonZeroUnsignedInt(smallest)

        #: Then
        assert smallest == 1, f'the smallest number the type holds is 1, got {smallest}'
        assert number.value == smallest, 'the minimum is itself a valid number'

    def test_str_with_a_three_digit_number_returns_its_digits(self) -> None:
        #: Given
        number = NonZeroUnsignedInt(250)

        #: When
        text = str(number)

        #: Then
        assert text == '250', f'a number interpolates as its digits, got {text!r}'


@pytest.mark.unit
class TestNonZeroUnsignedIntAsPydanticType:
    def test_validate_json_with_a_boolean_raises_pydantics_int_type_error(self) -> None:
        #: Given
        text = 'true'

        #: When
        with pytest.raises(ValidationError) as exc_info:
            ADAPTER.validate_json(text)

        #: Then
        errors = exc_info.value.errors()
        assert len(errors) == 1, f'one error is reported, got {errors}'
        assert errors[0]['type'] == 'int_type', 'a boolean is not a number, though Python takes it as an integer'
        assert errors[0]['msg'] == 'Input should be a valid integer', 'the message is the one pydantic gives'

    def test_validate_json_with_a_float_raises_pydantics_int_type_error(self) -> None:
        #: Given
        text = '1.0'

        #: When
        with pytest.raises(ValidationError) as exc_info:
            ADAPTER.validate_json(text)

        #: Then
        errors = exc_info.value.errors()
        assert len(errors) == 1, f'one error is reported, got {errors}'
        assert errors[0]['type'] == 'int_type', 'a number with a fraction is not a whole number, even a whole one'
        assert errors[0]['msg'] == 'Input should be a valid integer', 'the message is the one pydantic gives'

    def test_validate_json_with_a_string_raises_pydantics_int_type_error(self) -> None:
        #: Given
        text = '"1"'

        #: When
        with pytest.raises(ValidationError) as exc_info:
            ADAPTER.validate_json(text)

        #: Then
        errors = exc_info.value.errors()
        assert len(errors) == 1, f'one error is reported, got {errors}'
        assert errors[0]['type'] == 'int_type', 'a string of digits is not a number'
        assert errors[0]['msg'] == 'Input should be a valid integer', 'the message is the one pydantic gives'

    def test_validate_json_with_zero_raises_the_value_objects_rejection_as_a_validation_error(self) -> None:
        #: Given
        text = '0'

        #: When
        with pytest.raises(ValidationError) as exc_info:
            ADAPTER.validate_json(text)

        #: Then
        errors = exc_info.value.errors()
        assert len(errors) == 1, f'one error is reported, got {errors}'
        assert errors[0]['type'] == 'non_zero_unsigned_int', 'the rejection is reported under its own error type'
        assert errors[0]['msg'] == str(NonPositiveIntError(0)), 'the message is the rejection exactly'

    def test_validate_json_with_an_integer_returns_the_value_object(self) -> None:
        #: Given
        text = '250'

        #: When
        number = ADAPTER.validate_json(text)

        #: Then
        assert number == NonZeroUnsignedInt(250), 'the integer is parsed into the value object'

    def test_validate_python_with_an_instance_returns_it_unchanged(self) -> None:
        #: Given
        number = NonZeroUnsignedInt(250)

        #: When
        validated = ADAPTER.validate_python(number)

        #: Then
        assert validated is number, 'an instance is taken as it is'

    def test_dump_python_in_json_mode_returns_the_integer(self) -> None:
        #: Given
        number = NonZeroUnsignedInt(250)

        #: When
        dumped = ADAPTER.dump_python(number, mode='json')

        #: Then
        assert dumped == 250, f'the value object serializes back to its integer, got {dumped!r}'

    def test_json_schema_of_the_type_states_its_bound(self) -> None:
        #: Given
        expected = {'type': 'integer', 'minimum': NonZeroUnsignedInt.MINIMUM}

        #: When
        schema = ADAPTER.json_schema()

        #: Then
        assert schema == expected, f'the schema states the bound the value object checks, got {schema}'


@pytest.mark.unit
class TestUnsignedInt:
    def test_parse_with_zero_keeps_it(self) -> None:
        #: Given
        raw = 0

        #: When
        number = UnsignedInt.parse(raw)

        #: Then
        assert number.value == 0, f'0 is the smallest number the type holds, got {number.value}'

    def test_parse_with_a_negative_number_raises_negative_int(self) -> None:
        #: Given
        raw = -1

        #: When
        with pytest.raises(NegativeIntError) as exc_info:
            UnsignedInt.parse(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the rejected negative number'
        assert str(raw) in str(exc_info.value), f'the message names the rejected number, got {exc_info.value}'
        assert str(UnsignedInt.MINIMUM) in str(exc_info.value), f'the message names the bound, got {exc_info.value}'

    def test_construction_with_a_negative_number_raises_negative_int(self) -> None:
        #: Given
        raw = -1

        #: When
        with pytest.raises(NegativeIntError) as exc_info:
            UnsignedInt(raw)

        #: Then
        assert exc_info.value.value == raw, 'direct construction checks the number as parsing does'

    def test_minimum_of_the_type_is_zero(self) -> None:
        #: Given
        smallest = UnsignedInt.MINIMUM

        #: When
        number = UnsignedInt(smallest)

        #: Then
        assert smallest == 0, f'the smallest number the type holds is 0, got {smallest}'
        assert number.value == smallest, 'the minimum is itself a valid number'

    def test_str_with_a_three_digit_number_returns_its_digits(self) -> None:
        #: Given
        number = UnsignedInt(250)

        #: When
        text = str(number)

        #: Then
        assert text == '250', f'a number interpolates as its digits, got {text!r}'
