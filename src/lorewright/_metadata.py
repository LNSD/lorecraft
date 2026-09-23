"""Resolve the version recorded for the installed distribution.

The version's home is the git tag: hatch-vcs derives it at build time, so nothing in the tree
holds a literal that could disagree with the tag. What a running process can read back is the
version the installed copy was *built* with, which is what `importlib.metadata` returns.
"""

import logging
from importlib.metadata import PackageNotFoundError, version

logger = logging.getLogger(__name__)

# Distribution name as declared in pyproject.toml, which is what importlib.metadata keys on.
_DISTRIBUTION_NAME: str = 'lorewright'

# Reported when the package is imported from a source tree that was never installed: running
# `git describe` here would report a version no artifact carries, so the CLI says plainly that it
# does not know instead. PEP 440 accepts it as a version, so nothing downstream has to special-case it.
_UNINSTALLED_VERSION: str = '0+unknown'

try:
    __version__: str = version(_DISTRIBUTION_NAME)
except PackageNotFoundError:
    logger.exception(f'installed metadata for {_DISTRIBUTION_NAME} was unavailable')
    __version__ = _UNINSTALLED_VERSION
