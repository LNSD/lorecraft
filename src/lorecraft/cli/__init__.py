"""Command-line interface for lorecraft.

The root application carries the global options; every subcommand lives under `commands/` and
joins by registering its name. See `_registry` for what adding one involves.
"""

from ._app import build_app, main

__all__: list[str] = ['build_app', 'main']
