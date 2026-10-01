"""Lorecraft core: the base every other layer builds on.

It holds the error class each failure family derives from, and the root-relative path every layer spells a path
under the workspace root with.
"""

from lorecraft.core.error import Error
from lorecraft.core.path import ROOT, RootRelativePath, RootRelativePathError

__all__: list[str] = ['Error', 'ROOT', 'RootRelativePath', 'RootRelativePathError']
