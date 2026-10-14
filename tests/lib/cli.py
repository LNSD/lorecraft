"""Run the installed `lorecraft` console script, or its `lc` alias, in a subprocess, as a user would."""

import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

_CONSOLE_SCRIPT_NAME: Final[str] = 'lorecraft.exe' if sys.platform == 'win32' else 'lorecraft'
_ALIAS_SCRIPT_NAME: Final[str] = 'lc.exe' if sys.platform == 'win32' else 'lc'

# The scripts the environment running the tests installed, never whatever `lorecraft` or `lc` is first on PATH.
_COMMAND: Final[tuple[str, ...]] = (str(Path(sys.executable).parent / _CONSOLE_SCRIPT_NAME),)
_ALIAS_COMMAND: Final[tuple[str, ...]] = (str(Path(sys.executable).parent / _ALIAS_SCRIPT_NAME),)

_ANSI_ESCAPE: Final[re.Pattern[str]] = re.compile(r'\x1b\[[0-9;]*m')
"""A colour or style escape sequence, the only kind Rich draws a usage error with."""

_BOX_CHARACTERS: Final[str] = '╭╮╰╯─│ '
"""What Rich draws a usage error's box with, and the padding inside it."""


def run_cli(
    *arguments: str, cwd: Path | None = None, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the installed CLI in a subprocess and capture what it wrote.

    Args:
        arguments: Command-line arguments passed to `lorecraft`, after the program name.
        cwd: Directory the process starts in. The test's own working directory when omitted.
        env: The whole environment the process starts with, replacing the test's own. The test's own when omitted.

    Raises:
        subprocess.TimeoutExpired: If the process runs longer than 30 seconds.
    """
    return subprocess.run([*_COMMAND, *arguments], capture_output=True, text=True, timeout=30, cwd=cwd, env=env)


def run_alias(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run the installed `lc` alias in a subprocess and capture what it wrote.

    Args:
        arguments: Command-line arguments passed to `lc`, after the program name.
        cwd: Directory the process starts in. The test's own working directory when omitted.

    Raises:
        subprocess.TimeoutExpired: If the process runs longer than 30 seconds.
    """
    return subprocess.run([*_ALIAS_COMMAND, *arguments], capture_output=True, text=True, timeout=30, cwd=cwd)


def usage_error_message(stderr: str) -> str:
    """The text of Typer's usage error on one line, without colour, box borders or line wrapping.

    Rich colours the box when the runner's environment asks for it, as GitHub Actions' does, and the escape sequences
    split the text a test looks for. A test that reads a usage error reads it through this.

    Args:
        stderr: What a command that refused its input wrote to stderr.
    """
    plain = _ANSI_ESCAPE.sub('', stderr)
    lines = [line.strip(_BOX_CHARACTERS) for line in plain.splitlines()]
    return ' '.join(line for line in lines if line)
