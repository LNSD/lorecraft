"""The number values: what each keeps, what it refuses and how it prints, and how pydantic reads a non-zero one."""

from typing import Final

import pytest
from pydantic import TypeAdapter, ValidationError

from ..num import NegativeIntError, NonPositiveIntError, NonZeroUnsignedInt, UnsignedInt

ADAPTER: Final[TypeAdapter[NonZeroUnsignedInt]] = TypeAdapter(NonZeroUnsignedInt)


@pytest.mark.unit
class TestNonZeroUnsignedInt:
    def test_construction_with_one_keeps_it(self) -> None:
        #: Given
        raw = 1

        #: When
        number = NonZeroUnsignedInt(raw)

        #: Then
        assert number.value == 1, f'1 is the smallest number the type holds, got {number.value}'

    def test_construction_with_zero_raises_non_positive_int(self) -> None:
        #: Given
        raw = 0

        #: When
        with pytest.raises(NonPositiveIntError) as exc_info:
            NonZeroUnsignedInt(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the rejected zero'
        assert str(raw) in str(exc_info.value), f'the message names the rejected zero, got {exc_info.value}'
        assert str(NonZeroUnsignedInt.MINIMUM) in str(exc_info.value), (
            f'the message names the bound, got {exc_info.value}'
        )

    def test_construction_with_a_negative_number_raises_non_positive_int(self) -> None:
        #: Given
        raw = -1

        #: When
        with pytest.raises(NonPositiveIntError) as exc_info:
            NonZeroUnsignedInt(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the rejected negative number'
        assert str(raw) in str(exc_info.value), f'the message names the rejected number, got {exc_info.value}'

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

    def test_format_with_a_width_pads_the_digits(self) -> None:
        #: Given
        number = NonZeroUnsignedInt(7)

        #: When
        text = f'{number:>3}'

        #: Then
        assert text == '  7', f'a number is padded as its integer is, got {text!r}'

    def test_as_unsigned_returns_the_same_number_as_an_unsigned_int(self) -> None:
        #: Given
        number = NonZeroUnsignedInt(7)

        #: When
        unsigned = number.as_unsigned()

        #: Then
        assert unsigned == UnsignedInt(7), f'the number keeps its value, got {unsigned}'

    def test_between_with_adjacent_numbers_returns_zero(self) -> None:
        #: Given
        earlier = NonZeroUnsignedInt(4)
        later = NonZeroUnsignedInt(5)

        #: When
        between = later.between(earlier)

        #: Then
        assert between == UnsignedInt(0), f'no number lies between adjacent ones, got {between}'

    def test_between_with_a_gap_returns_the_numbers_inside_it(self) -> None:
        #: Given
        earlier = NonZeroUnsignedInt(4)
        later = NonZeroUnsignedInt(9)

        #: When
        between = later.between(earlier)

        #: Then
        assert between == UnsignedInt(4), f'5, 6, 7 and 8 lie between 4 and 9, got {between}'

    def test_between_with_a_number_not_above_the_earlier_raises_negative_int(self) -> None:
        #: Given
        earlier = NonZeroUnsignedInt(4)
        same = NonZeroUnsignedInt(4)

        #: When
        with pytest.raises(NegativeIntError) as exc_info:
            same.between(earlier)

        #: Then
        assert exc_info.value.value == -1, 'the error keeps the rejected count, one below zero for equal numbers'

    def test_position_returns_the_zero_based_place(self) -> None:
        #: Given
        number = NonZeroUnsignedInt(1)

        #: When
        position = number.position()

        #: Then
        assert position == 0, f'the first of a one-based sequence sits at 0, got {position}'

    def test_comparison_with_a_greater_number_orders_it_after(self) -> None:
        #: Given
        smaller = NonZeroUnsignedInt(1)
        greater = NonZeroUnsignedInt(2)

        #: When
        ordered = sorted([greater, smaller])

        #: Then
        assert ordered == [smaller, greater], f'numbers order by their integers, got {ordered}'

    def test_successor_returns_the_number_one_above(self) -> None:
        #: Given
        number = NonZeroUnsignedInt(500)

        #: When
        above = number.successor()

        #: Then
        assert above == NonZeroUnsignedInt(501), f'the successor of 500 is 501, got {above}'


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
        assert number == NonZeroUnsignedInt(250), 'the integer is read into the value object'

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
    def test_construction_with_zero_keeps_it(self) -> None:
        #: Given
        raw = 0

        #: When
        number = UnsignedInt(raw)

        #: Then
        assert number.value == 0, f'0 is the smallest number the type holds, got {number.value}'

    def test_construction_with_a_negative_number_raises_negative_int(self) -> None:
        #: Given
        raw = -1

        #: When
        with pytest.raises(NegativeIntError) as exc_info:
            UnsignedInt(raw)

        #: Then
        assert exc_info.value.value == raw, 'the error keeps the rejected negative number'
        assert str(raw) in str(exc_info.value), f'the message names the rejected number, got {exc_info.value}'
        assert str(UnsignedInt.MINIMUM) in str(exc_info.value), f'the message names the bound, got {exc_info.value}'

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

    def test_format_with_a_width_pads_the_digits(self) -> None:
        #: Given
        number = UnsignedInt(7)

        #: When
        text = f'{number:>3}'

        #: Then
        assert text == '  7', f'a number is padded as its integer is, got {text!r}'

    def test_or_one_with_zero_returns_one(self) -> None:
        #: Given
        number = UnsignedInt(0)

        #: When
        result = number.or_one()

        #: Then
        assert result == NonZeroUnsignedInt(1), f'0 is raised to the smallest number the other type holds, got {result}'

    def test_or_one_with_a_positive_number_returns_it(self) -> None:
        #: Given
        number = UnsignedInt(12)

        #: When
        result = number.or_one()

        #: Then
        assert result == NonZeroUnsignedInt(12), f'a number of at least 1 is kept, got {result}'

    def test_comparison_orders_numbers_by_their_integers(self) -> None:
        #: Given
        smaller = UnsignedInt(0)
        greater = UnsignedInt(1)

        #: When
        is_less = smaller < greater

        #: Then
        assert is_less, 'a number compares below a greater one'

    def test_add_returns_the_sum_as_one_number(self) -> None:
        #: Given
        left = UnsignedInt(2)
        right = UnsignedInt(3)

        #: When
        total = left + right

        #: Then
        assert total == UnsignedInt(5), f'the sum is a number of the same type, got {total!r}'

    def test_exceeds_with_a_cap_below_the_number_returns_true(self) -> None:
        #: Given
        count = UnsignedInt(501)
        cap = NonZeroUnsignedInt(500)

        #: When
        exceeds = count.exceeds(cap)

        #: Then
        assert exceeds, 'a number past the cap exceeds it'

    def test_exceeds_with_a_number_equal_to_the_cap_returns_false(self) -> None:
        #: Given
        count = UnsignedInt(500)
        cap = NonZeroUnsignedInt(500)

        #: When
        exceeds = count.exceeds(cap)

        #: Then
        assert not exceeds, 'a number equal to the cap is within it'

    def test_excess_over_with_a_cap_below_the_number_returns_the_difference(self) -> None:
        #: Given
        count = UnsignedInt(503)
        cap = NonZeroUnsignedInt(500)

        #: When
        excess = count.excess_over(cap)

        #: Then
        assert excess == NonZeroUnsignedInt(3), f'the excess is how far the number runs past the cap, got {excess}'

    def test_excess_over_with_a_number_equal_to_the_cap_raises_non_positive_int(self) -> None:
        #: Given
        count = UnsignedInt(500)
        cap = NonZeroUnsignedInt(500)

        #: When
        with pytest.raises(NonPositiveIntError) as exc_info:
            count.excess_over(cap)

        #: Then
        assert exc_info.value.value == 0, 'the error keeps the rejected excess, which is 0 for a number at the cap'

    def test_minus_with_an_amount_within_the_number_returns_what_is_left(self) -> None:
        #: Given
        number = UnsignedInt(3)

        #: When
        left = number.minus(NonZeroUnsignedInt(3))

        #: Then
        assert left == UnsignedInt(0), f'taking away the whole number leaves 0, got {left}'

    def test_minus_with_an_amount_past_the_number_returns_none(self) -> None:
        #: Given
        number = UnsignedInt(2)

        #: When
        left = number.minus(NonZeroUnsignedInt(3))

        #: Then
        assert left is None, f'there is no number below 0, got {left}'

    def test_successor_returns_the_number_one_above(self) -> None:
        #: Given
        number = UnsignedInt(0)

        #: When
        above = number.successor()

        #: Then
        assert above == NonZeroUnsignedInt(1), f'the successor of 0 is 1, got {above}'
