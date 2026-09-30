"""Map an explicit document or skill argument from the command line onto the workspace model.

An argument is only spelled on disk: the disk is asked only where it leads above the root, the part under the
root is taken as spelled, and every link in that part is followed through the snapshot, so it names what the
model saw even when the tree changed since. An explicit path is a boundary, so it is rejected with the most
specific reason it fails, where discovery would simply have ignored the file.
"""

import os
from pathlib import Path, PurePosixPath

from lorecraft.checks import Database
from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import CorpusName, EmptyCorpusNameError, InvalidCorpusNameCharacterError
from lorecraft.project.document import DocumentRef
from lorecraft.project.layout import DOCS_DIR, DOCUMENT_SUFFIX, SPECS_DIR
from lorecraft.project.skill import SkillRef
from lorecraft.project.workspace import WorkspaceModel


class MissingDocumentPathError(Error):
    """An explicit document argument leads to no file the snapshot holds, though it sits where a document may.

    Attributes:
        argument: The path exactly as typed.
    """

    argument: Path

    def __init__(self, argument: Path) -> None:
        self.argument = argument
        super().__init__(f'{argument}: no such file')


class NonFileDocumentPathError(Error):
    """An explicit document argument leads to a directory, not a file.

    Attributes:
        argument: The path exactly as typed.
    """

    argument: Path

    def __init__(self, argument: Path) -> None:
        self.argument = argument
        super().__init__(f'{argument}: expected a readable Markdown file')


class NonMarkdownDocumentPathError(Error):
    """An explicit document argument names a file that is not ``.md``.

    Attributes:
        argument: The path exactly as typed.
    """

    argument: Path

    def __init__(self, argument: Path) -> None:
        self.argument = argument
        super().__init__(f'{argument}: expected a .md file')


class OutsideDocsDocumentPathError(Error):
    """An explicit document argument lies outside ``docs/``, inside ``docs/__meta__/``, or outside the root.

    Attributes:
        argument: The path exactly as typed.
    """

    argument: Path

    def __init__(self, argument: Path) -> None:
        self.argument = argument
        super().__init__(f'{argument}: file must be inside docs/ and outside docs/__meta__/')


class CorpuslessDocumentPathError(Error):
    """An explicit document argument sits directly in ``docs/``, in no corpus directory.

    Attributes:
        argument: The path exactly as typed.
    """

    argument: Path

    def __init__(self, argument: Path) -> None:
        self.argument = argument
        super().__init__(f'{argument}: file must be inside a corpus directory under docs/')


class InvalidCorpusDocumentPathError(Error):
    """An explicit document argument's corpus directory is not a valid corpus name.

    Attributes:
        argument: The path exactly as typed.
        source: Why the directory's name is not a corpus name.
    """

    argument: Path
    source: EmptyCorpusNameError | InvalidCorpusNameCharacterError

    def __init__(self, argument: Path, *, source: EmptyCorpusNameError | InvalidCorpusNameCharacterError) -> None:
        self.argument = argument
        self.source = source
        super().__init__(f'{argument}: invalid corpus name')
        self.__cause__ = source


class UnknownCorpusDocumentPathError(Error):
    """An explicit document argument's corpus directory has no specification, so it is not a corpus.

    Attributes:
        argument: The path exactly as typed.
    """

    argument: Path

    def __init__(self, argument: Path) -> None:
        self.argument = argument
        super().__init__(f'{argument}: not a corpus: no docs/__meta__/<dir>.* specification')


class NestedDocumentPathError(Error):
    """An explicit document argument sits in a subdirectory of its corpus, where corpora are flat.

    Attributes:
        argument: The path exactly as typed.
    """

    argument: Path

    def __init__(self, argument: Path) -> None:
        self.argument = argument
        super().__init__(f'{argument}: corpora are flat; the file is in a subdirectory of its corpus')


class UnlistedDocumentPathError(Error):
    """An explicit document argument names a file the workspace model does not list as a document.

    Attributes:
        argument: The path exactly as typed.
    """

    argument: Path

    def __init__(self, argument: Path) -> None:
        self.argument = argument
        super().__init__(f'{argument}: not a document the workspace lists')


def select_document(database: Database, root: Path, working_directory: Path, argument: Path) -> DocumentRef:
    """Map one CLI argument onto the model's documents, resolving it through the snapshot rather than the disk.

    The argument is spelled under the root and followed through the snapshot as ``select_skills_at`` does, so it
    names the document the run reads: a document linked from inside the snapshot is named by the link, and a link
    outside it, which the scan never read, is judged by its spelling.

    The rules apply in order: a directory for a path the snapshot leads to one, then on the file it leads to not
    Markdown, outside ``docs/`` and in no corpus, then on the first segment after ``docs/`` an invalid corpus name
    (the parser's failure as its source) and an unknown corpus, then nested (more than one segment below the
    corpus), then ``model.locate``, where a miss is unlisted. The first segment is judged before depth so a nested
    path under a non-corpus (``docs/schemas/tables/x.md``) names the real cause, an unknown corpus, rather than a
    subdirectory of a corpus that does not exist. Where the snapshot leads to no file, the same rules judge the path
    as spelled, and one that passes them all is missing: a file the scan never entered, such as a nested one, is
    refused for where it sits rather than as missing.

    Args:
        database: The snapshot the argument is resolved in, and the model it must name a document of.
        root: The resolved workspace root; the argument is located relative to it.
        working_directory: What a relative argument is relative to.
        argument: The path as typed; quoted verbatim in the error message.

    Raises:
        NonFileDocumentPathError: If the snapshot leads the argument to a directory.
        NonMarkdownDocumentPathError: If it names a file that is not ``.md``.
        OutsideDocsDocumentPathError: If it lies outside ``docs/``, inside ``docs/__meta__/``, or outside the root.
        CorpuslessDocumentPathError: If it sits directly in ``docs/``.
        InvalidCorpusDocumentPathError: If its corpus directory is not a valid corpus name.
        UnknownCorpusDocumentPathError: If its corpus directory is not a corpus.
        NestedDocumentPathError: If it sits in a subdirectory of its corpus.
        MissingDocumentPathError: If it passes every rule of placement but the snapshot holds no file there.
        UnlistedDocumentPathError: If the model lists no document at the file it leads to.
    """
    # Lexical, as in `select_skills_at`: following links here would read the disk.
    named = Path(os.path.normpath(working_directory / argument))
    spelled = _spell_under_root(root, named)
    if spelled is None:
        raise OutsideDocsDocumentPathError(argument)
    document = database.resolve_file(spelled)
    if document is None and database.resolve(spelled) is not None:
        raise NonFileDocumentPathError(argument)

    model = database.model()
    if document is None:
        _require_document_placement(model, argument, spelled)
        raise MissingDocumentPathError(argument)
    _require_document_placement(model, argument, document)
    ref = model.locate(document)
    if ref is None:
        raise UnlistedDocumentPathError(argument)
    return ref


def _require_document_placement(model: WorkspaceModel, argument: Path, path: RootRelativePath) -> None:
    """Refuse ``path`` unless it is a Markdown file directly inside a corpus the model lists; the first rule it
    fails, in the order ``select_document`` gives, selects the error.

    Raises:
        NonMarkdownDocumentPathError: If ``path`` is not ``.md``.
        OutsideDocsDocumentPathError: If it lies outside ``docs/`` or inside ``docs/__meta__/``.
        CorpuslessDocumentPathError: If it sits directly in ``docs/``.
        InvalidCorpusDocumentPathError: If its corpus directory is not a valid corpus name.
        UnknownCorpusDocumentPathError: If its corpus directory is not a corpus.
        NestedDocumentPathError: If it sits in a subdirectory of its corpus.
    """
    if PurePosixPath(path.name).suffix != DOCUMENT_SUFFIX:
        raise NonMarkdownDocumentPathError(argument)
    if not path.is_relative_to(DOCS_DIR) or path.is_relative_to(SPECS_DIR):
        raise OutsideDocsDocumentPathError(argument)
    parts = path.parts[len(DOCS_DIR.parts) :]
    if len(parts) < 2:
        raise CorpuslessDocumentPathError(argument)

    try:
        corpus = CorpusName.parse(parts[0])
    except (EmptyCorpusNameError, InvalidCorpusNameCharacterError) as exc:
        raise InvalidCorpusDocumentPathError(argument, source=exc) from exc
    if model.corpus(corpus) is None:
        raise UnknownCorpusDocumentPathError(argument)
    if len(parts) > 2:
        raise NestedDocumentPathError(argument)


class UnlistedSkillPathError(Error):
    """An explicit skill argument does not name a skill the model lists: it lies outside the root, the snapshot
    holds nothing at it, or no skill the model lists is there.

    Attributes:
        argument: The path exactly as typed.
    """

    argument: Path

    def __init__(self, argument: Path) -> None:
        self.argument = argument
        super().__init__(f'{argument}: not a skill the workspace lists; name a skill directory or its SKILL.md')


def select_skills_at(database: Database, root: Path, working_directory: Path, argument: Path) -> tuple[SkillRef, ...]:
    """Map one CLI argument onto the model's skills, resolving it through the snapshot rather than the disk.

    The argument names a skill by its directory or by its ``SKILL.md``, through a link or not: a skill kept in
    ``skills/review/`` and linked from ``.agents/skills/review`` is named by either path. The part of the
    argument under the root is taken by its spelling alone, then every link in it is followed through the
    snapshot, and every skill the model lists at the real path it leads to is returned, so a directory two
    entries link to selects both.

    Args:
        database: The snapshot the argument is resolved in, and the model it must name a skill of.
        root: The resolved workspace root; the argument is located relative to it.
        working_directory: What a relative argument is relative to.
        argument: The path as typed; quoted verbatim in the error message.

    Returns:
        The skills at the named path, in the model's order; never empty.

    Raises:
        UnlistedSkillPathError: If the argument lies outside the root, the snapshot holds nothing at it,
            or no skill the model lists is there.
    """
    # Lexical, like rust-analyzer's `AbsPath::normalize`: `..` drops the component before it even when that one
    # is a link. Following links here would read the disk; the snapshot follows every link below the root.
    # `/` discards the working directory when the argument is absolute.
    named = Path(os.path.normpath(working_directory / argument))
    spelled = _spell_under_root(root, named)
    if spelled is None:
        raise UnlistedSkillPathError(argument)
    real_path = database.resolve(spelled)
    if real_path is None:
        raise UnlistedSkillPathError(argument)
    refs = database.model().locate_skills(real_path)
    if not refs:
        raise UnlistedSkillPathError(argument)
    return refs


def _spell_under_root(root: Path, named: Path) -> RootRelativePath | None:
    """``named`` relative to the root, or ``None`` when it lies outside it.

    The root is resolved, symlinks followed, but an argument may reach it through a link above it, such as
    ``~/code`` linked to ``/data/code``. The snapshot records nothing above the root, so there the disk is asked
    where each ancestor leads; below the root the argument is taken as spelled, and the snapshot follows its links.
    The disk is never asked about a path under the root: that would read the tree as it is now, not as the
    snapshot saw it.

    Args:
        root: The resolved workspace root.
        named: An absolute path, normalised, so holding no ``..``.
    """
    if named.is_relative_to(root):
        return RootRelativePath.parse(named.relative_to(root).as_posix())
    # Farthest ancestor first, from `/` down: the first one that leads to the root is where the part under the
    # root begins, and no ancestor below it is resolved. Nearest first would resolve those on the live disk.
    for ancestor in reversed(named.parents):
        if Path(os.path.realpath(ancestor)) == root:
            return RootRelativePath.parse(named.relative_to(ancestor).as_posix())
    return None
