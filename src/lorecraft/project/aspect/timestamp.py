"""Validation for fixed-precision timestamp name segments."""

from datetime import datetime

_FORMATS: dict[int, str] = {
    4: '%Y',
    6: '%Y%m',
    8: '%Y%m%d',
    10: '%Y%m%d%H',
    12: '%Y%m%d%H%M',
    14: '%Y%m%d%H%M%S',
    17: '%Y%m%d%H%M%S',
}


def is_valid_timestamp(value: str, width: int) -> bool:
    """Return whether a fixed-width name segment is a valid Gregorian timestamp."""
    if len(value) != width or not value.isascii():
        return False
    if width == 17:
        if value[14:] != 'UTC':
            return False
        value = value[:14]
    if not value.isdigit() or width not in _FORMATS:
        return False
    try:
        datetime.strptime(value, _FORMATS[width])
    except ValueError:
        return False
    return True
