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

A command may also name directories to check the skills in, each spelled root-relative. The loader reads each
one the agents do not already read as one skill when a `SKILL.md` is at its root, and otherwise as a skills
directory, and records the skills it finds under the spelled path, apart from the agents' skills.

Nothing here logs and nothing here catches broadly: a repository or schema error names its path already, so
it propagates unchanged to the command that loads the model, which reports it.
"""

from dataclasses import dataclass, field
from typing import assert_never

from lorecraft.agents import iter_agents
from lorecraft.core.path import ROOT, RootRelativePath
from lorecraft.project.aspect import (
    AspectFilename,
    AspectNamespace,
    EmptyAspectNameError,
    InvalidAspectNameCharacterError,
)
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document.ref import DocumentRef
from lorecraft.project.document.repo import Repository as DocumentRepository
from lorecraft.project.layout import SPECS_DIR
from lorecraft.project.schemas.name import CorpusSpecName, NamespaceSpecName, SpecName
from lorecraft.project.schemas.repo import Repository as SchemaRepository
from lorecraft.project.schemas.spec_file import (
    DottedSpecStemError,
    InvalidSpecStemError,
    NotASpecFileError,
    NotASpecStemError,
    SpecFile,
    SpecFileType,
    UnknownSpecFileTypeError,
    parse_spec_file,
)
from lorecraft.project.schemas.structure import StructureSpec
from lorecraft.project.skill.named_dir import NamedDir
from lorecraft.project.skill.outside import OutsideSymlink
from lorecraft.project.skill.ref import SkillLocation
from lorecraft.project.skill.repo import Repository as SkillRepository
from lorecraft.project.skill.skills_dir import SkillsDir
from lorecraft.vfs import FileSystem, ResolvedPath

from .model import Corpus, CorpusSpec, NamespaceSpec, WorkspaceModel, namespace_order_key


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
    *,
    named_dirs: tuple[RootRelativePath, ...] = (),
) -> WorkspaceModel:
    """Build the workspace model of the snapshot.

    Parse the spec filenames, keep corpus specs whose docs/<corpus>/ is a directory, list the Markdown files
    directly inside each, build a structure specification from every spec that has one, find the agents' skills
    directories and the skills in them, and the skills in each directory a command names.

    Args:
        schemas: Repository the specification files are listed and read from.
        documents: Repository the corpus directories and their Markdown files are listed from.
        skills: Repository the agents' skills directories and the named directories are resolved and their
            skills listed from.
        named_dirs: The directories a command names to check the skills in, root-relative as it spelled them;
            none by default.

    Raises:
        DirListError: If the specification directory or docs/ cannot be listed.
        CorpusListError: If a corpus directory cannot be listed.
        StructureSchemaReadError: If any structure specification cannot be read.
        StructureSpecDecodeError: If a structure specification is not JSON in the dialect's shape.
        StructureSpecFilenameError: If a structure specification is not at a specification filename.
        EmptyStructureSpecError: If a structure specification states no rule.
        InvalidTitleCountError: If a title count is below 1.
        InvalidTokenBudgetError: If a token budget is below 1.
        InvalidWordCapError: If an outline word cap is below 1.
        RepeatedOutlineSectionError: If an outline names a section twice.
        ForbiddenOutlineSectionError: If a specification forbids a section its outline names.
        AdjacentAnyRunsError: If an outline places two `any` runs side by side.
        InvalidFrontmatterSchemaError: If a frontmatter schema is rejected by the meta-schema.
        FrontmatterSchemaIdError: If a schema in a frontmatter schema carries `$id`.
        ForeignFrontmatterDialectError: If a schema in a frontmatter schema names another dialect.
        UntypedFrontmatterSchemaError: If a frontmatter schema's root does not state an object.
        DirResolveError: If a skills directory or a named directory cannot be resolved.
        EntryInspectError: If an entry on the way to a skills directory cannot be inspected, or a link's target
            read, while looking for where it leaves the repository.
        SkillsDirListError: If a skills directory cannot be listed.
        SkillEntryResolveError: If a symlinked skill entry cannot be resolved.
        SkillDirListError: If a skill directory cannot be listed.
        SkillFileResolveError: If a symlinked SKILL.md cannot be resolved.
    """
    spec_paths = schemas.list_spec_paths()
    corpus_directories = documents.list_corpus_directories()

    groups = _group_spec_files(spec_paths)

    corpora: list[Corpus] = []
    for corpus_name in sorted(groups, key=str):
        files = groups[corpus_name]
        if str(corpus_name) == SPECS_DIR.name:
            # `__meta__` is a valid corpus name, so a stray `__meta__.md` would otherwise turn the
            # specification directory into a corpus whose documents are the specifications themselves.
            continue
        if not files.spec:
            # A namespace spec narrows a corpus spec; without one there is nothing to narrow.
            continue
        if str(corpus_name) not in corpus_directories:
            # A corpus is a regular directory under docs/; a missing or linked one has no documents to list.
            continue
        refs = _list_document_refs(documents, corpus_name)
        corpora.append(_load_corpus(schemas, corpus_name, files, refs))

    skills_dirs, outside_skills_dirs = _load_skills_dirs(skills)
    skill_locations, outside_entries = _list_skill_locations(skills, skills_dirs)
    listed_named_dirs, outside_named = _list_named_dirs(skills, skills_dirs, named_dirs)
    # Keyed by path: two named directories, such as `skills` and `skills/review`, may reach one symlink.
    outside_by_path: dict[RootRelativePath, OutsideSymlink] = {}
    for outside in outside_skills_dirs + outside_entries + outside_named:
        outside_by_path[outside.path] = outside
    return WorkspaceModel(
        corpora=tuple(corpora),
        skills_dirs=skills_dirs,
        skill_locations=skill_locations,
        named_dirs=listed_named_dirs,
        outside_symlinks=tuple(outside_by_path[path] for path in sorted(outside_by_path)),
    )


def load_model(fs: FileSystem, *, named_dirs: tuple[RootRelativePath, ...] = ()) -> WorkspaceModel:
    """Wire one filesystem view into the three repositories and load the workspace model through them.

    The view decides where the model comes from: a `DiskFileSystem` reads the disk as it is at each call,
    and a `VirtualFileSystem` answers from one snapshot, so the model reflects a single moment.

    Args:
        fs: View of the repository the model is loaded from, rooted at the workspace root.
        named_dirs: The directories a command names to check the skills in, root-relative as it spelled them;
            none by default.

    Raises:
        DirListError: If the specification directory or docs/ cannot be listed.
        CorpusListError: If a corpus directory cannot be listed.
        StructureSchemaReadError: If any structure specification cannot be read.
        StructureSpecDecodeError: If a structure specification is not JSON in the dialect's shape.
        StructureSpecFilenameError: If a structure specification is not at a specification filename.
        EmptyStructureSpecError: If a structure specification states no rule.
        InvalidTitleCountError: If a title count is below 1.
        InvalidTokenBudgetError: If a token budget is below 1.
        InvalidWordCapError: If an outline word cap is below 1.
        RepeatedOutlineSectionError: If an outline names a section twice.
        ForbiddenOutlineSectionError: If a specification forbids a section its outline names.
        AdjacentAnyRunsError: If an outline places two `any` runs side by side.
        InvalidFrontmatterSchemaError: If a frontmatter schema is rejected by the meta-schema.
        FrontmatterSchemaIdError: If a schema in a frontmatter schema carries `$id`.
        ForeignFrontmatterDialectError: If a schema in a frontmatter schema names another dialect.
        UntypedFrontmatterSchemaError: If a frontmatter schema's root does not state an object.
        DirResolveError: If a skills directory or a named directory cannot be resolved.
        EntryInspectError: If an entry on the way to a skills directory cannot be inspected, or a link's target
            read, while looking for where it leaves the repository.
        SkillsDirListError: If a skills directory cannot be listed.
        SkillEntryResolveError: If a symlinked skill entry cannot be resolved.
        SkillDirListError: If a skill directory cannot be listed.
        SkillFileResolveError: If a symlinked SKILL.md cannot be resolved.
    """
    schemas = SchemaRepository(fs, SPECS_DIR)
    documents = DocumentRepository(fs)
    skills = SkillRepository(fs)
    return load_workspace(schemas, documents, skills, named_dirs=named_dirs)


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
    schemas: SchemaRepository, corpus_name: CorpusName, files: _CorpusFiles, refs: list[DocumentRef]
) -> Corpus:
    """Decode the corpus spec and its namespace specs.

    Args:
        schemas: Repository the structure specifications are read from.
        corpus_name: Name of the corpus being built, which every specification name of its files starts with.
        files: Specification files at the corpus spec's name and at each of its namespace specs' names.
        refs: Documents listed in the corpus directory; sorted by filename into the corpus.

    Raises:
        StructureSchemaReadError: If a structure specification cannot be read.
        StructureSpecDecodeError: If a structure specification is not JSON in the dialect's shape.
        StructureSpecFilenameError: If a structure specification is not at a specification filename.
        EmptyStructureSpecError: If a structure specification states no rule.
        InvalidTitleCountError: If a title count is below 1.
        InvalidTokenBudgetError: If a token budget is below 1.
        InvalidWordCapError: If an outline word cap is below 1.
        RepeatedOutlineSectionError: If an outline names a section twice.
        ForbiddenOutlineSectionError: If a specification forbids a section its outline names.
        AdjacentAnyRunsError: If an outline places two `any` runs side by side.
        InvalidFrontmatterSchemaError: If a frontmatter schema is rejected by the meta-schema.
        FrontmatterSchemaIdError: If a schema in a frontmatter schema carries `$id`.
        ForeignFrontmatterDialectError: If a schema in a frontmatter schema names another dialect.
        UntypedFrontmatterSchemaError: If a frontmatter schema's root does not state an object.
    """
    corpus_spec_name = CorpusSpecName(corpus_name)
    corpus_spec = CorpusSpec(
        name=corpus_spec_name,
        files=_sorted_paths(files.spec),
        structure=_load_structure(schemas, corpus_spec_name, files.spec),
    )

    # Broad to narrow: every namespace matching one filename is a prefix of that filename, so segment count
    # is broadness and two matches never tie; the value tiebreak only orders non-matching siblings.
    namespace_specs: list[NamespaceSpec] = []
    for namespace in sorted(files.namespaces, key=namespace_order_key):
        namespace_spec_name = NamespaceSpecName(corpus_name, namespace)
        namespace_files = files.namespaces[namespace]
        namespace_spec = NamespaceSpec(
            name=namespace_spec_name,
            files=_sorted_paths(namespace_files),
            structure=_load_structure(schemas, namespace_spec_name, namespace_files),
        )
        namespace_specs.append(namespace_spec)

    return Corpus(
        name=corpus_name,
        corpus_spec=corpus_spec,
        namespace_specs=tuple(namespace_specs),
        documents=tuple(sorted(refs, key=lambda ref: str(ref.filename))),
    )


def _sorted_paths(spec_files: list[SpecFile]) -> tuple[RootRelativePath, ...]:
    """The root-relative paths of the files at one specification name, sorted.

    Args:
        spec_files: Files at one specification name, prose and JSON, in listing order.
    """
    return tuple(sorted((spec_file.path for spec_file in spec_files), key=str))


def _load_structure(schemas: SchemaRepository, name: SpecName, spec_files: list[SpecFile]) -> StructureSpec | None:
    """Decode the structure JSON among the files at one specification name into a structure specification.

    Args:
        schemas: Repository the structure specification is read from.
        name: Specification name the files sit at: the corpus alone, or the corpus and a namespace.
        spec_files: Files at that name, prose and JSON, in listing order; only the structure file among them is decoded.

    Returns:
        The structure specification, or None when no file at the name is a structure file.

    Raises:
        StructureSchemaReadError: If the structure specification cannot be read.
        StructureSpecDecodeError: If a structure specification is not JSON in the dialect's shape.
        StructureSpecFilenameError: If a structure specification is not at a specification filename.
        EmptyStructureSpecError: If a structure specification states no rule.
        InvalidTitleCountError: If a title count is below 1.
        InvalidTokenBudgetError: If a token budget is below 1.
        InvalidWordCapError: If an outline word cap is below 1.
        RepeatedOutlineSectionError: If an outline names a section twice.
        ForbiddenOutlineSectionError: If a specification forbids a section its outline names.
        AdjacentAnyRunsError: If an outline places two `any` runs side by side.
        InvalidFrontmatterSchemaError: If a frontmatter schema is rejected by the meta-schema.
        FrontmatterSchemaIdError: If a schema in a frontmatter schema carries `$id`.
        ForeignFrontmatterDialectError: If a schema in a frontmatter schema names another dialect.
        UntypedFrontmatterSchemaError: If a frontmatter schema's root does not state an object.
    """
    structure: StructureSpec | None = None
    for spec_file in spec_files:
        if spec_file.type is SpecFileType.STRUCTURE:
            # Building the structure specification is the check: StructureSpec.parse rejects text that is not JSON in
            # the structure dialect, rules that are not usable, and a malformed frontmatter schema.
            structure = StructureSpec.parse(spec_file.path, schemas.get_structure_schema(name))
    return structure


def _list_document_refs(documents: DocumentRepository, corpus_name: CorpusName) -> list[DocumentRef]:
    """The refs of the validly named Markdown files the repository lists in the corpus; the rest are left out.

    Args:
        documents: Repository the corpus directory is listed from.
        corpus_name: Corpus whose directory is listed.

    Raises:
        CorpusListError: If the corpus directory cannot be listed.
    """
    refs: list[DocumentRef] = []
    for document_file in documents.list_documents(corpus_name):
        try:
            filename = AspectFilename.parse(document_file.stem)
        except (EmptyAspectNameError, InvalidAspectNameCharacterError):
            continue
        refs.append(DocumentRef(corpus=corpus_name, filename=filename))
    return refs


def _load_skills_dirs(skills: SkillRepository) -> tuple[tuple[SkillsDir, ...], tuple[OutsideSymlink, ...]]:
    """One record per agent and project skills directory it reads, for the directories the repository has.

    The records are sorted by agent then path, so the model does not depend on the order the agents are registered
    in. A declared directory whose symlink chain leaves the repository is no directory the repository has; it is
    returned apart, once however many agents declare it, sorted by path.

    Args:
        skills: Repository each declared skills directory is resolved through.

    Returns:
        A pair: the skills directories the repository has, one per agent and directory; then each declared
        directory whose chain leaves the repository, as an outside symlink.

    Raises:
        DirResolveError: If a skills directory cannot be resolved.
        EntryInspectError: If an entry on the way to a skills directory cannot be inspected, or a link's target
            read, while looking for where it leaves the repository.
    """
    skills_dirs: list[SkillsDir] = []
    outside: dict[RootRelativePath, OutsideSymlink] = {}
    for agent in iter_agents():
        for declared in agent.project_skills_dirs:
            path = RootRelativePath(declared)
            resolves_to = skills.find_skills_dir(path)
            if resolves_to is None:
                # The repository has no such directory, so the agent reads no skills from it; recorded when the
                # agent would read one outside the repository instead.
                leads_outside = skills.find_skills_dir_exit(path)
                if leads_outside is not None:
                    outside[path] = leads_outside
                continue
            skills_dirs.append(SkillsDir(agent=agent.name, path=path, resolves_to=resolves_to))
    skills_dirs.sort(key=lambda skills_dir: (str(skills_dir.agent), skills_dir.path))
    return tuple(skills_dirs), tuple(outside[path] for path in sorted(outside))


def _list_skill_locations(
    skills: SkillRepository, skills_dirs: tuple[SkillsDir, ...]
) -> tuple[tuple[SkillLocation, ...], tuple[OutsideSymlink, ...]]:
    """The location of every skill in the resolved directories behind `skills_dirs`, each once, sorted by directory.

    Two agents reading one resolved directory add no second skill: the directory is listed once. The locations are
    sorted as a whole, since one skills directory may sit inside another. Returned beside them, sorted by path, is
    every entry and every entry's `SKILL.md` in those directories whose symlink chain leaves the repository.

    Args:
        skills: Repository each resolved directory is listed through.
        skills_dirs: Skills directories the agents read; only the resolved directory each leads to is listed.

    Returns:
        A pair: the location of every skill; then every entry and entry's `SKILL.md` whose chain leaves the
        repository, as an outside symlink.

    Raises:
        SkillsDirListError: If a skills directory cannot be listed.
        SkillEntryResolveError: If a symlinked skill entry cannot be resolved.
        SkillDirListError: If a skill directory cannot be listed.
        SkillFileResolveError: If a symlinked SKILL.md cannot be resolved.
    """
    resolved_directories: set[ResolvedPath] = set()
    for skills_dir in skills_dirs:
        resolved_directories.add(skills_dir.resolves_to)

    locations: list[SkillLocation] = []
    outside_symlinks: list[OutsideSymlink] = []
    for resolved_directory in resolved_directories:
        listing = skills.list_skills(resolved_directory)
        locations.extend(listing.skills)
        outside_symlinks.extend(listing.outside_symlinks)
    return tuple(sorted(locations)), tuple(sorted(outside_symlinks, key=lambda outside: outside.path))


def _list_named_dirs(
    skills: SkillRepository, skills_dirs: tuple[SkillsDir, ...], paths: tuple[RootRelativePath, ...]
) -> tuple[tuple[NamedDir, ...], tuple[OutsideSymlink, ...]]:
    """One record per directory a command names, other than one the agents read, sorted by path, each once.

    A path leading to an agent's skills directory, or to an entry of one, is left to the agents' skills: a command
    selects those through `skills_dirs` and `skill_locations`, or through `outside_symlinks` for an entry leading
    outside, and a record here would list them, and the symlinks leading outside in them, a second time under
    another name. A path whose symlink chain leaves the repository is recorded as a directory holding that one
    outside symlink, as an agent's declared skills directory is: a link leading outside is reported, never skipped.
    Any other path leading to no directory under the root, such as a file or a dangling link, is no named directory,
    and neither is one leading to the root itself, which is the whole repository.

    Args:
        skills: Repository each named directory is resolved and listed through.
        skills_dirs: The agents' skills directories, as `_load_skills_dirs` returns them.
        paths: The directories as the command spelled them, root-relative, in any order, possibly repeated.

    Returns:
        A pair: a record per named directory, with the skills it holds and its symlinks leading outside; then every
        such symlink of every record, as the model's `outside_symlinks` holds them.

    Raises:
        DirResolveError: If a named directory, or the directory holding it, cannot be resolved.
        EntryInspectError: If an entry on the way to a named directory leading nowhere cannot be inspected, or a
            link's target read, while looking for where it leaves the repository.
        SkillsDirListError: If a named directory read as a skills directory cannot be listed.
        SkillEntryResolveError: If a symlinked entry of a named directory cannot be resolved.
        SkillDirListError: If a named directory, or a skill directory in it, cannot be listed.
        SkillFileResolveError: If a symlinked SKILL.md cannot be resolved.
    """
    agents_resolved_dirs: set[ResolvedPath] = set()
    for skills_dir in skills_dirs:
        agents_resolved_dirs.add(skills_dir.resolves_to)

    named_dirs: list[NamedDir] = []
    outside_symlinks: list[OutsideSymlink] = []
    for path in sorted(set(paths)):
        if skills.find_dir(path.parent) in agents_resolved_dirs:
            continue  # an entry of an agent's skills directory, leading outside or not
        resolved_directory = skills.find_dir(path)
        if resolved_directory is None:
            leads_outside = skills.find_skills_dir_exit(path)
            if leads_outside is not None:
                named_dirs.append(NamedDir(path, skills=(), outside_symlinks=(leads_outside,)))
                outside_symlinks.append(leads_outside)
            continue
        if resolved_directory == ROOT or resolved_directory in agents_resolved_dirs:
            continue
        listing = skills.list_named_skills(path, resolved_directory)
        named_dirs.append(NamedDir(path, skills=listing.skills, outside_symlinks=listing.outside_symlinks))
        outside_symlinks.extend(listing.outside_symlinks)
    return tuple(named_dirs), tuple(outside_symlinks)
