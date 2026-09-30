"""Map an explicit document or skill argument from the command line onto the workspace model.

A document argument is a disk path by definition, so it is resolved once, symlinks followed, and everything after
that is a pure question to the model. A skill argument is only spelled on disk: the disk is asked only where it
leads above the root, the part under the root is taken as spelled, and every link in that part is followed
through the snapshot, so it names what the model saw even when the tree changed since. An explicit path is a
boundary, so it is rejected with the most specific reason it fails, where discovery would simply have ignored
the file.
"""

import os
from enum import Enum
from pathlib import Path

from lorecraft.checks import Database
from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import CorpusName, CorpusNameError
from lorecraft.project.document import DocumentRef
from lorecraft.project.layout import DOCS_DIR, DOCUMENT_SUFFIX, SPECS_DIR
from lorecraft.project.skill import SkillRef
from lorecraft.project.workspace import WorkspaceModel
from lorecraft.vfs import disk_location


class DocumentPathProblem(Enum):
    """Which rule an explicit document argument failed; the message of each is its value."""

    UNREADABLE = 'cannot read file'
    NOT_A_FILE = 'expected a readable Markdown file'
    NOT_MARKDOWN = 'expected a .md file'
    OUTSIDE_DOCS = 'file must be inside docs/ and outside docs/__meta__/'
    NOT_IN_CORPUS = 'file must be inside a corpus directory under docs/'
    INVALID_CORPUS_NAME = 'invalid corpus name'
    NOT_A_CORPUS = 'not a corpus: no docs/__meta__/<dir>.* specification'
    NESTED = 'corpora are flat; the file is in a subdirectory of its corpus'
    NOT_LISTED = 'not a document the workspace lists'


class DocumentPathError(Error):
    """An explicit document argument does not name a document the model lists.

    Attributes:
        argument: The path exactly as typed.
        reason: Which rule it failed; tests compare this, never the message.
        detail: Extra text from the underlying failure (strerror, the CorpusName message), or ''.
    """

    argument: Path
    reason: DocumentPathProblem
    detail: str

    def __init__(self, argument: Path, reason: DocumentPathProblem, detail: str = '') -> None:
        self.argument = argument
        self.reason = reason
        self.detail = detail
        super().__init__(f'{argument}: {detail or reason.value}')


def select_document(model: WorkspaceModel, root: Path, argument: Path) -> DocumentRef:
    """Resolve one CLI argument (symlinks followed, one realpath) and map it onto the model.

    The rules apply in order: UNREADABLE, NOT_A_FILE, NOT_MARKDOWN, OUTSIDE_DOCS, NOT_IN_CORPUS, then on the
    first segment after docs/ INVALID_CORPUS_NAME (from ``CorpusName.parse``, chained) and NOT_A_CORPUS, then
    NESTED (more than one segment below the corpus), then ``model.locate``, where a miss is NOT_LISTED. The
    first segment is judged before depth so a nested path under a non-corpus (``docs/schemas/tables/x.md``)
    names the real cause, NOT_A_CORPUS, rather than a subdirectory of a corpus that does not exist.

    Args:
        model: The model the argument must name a document of.
        root: The resolved workspace root; ``docs/`` is judged relative to it.
        argument: The path as typed; quoted verbatim in the error message.

    Raises:
        DocumentPathError: One reason per rule above.
    """
    try:
        document = argument.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        # Python 3.12 raises RuntimeError, not OSError, for a symlink loop under strict resolution.
        detail = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
        raise DocumentPathError(argument, DocumentPathProblem.UNREADABLE, detail) from exc
    if not document.is_file():
        raise DocumentPathError(argument, DocumentPathProblem.NOT_A_FILE)
    if document.suffix != DOCUMENT_SUFFIX:
        raise DocumentPathError(argument, DocumentPathProblem.NOT_MARKDOWN)

    docs_root = disk_location(root, DOCS_DIR)
    specs_root = disk_location(root, SPECS_DIR)
    if not document.is_relative_to(docs_root) or document.is_relative_to(specs_root):
        raise DocumentPathError(argument, DocumentPathProblem.OUTSIDE_DOCS)
    parts = document.relative_to(docs_root).parts
    if len(parts) < 2:
        raise DocumentPathError(argument, DocumentPathProblem.NOT_IN_CORPUS)

    try:
        corpus = CorpusName.parse(parts[0])
    except CorpusNameError as exc:
        raise DocumentPathError(argument, DocumentPathProblem.INVALID_CORPUS_NAME, str(exc)) from exc
    if model.corpus(corpus) is None:
        raise DocumentPathError(argument, DocumentPathProblem.NOT_A_CORPUS)
    if len(parts) > 2:
        raise DocumentPathError(argument, DocumentPathProblem.NESTED)

    # Exactly two parts by now, both components of a resolved path under docs/, so neither is `..`.
    ref = model.locate(DOCS_DIR / parts[0] / parts[1])
    if ref is None:
        raise DocumentPathError(argument, DocumentPathProblem.NOT_LISTED)
    return ref


class SkillPathProblem(Enum):
    """Which rule an explicit skill argument failed; the message of each is its value."""

    NOT_LISTED = 'not a skill the workspace lists; name a skill directory or its SKILL.md'


class SkillPathError(Error):
    """An explicit skill argument does not name a skill the model lists.

    Attributes:
        argument: The path exactly as typed.
        reason: Which rule it failed; tests compare this, never the message.
    """

    argument: Path
    reason: SkillPathProblem

    def __init__(self, argument: Path, reason: SkillPathProblem) -> None:
        self.argument = argument
        self.reason = reason
        super().__init__(f'{argument}: {reason.value}')


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
        SkillPathError: NOT_LISTED when the argument lies outside the root, the snapshot holds nothing at it,
            or no skill the model lists is there.
    """
    # Lexical, like rust-analyzer's `AbsPath::normalize`: `..` drops the component before it even when that one
    # is a link. Following links here would read the disk; the snapshot follows every link below the root.
    # `/` discards the working directory when the argument is absolute.
    named = Path(os.path.normpath(working_directory / argument))
    spelled = _spell_under_root(root, named)
    if spelled is None:
        raise SkillPathError(argument, SkillPathProblem.NOT_LISTED)
    real_path = database.resolve(spelled)
    if real_path is None:
        raise SkillPathError(argument, SkillPathProblem.NOT_LISTED)
    refs = database.model().locate_skills(real_path)
    if not refs:
        raise SkillPathError(argument, SkillPathProblem.NOT_LISTED)
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
