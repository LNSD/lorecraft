"""Map an explicit document or skill argument from the command line onto the workspace model.

An argument is only spelled on disk: the disk is asked only where it leads above the root, the part under the
root is taken as spelled, and its links are followed through the snapshot, so it names what the model saw even
when the tree changed since. A skill argument naming an entry of an agent's skills directory keeps that entry's
own link unfollowed, so it names the skill an agent lists there and not every entry linked to the same directory.
A skill argument naming an agent's skills directory selects every skill listed there. Any other directory a skill
argument names is spelled before the snapshot is taken, so the snapshot reads it and the model lists the skills in
it under that spelling. An explicit path is a boundary, so it is rejected with the most specific reason it fails,
where discovery would simply have ignored the file.
"""

import os
from pathlib import Path, PurePosixPath

from lorecraft.agents import SKILL_ENTRY_FILENAME
from lorecraft.checks import Database, SkillScope, SkillSelection
from lorecraft.core.error import Error
from lorecraft.core.path import ROOT, RootRelativePath
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
    corpus), then ``model.find_document``, where a miss is unlisted. The first segment is judged before depth so a
    nested path under a non-corpus (``docs/schemas/tables/x.md``) names the real cause, an unknown corpus, rather
    than a subdirectory of a corpus that does not exist. Where the snapshot leads to no file, the same rules judge
    the path as spelled, and one that passes them all is missing: a file the scan never entered, such as a nested
    one, is refused for where it sits rather than as missing.

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
    spelled = _find_spelling_under_root(root, named)
    if spelled is None:
        raise OutsideDocsDocumentPathError(argument)
    document = database.find_canonical_file(spelled)
    if document is None and database.find_canonical_path(spelled) is not None:
        raise NonFileDocumentPathError(argument)

    model = database.model()
    if document is None:
        _reject_misplaced_document(model, argument, spelled)
        raise MissingDocumentPathError(argument)
    _reject_misplaced_document(model, argument, document)
    ref = model.find_document(document)
    if ref is None:
        raise UnlistedDocumentPathError(argument)
    return ref


def _reject_misplaced_document(model: WorkspaceModel, argument: Path, path: RootRelativePath) -> None:
    """Refuse `path` unless it is a Markdown file directly inside a corpus the model lists.

    The first rule it fails, in the order `select_document` gives, selects the error.

    Args:
        model: The workspace model whose corpora the path's corpus directory is looked up in.
        argument: The path as typed; carried into the error raised, so the message quotes what the user wrote.
        path: The root-relative path the rules are judged on, which may differ from `argument`.

    Raises:
        NonMarkdownDocumentPathError: If `path` is not `.md`.
        OutsideDocsDocumentPathError: If it lies outside `docs/` or inside `docs/__meta__/`.
        CorpuslessDocumentPathError: If it sits directly in `docs/`.
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
    if model.find_corpus(corpus) is None:
        raise UnknownCorpusDocumentPathError(argument)
    if len(parts) > 2:
        raise NestedDocumentPathError(argument)


class UnlistedSkillPathError(Error):
    """An explicit skill argument does not name a skill the model lists.

    It lies outside the root, the snapshot holds nothing at it, or no skill the model lists is there: it is a
    directory with no `SKILL.md` at its root or in a directory directly inside it, and no symlink leading outside
    the repository either, or it is the root itself.

    Attributes:
        argument: The path exactly as typed.
    """

    argument: Path

    def __init__(self, argument: Path) -> None:
        self.argument = argument
        super().__init__(f'{argument}: no skill there; name a skill directory, a directory of skills, or a SKILL.md')


def named_skill_dirs(root: Path, working_directory: Path, arguments: list[Path]) -> tuple[RootRelativePath, ...]:
    """The directories skill arguments name, root-relative as spelled, for the snapshot to read and the model to list.

    Spelled as `select_skills_at` spells an argument, without the snapshot, which is not taken yet. An argument
    naming a `SKILL.md` names the directory holding it; one outside the root names none. Whether each is a
    directory at all, and whether a skill, a skills directory or neither, only the snapshot and the model tell.

    Args:
        root: The resolved workspace root; each argument is located relative to it.
        working_directory: What a relative argument is relative to.
        arguments: The paths as typed.

    Returns:
        Each directory once, in the order first named.
    """
    directories: list[RootRelativePath] = []
    for argument in arguments:
        spelled = _find_spelling_under_root(root, Path(os.path.normpath(working_directory / argument)))
        if spelled is None:
            continue
        if spelled.name == SKILL_ENTRY_FILENAME:
            spelled = spelled.parent
        if spelled not in directories:
            directories.append(spelled)
    return tuple(directories)


def select_skills_at(
    database: Database, root: Path, working_directory: Path, argument: Path
) -> tuple[SkillSelection, ...]:
    """Map one CLI argument onto the model's skills, resolving it through the snapshot rather than the disk.

    The argument names a skills directory, a skill by its directory, or a skill by its `SKILL.md`, through a link
    or not. The part of the argument under the root is taken by its spelling alone, then read in four ways, in
    order.

    First as an entry of an agent's skills directory, as an agent lists it: the links above the entry are followed
    through the snapshot, the entry itself is kept by its name, and the skill the model lists there is returned
    alone. So `.agents/skills/beta` selects `beta` even when it links to `alpha`, and `.claude/skills/beta`,
    through a linked skills directory, selects it too.

    Then as a directory the snapshot was taken to read, `named_skill_dirs` of the arguments: the skills the model
    lists there, under the argument's spelling. A directory with a `SKILL.md` at its root is one skill, and any other
    holds each directory directly inside it with one. So `skills/review` selects the skill `skills/review`, and not
    `.agents/skills/review`, which links to it: a skill named both ways is two. One holding no skill but a symlink
    leading outside the repository, or leading outside itself, selects none: the run reports that symlink, as it
    does for an agent's skills directory. One holding neither names no skill.

    Then as an agent's skills directory: every link in it is followed through the snapshot, and when a skills
    directory the model lists leads to the canonical path it reaches, every skill listed there is returned, possibly
    none. So `.claude/skills`, a link to `.agents/skills`, selects the skills `.agents/skills` lists, under their
    refs there. The model never names such a directory, so the order of these two readings decides nothing.

    Otherwise as a canonical file: every skill whose `SKILL.md` leads to the file the argument leads to, such as
    `shared/LINT.md` that a linked `SKILL.md` leads to, is returned.

    A path naming a directory selects each skill whole; one naming a `SKILL.md`, by that name or as the file a
    linked `SKILL.md` leads to, selects its `SKILL.md` alone.

    Args:
        database: The snapshot the argument is resolved in, and the model it must name a skill of.
        root: The resolved workspace root; the argument is located relative to it.
        working_directory: What a relative argument is relative to.
        argument: The path as typed; quoted verbatim in the error message.

    Returns:
        The skills at the named path, each once, in the model's order, with what the path named of each; empty only
        for an agent's skills directory that holds no skill, or a named one holding only symlinks leading outside.

    Raises:
        UnlistedSkillPathError: If the argument lies outside the root, the snapshot holds nothing at it,
            or no skill the model lists is there.
    """
    # Lexical, as an IDE normalises a path: `..` drops the component before it even when that one
    # is a link. Following links here would read the disk; the snapshot follows every link below the root.
    # `/` discards the working directory when the argument is absolute.
    named = Path(os.path.normpath(working_directory / argument))
    spelled = _find_spelling_under_root(root, named)
    if spelled is None:
        raise UnlistedSkillPathError(argument)
    listed = _select_listed_skill(database, spelled)
    if listed is not None:
        return (listed,)
    model = database.model()
    # Before the canonical path is asked: a named path leading outside the repository leads to none, and is reported.
    in_named_dir = _select_named_skills(model, spelled)
    if in_named_dir is not None:
        return in_named_dir
    canonical_path = database.find_canonical_path(spelled)
    if canonical_path is None:
        raise UnlistedSkillPathError(argument)
    if model.has_skills_dir(canonical_path):
        return select_whole(model.skills_in(canonical_path))
    refs = model.locate_skill_files(canonical_path)
    if not refs:
        raise UnlistedSkillPathError(argument)
    selections: list[SkillSelection] = []
    for ref in refs:
        selections.append(SkillSelection(ref, SkillScope.SKILL_FILE))
    return tuple(selections)


def select_whole(refs: tuple[SkillRef, ...]) -> tuple[SkillSelection, ...]:
    """Each skill selected whole, in the order given.

    Args:
        refs: The skills to select, such as every skill the model lists or those a skills directory holds.
    """
    selections: list[SkillSelection] = []
    for ref in refs:
        selections.append(SkillSelection(ref, SkillScope.WHOLE_SKILL))
    return tuple(selections)


def _select_listed_skill(database: Database, spelled: RootRelativePath) -> SkillSelection | None:
    """The skill listed at the entry `spelled` names, by the entry's directory or its `SKILL.md`, or `None`.

    The entry's parent is followed through the snapshot, so a linked skills directory such as `.claude/skills`
    leads to the canonical one the model lists its skills under. The entry itself is kept as spelled: following it
    would lead to the directory its files live in, which every entry linked there shares.

    The skill is selected by its `SKILL.md` alone when `spelled` ends in `SKILL.md`, and whole when it names the
    entry's directory. The spelling decides it here because the argument is read by its spelling; a path resolved
    to its canonical path has only that location to tell the file from the directory.

    Args:
        database: The snapshot the entry's parent is resolved in, and the model it must name a skill of.
        spelled: The argument, root-relative and taken by its spelling alone.
    """
    entry = spelled
    scope = SkillScope.WHOLE_SKILL
    if spelled.name == SKILL_ENTRY_FILENAME:
        entry = spelled.parent
        scope = SkillScope.SKILL_FILE
    # The root is no entry: it has no name, and no skill is listed at it.
    if entry == ROOT:
        return None
    canonical_parent = database.find_canonical_path(entry.parent)
    if canonical_parent is None:
        return None
    ref = database.model().find_skill(canonical_parent / entry.name)
    if ref is None:
        return None
    return SkillSelection(ref, scope)


def _select_named_skills(model: WorkspaceModel, spelled: RootRelativePath) -> tuple[SkillSelection, ...] | None:
    """The skills of the directory a command named as `spelled`, or of the one holding a `SKILL.md` it names.

    A directory selects each skill it holds whole. A `SKILL.md` selects its skill by that file alone, when the
    directory holding it was named and is that one skill; a `SKILL.md` inside a directory of skills is no skill.
    A named directory holding no skill but a symlink leading outside selects none, so the run reports the symlink;
    so does a `SKILL.md` named that is itself such a symlink.

    Args:
        model: The model whose named directories are looked up.
        spelled: The argument, root-relative and taken by its spelling alone.

    Returns:
        The selections, `()` for a named directory holding only symlinks leading outside, or `None` when no
        named directory holding anything is there, so the argument is read another way.
    """
    if spelled.name != SKILL_ENTRY_FILENAME:
        named_dir = model.find_named_dir(spelled)
        if named_dir is None or named_dir.is_empty():
            return None
        refs: list[SkillRef] = []
        for location in named_dir.skills:
            refs.append(location.ref)
        return select_whole(tuple(refs))

    named_dir = model.find_named_dir(spelled.parent)
    if named_dir is None:
        return None
    for location in named_dir.skills:
        if location.ref.directory == spelled.parent:
            return (SkillSelection(location.ref, SkillScope.SKILL_FILE),)
    for outside in named_dir.outside_symlinks:
        if outside.path == spelled:
            return ()  # the `SKILL.md` named leads outside: the one skill it would be is that finding
    return None


def _find_spelling_under_root(root: Path, named: Path) -> RootRelativePath | None:
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
