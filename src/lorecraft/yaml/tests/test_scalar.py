"""Plain scalars: each core-schema row reads as the type YAML 1.2 gives it, and no other."""

import sys

import pytest

from ..scalar import resolve_plain_scalar


@pytest.mark.unit
class TestResolvePlainScalar:
    def test_resolve_plain_scalar_with_an_empty_text_returns_none(self) -> None:
        #: Given
        text = ''

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value is None, f'{text!r} reads as None, got {value!r}'

    def test_resolve_plain_scalar_with_a_tilde_returns_none(self) -> None:
        #: Given
        text = '~'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value is None, f'{text!r} reads as None, got {value!r}'

    def test_resolve_plain_scalar_with_the_word_null_returns_none(self) -> None:
        #: Given
        text = 'null'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value is None, f'{text!r} reads as None, got {value!r}'

    def test_resolve_plain_scalar_with_the_capitalised_word_null_returns_none(self) -> None:
        #: Given
        text = 'Null'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value is None, f'{text!r} reads as None, got {value!r}'

    def test_resolve_plain_scalar_with_the_uppercase_word_null_returns_none(self) -> None:
        #: Given
        text = 'NULL'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value is None, f'{text!r} reads as None, got {value!r}'

    def test_resolve_plain_scalar_with_the_word_true_returns_a_bool(self) -> None:
        #: Given
        text = 'true'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value is True, f'{text!r} reads as True, got {value!r}'

    def test_resolve_plain_scalar_with_the_capitalised_word_true_returns_a_bool(self) -> None:
        #: Given
        text = 'True'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value is True, f'{text!r} reads as True, got {value!r}'

    def test_resolve_plain_scalar_with_the_uppercase_word_true_returns_a_bool(self) -> None:
        #: Given
        text = 'TRUE'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value is True, f'{text!r} reads as True, got {value!r}'

    def test_resolve_plain_scalar_with_the_word_false_returns_a_bool(self) -> None:
        #: Given
        text = 'false'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value is False, f'{text!r} reads as False, got {value!r}'

    def test_resolve_plain_scalar_with_the_capitalised_word_false_returns_a_bool(self) -> None:
        #: Given
        text = 'False'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value is False, f'{text!r} reads as False, got {value!r}'

    def test_resolve_plain_scalar_with_the_uppercase_word_false_returns_a_bool(self) -> None:
        #: Given
        text = 'FALSE'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value is False, f'{text!r} reads as False, got {value!r}'

    def test_resolve_plain_scalar_with_the_word_yes_returns_the_string(self) -> None:
        #: Given
        text = 'yes'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 'yes', f'{text!r} reads as {"'yes'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_the_word_no_returns_the_string(self) -> None:
        #: Given
        text = 'no'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 'no', f'{text!r} reads as {"'no'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_the_word_on_returns_the_string(self) -> None:
        #: Given
        text = 'on'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 'on', f'{text!r} reads as {"'on'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_the_word_off_returns_the_string(self) -> None:
        #: Given
        text = 'off'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 'off', f'{text!r} reads as {"'off'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_a_mixed_case_true_returns_the_string(self) -> None:
        #: Given
        text = 'tRUE'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 'tRUE', f'{text!r} reads as {"'tRUE'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_a_decimal_integer_returns_an_int(self) -> None:
        #: Given
        text = '12'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 12, f'{text!r} reads as {"12"}, got {value!r}'
        assert type(value) is int, f'{text!r} is a int, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_a_negative_integer_returns_an_int(self) -> None:
        #: Given
        text = '-3'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == -3, f'{text!r} reads as {"-3"}, got {value!r}'
        assert type(value) is int, f'{text!r} is a int, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_a_signed_integer_returns_an_int(self) -> None:
        #: Given
        text = '+7'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 7, f'{text!r} reads as {"7"}, got {value!r}'
        assert type(value) is int, f'{text!r} is a int, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_zero_returns_an_int(self) -> None:
        #: Given
        text = '0'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 0, f'{text!r} reads as {"0"}, got {value!r}'
        assert type(value) is int, f'{text!r} is a int, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_a_leading_zero_integer_returns_an_int(self) -> None:
        #: Given
        text = '017'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 17, f'{text!r} reads as {"17"}, got {value!r}'
        assert type(value) is int, f'{text!r} is a int, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_an_octal_integer_returns_an_int(self) -> None:
        #: Given
        text = '0o17'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 15, f'{text!r} reads as {"15"}, got {value!r}'
        assert type(value) is int, f'{text!r} is a int, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_a_hexadecimal_integer_returns_an_int(self) -> None:
        #: Given
        text = '0x1F'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 31, f'{text!r} reads as {"31"}, got {value!r}'
        assert type(value) is int, f'{text!r} is a int, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_a_decimal_fraction_returns_a_float(self) -> None:
        #: Given
        text = '1.5'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 1.5, f'{text!r} reads as {"1.5"}, got {value!r}'
        assert type(value) is float, f'{text!r} is a float, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_a_leading_dot_fraction_returns_a_float(self) -> None:
        #: Given
        text = '.5'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 0.5, f'{text!r} reads as {"0.5"}, got {value!r}'
        assert type(value) is float, f'{text!r} is a float, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_a_trailing_dot_fraction_returns_a_float(self) -> None:
        #: Given
        text = '1.'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 1.0, f'{text!r} reads as {"1.0"}, got {value!r}'
        assert type(value) is float, f'{text!r} is a float, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_an_exponent_returns_a_float(self) -> None:
        #: Given
        text = '1e3'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == 1000.0, f'{text!r} reads as {"1000.0"}, got {value!r}'
        assert type(value) is float, f'{text!r} is a float, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_a_negative_exponent_fraction_returns_a_float(self) -> None:
        #: Given
        text = '-2.5E-1'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == -0.25, f'{text!r} reads as {"-0.25"}, got {value!r}'
        assert type(value) is float, f'{text!r} is a float, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_positive_infinity_returns_the_string(self) -> None:
        #: Given
        text = '.inf'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == '.inf', f'{text!r} reads as {"'.inf'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_negative_infinity_returns_the_string(self) -> None:
        #: Given
        text = '-.inf'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == '-.inf', f'{text!r} reads as {"'-.inf'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_not_a_number_returns_the_string(self) -> None:
        #: Given
        text = '.nan'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == '.nan', f'{text!r} reads as {"'.nan'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_an_exponent_past_what_a_float_holds_returns_the_string(self) -> None:
        #: Given
        text = '1e999'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == '1e999', f'{text!r} reads as {"'1e999'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_a_date_returns_the_string(self) -> None:
        #: Given
        text = '2026-10-05'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == '2026-10-05', f'{text!r} reads as {"'2026-10-05'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_a_time_returns_the_string(self) -> None:
        #: Given
        text = '1:30'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == '1:30', f'{text!r} reads as {"'1:30'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_a_binary_integer_returns_the_string(self) -> None:
        #: Given
        text = '0b101'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == '0b101', f'{text!r} reads as {"'0b101'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_an_integer_with_an_underscore_returns_the_string(self) -> None:
        #: Given
        text = '1_000'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == '1_000', f'{text!r} reads as {"'1_000'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_an_octal_with_a_digit_out_of_range_returns_the_string(self) -> None:
        #: Given
        text = '0o8'

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == '0o8', f'{text!r} reads as {"'0o8'"}, got {value!r}'
        assert type(value) is str, f'{text!r} is a str, got {type(value).__name__}'

    def test_resolve_plain_scalar_with_more_digits_than_the_conversion_limit_returns_the_string(self) -> None:
        #: Given
        text = '1' * (sys.get_int_max_str_digits() + 1)

        #: When
        value = resolve_plain_scalar(text)

        #: Then
        assert value == text, 'an integer longer than the interpreter converts stays the text it is written as'
