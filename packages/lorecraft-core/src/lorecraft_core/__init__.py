"""Lorecraft core: the base every other package builds on — the error class each failure family derives from.

It imports no workspace package.
"""

from lorecraft_core.error import Error

__all__: list[str] = ['Error']
