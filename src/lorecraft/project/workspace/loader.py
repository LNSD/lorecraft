"""Build the workspace model from the specification directory, the corpus directories and the skills directories.

Discovery is spec-first: a directory under `docs/` is a corpus only when `docs/__meta__/` holds a file at
its specification name. The loader lists the specification directory, parses each filename once with
`parse_spec_file`, sorts the parsed files into corpus specs and namespace specs, keeps the corpora whose
`docs/<corpus>/` is a regular directory, lists the Markdown files directly inside each, and builds a
`StructureSpec` from every structure specification, which proves each one usable, its frontmatter schema
included, before any document is read.
It also records the raw structure source and each usable embedded frontmatter JSON Schema as immutable, typed inputs
for the model; parsed structure specifications remain in their existing layer.

The skills come from the agents: the loader asks each agent in `lorecraft.agents` which project skills
directories it reads, keeps the ones the repository has, and lists the skills in each resolved directory once. A
skills directory, a skill or a `SKILL.md` whose symlink chain leaves the repository is recorded in the model
as an outside symlink, for a check to report. Any other entry that does not fit the layout is left out of the
model; nothing it leaves out fails the run.

The loader is total over the declaration: it reads each unit on its own, a structure file, a corpus directory, a
skills directory, a skill or a `SKILL.md`, and a unit that fails is recorded in the model as a load failure
while the loader goes on with the next one. A structure file that fails stands in its spec layer as a
`FailedStructure` and is listed too. Each repository still raises its own error variant; the loader catches the
variants of one unit, keeps the details they carry and drops the exception. Nothing here logs.
"""

import json
from dataclasses import dataclass, field, replace
from typing import assert_never

from pydantic import JsonValue

from lorecraft.agents import SKILL_ENTRYPOINT, iter_agents
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import (
    AspectFilename,
    AspectNamespace,
    EmptyAspectNameError,
    InvalidAspectNameCharacterError,
)
from lorecraft.project.corpus import META_CORPUS_NAME, SKILLS_CORPUS_NAME, CorpusName, ReservedCorpusDirectory
from lorecraft.project.document import CorpusListError, SpecRef
from lorecraft.project.document import Repository as DocumentRepository
from lorecraft.project.layout import DOCS_DIR, SPECS_DIR
from lorecraft.project.schemas import (
    CorpusSpecName,
    DottedSpecStemError,
    InvalidSpecStemError,
    NamespaceSpecName,
    NotASpecFileError,
    NotASpecStemError,
    ProseSpecFile,
    SpecFile,
    StructureSchema,
    StructureSchemaReadError,
    StructureSpec,
    StructureSpecFile,
    UnknownSpecFileTypeError,
    parse_spec_file,
)
from lorecraft.project.schemas import Repository as SchemaRepository
from lorecraft.project.schemas.agent_skills_compatibility import agent_skills_schema_contradictions
from lorecraft.project.schemas.structure_failure import ContradictorySkillField
from lorecraft.project.skill import (
    OutsideSymlink,
    SkillDirListError,
    SkillEntryResolveError,
    SkillFileResolveError,
    SkillLocation,
    SkillsDir,
    SkillsDirListError,
)
from lorecraft.project.skill import Repository as SkillRepository
from lorecraft.schemas import (
    RepositoryOrigin,
    SchemaInput,
    SchemaKind,
    SchemaRef,
)
from lorecraft.vfs import (
    DIR_LIST_FAILURES,
    ROOT_EXIT_WALK_FAILURES,
    DirResolveError,
    FileReadError,
    FileResolveError,
    FileSystem,
    RecordedDirResolveError,
    RecordedFileReadError,
    RecordedFileReadPathError,
    RecordedFileResolveError,
    RecordedRootExitWalkError,
    ResolvedPath,
    RootExitWalkError,
    TextDecodeError,
    UnrecordedFileError,
)

from .failure import (
    FailedStructure,
    LoadFailure,
    NonUtf8StructureFile,
    StructureLoadFailure,
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
)
from .model import (
    BuiltinSpecLayer,
    Corpus,
    CorpusNamespace,
    CorpusSpec,
    WorkspaceModel,
    agent_skills_floor_enabled,
    namespace_order_key,
)


@dataclass(slots=True)
class _NameFiles:
    """The specification files at one specification name.

    Attributes:
        structure: The structure file, or None when the name has none.
        prose: The prose files, in listing order.
    """

    structure: StructureSpecFile | None = None
    prose: list[ProseSpecFile] = field(default_factory=list)

    def add(self, spec_file: SpecFile) -> None:
        """File one specification file under the name.

        Args:
            spec_file: A file at this specification name.
        """
        match spec_file:
            case ProseSpecFile():
                self.prose.append(spec_file)
            case StructureSpecFile():
                self.structure = spec_file
            case _:
                assert_never(spec_file)

    def is_empty(self) -> bool:
        """True when no file was filed under the name."""
        return self.structure is None and not self.prose


@dataclass(slots=True)
class _CorpusFiles:
    """The specification files naming one corpus, gathered before `docs/<corpus>/` is checked.

    Attributes:
        spec: Files at the `<corpus>` specification name; empty when the corpus has no spec of its own.
        namespaces: Files at each `<corpus>-<namespace>` specification name, keyed by namespace.
    """

    spec: _NameFiles = field(default_factory=_NameFiles)
    namespaces: dict[AspectNamespace, _NameFiles] = field(default_factory=dict)


def load_workspace(
    schemas: SchemaRepository,
    documents: DocumentRepository,
    skills: SkillRepository,
    *,
    builtin_layers: tuple[BuiltinSpecLayer, ...],
) -> WorkspaceModel:
    """Build the workspace model of the snapshot; invalid repository declarations are recorded, not raised.

    Parse the spec filenames, keep corpus specs whose docs/<corpus>/ is a directory, list the Markdown files
    directly inside each, build a structure specification from every spec that has one, and find the agents' skills
    directories and the skills in them. Each unit that cannot be read or used is recorded in the model's
    `load_failures`, and the units that can are loaded as if it had not failed.

    Args:
        schemas: Repository the specification files are listed and read from.
        documents: Repository the corpus directories and their Markdown files are listed from.
        skills: Repository the agents' skills directories are resolved and their skills listed from.
        builtin_layers: The builtin specification layers enabled for this workspace.

    Raises:
        DuplicateSchemaRefError: If enabled builtin layers or repository specs repeat a schema reference.
    """
    failures: list[LoadFailure] = []
    schema_inputs: dict[SchemaRef, SchemaInput] = {}
    skills_floor_enabled = agent_skills_floor_enabled(builtin_layers)
    spec_paths = _list_spec_paths(schemas, failures)
    corpus_directories, dropped_corpora = _list_corpus_directories(documents, failures)
    unchecked_symlinks: list[RootRelativePath] = list(dropped_corpora)

    groups = _group_spec_files(spec_paths)
    listed_specifications = tuple(
        sorted(
            SpecRef(file.path)
            for group in groups.values()
            for named_files in (group.spec, *group.namespaces.values())
            for file in named_files.prose
        )
    )

    corpora: dict[CorpusName, Corpus] = {}
    skills_corpus: Corpus | None = None
    meta_corpus: Corpus | None = None
    overlapping_directories: set[ReservedCorpusDirectory] = set()
    for corpus_name in sorted(groups, key=str):
        files = groups[corpus_name]
        if files.spec.is_empty():
            # A namespace spec narrows a corpus spec; without one there is nothing to narrow.
            continue
        has_directory = PathComponent.parse(str(corpus_name)) in corpus_directories
        if str(corpus_name) in {META_CORPUS_NAME, SKILLS_CORPUS_NAME}:
            # Reserved corpora have no documents directory; their items come from another repository listing.
            if has_directory:
                directory = DOCS_DIR / PathComponent.parse(str(corpus_name))
                overlapping_directories.add(ReservedCorpusDirectory(directory, corpus_name))
            reserved = _load_corpus(
                schemas,
                corpus_name,
                files,
                [],
                failures,
                schema_inputs,
                skills_floor_enabled,
            )
            if str(corpus_name) == META_CORPUS_NAME:
                meta_corpus = reserved
            else:
                skills_corpus = reserved
            continue
        if not has_directory:
            # A corpus is a regular directory under docs/; a missing or linked one has no documents to list.
            continue
        filenames, dropped_documents = _list_document_filenames(documents, corpus_name, failures)
        unchecked_symlinks.extend(dropped_documents)
        corpora[corpus_name] = _load_corpus(
            schemas, corpus_name, files, filenames, failures, schema_inputs, skills_floor_enabled
        )

    skills_dirs, outside_skills_dirs = _load_skills_dirs(skills, failures)
    skill_locations, outside_entries = _list_skill_locations(skills, skills_dirs, failures)
    # Keyed by path: when one resolved skills directory is an entry of another, the same `<entry>/SKILL.md` symlink
    # is reached twice, as the outer listing's entry `SKILL.md` and as an entry of the inner listing.
    outside_by_path: dict[RootRelativePath, OutsideSymlink] = {}
    for outside in outside_skills_dirs + outside_entries:
        outside_by_path[outside.path] = outside
    return WorkspaceModel(
        corpora=FrozenMapping(corpora),
        skills_dirs=frozenset(skills_dirs),
        skill_locations=FrozenMapping({location.ref: location for location in skill_locations}),
        outside_symlinks=FrozenMapping(outside_by_path),
        # Two agents declaring one skills directory meet its failure twice; it is one failure at one path.
        load_failures=tuple(dict.fromkeys(failures)),
        skills_corpus=skills_corpus,
        meta_corpus=meta_corpus,
        listed_specifications=listed_specifications,
        overlapping_directories=frozenset(overlapping_directories),
        unchecked_symlinks=tuple(sorted(set(unchecked_symlinks), key=str)),
        repository_schema_inputs=FrozenMapping(schema_inputs),
        builtin_layers=builtin_layers,
    )


def load_model(
    fs: FileSystem,
    *,
    builtin_layers: tuple[BuiltinSpecLayer, ...],
) -> WorkspaceModel:
    """Wire one filesystem view into the three repositories and load the workspace model through them.

    The view decides where the model comes from: a view of the disk reads it as it is at each call,
    and a `VirtualFileSystem` answers from one snapshot, so the model reflects a single moment. Nothing the
    declaration holds raises: a unit that fails is recorded in the model.

    Args:
        fs: View of the repository the model is loaded from, rooted at the workspace root.
        builtin_layers: The builtin specification layers enabled for this workspace.
    """
    schemas = SchemaRepository(fs, SPECS_DIR)
    documents = DocumentRepository(fs)
    skills = SkillRepository(fs)
    return load_workspace(
        schemas,
        documents,
        skills,
        builtin_layers=builtin_layers,
    )


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


def _list_corpus_directories(
    documents: DocumentRepository, failures: list[LoadFailure]
) -> tuple[frozenset[PathComponent], tuple[RootRelativePath, ...]]:
    """The regular corpus directories and symlinked corpus paths under docs/, or none on a listing failure.

    Args:
        documents: Repository docs/ is listed from.
        failures: The load failures so far; a directory that cannot be listed is appended.

    Returns:
        A pair: regular corpus directory names, then symlinked paths whose names are valid corpus names. Both are
        empty when docs/ cannot be listed.
    """
    try:
        return documents.list_corpus_directories()
    except DIR_LIST_FAILURES as exc:
        failures.append(LoadFailure(exc.path, UnlistableDirectory(exc.refusal)))
        return frozenset(), ()


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
                group.spec.add(spec_file)
            case NamespaceSpecName(namespace=namespace):
                group.namespaces.setdefault(namespace, _NameFiles()).add(spec_file)
            case _:
                assert_never(spec_file.name)
    return groups


def _load_corpus(
    schemas: SchemaRepository,
    corpus_name: CorpusName,
    files: _CorpusFiles,
    filenames: list[AspectFilename],
    failures: list[LoadFailure],
    schema_inputs: dict[SchemaRef, SchemaInput],
    skills_floor_enabled: bool,
) -> Corpus:
    """Decode the corpus spec and its namespace specs; a structure file that fails stands in its layer.

    Args:
        schemas: Repository the structure specifications are read from.
        corpus_name: Name of the corpus being built, which every specification name of its files starts with.
        files: Specification files at the corpus spec's name and at each of its namespace specs' names.
        filenames: Stems of the documents listed in the corpus directory, which the corpus lists by filename.
        failures: The load failures so far; each structure file that fails is appended.
        schema_inputs: Raw repository inputs collected from the structure files.
        skills_floor_enabled: Whether the builtin Agent Skills floor is enabled.
    """
    corpus_spec_name = CorpusSpecName(corpus_name)
    corpus_spec = CorpusSpec(
        name=corpus_spec_name,
        files=_sorted_paths(files.spec),
        structure=_load_structure(schemas, files.spec.structure, failures, schema_inputs, skills_floor_enabled),
    )

    # The corpus orders its namespace specs itself; they are decoded broad to narrow too, so that of two broken
    # structure specifications the broader one is the failure listed first.
    namespaces: dict[AspectNamespace, CorpusNamespace] = {}
    for namespace in sorted(files.namespaces, key=namespace_order_key):
        namespace_files = files.namespaces[namespace]
        namespaces[namespace] = CorpusNamespace(
            files=_sorted_paths(namespace_files),
            structure=_load_structure(
                schemas,
                namespace_files.structure,
                failures,
                schema_inputs,
                skills_floor_enabled,
            ),
        )

    return Corpus(corpus_spec=corpus_spec, namespaces=FrozenMapping(namespaces), filenames=frozenset(filenames))


def _sorted_paths(name_files: _NameFiles) -> tuple[RootRelativePath, ...]:
    """The root-relative paths of the files at one specification name, sorted.

    Args:
        name_files: Files at one specification name, prose and JSON.
    """
    paths = [prose.path for prose in name_files.prose]
    if name_files.structure is not None:
        paths.append(name_files.structure.path)
    return tuple(sorted(paths, key=str))


def _load_structure(
    schemas: SchemaRepository,
    structure_file: StructureSpecFile | None,
    failures: list[LoadFailure],
    schema_inputs: dict[SchemaRef, SchemaInput],
    skills_floor_enabled: bool,
) -> StructureSpec | FailedStructure | None:
    """Decode the structure JSON at one specification name into a structure specification.

    Args:
        schemas: Repository the structure specification is read from.
        structure_file: The name's structure file, or None when the name has none; the prose is never decoded.
        failures: The load failures so far; a structure file that cannot be read or used is appended.
        schema_inputs: Raw repository inputs collected by typed reference.
        skills_floor_enabled: Whether the builtin Agent Skills floor is enabled.

    Returns:
        The structure specification, the failed structure standing in its place when the file cannot be read or
        used, or None when the name has no structure file.
    """
    if structure_file is None:
        return None
    try:
        text = schemas.get_structure_schema(structure_file)
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
        return _record_failed_structure(failures, structure_file.path, failure)
    parsed = StructureSpec.parse(structure_file, StructureSchema(text))
    identity = str(structure_file.name)
    origin = RepositoryOrigin(structure_file.path, identity)
    try:
        document: JsonValue = json.loads(text)
    except json.JSONDecodeError:
        document = None
    if isinstance(document, dict):
        structure_ref = SchemaRef(SchemaKind.STRUCTURE, identity)
        schema_inputs[structure_ref] = SchemaInput(structure_ref, origin, FrozenMapping.from_plain(document))
    # Parsing is the check, and it raises nothing: text that is not JSON in the structure dialect, a title pattern
    # that does not compile, a frontmatter schema that cannot be held and rules that are not usable each come back
    # as their failure record.
    if isinstance(parsed, StructureSpec):
        if parsed.frontmatter is not None:
            frontmatter_document = document.get('frontmatter') if isinstance(document, dict) else None
            if isinstance(frontmatter_document, dict):
                frontmatter_ref = SchemaRef(SchemaKind.FRONTMATTER, identity)
                schema_inputs[frontmatter_ref] = SchemaInput(
                    frontmatter_ref, origin, FrozenMapping.from_plain(frontmatter_document)
                )
                parsed = replace(parsed, frontmatter_schema_ref=frontmatter_ref)
        if skills_floor_enabled and parsed.frontmatter is not None:
            contradictions = agent_skills_schema_contradictions(parsed.frontmatter.schema.to_plain())
            if contradictions:
                return _record_failed_structure(
                    failures,
                    structure_file.path,
                    ContradictorySkillField(contradictions),
                )
        return parsed
    return _record_failed_structure(failures, structure_file.path, parsed)


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
) -> tuple[list[AspectFilename], tuple[RootRelativePath, ...]]:
    """The stems of the validly named Markdown files the repository lists in the corpus; the rest are left out.

    A corpus directory that cannot be listed holds no document, and the failure is recorded.

    Args:
        documents: Repository the corpus directory is listed from.
        corpus_name: Corpus whose directory is listed.
        failures: The load failures so far; a directory that cannot be listed is appended.

    Returns:
        A pair: valid document filenames, then paths of symlinked `.md` entries. Both are empty when the corpus
        directory cannot be listed.
    """
    try:
        document_files, dropped_symlinks = documents.list_documents(corpus_name)
    except CorpusListError as exc:
        failures.append(LoadFailure(exc.source.path, UnlistableCorpusDirectory(exc.corpus, exc.source.refusal)))
        return [], ()

    filenames: list[AspectFilename] = []
    for document_file in document_files:
        try:
            filename = AspectFilename.parse(document_file.stem)
        except EmptyAspectNameError, InvalidAspectNameCharacterError:
            continue
        filenames.append(filename)
    return filenames, dropped_symlinks


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
        for path in agent.project_skills_dirs:
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
            except ROOT_EXIT_WALK_FAILURES as exc:
                failures.append(LoadFailure(path, UninspectableSkillsDirectory(exc.entry, exc.refusal)))
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
                found = skills.find_skill_entry(resolved_directory, entry)
            except SkillEntryResolveError as exc:
                match exc.source:
                    case DirResolveError():
                        condition = UnresolvableSkillEntry(exc.source.refusal)
                    case RecordedDirResolveError():
                        condition = UninspectableSkillEntry(exc.source.source.path, exc.source.refusal)
                    case RootExitWalkError() | RecordedRootExitWalkError():
                        condition = UninspectableSkillEntry(exc.source.entry, exc.source.refusal)
                    case _:
                        assert_never(exc.source)
                failures.append(LoadFailure(entry_path, condition))
                continue
            except SkillDirListError as exc:
                condition = UnlistableSkillDirectory(exc.directory, exc.source.refusal)
                failures.append(LoadFailure(entry_path, condition))
                continue
            except SkillFileResolveError as exc:
                skill_file_path = entry_path / SKILL_ENTRYPOINT
                match exc.source:
                    case FileResolveError():
                        condition = UnresolvableSkillFile(exc.skill_file, exc.source.refusal)
                    case RecordedFileResolveError():
                        condition = UninspectableSkillFile(exc.skill_file, exc.source.source.path, exc.source.refusal)
                    case RootExitWalkError() | RecordedRootExitWalkError():
                        condition = UninspectableSkillFile(exc.skill_file, exc.source.entry, exc.source.refusal)
                    case _:
                        assert_never(exc.source)
                failures.append(LoadFailure(skill_file_path, condition))
                continue
            match found:
                case SkillLocation():
                    locations.append(found)
                case OutsideSymlink():
                    outside_symlinks.append(found)
                case None:
                    pass
                case _:
                    assert_never(found)
    return tuple(sorted(locations)), tuple(sorted(outside_symlinks, key=lambda outside: outside.path))
