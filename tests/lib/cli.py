"""Run the installed ``lorecraft`` console script in a subprocess, as a user would."""

import subprocess
import sys
from pathlib import Path
from typing import Final

_CONSOLE_SCRIPT_NAME: Final[str] = 'lorecraft.exe' if sys.platform == 'win32' else 'lorecraft'

# The script the environment running the tests installed, never whatever `lorecraft` is first on PATH.
_COMMAND: Final[tuple[str, ...]] = (str(Path(sys.executable).parent / _CONSOLE_SCRIPT_NAME),)


def run_cli(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run the installed CLI in a subprocess and capture what it wrote."""
    return subprocess.run([*_COMMAND, *arguments], capture_output=True, text=True, timeout=30, cwd=cwd)
