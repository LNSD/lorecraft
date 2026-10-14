"""Report a failure a command cannot recover from: the error, then each cause beneath it.

A command is the top of every chain. The layers beneath wrap a failure in their own variant and raise, each
message naming only its own step, so the whole story is the chain, not any one message. This is the one place
the command line writes that chain out.
"""

from dataclasses import dataclass
from typing import assert_never

import typer

from lorecraft.agents import SKILL_ENTRY_FILENAME
from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas.structure_file import JSON_SCHEMA_DIALECT
from lorecraft.project.workspace import (
    AdjacentAnyRuns,
    EmptyStructureSpec,
    ForbiddenOutlineSections,
    ForeignFrontmatterDialect,
    FrontmatterSchemaId,
    InvalidFrontmatterSchema,
    InvalidTitlePattern,
    LoadFailure,
    NonUtf8StructureFile,
    RepeatedForbiddenSections,
    RepeatedOutlineSections,
    UndecodableStructureSpec,
    UninspectableSkillEntry,
    UninspectableSkillFile,
    UninspectableSkillsDirectory,
    UnlistableCorpusDirectory,
    UnlistableDirectory,
    UnlistableSkillDirectory,
    UnlistableSkillsDirectory,
    UnreadableStructureFile,
    UnrecordedStructureFile,
    UnresolvableSkillEntry,
    UnresolvableSkillFile,
    UnresolvableSkillsDirectory,
    UntypedFrontmatterSchema,
    WorkspaceModel,
)
from lorecraft.vfs import OsRefusal

from .output import ExitStatus


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


def exit_on_load_failure(model: WorkspaceModel) -> None:
    """Report the first load failure the model recorded and exit with the failure status; do nothing without one.

    `lorecraft inspect` prints the model, which holds nothing of a unit that failed, so it treats a model that recorded
    one as it treated the error the loader raised for it: the same message, the same causes, exit 2. The first
    failure is the first the loader met, which is the one it raised before failures were recorded. `lorecraft check`
    reports a failure as a diagnostic instead.

    Args:
        model: The workspace model the command opened.

    Raises:
        typer.Exit: With the failure status, when the model recorded a load failure.
    """
    if not model.load_failures:
        return
    report_load_failure(model.load_failures[0])
    raise typer.Exit(code=ExitStatus.FAILURE)


@dataclass(frozen=True, slots=True)
class FailureText:
    """What a load failure is reported as: the message of the error it stands for, then the message of each cause.

    Attributes:
        message: The message of the error the load failure stands for.
        causes: The message of each cause beneath it, outermost first; none when the failure has no cause.
    """

    message: str
    causes: tuple[str, ...] = ()


def report_load_failure(failure: LoadFailure) -> None:
    """Write a recorded load failure to stderr as `report_failure` writes the error it stands for.

    Args:
        failure: A load failure the model recorded.
    """
    text = _failure_text(failure)
    typer.echo(f'error: {text.message}', err=True)
    for cause in text.causes:
        typer.echo(f'  caused by: {cause}', err=True)


def _failure_text(failure: LoadFailure) -> FailureText:
    """The message of the error a load failure stands for, then the message of each cause beneath it.

    Args:
        failure: A load failure the model recorded.
    """
    path = failure.path
    condition = failure.condition
    match condition:
        case UnreadableStructureFile(name=name, refusal=refusal):
            return FailureText(
                f'cannot read the structure schema {name}', (f'cannot read file {path}: {refusal.value}',)
            )
        case UnrecordedStructureFile(name=name):
            return FailureText(
                f'cannot read the structure schema {name}', (f'cannot read file {path}: not in the snapshot',)
            )
        case NonUtf8StructureFile():
            return FailureText(f'file {path} is not UTF-8')
        case UndecodableStructureSpec(problems=problems):
            return FailureText(f'invalid structure schema {path}: {"; ".join(str(problem) for problem in problems)}')
        case EmptyStructureSpec():
            return FailureText(f'invalid structure schema {path}: states no rule, so it would check nothing')
        case RepeatedOutlineSections(sections=sections):
            names = [str(name) for name in sections]
            return FailureText(
                f'invalid structure schema {path}: names sections more than once in the outline: {names}'
            )
        case RepeatedForbiddenSections(sections=sections):
            names = [str(name) for name in sections]
            return FailureText(f'invalid structure schema {path}: forbids sections more than once: {names}')
        case ForbiddenOutlineSections(sections=sections):
            names = [str(name) for name in sections]
            return FailureText(f'invalid structure schema {path}: forbids sections its own outline names: {names}')
        case AdjacentAnyRuns():
            return FailureText(f'invalid structure schema {path}: places two `any` runs side by side')
        case InvalidTitlePattern(pattern=pattern):
            return FailureText(
                f'invalid structure schema {path}: title pattern {pattern!r} is not a valid regular expression'
            )
        case InvalidFrontmatterSchema(problem=problem):
            return FailureText(f'invalid structure schema {path}: frontmatter is not a valid JSON Schema: {problem}')
        case FrontmatterSchemaId():
            return FailureText(f'invalid structure schema {path}: frontmatter schema may not carry $id')
        case ForeignFrontmatterDialect(dialect=dialect):
            return FailureText(
                f'invalid structure schema {path}: frontmatter schema names {dialect!r} in $schema; only '
                f'{JSON_SCHEMA_DIALECT} is allowed'
            )
        case UntypedFrontmatterSchema():
            return FailureText(f'invalid structure schema {path}: frontmatter schema root must state "type": "object"')
        case UnlistableDirectory(refusal=refusal):
            return FailureText(_cannot_list(path, refusal))
        case UnlistableCorpusDirectory(corpus=corpus, refusal=refusal):
            return FailureText(f'cannot list the documents of corpus {corpus}', (_cannot_list(path, refusal),))
        case UnresolvableSkillsDirectory(refusal=refusal):
            return FailureText(f'cannot resolve directory {path}: {refusal.value}')
        case UninspectableSkillsDirectory(failed_at=failed_at, refusal=refusal):
            return FailureText(f'cannot inspect entry {failed_at}: {refusal.value}')
        case UnlistableSkillsDirectory(failed_at=failed_at, refusal=refusal):
            return FailureText(f'cannot list the skills in {failed_at}', (_cannot_list(failed_at, refusal),))
        case UnresolvableSkillEntry(refusal=refusal):
            return FailureText(
                f'cannot resolve skill entry {path}', (f'cannot resolve directory {path}: {refusal.value}',)
            )
        case UninspectableSkillEntry(failed_at=failed_at, refusal=refusal):
            return FailureText(
                f'cannot resolve skill entry {path}', (f'cannot inspect entry {failed_at}: {refusal.value}',)
            )
        case UnlistableSkillDirectory(failed_at=failed_at, refusal=refusal):
            return FailureText(
                f'cannot look for {SKILL_ENTRY_FILENAME} in {failed_at}', (_cannot_list(failed_at, refusal),)
            )
        case UnresolvableSkillFile(failed_at=failed_at, refusal=refusal):
            return FailureText(f'cannot resolve {failed_at}', (f'cannot resolve file {failed_at}: {refusal.value}',))
        case UninspectableSkillFile(skill_file=skill_file, failed_at=failed_at, refusal=refusal):
            return FailureText(f'cannot resolve {skill_file}', (f'cannot inspect entry {failed_at}: {refusal.value}',))
        case _:
            assert_never(condition)


def _cannot_list(path: RootRelativePath, refusal: OsRefusal) -> str:
    """The message of the failure to list one directory.

    Args:
        path: The directory that could not be listed.
        refusal: Why the operating system refused the listing.
    """
    return f'cannot list directory {path}: {refusal.value}'
