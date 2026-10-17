"""The workspace model: an immutable snapshot of which corpora, specs, documents and skills a repository declares.

The loader builds one model per run from `docs/__meta__/`, the corpus directories and the project skills
directories; every query here is pure. The model holds structure (corpora, document refs, skills directories, skill
refs) and configuration (decoded specs), never document content: text stays behind the document repository and is
read on demand through a `DocumentRef`, and the model reads no `SKILL.md`.

Governance is the one computation the model owns. A document is governed by its corpus spec first, then by
every namespace spec whose namespace matches its filename, broad to narrow. A namespace spec narrows a
base; it never supplies one, so a corpus spec that states no rule of one kind, a structure specification or a
frontmatter schema, leaves the document ungoverned for that kind whatever the namespace specs carry.
"""

from dataclasses import InitVar, dataclass, field
from typing import assert_never

from lorecraft.agents import AgentName
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename, AspectNamespace
from lorecraft.project.corpus import CorpusName, ReservedCorpusDirectory
from lorecraft.project.document import DocumentRef, SpecRef
from lorecraft.project.item import (
    DocumentOrigin,
    ItemFacet,
    MarkdownItemDescriptor,
    MarkdownItemRef,
    SkillEntryOrigin,
    SkillResourceOrigin,
    SpecificationOrigin,
)
from lorecraft.project.layout import DOCS_DIR, DOCUMENT_SUFFIX, SPECS_DIR
from lorecraft.project.link_target import DocumentDirectory, SkillRoot
from lorecraft.project.schemas import CorpusSpecName, NamespaceSpecName, StatedFrontmatterSchema, StructureSpec
from lorecraft.project.skill import OutsideSymlink, SkillLocation, SkillRef, SkillResourceLocation, SkillsDir
from lorecraft.vfs import ResolvedPath

from .failure import FailedStructure, LoadFailure


@dataclass(frozen=True, slots=True)
class CorpusSpec:
    """A corpus spec in docs/__meta__, at the `<corpus>` specification name, and its decoded structure specification.

    A corpus spec governs every document in its corpus.

    Attributes:
        name: The specification name, the corpus alone.
        files: Every root-relative file at this specification name (prose and JSON), sorted; may be prose only.
        structure: The structure specification, the `FailedStructure` standing in its place when
            `<name>.spec.json` could not be read or used, or None when that file does not exist.
    """

    name: CorpusSpecName
    files: tuple[RootRelativePath, ...]
    structure: StructureSpec | FailedStructure | None


@dataclass(frozen=True, slots=True)
class NamespaceSpec:
    """A namespace spec in docs/__meta__, at a `<corpus>-<namespace>` specification name, narrowing its corpus spec.

    Attributes:
        name: The specification name, the corpus and the namespace.
        files: Every root-relative file at this specification name (prose and JSON), sorted; may be prose only.
        structure: The structure specification, the `FailedStructure` standing in its place when
            `<name>.spec.json` could not be read or used, or None when that file does not exist.
    """

    name: NamespaceSpecName
    files: tuple[RootRelativePath, ...]
    structure: StructureSpec | FailedStructure | None

    def is_governing(self, filename: AspectFilename | str) -> bool:
        """True when the spec's namespace matches the filename.

        Args:
            filename: Document filename stem, or a skill's listed name, whose governance is asked; matched by
                hyphen-delimited prefix.
        """
        return self.name.namespace.is_prefix_of(filename)


type Spec = CorpusSpec | NamespaceSpec


@dataclass(frozen=True, slots=True)
class Governance:
    """The specs that govern one document, broad to narrow.

    A layer whose structure file failed to load is held as it is, with its `FailedStructure`. The queries below read
    only the layers that loaded; `failed_layers` names the others, so a consumer decides what a failed layer means.

    The governance is built from a corpus and a filename and keeps only the specs they yield, so it cannot hold a spec
    of another corpus, one whose namespace does not match the filename, or one twice. Two governances are equal when
    they govern the same document with the same specs, whatever else their corpora hold.

    Attributes:
        ref: The governed document, or None when a listed name that is no valid filename stem, such as a skill's
            directory name, was matched.
        corpus_spec: The spec of the document's corpus, which governs every document in it.
        namespace_specs: Every namespace spec whose namespace matches the document, broad to narrow.
    """

    # Construction arguments, not fields: neither is kept, so neither takes part in equality or hashing.
    corpus: InitVar['Corpus']  # defined below: a corpus builds its governance, and the governance reads it
    filename: InitVar[AspectFilename | str]  # matched by hyphen-delimited prefix; the item is the corpus's
    ref: DocumentRef | None = field(init=False)
    corpus_spec: CorpusSpec = field(init=False)
    namespace_specs: tuple[NamespaceSpec, ...] = field(init=False)

    def __post_init__(self, corpus: 'Corpus', filename: AspectFilename | str) -> None:
        """Derive the governing specs once, from the corpus and the filename."""
        matching: list[NamespaceSpec] = []
        for namespace_spec in corpus.namespace_specs:
            if namespace_spec.is_governing(filename):
                matching.append(namespace_spec)
        # The class is frozen, so the derived values are set through `object`; deriving them here means they cannot
        # disagree with the corpus and filename.
        ref = DocumentRef(corpus=corpus.name, filename=filename) if isinstance(filename, AspectFilename) else None
        object.__setattr__(self, 'ref', ref)
        object.__setattr__(self, 'corpus_spec', corpus.corpus_spec)
        object.__setattr__(self, 'namespace_specs', tuple(matching))

    def specs(self) -> tuple[Spec, ...]:
        """Every governing spec, corpus spec first."""
        return (self.corpus_spec, *self.namespace_specs)

    def failed_layers(self) -> tuple[FailedStructure, ...]:
        """The structure files of the layers that failed to load, in layer order, corpus spec first."""
        failed: list[FailedStructure] = []
        for spec in self.specs():
            match spec.structure:
                case FailedStructure():
                    failed.append(spec.structure)
                case StructureSpec() | None:
                    pass  # loaded, or none stated: no failed layer
                case _:
                    assert_never(spec.structure)
        return tuple(failed)

    def corpus_structure(self) -> StructureSpec | None:
        """The corpus spec's structure specification, or None when it states none or its layer failed to load."""
        structure = self.corpus_spec.structure
        match structure:
            case StructureSpec():
                return structure
            case FailedStructure() | None:
                return None
            case _:
                assert_never(structure)

    def structure_specs(self) -> tuple[StructureSpec, ...]:
        """Structure specifications to apply in order, the layers that loaded; `()` means ungoverned for structure.

        A corpus spec without a loaded structure specification leaves the document ungoverned even when a
        matching namespace spec carries one: a namespace narrows a base, it cannot supply one. A layer that failed to
        load is left out, and `failed_layers` lists it.
        """
        if self.corpus_structure() is None:
            return ()
        structure_specs: list[StructureSpec] = []
        for spec in self.specs():
            match spec.structure:
                case StructureSpec():
                    structure_specs.append(spec.structure)
                case FailedStructure() | None:
                    pass  # no structure specification loaded in this layer
                case _:
                    assert_never(spec.structure)
        return tuple(structure_specs)

    def frontmatter_schemas(self) -> tuple[StatedFrontmatterSchema, ...]:
        """Frontmatter schemas to apply in order, each with its specification; `()` means ungoverned for frontmatter.

        Each comes from the `frontmatter` key of a structure specification that loaded. As with `structure_specs`, a
        corpus spec whose structure specification states no frontmatter schema leaves the document ungoverned even
        when a matching namespace spec states one.
        """
        corpus_structure = self.corpus_structure()
        if corpus_structure is None or corpus_structure.frontmatter is None:
            return ()
        schemas: list[StatedFrontmatterSchema] = []
        for structure_spec in self.structure_specs():
            if structure_spec.frontmatter is not None:
                schemas.append(StatedFrontmatterSchema(spec=structure_spec.path, schema=structure_spec.frontmatter))
        return tuple(schemas)

    def outline_specs(self) -> tuple[StructureSpec, ...]:
        """Structure specifications that state an outline, in order; `()` means ungoverned for the outline.

        They are the ones among `structure_specs` that state one, so a namespace outline never governs alone either.
        """
        outline_specs: list[StructureSpec] = []
        for structure_spec in self.structure_specs():
            if structure_spec.outline:
                outline_specs.append(structure_spec)
        return tuple(outline_specs)


def namespace_order_key(namespace: AspectNamespace) -> tuple[int, str]:
    """The broad-to-narrow order of a corpus's namespace specs: segment count first, then value.

    Every namespace matching one filename is a prefix of that filename, so segment count is broadness and two
    matches never tie; the value tiebreak only orders non-matching siblings.

    Args:
        namespace: Namespace of one spec, whose hyphens give its segment count.
    """
    value = str(namespace)
    return (value.count('-'), value)


@dataclass(frozen=True, slots=True)
class CorpusNamespace:
    """A namespace spec as its corpus holds it: the spec's files and structure, without its corpus or its namespace.

    The `Corpus` holding the record supplies the corpus and keys the record by its namespace, so the record cannot
    name another corpus or another namespace; `Corpus.namespace_specs` builds the `NamespaceSpec` from all three.

    Attributes:
        files: Every root-relative file at the spec's specification name (prose and JSON), sorted; may be prose only.
        structure: The structure specification, the `FailedStructure` standing in its place when the spec's
            `.spec.json` could not be read or used, or None when the spec has no such file.
    """

    files: tuple[RootRelativePath, ...]
    structure: StructureSpec | FailedStructure | None


@dataclass(frozen=True, slots=True)
class Corpus:
    """One corpus: its spec, the namespaces narrowing it, and the filenames of its documents.

    The corpus is the one its spec names. Its namespace specs and its documents are built from the parts the corpus
    does not fix, a namespace and a filename, so none of them can belong to another corpus. A namespace is held
    once and so is a filename, whatever order they were given in: the corpus lists namespace specs broad to narrow
    and documents by filename.

    Attributes:
        corpus_spec: The corpus spec; always present (discovery is spec-first), possibly prose only.
        namespaces: The namespace specs narrowing the corpus spec, each without its corpus, by namespace.
        filenames: Stems of the Markdown files directly inside docs/<name>/.
    """

    corpus_spec: CorpusSpec
    namespaces: FrozenMapping[AspectNamespace, CorpusNamespace]
    filenames: frozenset[AspectFilename]

    @property
    def name(self) -> CorpusName:
        """Directory name under docs/: the corpus the corpus spec names."""
        return self.corpus_spec.name.corpus

    @property
    def namespace_specs(self) -> tuple[NamespaceSpec, ...]:
        """The specs narrowing the corpus spec, one per namespace, broad to narrow by (segment count, value)."""
        namespace_specs: list[NamespaceSpec] = []
        for namespace in sorted(self.namespaces, key=namespace_order_key):
            corpus_namespace = self.namespaces[namespace]
            name = NamespaceSpecName(self.name, namespace)
            namespace_specs.append(NamespaceSpec(name, corpus_namespace.files, corpus_namespace.structure))
        return tuple(namespace_specs)

    @property
    def documents(self) -> tuple[DocumentRef, ...]:
        """Refs of the Markdown files directly inside docs/<name>/, one per filename, sorted by filename."""
        refs: list[DocumentRef] = []
        for filename in sorted(self.filenames, key=str):
            refs.append(DocumentRef(corpus=self.name, filename=filename))
        return tuple(refs)

    def document_base(self, filename: AspectFilename) -> DocumentRef | None:
        """The document this one extends: the narrowest of the corpus's documents whose name continues into this one.

        A name `a` is an ancestor of `b` when `b` starts with `a-`, so `python-fn` is an ancestor of
        `python-fn-unchecked`. A missing intermediate name is skipped: the base is the nearest ancestor the corpus
        holds.

        Args:
            filename: Stem of the document whose base is wanted; it need not be one of the corpus's.
        """
        name = str(filename)
        ancestors = [
            candidate for candidate in self.filenames if candidate != filename and name.startswith(f'{candidate}-')
        ]
        if not ancestors:
            return None
        # The narrowest ancestor has the most hyphen-delimited segments, so no two ancestors tie.
        narrowest = max(ancestors, key=lambda candidate: str(candidate).count('-'))
        return DocumentRef(corpus=self.name, filename=narrowest)

    @property
    def directory(self) -> RootRelativePath:
        """Root-relative `docs/<name>`, the directory the corpus's documents sit directly inside."""
        # A corpus name is validated snake case, so it is a valid component.
        return DOCS_DIR / PathComponent.parse(str(self.name))

    def governance(self, filename: AspectFilename | str) -> Governance:
        """Corpus spec, then every namespace spec that matches, broad to narrow. Pure.

        Args:
            filename: Stem of the document, or listed name of the skill, whose governing specs are wanted; it names
                no corpus, so the governed item is this corpus's.
        """
        return Governance(self, filename)


@dataclass(frozen=True, slots=True)
class ResolvedItem:
    """A listed item's descriptor and the specifications governing it, resolved together.

    Attributes:
        descriptor: The item's model-resolved locations and origin facts.
        governance: The governing specs, or `None` when none governs the item.
    """

    descriptor: MarkdownItemDescriptor
    governance: Governance | None


@dataclass(frozen=True, slots=True)
class WorkspaceModel:
    """Immutable snapshot of structure and config; holds no root path and no document content.

    Every collection but `load_failures` holds each of its members once and has no order of its own: the `sorted_*`
    properties list them in the order a consumer reads them in. A mapping's key is its value's own name, ref or
    path, and construction rejects a key that is not.

    Attributes:
        corpora: Every corpus, by name.
        skills_dirs: Every project skills directory an agent reads that the repository has, one record per
            agent and directory. Two agents reading one resolved directory are two records with the same
            `resolves_to`.
        skill_locations: The location of every skill directly inside the directories those resolve to,
            by the skill's ref; `skills()` lists the refs alone, and `skill_agents` says which
            agents read one. A skill belongs to no corpus, so no spec governs it and `documents()` does not
            list it. The locations, not the refs, record where each link leads, so two models differ when a
            link is retargeted even though every ref is the same.
        skills_corpus: The reserved `skills` corpus, whose specs govern the skills by their listed directory name, or
            None when no `skills` spec exists. It lists no document: its documents are the skills, which
            `find_skill_governance` resolves, and no directory under `docs/` backs it.
        overlapping_directories: The directories under `docs/` that take a reserved corpus's name, which the model
            ignores: none of their documents is listed.
        outside_symlinks: Every skills directory an agent declares, entry in a resolved skills directory, and
            `SKILL.md` of such an entry, whose symlink chain leaves the repository, by path.
            None of them is a skills directory or a skill of the model; a symlink inside a skill is in its
            resource listing.
        load_failures: Every unit of the declaration that could not be read or used, each once, in the order the
            loader met them: a structure file, whose `FailedStructure` also stands in its layer, a corpus directory,
            a skills directory, a skill entry or a `SKILL.md`, and a `docs/` or `docs/__meta__/` that cannot be
            listed. Nothing a failure touches is in the model beyond that record; every other unit is loaded.
    """

    corpora: FrozenMapping[CorpusName, Corpus]
    skills_dirs: frozenset[SkillsDir]
    skill_locations: FrozenMapping[SkillRef, SkillLocation]
    outside_symlinks: FrozenMapping[RootRelativePath, OutsideSymlink]
    load_failures: tuple[LoadFailure, ...]
    skills_corpus: Corpus | None = None
    overlapping_directories: frozenset[ReservedCorpusDirectory] = frozenset()

    def __post_init__(self) -> None:
        """Keep a key from naming something other than its value, which the lookups read the key alone to answer.

        Raises:
            ValueError: If a key of `corpora`, `skill_locations` or `outside_symlinks` is not its value's own name,
                ref or path.
        """
        for name, corpus in self.corpora.items():
            if name != corpus.name:
                raise ValueError(f'corpora key {name} holds the corpus {corpus.name}')
        for ref, location in self.skill_locations.items():
            if ref != location.ref:
                raise ValueError(f'skill_locations key {ref.directory} holds the skill {location.ref.directory}')
        for path, outside in self.outside_symlinks.items():
            if path != outside.path:
                raise ValueError(f'outside_symlinks key {path} holds the symlink at {outside.path}')

    @property
    def sorted_corpora(self) -> tuple[Corpus, ...]:
        """Every corpus, sorted by name."""
        return tuple(self.corpora[name] for name in sorted(self.corpora, key=str))

    @property
    def sorted_skills_dirs(self) -> tuple[SkillsDir, ...]:
        """Every skills directory, sorted by agent then path."""
        return tuple(sorted(self.skills_dirs, key=lambda skills_dir: (str(skills_dir.agent), skills_dir.path)))

    @property
    def sorted_skill_locations(self) -> tuple[SkillLocation, ...]:
        """Every skill's location, sorted by ref, which is by directory."""
        return tuple(self.skill_locations[ref] for ref in sorted(self.skill_locations))

    @property
    def sorted_outside_symlinks(self) -> tuple[OutsideSymlink, ...]:
        """Every symlink leading outside the repository, sorted by path."""
        return tuple(self.outside_symlinks[path] for path in sorted(self.outside_symlinks))

    @property
    def sorted_overlapping_directories(self) -> tuple[ReservedCorpusDirectory, ...]:
        """Every directory under `docs/` that takes a reserved corpus's name, sorted by path."""
        return tuple(sorted(self.overlapping_directories))

    def find_corpus(self, name: CorpusName) -> Corpus | None:
        """The corpus with this name, or None when the model has none.

        Args:
            name: Corpus directory name under docs/.
        """
        return self.corpora.get(name)

    def documents(self) -> tuple[DocumentRef, ...]:
        """Every ref, corpus order then filename order."""
        refs: list[DocumentRef] = []
        for corpus in self.sorted_corpora:
            refs.extend(corpus.documents)
        return tuple(refs)

    def find_document(self, path: RootRelativePath) -> DocumentRef | None:
        """The ref whose `path` equals this root-relative path, or None.

        Args:
            path: Document path to look up, compared whole and lexically.
        """
        for ref in self.documents():
            if ref.path == path:
                return ref
        return None

    def specifications(self) -> tuple[SpecRef, ...]:
        """Every meta specification, a Markdown file of a corpus or namespace spec, sorted by path; no README."""
        specs: list[Spec] = []
        for corpus in (*self.sorted_corpora, *([self.skills_corpus] if self.skills_corpus is not None else [])):
            specs.append(corpus.corpus_spec)
            specs.extend(corpus.namespace_specs)
        refs: set[SpecRef] = set()
        for spec in specs:
            for file in spec.files:
                if file.value.name.endswith(DOCUMENT_SUFFIX) and file.parent == SPECS_DIR:
                    refs.add(SpecRef(file))
        return tuple(sorted(refs))

    def skills(self) -> tuple[SkillRef, ...]:
        """Every ref of a skill in the agents' skills directories, in directory order."""
        return tuple(sorted(self.skill_locations))

    def find_skill_location(self, directory: RootRelativePath) -> SkillLocation | None:
        """The location of the skill whose ref's `directory` equals this root-relative path, or None.

        Args:
            directory: Skill directory to look up, `<resolved skills directory>/<entry>`, compared whole and
                lexically: an entry that is a link is found by its own name, never by the directory it leads to.
        """
        name = directory.name
        if name is None:
            return None  # the root is no skill's directory
        return self.skill_locations.get(SkillRef(ResolvedPath(directory.parent), name))

    def has_skills_dir(self, resolved_path: ResolvedPath) -> bool:
        """True when a skills directory the model lists leads to this resolved path.

        Args:
            resolved_path: A resolved directory, root-relative, with no symlink on the way to it, compared whole and
                lexically against each skills directory's `resolves_to`.
        """
        for skills_dir in self.skills_dirs:
            if skills_dir.resolves_to == resolved_path:
                return True
        return False

    def skill_locations_in(self, resolved_path: ResolvedPath) -> tuple[SkillLocation, ...]:
        """The locations of the skills listed directly inside this resolved directory.

        Args:
            resolved_path: A resolved directory, root-relative, matched against each skill's skills directory.

        Returns:
            Every such skill's location, in the model's order, or `()` when the directory holds none.
        """
        locations: list[SkillLocation] = []
        for location in self.sorted_skill_locations:
            if location.ref.skills_dir == resolved_path:
                locations.append(location)
        return tuple(locations)

    def has_outside_symlink(self, path: RootRelativePath) -> bool:
        """True when the model records a symlink leading outside the repository at this path.

        Args:
            path: Where an agent reaches the symlink, root-relative, compared whole and lexically against each
                outside symlink's `path`: a link is found by its own name, never by where it leads.
        """
        return path in self.outside_symlinks

    def locate_skill_files(self, path: ResolvedPath) -> tuple[SkillLocation, ...]:
        """The locations of the skills whose `SKILL.md` leads to this resolved file.

        Args:
            path: A resolved path, root-relative, with no symlink on the way to it.

        Returns:
            Every such skill's location, in the model's order, or `()` when none is there. Two skills whose
            `SKILL.md` links lead to one file are both returned.
        """
        locations: list[SkillLocation] = []
        for location in self.sorted_skill_locations:
            if location.file_resolves_to == path:
                locations.append(location)
        return tuple(locations)

    def skill_agents(self, ref: SkillRef) -> tuple[AgentName, ...]:
        """The agents that read a skill: those with a skills directory that leads to the one holding it.

        Args:
            ref: Skill whose skills directory is matched against each skills directory's resolved directory.

        Returns:
            The agents in name order, each once, or `()` when no skills directory leads there.
        """
        agents: list[AgentName] = []
        for skills_dir in self.sorted_skills_dirs:
            if skills_dir.resolves_to == ref.skills_dir and skills_dir.agent not in agents:
                agents.append(skills_dir.agent)
        return tuple(agents)

    def find_governance(self, ref: DocumentRef) -> Governance | None:
        """The specs governing a document, or `None` when the model holds no corpus named `ref.corpus`.

        `None` means no specification governs the document: the model has no spec of its corpus to start from.

        Args:
            ref: Document to look up, whether or not the model lists it; only its corpus and filename are read.
        """
        corpus = self.find_corpus(ref.corpus)
        if corpus is None:
            return None
        return corpus.governance(ref.filename)

    def find_skill_governance(self, ref: SkillRef) -> Governance | None:
        """The specs governing a skill by its listed directory name, or None when the model has no `skills` spec.

        Every skill the model lists has the global `skills` layer, whatever its name, and a namespace matches the
        listed name as it is: a name no document could take, such as `3d-tools`, is still governed. The governance
        names no document, so its `ref` is None for such a name.

        Args:
            ref: Skill to look up, whether or not the model lists it; only its listed directory name is read.
        """
        if self.skills_corpus is None:
            return None
        return self.skills_corpus.governance(str(ref.entry))

    def find_item(self, ref: MarkdownItemRef) -> ResolvedItem | None:
        """The facts of the document or skill entry the model lists at this reference, or None.

        Scans the model's documents and skills, so it answers a lookup by reference; a caller holding a document or
        skill ref resolves it with `resolve_item` and never calls this once per item.

        Args:
            ref: Common reference to look up; compared by its path, whole and lexically.
        """
        document = self.find_document(ref.path)
        if document is not None:
            return self.resolve_item(document)
        for skill in self.skill_locations:
            if skill.path == ref.path:
                return self.resolve_item(skill)
        for specification in self.specifications():
            if specification.path == ref.path:
                return self.resolve_item(specification)
        return None

    def describe_item(self, ref: DocumentRef | SkillRef | SpecRef) -> MarkdownItemDescriptor:
        """Resolve the shared location and origin facts for a document or skill entry.

        The existing references remain accepted by repositories and database queries. This descriptor is the
        common model contract for callers that need to handle either kind without classifying its origin.
        """
        return self.resolve_item(ref).descriptor

    def resolve_resource(self, location: SkillResourceLocation) -> ResolvedItem:
        """Resolve a skill resource's descriptor, with the governance of the skill that holds it.

        The model lists no resource: only the skill's resource listing locates one, so the caller hands the location
        over. The resource keeps its own ref and read location, and takes the governance identity of its skill, never
        of its filename. The package governs a resource as it does a skill entry, so the structure facet its Markdown
        rules read is active; the frontmatter, outline and budget facets stay inactive, so no entry-only check
        judges it.

        Args:
            location: Resource to resolve, as its skill's resource listing locates it.
        """
        skill = location.ref.skill
        descriptor = MarkdownItemDescriptor(
            ref=MarkdownItemRef(location.ref.path),
            read_location=location.resolves_to,
            link_base=SkillRoot(skill.directory),
            origin=SkillResourceOrigin(skill_entry=str(skill.entry)),
            governance_corpus='skills',
            aspect_name=str(skill.entry),
            active_facets=frozenset({ItemFacet.STRUCTURE, ItemFacet.MARKDOWN}),
        )
        return ResolvedItem(descriptor, self.find_skill_governance(skill))

    def resolve_item(self, ref: DocumentRef | SkillRef | SpecRef) -> ResolvedItem:
        """Resolve an item's descriptor together with the specs governing it, finding the governance once.

        A corpus document is governed by the specs of its corpus and matching namespaces. A skill entry resolves with no
        governance until the checks of a skill's `SKILL.md` read the `skills` corpus; `find_skill_governance` answers
        it for inspection.

        Args:
            ref: Document, skill entry or meta specification to resolve, whether or not the model lists a document's
                corpus. The package governs a specification, so it resolves with no governance and the structure and
                Markdown checks active.
        """
        match ref:
            case DocumentRef():
                governance = self.find_governance(ref)
                schemas = governance.frontmatter_schemas() if governance is not None else ()
                facets = {ItemFacet.MARKDOWN}
                if schemas:
                    facets.add(ItemFacet.FRONTMATTER)
                if governance is not None and governance.corpus_structure() is not None:
                    facets.add(ItemFacet.STRUCTURE)
                if governance is not None and governance.outline_specs():
                    facets.add(ItemFacet.OUTLINE)
                if governance is not None and any(spec.tokens is not None for spec in governance.structure_specs()):
                    facets.add(ItemFacet.BUDGET)
                descriptor = MarkdownItemDescriptor(
                    ref=MarkdownItemRef(ref.path),
                    read_location=ResolvedPath(ref.path),
                    link_base=DocumentDirectory(RootRelativePath(ref.path.value.parent)),
                    origin=DocumentOrigin(
                        expected_name=str(ref.filename),
                        corpus=str(ref.corpus),
                        schema_paths=tuple(schema.spec for schema in schemas),
                    ),
                    governance_corpus=str(ref.corpus),
                    aspect_name=str(ref.filename),
                    active_facets=frozenset(facets),
                )
                return ResolvedItem(descriptor, governance)
            case SkillRef():
                location = self.skill_locations[ref]
                link_target = location.resolves_to if location.resolves_to != ref.directory else None
                descriptor = MarkdownItemDescriptor(
                    ref=MarkdownItemRef(ref.path),
                    read_location=location.file_resolves_to,
                    link_base=SkillRoot(ref.directory),
                    origin=SkillEntryOrigin(expected_name=str(ref.entry), link_target=link_target),
                    governance_corpus='skills',
                    aspect_name=str(ref.entry),
                    active_facets=frozenset({ItemFacet.FRONTMATTER, ItemFacet.STRUCTURE, ItemFacet.MARKDOWN}),
                )
                return ResolvedItem(descriptor, None)
            case SpecRef():
                descriptor = MarkdownItemDescriptor(
                    ref=MarkdownItemRef(ref.path),
                    read_location=ResolvedPath(ref.path),
                    link_base=DocumentDirectory(SPECS_DIR),
                    origin=SpecificationOrigin(expected_name=ref.name, corpus=ref.corpus),
                    governance_corpus=ref.corpus,
                    aspect_name=ref.name,
                    active_facets=frozenset({ItemFacet.STRUCTURE, ItemFacet.MARKDOWN}),
                )
                return ResolvedItem(descriptor, None)
            case _:
                assert_never(ref)
