"""Report a failure a command cannot recover from: the error, then each cause beneath it.

A command is the top of every chain. The layers beneath wrap a failure in their own variant and raise, each
message naming only its own step, so the whole story is the chain, not any one message. This is the one place
the command line writes that chain out.
"""

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

    Until a load failure is reported as a diagnostic, a command treats a model that recorded one as it treated the
    error the loader raised for it: the same message, the same causes, exit 2. The first failure is the first the
    loader met, which is the one it raised before failures were recorded.

    Args:
        model: The workspace model the command opened.

    Raises:
        typer.Exit: With the failure status, when the model recorded a load failure.
    """
    if not model.load_failures:
        return
    report_load_failure(model.load_failures[0])
    raise typer.Exit(code=ExitStatus.FAILURE)


def report_load_failure(failure: LoadFailure) -> None:
    """Write a recorded load failure to stderr as `report_failure` writes the error it stands for.

    Args:
        failure: A load failure the model recorded.
    """
    message, *causes = _failure_lines(failure)
    typer.echo(f'error: {message}', err=True)
    for cause in causes:
        typer.echo(f'  caused by: {cause}', err=True)


def _failure_lines(failure: LoadFailure) -> list[str]:
    """The message of the error a load failure stands for, then the message of each cause beneath it.

    Args:
        failure: A load failure the model recorded.
    """
    path = failure.path
    condition = failure.condition
    match condition:
        case UnreadableStructureFile(name=name, refusal=refusal):
            return [f'cannot read the structure schema {name}', f'cannot read file {path}: {refusal.value}']
        case UnrecordedStructureFile(name=name):
            return [f'cannot read the structure schema {name}', f'cannot read file {path}: not in the snapshot']
        case NonUtf8StructureFile():
            return [f'file {path} is not UTF-8']
        case UndecodableStructureSpec(problems=problems):
            return [f'invalid structure schema {path}: {"; ".join(problems)}']
        case EmptyStructureSpec():
            return [f'invalid structure schema {path}: states no rule, so it would check nothing']
        case RepeatedOutlineSections(sections=sections):
            return [f'invalid structure schema {path}: names sections more than once in the outline: {list(sections)}']
        case RepeatedForbiddenSections(sections=sections):
            return [f'invalid structure schema {path}: forbids sections more than once: {list(sections)}']
        case ForbiddenOutlineSections(sections=sections):
            return [f'invalid structure schema {path}: forbids sections its own outline names: {list(sections)}']
        case AdjacentAnyRuns():
            return [f'invalid structure schema {path}: places two `any` runs side by side']
        case InvalidTitlePattern(pattern=pattern):
            return [f'invalid structure schema {path}: title pattern {pattern!r} is not a valid regular expression']
        case InvalidFrontmatterSchema(problem=problem):
            return [f'invalid structure schema {path}: frontmatter is not a valid JSON Schema: {problem}']
        case FrontmatterSchemaId():
            return [f'invalid structure schema {path}: frontmatter schema may not carry $id']
        case ForeignFrontmatterDialect(dialect=dialect):
            return [
                f'invalid structure schema {path}: frontmatter schema names {dialect} in $schema; only '
                f'{JSON_SCHEMA_DIALECT} is allowed'
            ]
        case UntypedFrontmatterSchema():
            return [f'invalid structure schema {path}: frontmatter schema root must state "type": "object"']
        case UnlistableDirectory(refusal=refusal):
            return [_cannot_list(path, refusal)]
        case UnlistableCorpusDirectory(corpus=corpus, refusal=refusal):
            return [f'cannot list the documents of corpus {corpus}', _cannot_list(path, refusal)]
        case UnresolvableSkillsDirectory(refusal=refusal):
            return [f'cannot resolve directory {path}: {refusal.value}']
        case UninspectableSkillsDirectory(failed_at=failed_at, refusal=refusal):
            return [f'cannot inspect entry {failed_at}: {refusal.value}']
        case UnlistableSkillsDirectory(failed_at=failed_at, refusal=refusal):
            return [f'cannot list the skills in {failed_at}', _cannot_list(failed_at, refusal)]
        case UnresolvableSkillEntry(refusal=refusal):
            return [f'cannot resolve skill entry {path}', f'cannot resolve directory {path}: {refusal.value}']
        case UninspectableSkillEntry(failed_at=failed_at, refusal=refusal):
            return [f'cannot resolve skill entry {path}', f'cannot inspect entry {failed_at}: {refusal.value}']
        case UnlistableSkillDirectory(failed_at=failed_at, refusal=refusal):
            return [f'cannot look for {SKILL_ENTRY_FILENAME} in {failed_at}', _cannot_list(failed_at, refusal)]
        case UnresolvableSkillFile(failed_at=failed_at, refusal=refusal):
            return [f'cannot resolve {failed_at}', f'cannot resolve file {failed_at}: {refusal.value}']
        case UninspectableSkillFile(skill_file=skill_file, failed_at=failed_at, refusal=refusal):
            return [f'cannot resolve {skill_file}', f'cannot inspect entry {failed_at}: {refusal.value}']
        case _:
            assert_never(condition)


def _cannot_list(path: RootRelativePath, refusal: OsRefusal) -> str:
    """The message of the failure to list one directory.

    Args:
        path: The directory that could not be listed.
        refusal: Why the operating system refused the listing.
    """
    return f'cannot list directory {path}: {refusal.value}'
