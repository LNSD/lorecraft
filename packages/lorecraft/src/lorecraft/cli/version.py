"""Build the version strings the CLI prints, and describe the checkout it runs from.

Both the root `--version` option and the `version` subcommand read from here, so the two can never
drift apart. The detailed form exists for bug reports: it carries the interpreter, the platform and
the install location, which are what a reproduction usually turns on.

The version `importlib.metadata` reports was frozen when the package was built, so it says nothing
about uncommitted work. `git_description` is the live half, and it is deliberately separate: this
module's formatting is pure, and the one function that shells out is the one function named for it.
"""

import logging
import platform
import subprocess
from pathlib import Path

from .. import __version__

logger = logging.getLogger(__name__)

# The name the CLI is invoked by, and the name under which the package is distributed. They are
# the same string today; keeping one constant means a rename touches one line.
_PROGRAM_NAME: str = 'lorecraft'

# --tags so an annotated or lightweight tag both count, --always so a checkout with no tag still
# reports its commit, --dirty so uncommitted work is visible rather than implied.
_GIT_DESCRIBE: tuple[str, ...] = ('git', 'describe', '--tags', '--always', '--dirty')

# Seconds a `git describe` may take before the CLI gives up on it. A local describe is milliseconds;
# the bound is here so a wedged git can never hang `version --verbose`.
_GIT_TIMEOUT_SECONDS: float = 5.0


def short_version() -> str:
    """Return the one-line version, as `lorecraft <version>`."""
    return f'{_PROGRAM_NAME} {__version__}'


def detailed_version(commit: str | None) -> str:
    """Return the multi-line version: the short line, the commit, the interpreter, the platform, the install path.

    Args:
        commit: Checkout description to report, as `git_description` returns it. `None` omits the
            line entirely rather than printing a placeholder, because an installed copy has no
            checkout to describe.

    Returns:
        A block of newline-separated lines, without a trailing newline.
    """
    install_path = Path(__file__).resolve().parent.parent
    lines = [short_version()]
    if commit is not None:
        lines.append(f'Commit:   {commit}')
    lines.extend(
        [
            f'Python:   {platform.python_version()} ({platform.python_implementation()})',
            f'Platform: {platform.platform()}',
            f'Install:  {install_path}',
        ]
    )
    return '\n'.join(lines)


def git_description() -> str | None:
    """Describe the git checkout this package was loaded from, dirty state included.

    Returns:
        The `git describe --tags --always --dirty` output — `v0.1.0`, `v0.1.0-2-g93b1ed1`, or either
        with a `-dirty` suffix. `None` when the package is not running from a checkout, when git is
        not installed, or when the command fails or times out: an absent line is honest, and a
        version command is not worth failing over.
    """
    checkout_root = _checkout_root()
    if checkout_root is None:
        return None

    try:
        completed = subprocess.run(
            _GIT_DESCRIBE,
            cwd=checkout_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        logger.exception(f'git description was unavailable for {checkout_root}')
        return None

    return completed.stdout.strip() or None


def _checkout_root() -> Path | None:
    """Return the checkout this module was loaded from, or `None` for an installed copy.

    Only the repository's own workspace layout counts. A virtual environment often sits inside some
    other project's checkout, so running `git describe` from an installed copy's directory would
    happily describe a repository that has nothing to do with this package.
    """
    # <checkout>/packages/lorecraft/src/lorecraft/cli/version.py
    #   -> parents[0] cli, [1] lorecraft, [2] src, [3] the lorecraft package, [4] packages, [5] the checkout
    source_root = Path(__file__).resolve().parents[2]
    packages_dir = source_root.parents[1]
    if source_root.name != 'src' or packages_dir.name != 'packages':
        return None

    checkout_root = packages_dir.parent
    return checkout_root if (checkout_root / '.git').exists() else None
