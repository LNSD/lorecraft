"""How every command reports: the output formats it can print in, and the statuses it exits with.

Each command imports both from here, so `--format` and the exit status mean the same in every command. What a
command prints in each format is documented beside the function that prints it.
"""

from enum import Enum, IntEnum


class OutputFormat(Enum):
    """How a command prints its result; the value is what `--format` accepts."""

    TEXT = 'text'
    """Text for a person to read: the result on stdout, any summary on stderr."""
    JSON = 'json'
    """One JSON document on stdout, for a script to parse."""


class ExitStatus(IntEnum):
    """The exit status of a command that did not succeed, as `docs/feat/cli.md` documents it.

    A command that succeeds returns without raising, so no member stands for 0. A usage error also exits 2,
    raised by Typer before the command runs, so it shares `FAILURE`'s number.
    """

    FINDINGS = 1
    """The command ran and found something, such as a check reporting a finding."""
    FAILURE = 2
    """The command could not start or could not finish: only the error is printed."""
