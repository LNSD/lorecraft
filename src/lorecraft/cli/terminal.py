"""Decide how text is drawn for the terminal a command prints to: colour, Unicode and width.

This is the one place that asks the process about its terminal and its environment, so the renderers stay pure
functions of the style they are handed. The colour variables are read once, by `read_color_environment`, into a
`ColorEnvironment`; the colour decision, `decide_color`, is a pure function of that value, `--color` and whether
stdout is a terminal. The width comes from `shutil.get_terminal_size`, which honours `COLUMNS` on a terminal; no
other code of ours reads `os.environ`.
"""

import os
import shutil
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Self, assert_never

from .diagnostic_text import TextStyle
from .output import ColorChoice

# The width of a pipe or a file, which has no terminal to ask: wide enough that a help or note rarely wraps.
_UNKNOWN_WIDTH: Final[int] = 100


@dataclass(frozen=True, slots=True)
class ColorEnvironment:
    """What the environment says about colour, by the two conventions programs share.

    Attributes:
        force_color: True when `FORCE_COLOR` is set to a non-empty value, which asks for colour even when stdout is
            not a terminal (force-color.org).
        no_color: True when `NO_COLOR` is set to a non-empty value, which asks for no colour (no-color.org).
    """

    force_color: bool
    no_color: bool

    @classmethod
    def parse(cls, environ: Mapping[str, str]) -> Self:
        """Read the two variables from an environment; a variable that is unset or empty counts as not set.

        Both conventions give an empty value no meaning, so only a non-empty value is a request.

        Args:
            environ: The environment, such as `os.environ`; any other variable in it is ignored.
        """
        return cls(force_color=bool(environ.get('FORCE_COLOR')), no_color=bool(environ.get('NO_COLOR')))


def read_color_environment() -> ColorEnvironment:
    """The colour variables of this process's environment, the one read of it."""
    return ColorEnvironment.parse(os.environ)


def decide_color(choice: ColorChoice, environment: ColorEnvironment, *, is_terminal: bool) -> bool:
    """Whether to colour the text, by the first of these that applies.

    1. An explicit `--color always` or `--color never`.
    2. Under `auto`, a non-empty `FORCE_COLOR`, which colours even a pipe.
    3. Under `auto`, a non-empty `NO_COLOR`, which does not colour.
    4. Under `auto`, whether stdout is a terminal.

    Args:
        choice: What `--color` said.
        environment: What the environment says about colour.
        is_terminal: True when stdout is a terminal.
    """
    match choice:
        case ColorChoice.ALWAYS:
            return True
        case ColorChoice.NEVER:
            return False
        case ColorChoice.AUTO:
            if environment.force_color:
                return True
            if environment.no_color:
                return False
            return is_terminal
        case _:
            assert_never(choice)


def detect_text_style(choice: ColorChoice, environment: ColorEnvironment) -> TextStyle:
    """The style for stdout: the colour `decide_color` gives, Unicode when stdout encodes it, and its width.

    Args:
        choice: What `--color` said.
        environment: What the environment says about colour, read once at the command line's edge.
    """
    is_terminal = sys.stdout.isatty()
    color = decide_color(choice, environment, is_terminal=is_terminal)

    encoding = (sys.stdout.encoding or '').lower().replace('-', '').replace('_', '')
    # A pipe or a file is not asked: the environment's `COLUMNS` describes some other terminal, and the same run would
    # wrap differently from one machine to the next.
    width = _UNKNOWN_WIDTH
    if is_terminal:
        width = shutil.get_terminal_size().columns
    return TextStyle(color=color, unicode=encoding == 'utf8', width=width)
