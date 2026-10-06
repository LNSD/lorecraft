"""Route subcommands to the root application without the root application naming them.

A subcommand joins the CLI by calling `@register(<name>)` beside its own handler, in a module
under `commands/`. `mount` imports every module in that package and adds what registered itself,
so adding a subcommand is adding one file: no dispatcher, no import list, and no `__init__.py`
to edit.
"""

import importlib
import pkgutil
from collections.abc import Callable

import typer

from . import commands

# A handler is a Typer command function: Typer reads its signature for the options and its
# docstring for the help text, so the parameters are its own business and `...` is honest here.
type CommandHandler = Callable[..., None]

_HANDLERS: dict[str, CommandHandler] = {}
_discovered: bool = False


class DuplicateCommandError(RuntimeError):
    """Two handlers claimed one subcommand name.

    It is a defect in the package, never the user's input, so the traceback, not the message, says where the
    second claim was made.

    Attributes:
        name: The subcommand name claimed twice.
    """

    name: str

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f'subcommand {name!r} is already registered')


def register(name: str) -> Callable[[CommandHandler], CommandHandler]:
    """Register the decorated function as the `name` subcommand.

    Args:
        name: Subcommand as typed on the command line, so `'version'` for `lorecraft version`.

    Returns:
        A decorator that records the handler and returns it unchanged, so the function is still
        directly callable and directly testable.

    Raises:
        DuplicateCommandError: At decoration time, when `name` is already held by a different
            handler. Registering the same handler again is a no-op, so a re-imported
            module is harmless.
    """

    def decorator(handler: CommandHandler) -> CommandHandler:
        registered = _HANDLERS.get(name)
        if registered is not None and registered is not handler:
            raise DuplicateCommandError(name)
        _HANDLERS[name] = handler
        return handler

    return decorator


def mount(app: typer.Typer) -> None:
    """Add every registered subcommand to `app`, discovering them first.

    Commands are mounted in name order, the order `--help` lists them in.

    Args:
        app: Root application the subcommands are attached to. Mounting twice onto the same
            application would list every subcommand twice, so call this once per application.
    """
    _discover()
    for name in sorted(_HANDLERS):
        app.command(name=name)(_HANDLERS[name])


# Runs once per process, before mutmut swaps a mutant in, so no test can ever see a mutant of it.
def _discover() -> None:  # pragma: no mutate block
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
