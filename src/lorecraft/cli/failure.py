"""Report a failure a command cannot recover from: the error, then each cause beneath it.

A command is the top of every chain. The layers beneath wrap a failure in their own variant and raise, each
message naming only its own step, so the whole story is the chain, not any one message. This is the one place
the command line writes that chain out.
"""

import typer

from lorecraft.core.error import Error


def report_failure(failure: Error) -> None:
    """Write ``failure`` to stderr as ``error: <message>``, then one ``  caused by: <message>`` line per cause.

    The walk follows ``__cause__`` from ``failure`` down, and stops at the first cause that is not an ``Error``.
    That one is a foreign exception, whose ``str()`` is not written to be read on its own; the variant that
    translated it states what the user needs from its own fields.

    Args:
        failure: The error a command caught at its top level.
    """
    typer.echo(f'error: {failure}', err=True)
    cause = failure.__cause__
    while isinstance(cause, Error):
        typer.echo(f'  caused by: {cause}', err=True)
        cause = cause.__cause__
