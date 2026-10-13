"""Build the workspace model from the specification directory, the corpus directories and the skills directories.

Discovery is spec-first: a directory under `docs/` is a corpus only when `docs/__meta__/` holds a file at
its specification name. The loader lists the specification directory, parses each filename once with
`parse_spec_file`, sorts the parsed files into corpus specs and namespace specs, keeps the corpora whose
`docs/<corpus>/` is a regular directory, lists the Markdown files directly inside each, and builds a
`StructureSpec` from every structure specification, which proves each one usable, its frontmatter schema
included, before any document is read.

The skills come from the agents: the loader asks each agent in `lorecraft.agents` which project skills
directories it reads, keeps the ones the repository has, and lists the skills in each resolved directory once. A
skills directory, a skill entry or a `SKILL.md` whose symlink chain leaves the repository is recorded in the model
as an outside symlink, for a check to report. Any other entry that does not fit the layout is left out of the
model; nothing it leaves out fails the run.

The loader is total over the declaration: it reads each unit on its own, a structure file, a corpus directory, a
skills directory, a skill entry or a `SKILL.md`, and a unit that fails is recorded in the model as a load failure
while the loader goes on with the next one. A structure file that fails stands in its meta spec layer as a
`FailedStructure` and is listed too. Each repository still raises its own error variant; the loader catches the
variants of one unit, keeps the facts they carry and drops the exception. Nothing here logs.
"""

from dataclasses import dataclass, field
from typing import assert_never

from lorecraft.agents import SKILL_ENTRY_FILENAME, iter_agents
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import (
    AspectFilename,
    AspectNamespace,
    EmptyAspectNameError,
    InvalidAspectNameCharacterError,
)
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document.repo import CorpusListError
from lorecraft.project.document.repo import Repository as DocumentRepository
from lorecraft.project.layout import SPECS_DIR
from lorecraft.project.schemas.name import CorpusSpecName, NamespaceSpecName, SpecName
from lorecraft.project.schemas.repo import Repository as SchemaRepository
from lorecraft.project.schemas.repo import StructureSchemaReadError
from lorecraft.project.schemas.spec_file import (
    DottedSpecStemError,
    InvalidSpecStemError,
    NotASpecFileError,
    NotASpecStemError,
    ProseSpecFile,
    SpecFile,
    StructureSpecFile,
    UnknownSpecFileTypeError,
    parse_spec_file,
)
from lorecraft.project.schemas.structure import (
    AdjacentAnyRunsError,
    EmptyStructureSpecError,
    ForbiddenOutlineSectionError,
    ForeignFrontmatterDialectError,
    FrontmatterSchemaIdError,
    InvalidFrontmatterSchemaError,
    InvalidTitlePatternError,
    RepeatedForbiddenSectionError,
    RepeatedOutlineSectionError,
    StructureSpec,
    StructureSpecDecodeError,
    UntypedFrontmatterSchemaError,
)
from lorecraft.project.skill.outside import OutsideSymlink
from lorecraft.project.skill.ref import SkillLocation
from lorecraft.project.skill.repo import Repository as SkillRepository
from lorecraft.project.skill.repo import (
    SkillDirListError,
    SkillEntryResolveError,
    SkillFileResolveError,
    SkillsDirListError,
)
from lorecraft.project.skill.skills_dir import SkillsDir
from lorecraft.vfs import (
    DIR_LIST_FAILURES,
    ENTRY_INSPECT_FAILURES,
    DirResolveError,
    EntryInspectError,
    FileReadError,
    FileResolveError,
    FileSystem,
    RecordedDirResolveError,
    RecordedEntryInspectError,
    RecordedFileReadError,
    RecordedFileReadPathError,
    RecordedFileResolveError,
    ResolvedPath,
    TextDecodeError,
    UnrecordedFileError,
)

from .failure import (
    AdjacentAnyRuns,
    EmptyStructureSpec,
    FailedStructure,
    ForbiddenOutlineSections,
    ForeignFrontmatterDialect,
    FrontmatterSchemaId,
    InvalidFrontmatterSchema,
    InvalidTitlePattern,
    LoadFailure,
    NonUtf8StructureFile,
    RepeatedForbiddenSections,
    RepeatedOutlineSections,
    StructureLoadFailure,
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
)
from .model import Corpus, CorpusNamespace, CorpusSpec, WorkspaceModel, namespace_order_key


@dataclass(slots=True)
class _CorpusFiles:
    """The specification files naming one corpus, gathered before `docs/<corpus>/` is checked.

    Attributes:
        spec: Files at the `<corpus>` specification name; empty when the corpus has no spec of its own.
        namespaces: Files at each `<corpus>-<namespace>` specification name, keyed by namespace.
    """

    spec: list[SpecFile] = field(default_factory=list)
    namespaces: dict[AspectNamespace, list[SpecFile]] = field(default_factory=dict)


def load_workspace(
    schemas: SchemaRepository,
    documents: DocumentRepository,
    skills: SkillRepository,
) -> WorkspaceModel:
    """Build the workspace model of the snapshot; it raises nothing for the declaration.

    Parse the spec filenames, keep corpus specs whose docs/<corpus>/ is a directory, list the Markdown files
    directly inside each, build a structure specification from every spec that has one, and find the agents' skills
    directories and the skills in them. Each unit that cannot be read or used is recorded in the model's
    `load_failures`, and the units that can are loaded as if it had not failed.

    Args:
        schemas: Repository the specification files are listed and read from.
        documents: Repository the corpus directories and their Markdown files are listed from.
        skills: Repository the agents' skills directories are resolved and their skills listed from.
    """
    failures: list[LoadFailure] = []
    spec_paths = _list_spec_paths(schemas, failures)
    corpus_directories = _list_corpus_directories(documents, failures)

    groups = _group_spec_files(spec_paths)

    corpora: list[Corpus] = []
    for corpus_name in sorted(groups, key=str):
        files = groups[corpus_name]
        if not files.spec:
            # A namespace spec narrows a corpus spec; without one there is nothing to narrow.
            continue
        if PathComponent.parse(str(corpus_name)) not in corpus_directories:
            # A corpus is a regular directory under docs/; a missing or linked one has no documents to list.
            continue
        filenames = _list_document_filenames(documents, corpus_name, failures)
        corpora.append(_load_corpus(schemas, corpus_name, files, filenames, failures))

    skills_dirs, outside_skills_dirs = _load_skills_dirs(skills, failures)
    skill_locations, outside_entries = _list_skill_locations(skills, skills_dirs, failures)
    # Keyed by path: when one resolved skills directory is an entry of another, the same `<entry>/SKILL.md` symlink
    # is reached twice, as the outer listing's entry `SKILL.md` and as an entry of the inner listing.
    outside_by_path: dict[RootRelativePath, OutsideSymlink] = {}
    for outside in outside_skills_dirs + outside_entries:
        outside_by_path[outside.path] = outside
    return WorkspaceModel(
        corpora=tuple(corpora),
        skills_dirs=skills_dirs,
        skill_locations=skill_locations,
        outside_symlinks=tuple(outside_by_path[path] for path in sorted(outside_by_path)),
        # Two agents declaring one skills directory meet its failure twice; it is one failure at one path.
        load_failures=tuple(dict.fromkeys(failures)),
    )


def load_model(fs: FileSystem) -> WorkspaceModel:
    """Wire one filesystem view into the three repositories and load the workspace model through them.

    The view decides where the model comes from: a `DiskFileSystem` reads the disk as it is at each call,
    and a `VirtualFileSystem` answers from one snapshot, so the model reflects a single moment. Nothing the
    declaration holds raises: a unit that fails is recorded in the model.

    Args:
        fs: View of the repository the model is loaded from, rooted at the workspace root.
    """
    schemas = SchemaRepository(fs, SPECS_DIR)
    documents = DocumentRepository(fs)
    skills = SkillRepository(fs)
    return load_workspace(schemas, documents, skills)


def _list_spec_paths(schemas: SchemaRepository, failures: list[LoadFailure]) -> list[RootRelativePath]:
    """Every file in the specification directory, or `[]` when it cannot be listed, which is then recorded.

    Args:
        schemas: Repository the specification directory is listed from.
        failures: The load failures so far; a directory that cannot be listed is appended.
    """
    try:
        return schemas.list_spec_paths()
    except DIR_LIST_FAILURES as exc:
        failures.append(LoadFailure(exc.path, UnlistableDirectory(exc.refusal)))
        return []


def _list_corpus_directories(documents: DocumentRepository, failures: list[LoadFailure]) -> frozenset[PathComponent]:
    """The names of the regular directories under docs/, or none when docs/ cannot be listed, which is then recorded.

    Args:
        documents: Repository docs/ is listed from.
        failures: The load failures so far; a directory that cannot be listed is appended.
    """
    try:
        return documents.list_corpus_directories()
    except DIR_LIST_FAILURES as exc:
        failures.append(LoadFailure(exc.path, UnlistableDirectory(exc.refusal)))
        return frozenset()


def _group_spec_files(spec_paths: list[RootRelativePath]) -> dict[CorpusName, _CorpusFiles]:
    """Parse every file in the specification directory and file it under the corpus its specification name starts with.

    A file whose name does not parse as a specification filename, such as `README.md`, is left out.

    Args:
        spec_paths: Every file listed in the specification directory, in listing order.
    """
    groups: dict[CorpusName, _CorpusFiles] = {}
    for path in spec_paths:
        try:
            spec_file = parse_spec_file(path)
        except (
            NotASpecFileError,
            UnknownSpecFileTypeError,
            NotASpecStemError,
            DottedSpecStemError,
            InvalidSpecStemError,
        ):
            continue

        group = groups.setdefault(spec_file.corpus, _CorpusFiles())
        match spec_file.name:
            case CorpusSpecName():
                group.spec.append(spec_file)
            case NamespaceSpecName(namespace=namespace):
                group.namespaces.setdefault(namespace, []).append(spec_file)
            case _:
                assert_never(spec_file.name)
    return groups


def _load_corpus(
    schemas: SchemaRepository,
    corpus_name: CorpusName,
    files: _CorpusFiles,
    filenames: list[AspectFilename],
    failures: list[LoadFailure],
) -> Corpus:
    """Decode the corpus spec and its namespace specs; a structure file that fails stands in its layer.

    Args:
        schemas: Repository the structure specifications are read from.
        corpus_name: Name of the corpus being built, which every specification name of its files starts with.
        files: Specification files at the corpus spec's name and at each of its namespace specs' names.
        filenames: Stems of the documents listed in the corpus directory, which the corpus lists by filename.
        failures: The load failures so far; each structure file that fails is appended.
    """
    corpus_spec_name = CorpusSpecName(corpus_name)
    corpus_spec = CorpusSpec(
        name=corpus_spec_name,
        files=_sorted_paths(files.spec),
        structure=_load_structure(schemas, corpus_spec_name, files.spec, failures),
    )

    # The corpus orders its namespace specs itself; they are decoded broad to narrow too, so that of two broken
    # structure specifications the broader one is the failure listed first.
    namespaces: list[CorpusNamespace] = []
    for namespace in sorted(files.namespaces, key=namespace_order_key):
        namespace_spec_name = NamespaceSpecName(corpus_name, namespace)
        namespace_files = files.namespaces[namespace]
        corpus_namespace = CorpusNamespace(
            namespace=namespace,
            files=_sorted_paths(namespace_files),
            structure=_load_structure(schemas, namespace_spec_name, namespace_files, failures),
        )
        namespaces.append(corpus_namespace)

    return Corpus(corpus_spec=corpus_spec, namespaces=tuple(namespaces), filenames=tuple(filenames))


def _sorted_paths(spec_files: list[SpecFile]) -> tuple[RootRelativePath, ...]:
    """The root-relative paths of the files at one specification name, sorted.

    Args:
        spec_files: Files at one specification name, prose and JSON, in listing order.
    """
    return tuple(sorted((spec_file.path for spec_file in spec_files), key=str))


def _load_structure(
    schemas: SchemaRepository, name: SpecName, spec_files: list[SpecFile], failures: list[LoadFailure]
) -> StructureSpec | FailedStructure | None:
    """Decode the structure JSON among the files at one specification name into a structure specification.

    Args:
        schemas: Repository the structure specification is read from.
        name: Specification name the files sit at: the corpus alone, or the corpus and a namespace.
        spec_files: Files at that name, prose and JSON, in listing order; only the structure file among them is decoded.
        failures: The load failures so far; a structure file that cannot be read or used is appended.

    Returns:
        The structure specification, the failed structure standing in its place when the file cannot be read or
        used, or None when no file at the name is a structure file.
    """
    structure: StructureSpec | FailedStructure | None = None
    for spec_file in spec_files:
        match spec_file:
            case StructureSpecFile():
                # Building the structure specification is the check: StructureSpec.parse rejects text that is not JSON
                # in the structure dialect, rules that are not usable, and a malformed frontmatter schema.
                try:
                    structure = StructureSpec.parse(spec_file, schemas.get_structure_schema(name))
                except StructureSchemaReadError as exc:
                    match exc.source:
                        case FileReadError() | RecordedFileReadError() | RecordedFileReadPathError():
                            failure: StructureLoadFailure = UnreadableStructureFile(exc.name, exc.source.refusal)
                        case UnrecordedFileError():
                            failure = UnrecordedStructureFile(exc.name)
                        case TextDecodeError():
                            failure = NonUtf8StructureFile(exc.source.failure)
                        case _:
                            assert_never(exc.source)
                    structure = _record_failed_structure(failures, spec_file.path, failure)
                except StructureSpecDecodeError as exc:
                    failure = UndecodableStructureSpec(exc.problems)
                    structure = _record_failed_structure(failures, spec_file.path, failure)
                except EmptyStructureSpecError:
                    structure = _record_failed_structure(failures, spec_file.path, EmptyStructureSpec())
                except RepeatedOutlineSectionError as exc:
                    failure = RepeatedOutlineSections(exc.sections)
                    structure = _record_failed_structure(failures, spec_file.path, failure)
                except RepeatedForbiddenSectionError as exc:
                    failure = RepeatedForbiddenSections(exc.sections)
                    structure = _record_failed_structure(failures, spec_file.path, failure)
                except ForbiddenOutlineSectionError as exc:
                    failure = ForbiddenOutlineSections(exc.sections)
                    structure = _record_failed_structure(failures, spec_file.path, failure)
                except AdjacentAnyRunsError:
                    structure = _record_failed_structure(failures, spec_file.path, AdjacentAnyRuns())
                except InvalidTitlePatternError as exc:
                    failure = InvalidTitlePattern(exc.pattern, exc.problem)
                    structure = _record_failed_structure(failures, spec_file.path, failure)
                except InvalidFrontmatterSchemaError as exc:
                    failure = InvalidFrontmatterSchema(exc.problem)
                    structure = _record_failed_structure(failures, spec_file.path, failure)
                except FrontmatterSchemaIdError:
                    structure = _record_failed_structure(failures, spec_file.path, FrontmatterSchemaId())
                except ForeignFrontmatterDialectError as exc:
                    # The dialect is whatever JSON value `$schema` held, so the record keeps it as its `repr` text.
                    failure = ForeignFrontmatterDialect(repr(exc.dialect))
                    structure = _record_failed_structure(failures, spec_file.path, failure)
                except UntypedFrontmatterSchemaError:
                    structure = _record_failed_structure(failures, spec_file.path, UntypedFrontmatterSchema())
            case ProseSpecFile():
                pass  # the prose is written for a reader, and no check decodes it
            case _:
                assert_never(spec_file)
    return structure


def _record_failed_structure(
    failures: list[LoadFailure], path: RootRelativePath, failure: StructureLoadFailure
) -> FailedStructure:
    """List a structure file's failure on the model and return the failed structure that stands in its layer.

    Args:
        failures: The load failures so far; the failure is appended.
        path: Root-relative path of the structure file.
        failure: The condition the file failed with.
    """
    failures.append(LoadFailure(path, failure))
    return FailedStructure(path, failure)


def _list_document_filenames(
    documents: DocumentRepository, corpus_name: CorpusName, failures: list[LoadFailure]
) -> list[AspectFilename]:
    """The stems of the validly named Markdown files the repository lists in the corpus; the rest are left out.

    A corpus directory that cannot be listed holds no document, and the failure is recorded.

    Args:
        documents: Repository the corpus directory is listed from.
        corpus_name: Corpus whose directory is listed.
        failures: The load failures so far; a directory that cannot be listed is appended.
    """
    try:
        document_files = documents.list_documents(corpus_name)
    except CorpusListError as exc:
        failures.append(LoadFailure(exc.source.path, UnlistableCorpusDirectory(exc.corpus, exc.source.refusal)))
        return []

    filenames: list[AspectFilename] = []
    for document_file in document_files:
        try:
            filename = AspectFilename.parse(document_file.stem)
        except (EmptyAspectNameError, InvalidAspectNameCharacterError):
            continue
        filenames.append(filename)
    return filenames


def _load_skills_dirs(
    skills: SkillRepository, failures: list[LoadFailure]
) -> tuple[tuple[SkillsDir, ...], tuple[OutsideSymlink, ...]]:
    """One record per agent and project skills directory it reads, for the directories the repository has.

    The records are sorted by agent then path, so the model does not depend on the order the agents are registered
    in. A declared directory whose symlink chain leaves the repository is no directory the repository has; it is
    returned apart, once however many agents declare it, sorted by path. A declared directory that cannot be
    resolved is recorded as a failure and read by no agent.

    Args:
        skills: Repository each declared skills directory is resolved through.
        failures: The load failures so far; a skills directory that cannot be resolved is appended.

    Returns:
        A pair: the skills directories the repository has, one per agent and directory; then each declared
        directory whose chain leaves the repository, as an outside symlink.
    """
    skills_dirs: list[SkillsDir] = []
    outside: dict[RootRelativePath, OutsideSymlink] = {}
    for agent in iter_agents():
        for declared in agent.project_skills_dirs:
            path = RootRelativePath(declared)
            try:
                resolves_to = skills.find_skills_dir(path)
                if resolves_to is None:
                    # The repository has no such directory, so the agent reads no skills from it; recorded when the
                    # agent would read one outside the repository instead.
                    leads_outside = skills.find_skills_dir_exit(path)
                    if leads_outside is not None:
                        outside[path] = leads_outside
                    continue
            except DirResolveError as exc:
                failures.append(LoadFailure(path, UnresolvableSkillsDirectory(exc.refusal)))
                continue
            except RecordedDirResolveError as exc:
                # The snapshot kept which entry on the way was refused, which the disk's lookup does not say.
                failures.append(LoadFailure(path, UninspectableSkillsDirectory(exc.source.path, exc.refusal)))
                continue
            except ENTRY_INSPECT_FAILURES as exc:
                failures.append(LoadFailure(path, UninspectableSkillsDirectory(exc.path, exc.refusal)))
                continue
            skills_dirs.append(SkillsDir(agent=agent.name, path=path, resolves_to=resolves_to))
    skills_dirs.sort(key=lambda skills_dir: (str(skills_dir.agent), skills_dir.path))
    return tuple(skills_dirs), tuple(outside[path] for path in sorted(outside))


def _list_skill_locations(
    skills: SkillRepository, skills_dirs: tuple[SkillsDir, ...], failures: list[LoadFailure]
) -> tuple[tuple[SkillLocation, ...], tuple[OutsideSymlink, ...]]:
    """The location of every skill in the resolved directories behind `skills_dirs`, each once, sorted by directory.

    Two agents reading one resolved directory add no second skill: the directory is listed once. The locations are
    sorted as a whole, since one skills directory may sit inside another. Returned beside them, sorted by path, is
    every entry and every entry's `SKILL.md` in those directories whose symlink chain leaves the repository.

    Each entry is a unit of its own: one that cannot be resolved is recorded as a failure and the entries after it
    are listed. A directory that cannot be listed lists no skill and is recorded.

    Args:
        skills: Repository each resolved directory is listed through.
        skills_dirs: Skills directories the agents read; only the resolved directory each leads to is listed.
        failures: The load failures so far; each unit that fails is appended.

    Returns:
        A pair: the location of every skill; then every entry and entry's `SKILL.md` whose chain leaves the
        repository, as an outside symlink.
    """
    resolved_directories: set[ResolvedPath] = set()
    for skills_dir in skills_dirs:
        resolved_directories.add(skills_dir.resolves_to)

    locations: list[SkillLocation] = []
    outside_symlinks: list[OutsideSymlink] = []
    # Sorted, so the failures are met in the same order whatever the order the set holds its directories in.
    for resolved_directory in sorted(resolved_directories):
        try:
            entries = skills.list_skill_entries(resolved_directory)
        except SkillsDirListError as exc:
            # Filed at each path an agent declares for the directory, which may be a link to it.
            for skills_dir in skills_dirs:
                if skills_dir.resolves_to == resolved_directory:
                    condition = UnlistableSkillsDirectory(exc.skills_dir, exc.source.refusal)
                    failures.append(LoadFailure(skills_dir.path, condition))
            continue
        for entry in entries:
            # Where an agent reaches the entry, which may be a link: a failure is filed here, not where it leads.
            entry_path = resolved_directory / entry.name
            try:
                listing = skills.list_skill_entry(resolved_directory, entry)
            except SkillEntryResolveError as exc:
                match exc.source:
                    case DirResolveError():
                        condition = UnresolvableSkillEntry(exc.source.refusal)
                    case RecordedDirResolveError():
                        condition = UninspectableSkillEntry(exc.source.source.path, exc.source.refusal)
                    case EntryInspectError() | RecordedEntryInspectError():
                        condition = UninspectableSkillEntry(exc.source.path, exc.source.refusal)
                    case _:
                        assert_never(exc.source)
                failures.append(LoadFailure(entry_path, condition))
                continue
            except SkillDirListError as exc:
                condition = UnlistableSkillDirectory(exc.directory, exc.source.refusal)
                failures.append(LoadFailure(entry_path, condition))
                continue
            except SkillFileResolveError as exc:
                skill_file_path = entry_path / SKILL_ENTRY_FILENAME
                match exc.source:
                    case FileResolveError():
                        condition = UnresolvableSkillFile(exc.skill_file, exc.source.refusal)
                    case RecordedFileResolveError():
                        condition = UninspectableSkillFile(exc.skill_file, exc.source.source.path, exc.source.refusal)
                    case EntryInspectError() | RecordedEntryInspectError():
                        condition = UninspectableSkillFile(exc.skill_file, exc.source.path, exc.source.refusal)
                    case _:
                        assert_never(exc.source)
                failures.append(LoadFailure(skill_file_path, condition))
                continue
            locations.extend(listing.skills)
            outside_symlinks.extend(listing.outside_symlinks)
    return tuple(sorted(locations)), tuple(sorted(outside_symlinks, key=lambda outside: outside.path))
