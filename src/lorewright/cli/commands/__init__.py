"""Subcommands of the `lorewright` CLI, one per module.

Every module here is imported by the registry's discovery walk, so a new subcommand is a new file
in this package with a `@register(<name>)` handler in it. This `__init__.py` deliberately imports
nothing: naming the modules here would be the dispatcher the registry exists to avoid.
"""

__all__: list[str] = []
