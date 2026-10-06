"""The workspace model: an immutable snapshot of which corpora, specs, documents and skills a repository declares.

The loader builds one model per run from `docs/__meta__/`, the corpus directories, the project skills
directories and the directories a command names to check the skills in; every query here is pure. The model holds
structure (corpora, document refs, skills directories, named directories, skill refs) and configuration (decoded
specs), never document content: text stays behind the document repository and is read on demand through a
`DocumentRef`, and the model reads no `SKILL.md`.

Governance is the one computation the model owns. A document is governed by its corpus spec first, then by
every namespace spec whose namespace matches its filename, broad to narrow. A namespace spec narrows a
base; it never supplies one, so a corpus spec that states no rule of one kind, a structure specification or a
frontmatter schema, leaves the document ungoverned for that kind whatever the namespace specs carry.
"""

from dataclasses import dataclass

from lorecraft.agents import AgentName
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename, AspectNamespace
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document.ref import DocumentRef
from lorecraft.project.layout import DOCS_DIR
from lorecraft.project.schemas.name import CorpusSpecName, NamespaceSpecName
from lorecraft.project.schemas.structure import FrontmatterSchema, StructureSpec
from lorecraft.project.skill.named_dir import NamedDir
from lorecraft.project.skill.outside import OutsideSymlink
from lorecraft.project.skill.ref import SkillLocation, SkillRef
from lorecraft.project.skill.skills_dir import SkillsDir
from lorecraft.vfs import ResolvedPath


@dataclass(frozen=True, slots=True)
class CorpusSpec:
    """A corpus spec in docs/__meta__, at the `<corpus>` specification name, and its decoded structure specification.

    A corpus spec governs every document in its corpus.

    Attributes:
        name: The specification name, the corpus alone.
        files: Every root-relative file at this specification name (prose and JSON), sorted; may be prose only.
        structure: The structure specification, or None when `<name>.structure.json` does not exist.
    """

    name: CorpusSpecName
    files: tuple[RootRelativePath, ...]
    structure: StructureSpec | None


@dataclass(frozen=True, slots=True)
class NamespaceSpec:
    """A namespace spec in docs/__meta__, at a `<corpus>-<namespace>` specification name, narrowing its corpus spec.

    Attributes:
        name: The specification name, the corpus and the namespace.
        files: Every root-relative file at this specification name (prose and JSON), sorted; may be prose only.
        structure: The structure specification, or None when `<name>.structure.json` does not exist.
    """

    name: NamespaceSpecName
    files: tuple[RootRelativePath, ...]
    structure: StructureSpec | None

    def is_governing(self, filename: AspectFilename) -> bool:
        """True when the spec's namespace matches the filename.

        Args:
            filename: Document filename stem whose governance is asked; matched by hyphen-delimited prefix.
        """
        return self.name.namespace.is_prefix_of(filename)


type Spec = CorpusSpec | NamespaceSpec


@dataclass(frozen=True, slots=True)
class Governance:
    """The specs that govern one document, broad to narrow.

    Attributes:
        ref: The governed document.
        corpus_spec: The spec of the document's corpus, which governs every document in it.
        namespace_specs: Every namespace spec whose namespace matches the document, broad to narrow.
    """

    ref: DocumentRef
    corpus_spec: CorpusSpec
    namespace_specs: tuple[NamespaceSpec, ...]

    def specs(self) -> tuple[Spec, ...]:
        """Every governing spec, corpus spec first."""
        return (self.corpus_spec, *self.namespace_specs)

    def structure_specs(self) -> tuple[StructureSpec, ...]:
        """Structure specifications to apply in order; `()` means ungoverned for structure.

        A corpus spec without a structure specification leaves the document ungoverned even when a matching
        namespace spec carries one: a namespace narrows a base, it cannot supply one.
        """
        if self.corpus_spec.structure is None:
            return ()
        structure_specs: list[StructureSpec] = []
        for spec in self.specs():
            if spec.structure is not None:
                structure_specs.append(spec.structure)
        return tuple(structure_specs)

    def frontmatter_schemas(self) -> tuple[FrontmatterSchema, ...]:
        """Frontmatter schemas to apply in order; `()` means ungoverned for frontmatter.

        Each comes from the `frontmatter` key of a structure specification. As with `structure_specs`, a corpus
        spec whose structure specification states no frontmatter schema leaves the document ungoverned even when a
        matching namespace spec states one.
        """
        corpus_structure = self.corpus_spec.structure
        if corpus_structure is None or corpus_structure.frontmatter is None:
            return ()
        schemas: list[FrontmatterSchema] = []
        for structure_spec in self.structure_specs():
            if structure_spec.frontmatter is not None:
                schemas.append(structure_spec.frontmatter)
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
    """A namespace spec as its corpus holds it: the namespace, without the corpus, and the spec's files.

    The `Corpus` holding the record supplies the corpus, so the record cannot name another one;
    `Corpus.namespace_specs` builds the `NamespaceSpec` from both.

    Attributes:
        namespace: The namespace, the specification name after its corpus.
        files: Every root-relative file at the spec's specification name (prose and JSON), sorted; may be prose only.
        structure: The structure specification, or None when the spec has no `.structure.json` file.
    """

    namespace: AspectNamespace
    files: tuple[RootRelativePath, ...]
    structure: StructureSpec | None


@dataclass(frozen=True, slots=True)
class Corpus:
    """One corpus: its spec, the namespaces narrowing it, and the filenames of its documents.

    The corpus is the one its spec names. Its namespace specs and its documents are built from the parts the corpus
    does not fix, a namespace and a filename, so none of them can belong to another corpus. Either part may be passed
    in any order: the corpus lists namespace specs broad to narrow and documents by filename.

    Attributes:
        corpus_spec: The corpus spec; always present (discovery is spec-first), possibly prose only.
        namespaces: The namespace specs narrowing the corpus spec, each without its corpus, in any order.
        filenames: Stems of the Markdown files directly inside docs/<name>/, in any order.
    """

    corpus_spec: CorpusSpec
    namespaces: tuple[CorpusNamespace, ...]
    filenames: tuple[AspectFilename, ...]

    @property
    def name(self) -> CorpusName:
        """Directory name under docs/: the corpus the corpus spec names."""
        return self.corpus_spec.name.corpus

    @property
    def namespace_specs(self) -> tuple[NamespaceSpec, ...]:
        """The specs narrowing the corpus spec, one per namespace, broad to narrow by (segment count, value)."""
        broad_to_narrow = sorted(
            self.namespaces, key=lambda corpus_namespace: namespace_order_key(corpus_namespace.namespace)
        )
        namespace_specs: list[NamespaceSpec] = []
        for corpus_namespace in broad_to_narrow:
            name = NamespaceSpecName(self.name, corpus_namespace.namespace)
            namespace_specs.append(NamespaceSpec(name, corpus_namespace.files, corpus_namespace.structure))
        return tuple(namespace_specs)

    @property
    def documents(self) -> tuple[DocumentRef, ...]:
        """Refs of the Markdown files directly inside docs/<name>/, one per filename, sorted by filename."""
        refs: list[DocumentRef] = []
        for filename in sorted(self.filenames, key=str):
            refs.append(DocumentRef(corpus=self.name, filename=filename))
        return tuple(refs)

    @property
    def directory(self) -> RootRelativePath:
        """Root-relative ``docs/<name>``, the directory the corpus's documents sit directly inside."""
        return DOCS_DIR / str(self.name)

    def governance(self, filename: AspectFilename) -> Governance:
        """Corpus spec, then every namespace spec that matches, broad to narrow. Pure.

        Args:
            filename: Stem of the document whose governing specs are wanted; it names no corpus, so the governed
                document is this corpus's.
        """
        matching: list[NamespaceSpec] = []
        for namespace_spec in self.namespace_specs:
            if namespace_spec.is_governing(filename):
                matching.append(namespace_spec)
        ref = DocumentRef(corpus=self.name, filename=filename)
        return Governance(ref, self.corpus_spec, tuple(matching))


@dataclass(frozen=True, slots=True)
class WorkspaceModel:
    """Immutable snapshot of structure and config; holds no root path and no document content.

    Attributes:
        corpora: Every corpus, sorted by name.
        skills_dirs: Every project skills directory an agent reads that the repository has, one record per
            agent and directory, sorted by agent then path. Two agents reading one resolved directory are two
            records with the same ``resolves_to``.
        skill_locations: The location of every skill directly inside the directories those resolve to,
            each once, sorted by directory; ``skills()`` lists the refs alone, and ``skill_agents`` says which
            agents read one. A skill belongs to no corpus, so no spec governs it and ``documents()`` does not
            list it. The locations, not the refs, record where each link leads, so two models differ when a
            link is retargeted even though every ref is the same.
        named_dirs: Every directory a command names to check the skills in, other than an agent's skills
            directory or an entry in one, which `skills_dirs` and `skill_locations` already read, sorted by path.
            Each holds the locations of its own skills, so `skills()` does not list them and `find_skill_location`
            does not find them; `find_named_dir` hands them out. Empty in a run that names none.
        outside_symlinks: Every skills directory an agent declares, entry in a resolved skills directory or a named
            directory, and `SKILL.md` of such an entry or of a named directory, whose symlink chain leaves the
            repository, sorted by path, each once. None of them is a skills directory or a skill of the model; a
            symlink inside a skill is in its resource listing.
    """

    corpora: tuple[Corpus, ...]
    skills_dirs: tuple[SkillsDir, ...]
    skill_locations: tuple[SkillLocation, ...]
    named_dirs: tuple[NamedDir, ...]
    outside_symlinks: tuple[OutsideSymlink, ...]

    def find_corpus(self, name: CorpusName) -> Corpus | None:
        """The corpus with this name, or None when the model has none.

        Args:
            name: Corpus directory name under docs/.
        """
        for corpus in self.corpora:
            if corpus.name == name:
                return corpus
        return None

    def documents(self) -> tuple[DocumentRef, ...]:
        """Every ref, corpus order then filename order."""
        refs: list[DocumentRef] = []
        for corpus in self.corpora:
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

    def skills(self) -> tuple[SkillRef, ...]:
        """Every ref of a skill in the agents' skills directories, in directory order; no named directory's."""
        refs: list[SkillRef] = []
        for location in self.skill_locations:
            refs.append(location.ref)
        return tuple(refs)

    def find_skill_location(self, directory: RootRelativePath) -> SkillLocation | None:
        """The location of the skill whose ref's `directory` equals this root-relative path, or None.

        Only the agents' skills are looked up, never a named directory's: `find_named_dir` finds those.

        Args:
            directory: Skill directory to look up, `<resolved skills directory>/<entry>`, compared whole and
                lexically: an entry that is a link is found by its own name, never by the directory it leads to.
        """
        for location in self.skill_locations:
            if location.ref.directory == directory:
                return location
        return None

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
            resolved_path: A resolved directory, root-relative, matched against each skill directory's parent.

        Returns:
            Every such skill's location, in the model's order, or `()` when the directory holds none.
        """
        locations: list[SkillLocation] = []
        for location in self.skill_locations:
            if location.ref.directory.parent == resolved_path:
                locations.append(location)
        return tuple(locations)

    def find_named_dir(self, path: RootRelativePath) -> NamedDir | None:
        """The directory a command named as `path`, or `None` when it named none there.

        Args:
            path: The directory as the command spelled it, root-relative, compared whole and lexically.
        """
        for named_dir in self.named_dirs:
            if named_dir.path == path:
                return named_dir
        return None

    def has_outside_symlink(self, path: RootRelativePath) -> bool:
        """True when the model records a symlink leading outside the repository at this path.

        Args:
            path: Where an agent reaches the symlink, root-relative, compared whole and lexically against each
                outside symlink's `path`: a link is found by its own name, never by where it leads.
        """
        for outside in self.outside_symlinks:
            if outside.path == path:
                return True
        return False

    def locate_skill_files(self, path: ResolvedPath) -> tuple[SkillLocation, ...]:
        """The locations of the skills whose `SKILL.md` leads to this resolved file, an agent's or a named one's.

        Args:
            path: A resolved path, root-relative, with no symlink on the way to it.

        Returns:
            Every such skill's location, each once, the agents' first, then the named directories' in their order,
            or `()` when none is there. Two skills whose `SKILL.md` links lead to one file are both returned.
        """
        locations: list[SkillLocation] = []
        located: set[SkillRef] = set()
        for location in self.skill_locations:
            if location.file_resolves_to == path:
                locations.append(location)
                located.add(location.ref)
        for named_dir in self.named_dirs:
            for location in named_dir.skills:
                # Two named directories may hold one skill, such as `skills` and `skills/review`.
                if location.file_resolves_to == path and location.ref not in located:
                    locations.append(location)
                    located.add(location.ref)
        return tuple(locations)

    def skill_agents(self, ref: SkillRef) -> tuple[AgentName, ...]:
        """The agents that read a skill: those with a skills directory that leads to the one holding it.

        Args:
            ref: Skill whose directory's parent is matched against each skills directory's resolved directory.

        Returns:
            The agents in name order, each once, or ``()`` when no skills directory leads there.
        """
        agents: list[AgentName] = []
        for skills_dir in self.skills_dirs:
            if skills_dir.resolves_to == ref.directory.parent and skills_dir.agent not in agents:
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

    def frontmatter_schemas_of(self, ref: DocumentRef) -> tuple[FrontmatterSchema, ...]:
        """The frontmatter schemas that govern a document, in the order `Governance.frontmatter_schemas` applies them.

        `()` means no frontmatter schema governs the document, one of a corpus the model does not hold included.

        Args:
            ref: Document to look up, whether or not the model lists it; only its corpus and filename are read.
        """
        governance = self.find_governance(ref)
        if governance is None:
            return ()
        return governance.frontmatter_schemas()

    def outline_specs_of(self, ref: DocumentRef) -> tuple[StructureSpec, ...]:
        """The structure specifications that state an outline for a document, in the order they apply.

        `()` means no outline governs the document, one of a corpus the model does not hold included.

        Args:
            ref: Document to look up, whether or not the model lists it; only its corpus and filename are read.
        """
        governance = self.find_governance(ref)
        if governance is None:
            return ()
        return governance.outline_specs()
