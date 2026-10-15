"""What a plain scalar's text reads as, by YAML 1.2's core schema: null, a boolean, an integer, a float or a string.

Only a plain scalar is resolved. A quoted scalar, and a literal or folded block, is a string whatever its text says,
which the caller decides before it asks. The core schema's `.inf` and `.nan` are left out: JSON has no number for
either, so they read as strings.
"""

import math
import re
import sys
from typing import Final

from .tree import YamlScalarValue

_NULL_WORDS: Final[frozenset[str]] = frozenset({'', '~', 'null', 'Null', 'NULL'})
"""The plain scalars YAML 1.2's core schema reads as null; the empty one is a key or an item written with no value."""

_TRUE_WORDS: Final[frozenset[str]] = frozenset({'true', 'True', 'TRUE'})
"""The plain scalars YAML 1.2's core schema reads as true."""

_FALSE_WORDS: Final[frozenset[str]] = frozenset({'false', 'False', 'FALSE'})
"""The plain scalars YAML 1.2's core schema reads as false."""

_DECIMAL_INT: Final[re.Pattern[str]] = re.compile(r'[-+]?[0-9]+')
"""A plain scalar YAML 1.2's core schema reads as a decimal integer. A leading zero does not make it octal."""

_OCTAL_INT: Final[re.Pattern[str]] = re.compile(r'0o[0-7]+')
"""A plain scalar YAML 1.2's core schema reads as an octal integer."""

_HEX_INT: Final[re.Pattern[str]] = re.compile(r'0x[0-9a-fA-F]+')
"""A plain scalar YAML 1.2's core schema reads as a hexadecimal integer."""

_FLOAT: Final[re.Pattern[str]] = re.compile(r'[-+]?(\.[0-9]+|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?')
"""A plain scalar YAML 1.2's core schema reads as a float. It matches every decimal integer too, so the integer
patterns are tried first."""


def resolve_plain_scalar(text: str) -> YamlScalarValue:
    """What a plain scalar reads as: its text, unless the whole text is a core schema null, boolean or number.

    Args:
        text: The scalar's text, as it is written, with no quotes.
    """
    if text in _NULL_WORDS:
        return None
    if text in _TRUE_WORDS:
        return True
    if text in _FALSE_WORDS:
        return False
    if _OCTAL_INT.fullmatch(text):
        return int(text.removeprefix('0o'), 8)
    if _HEX_INT.fullmatch(text):
        return int(text.removeprefix('0x'), 16)
    # `int` refuses more decimal digits than the interpreter's integer string conversion limit, 4300 by default,
    # so a longer integer stays the text it is written as. The octal and hexadecimal conversions have no limit.
    if _DECIMAL_INT.fullmatch(text):
        if len(text.lstrip('+-')) > sys.get_int_max_str_digits():
            return text
        return int(text)
    if _FLOAT.fullmatch(text):
        number = float(text)
        # An exponent past what a float holds converts to infinity, which JSON has no number for, so the scalar
        # stays the text it is written as, like `.inf`.
        if not math.isinf(number):
            return number
    return text
