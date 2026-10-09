"""Run the installed ``lorecraft`` console script, or its ``lc`` alias, in a subprocess, as a user would.

It also runs the entry point in a fresh interpreter to list the modules a command loads, which the console script
cannot report.
"""

import json
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

# Runs the entry point as the console script does, then prints the names of the modules it loaded as one JSON list.
# `main` ends the process with `SystemExit` for `--version`, `--help` and a failing command, so that is caught.
_MODULES_PROBE: Final[str] = """
import json, sys
from lorecraft.cli import main

sys.argv = ['lorecraft', *sys.argv[1:]]
try:
    main()
except SystemExit:
    pass
print(json.dumps(sorted(sys.modules)))
"""


def run_cli(
    *arguments: str, cwd: Path | None = None, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the installed CLI in a subprocess and capture what it wrote.

    Args:
        arguments: Command-line arguments passed to `lorecraft`, after the program name.
        cwd: Directory the process starts in. The test's own working directory when omitted.
        env: The whole environment the process starts with, replacing the test's own. The test's own when omitted.
    """
    return subprocess.run([*_COMMAND, *arguments], capture_output=True, text=True, timeout=30, cwd=cwd, env=env)


def run_alias(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run the installed `lc` alias in a subprocess and capture what it wrote.

    Args:
        arguments: Command-line arguments passed to `lc`, after the program name.
        cwd: Directory the process starts in. The test's own working directory when omitted.
    """
    return subprocess.run([*_ALIAS_COMMAND, *arguments], capture_output=True, text=True, timeout=30, cwd=cwd)


def list_modules_loaded_by_cli(*arguments: str) -> list[str]:
    """Run the CLI in a fresh interpreter and return the names of the modules it loaded.

    It cannot go through `run_cli`: the console script cannot report `sys.modules`, so this starts the entry point
    from the same interpreter with a probe, under the same timeout and capture.

    Args:
        arguments: Command-line arguments passed to `lorecraft`, after the program name.
    """
    completed = subprocess.run(
        [sys.executable, '-c', _MODULES_PROBE, *arguments], capture_output=True, text=True, timeout=30, check=False
    )
    # A command that fails to import prints a traceback on stderr and nothing on stdout; show it, not an IndexError.
    assert completed.stdout, completed.stderr
    # The probe's list is the last line; a command may have printed its own output before it.
    return json.loads(completed.stdout.splitlines()[-1])
