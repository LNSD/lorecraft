"""Build the workspace model from the specification directory, the corpus directories and the skills directories.

Discovery is spec-first: a directory under ``docs/`` is a corpus only when ``docs/__meta__/`` holds a file at
its stem. The loader lists the specification directory, parses each filename once with ``parse_spec_file``,
sorts the parsed files into corpus stems and namespace stems, keeps the corpora whose
``docs/<corpus>/`` is a regular directory, lists the Markdown files directly inside each, and builds a
``StructureAspect`` from every structure specification, which proves each one usable, its frontmatter schema
included, before any document is read.

The skills come from the agents: the loader asks each agent in ``lorecraft.agents`` which project skills
directories it reads, keeps the ones the repository has, and lists the skills in each real directory once. An
entry that does not fit the layout is left out of the model; nothing it leaves out fails the run.

Nothing here logs and nothing here catches broadly: a repository or schema error names its path already, so
it propagates unchanged to the command that loads the model, which reports it.
"""

from dataclasses import dataclass, field

from lorecraft.agents import iter_agents
from lorecraft.project.aspect import AspectFilename, AspectFilenameError, AspectNamespace
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document.ref import DocumentRef
from lorecraft.project.document.repo import Repository as DocumentRepository
from lorecraft.project.layout import SPECS_DIR
from lorecraft.project.schemas.name import SchemaName
from lorecraft.project.schemas.repo import Repository as SchemaRepository
from lorecraft.project.schemas.spec_file import SpecAspect, SpecFile, SpecFilenameError, parse_spec_file
from lorecraft.project.schemas.structure import StructureAspect
from lorecraft.project.skill.ref import SkillLocation
from lorecraft.project.skill.repo import Repository as SkillRepository
from lorecraft.project.skill.skills_dir import SkillsDir
from lorecraft.vfs import FileSystem, RootRelativePath

from .model import Corpus, Spec, WorkspaceModel, namespace_order_key


@dataclass(slots=True)
class _CorpusFiles:
    """The specification files naming one corpus, gathered before ``docs/<corpus>/`` is checked.

    Attributes:
        spec: Files at the ``<corpus>`` stem; empty when the corpus has no spec of its own.
        namespaces: Files at each ``<corpus>-<namespace>`` stem, keyed by namespace.
    """

    spec: list[SpecFile] = field(default_factory=list)
    namespaces: dict[AspectNamespace, list[SpecFile]] = field(default_factory=dict)


def load_workspace(schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository) -> WorkspaceModel:
    """Build the snapshot: parse the spec filenames, keep corpus stems whose docs/<corpus>/ is a directory, list
    the Markdown files directly inside each, build a structure aspect from every spec that has one, and find the
    agents' skills directories and the skills in them.

    Raises:
        ListSpecsError: If the specification directory cannot be listed.
        ListCorpusDirectoriesError: If docs/ cannot be listed.
        ListDocumentsError: If a corpus directory cannot be listed.
        GetStructureSchemaError: If any structure specification cannot be read.
        InvalidStructureSchemaError: If any structure specification is not JSON in the dialect, or states no usable
            rules, its frontmatter schema included.
        ResolveSkillsDirError: If a skills directory cannot be resolved.
        ListSkillsError: If a skills directory or a skill directory cannot be listed.
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

    skills_dirs = _load_skills_dirs(skills)
    skill_locations = _list_skill_locations(skills, skills_dirs)
    return WorkspaceModel(corpora=tuple(corpora), skills_dirs=skills_dirs, skill_locations=skill_locations)


def load_model(fs: FileSystem) -> WorkspaceModel:
    """Wire one filesystem view into the three repositories and load the workspace model through them.

    The view decides where the model comes from: a ``DiskFileSystem`` reads the disk as it is at each call,
    and a ``VirtualFileSystem`` answers from one snapshot, so the model reflects a single moment.

    Raises:
        ListSpecsError: If the specification directory cannot be listed.
        ListCorpusDirectoriesError: If docs/ cannot be listed.
        ListDocumentsError: If a corpus directory cannot be listed.
        GetStructureSchemaError: If any structure specification cannot be read.
        InvalidStructureSchemaError: If any structure specification is not JSON in the dialect, or states no usable
            rules, its frontmatter schema included.
        ResolveSkillsDirError: If a skills directory cannot be resolved.
        ListSkillsError: If a skills directory or a skill directory cannot be listed.
    """
    schemas = SchemaRepository(fs, SPECS_DIR)
    documents = DocumentRepository(fs)
    skills = SkillRepository(fs)
    return load_workspace(schemas, documents, skills)


def _group_spec_files(spec_paths: list[RootRelativePath]) -> dict[CorpusName, _CorpusFiles]:
    """Parse every file in the specification directory and file it under the corpus its stem names.

    A file whose name does not parse as a specification filename, such as ``README.md``, is left out.
    """
    groups: dict[CorpusName, _CorpusFiles] = {}
    for path in spec_paths:
        try:
            spec_file = parse_spec_file(path)
        except SpecFilenameError:
            continue

        group = groups.setdefault(spec_file.corpus, _CorpusFiles())
        if len(spec_file.name) == 1:
            group.spec.append(spec_file)
        else:
            group.namespaces.setdefault(spec_file.name[1], []).append(spec_file)
    return groups


def _load_corpus(
    schemas: SchemaRepository, corpus_name: CorpusName, files: _CorpusFiles, refs: list[DocumentRef]
) -> Corpus:
    """Decode the corpus spec and its namespace specs.

    Raises:
        GetStructureSchemaError: If a structure specification cannot be read.
        InvalidStructureSchemaError: If a structure specification is not JSON in the dialect, or states no usable
            rules, its frontmatter schema included.
    """
    spec = _load_spec(schemas, (corpus_name,), files.spec)

    # Broad to narrow: every namespace matching one filename is a prefix of that filename, so segment count
    # is broadness and two matches never tie; the value tiebreak only orders non-matching siblings.
    namespace_specs: list[Spec] = []
    for namespace in sorted(files.namespaces, key=namespace_order_key):
        namespace_specs.append(_load_spec(schemas, (corpus_name, namespace), files.namespaces[namespace]))

    return Corpus(
        name=corpus_name,
        spec=spec,
        namespace_specs=tuple(namespace_specs),
        documents=tuple(sorted(refs, key=lambda ref: str(ref.filename))),
    )


def _load_spec(schemas: SchemaRepository, name: SchemaName, spec_files: list[SpecFile]) -> Spec:
    """Build one spec from the files at its stem, decoding its structure JSON into an aspect.

    Raises:
        GetStructureSchemaError: If the structure specification cannot be read.
        InvalidStructureSchemaError: If the structure specification is not JSON in the dialect, or states no usable
            rules, its frontmatter schema included.
    """
    structure: StructureAspect | None = None
    for spec_file in spec_files:
        if spec_file.aspect is SpecAspect.STRUCTURE:
            # Building the aspect is the check: StructureAspect.parse rejects text that is not JSON in the structure
            # dialect, rules that are not usable, and a malformed frontmatter schema.
            structure = StructureAspect.parse(spec_file.path, schemas.get_structure_schema(name))
    paths = tuple(sorted((spec_file.path for spec_file in spec_files), key=str))
    return Spec(name=name, files=paths, structure=structure)


def _list_document_refs(documents: DocumentRepository, corpus_name: CorpusName) -> list[DocumentRef]:
    """The refs of the validly named Markdown files the repository lists in the corpus; the rest are left out.

    Raises:
        ListDocumentsError: If the corpus directory cannot be listed.
    """
    refs: list[DocumentRef] = []
    for document_file in documents.list_documents(corpus_name):
        try:
            filename = AspectFilename.parse(document_file.stem)
        except AspectFilenameError:
            continue
        refs.append(DocumentRef(corpus=corpus_name, filename=filename))
    return refs


def _load_skills_dirs(skills: SkillRepository) -> tuple[SkillsDir, ...]:
    """One record per agent and project skills directory it reads, for the directories the repository has.

    Sorted by agent then path, so the model does not depend on the order the agents are registered in.

    Raises:
        ResolveSkillsDirError: If a skills directory cannot be resolved.
    """
    skills_dirs: list[SkillsDir] = []
    for agent in iter_agents():
        for declared in agent.project_skills_dirs:
            path = RootRelativePath(declared)
            resolves_to = skills.resolve_skills_dir(path)
            if resolves_to is None:
                # The repository has no such directory, so the agent reads no skills from it.
                continue
            skills_dirs.append(SkillsDir(agent=agent.name, path=path, resolves_to=resolves_to))
    skills_dirs.sort(key=lambda skills_dir: (str(skills_dir.agent), skills_dir.path))
    return tuple(skills_dirs)


def _list_skill_locations(skills: SkillRepository, skills_dirs: tuple[SkillsDir, ...]) -> tuple[SkillLocation, ...]:
    """The location of every skill in the real directories behind ``skills_dirs``, each once, sorted by directory.

    Two agents reading one real directory add no second skill: the directory is listed once. The locations are
    sorted as a whole, since one skills directory may sit inside another.

    Raises:
        ListSkillsError: If a skills directory or a skill directory cannot be listed.
    """
    real_directories: set[RootRelativePath] = set()
    for skills_dir in skills_dirs:
        real_directories.add(skills_dir.resolves_to)

    locations: list[SkillLocation] = []
    for real_directory in real_directories:
        locations.extend(skills.list_skills(real_directory))
    return tuple(sorted(locations))
