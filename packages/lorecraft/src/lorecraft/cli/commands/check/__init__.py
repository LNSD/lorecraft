"""The `check` command group: one subcommand per documentation check, each in its own module here.

Importing this package registers the group and imports every module beside this one, so each check joins
the group the same way a top-level command joins the root: by being a file in the package.
"""

import importlib
import pkgutil

import typer

from lorecraft.cli.registry import register_group

app: typer.Typer = typer.Typer(help='Run a check against repository documentation.', no_args_is_help=True)
register_group('check', app)

__all__ = ['app']

# Each check lives in its own module and joins this group when imported. The group must exist before the
# imports, because every check module attaches its command to `app`.
for module_info in pkgutil.iter_modules(__path__):
    importlib.import_module(f'{__name__}.{module_info.name}')
