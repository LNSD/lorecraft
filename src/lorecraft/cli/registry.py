"""Route subcommands to the root application without the root application naming them.

A subcommand joins the CLI by calling `@register(<name>)` beside its own handler, in a module
under `commands/`. `mount` imports every module in that package and adds what registered itself,
so adding a subcommand is adding one file: no dispatcher, no import list, and no `__init__.py`
to edit. A command group, such as `check`, is a subpackage of `commands/` that builds its own Typer
application and calls `register_group(<name>, <app>)`; its subcommands join that application.
"""

import importlib
import pkgutil
from collections.abc import Callable

import typer

from . import commands

# A handler is a Typer command function: Typer reads its signature for the options and its
# docstring for the help text, so the parameters are its own business and `...` is honest here.
CommandHandler = Callable[..., None]

_HANDLERS: dict[str, CommandHandler] = {}
_GROUPS: dict[str, typer.Typer] = {}
_discovered: bool = False


class DuplicateCommandError(RuntimeError):
    """Two handlers claimed the same subcommand name."""


def register(name: str) -> Callable[[CommandHandler], CommandHandler]:
    """Register the decorated function as the `name` subcommand.

    Args:
        name: Subcommand as typed on the command line, so `'version'` for `lorecraft version`.

    Returns:
        A decorator that records the handler and returns it unchanged, so the function is still
        directly callable and directly testable.

    Raises:
        DuplicateCommandError: At decoration time, when `name` is already held by a different
            handler or by a group. Registering the same handler again is a no-op, so a re-imported
            module is harmless.
    """

    def decorator(handler: CommandHandler) -> CommandHandler:
        if name in _GROUPS:
            raise DuplicateCommandError(f'subcommand {name!r} is already registered as a group')
        registered = _HANDLERS.get(name)
        if registered is not None and registered is not handler:
            raise DuplicateCommandError(f'subcommand {name!r} is already registered to {registered!r}')
        _HANDLERS[name] = handler
        return handler

    return decorator


def register_group(name: str, group: typer.Typer) -> None:
    """Register a Typer application as the `name` command group.

    Args:
        name: Group as typed on the command line, so `'check'` for `lorecraft check frontmatter`.
        group: Typer application holding the group's subcommands.

    Raises:
        DuplicateCommandError: When `name` is already held by a command or by a different group.
            Registering the same group again is a no-op.
    """
    if name in _HANDLERS:
        raise DuplicateCommandError(f'subcommand {name!r} is already registered as a command')
    registered = _GROUPS.get(name)
    if registered is not None and registered is not group:
        raise DuplicateCommandError(f'subcommand {name!r} is already registered to another group')
    _GROUPS[name] = group


def mount(app: typer.Typer) -> None:
    """Add every registered subcommand to `app`, discovering them first.

    Commands and groups are mounted in name order. `--help` lists the commands in that order, then the
    groups in that order: Typer keeps the two apart.

    Args:
        app: Root application the subcommands are attached to. Mounting twice onto the same
            application would list every subcommand twice, so call this once per application.
    """
    _discover()
    for name in sorted(_HANDLERS.keys() | _GROUPS.keys()):
        group = _GROUPS.get(name)
        if group is not None:
            app.add_typer(group, name=name)
        else:
            app.command(name=name)(_HANDLERS[name])


def _discover() -> None:
    """Import every module under `commands`, so that each one's `register` call runs.

    Runs once per process; later calls return immediately. An import failure propagates because
    these are built-in commands, and starting without one would leave the command surface incomplete.
    """
    global _discovered
    if _discovered:
        return

    for module_info in pkgutil.iter_modules(commands.__path__):
        module_name = f'{commands.__name__}.{module_info.name}'
        importlib.import_module(module_name)

    _discovered = True
