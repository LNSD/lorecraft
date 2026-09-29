"""Lorecraft core: the base every other layer builds on — the error class each failure family derives from.

It imports no other layer.
"""

from lorecraft.core.error import Error

__all__: list[str] = ['Error']
