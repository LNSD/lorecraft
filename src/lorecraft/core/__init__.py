"""Lorecraft core: the base every other layer builds on.

It holds the error class each failure family derives from and the generic value types every layer spells its
arguments in. Each submodule is its own entry point, imported by its full name, such as `lorecraft.core.path`:
this package re-exports nothing.
"""
