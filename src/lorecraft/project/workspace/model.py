"""The workspace model: an immutable snapshot of which corpora, specs, documents and skills a repository declares.

The loader builds one model per run from ``docs/__meta__/``, the corpus directories and the project skills
directories; every query here is pure. The model holds structure (corpora, document refs, skills directories,
skill refs) and configuration (decoded specs), never document content: text stays behind the document
repository and is read on demand through a ``DocumentRef``, and the model reads no ``SKILL.md``.

Governance is the one computation the model owns. A document is governed by its corpus spec first, then by
every namespace spec whose namespace matches its filename, broad to narrow. A namespace spec narrows a
base; it never supplies one, so a corpus spec without an aspect leaves the document ungoverned for that
aspect whatever the namespace specs carry.
"""

from dataclasses import dataclass

from lorecraft.agents import AgentName
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename, AspectNamespace
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document.ref import DocumentRef
from lorecraft.project.layout import DOCS_DIR
from lorecraft.project.schemas.name import SchemaName
from lorecraft.project.schemas.structure import FrontmatterSchema, StructureAspect
from lorecraft.project.skill.outside import OutsideSymlink
from lorecraft.project.skill.ref import SkillLocation, SkillRef
from lorecraft.project.skill.skills_dir import SkillsDir


@dataclass(frozen=True, slots=True)
class Spec:
    """One specification stem in docs/__meta__ and the aspects decoded from it.

    Not hashable: a structure aspect's ``FrontmatterSchema`` holds a dict, so instances must not be put in a set or
    used as a key.

    Attributes:
        name: The stem, parsed.
        files: Every root-relative file at this stem (prose and JSON), sorted; may be prose only.
        structure: The structure aspect, or None when ``<stem>.structure.json`` does not exist.
    """

    name: SchemaName
    files: tuple[RootRelativePath, ...]
    structure: StructureAspect | None

    @property
    def corpus(self) -> CorpusName:
        """The corpus this stem belongs to."""
        return self.name[0]

    @property
    def namespace(self) -> AspectNamespace | None:
        """The namespace of a ``<corpus>-<namespace>`` stem; None for a corpus stem."""
        if len(self.name) == 1:
            return None
        return self.name[1]

    def is_governing(self, filename: AspectFilename) -> bool:
        """True for a corpus stem always; for a namespace stem when the namespace matches.

        Args:
            filename: Document filename stem whose governance is asked; matched by hyphen-delimited prefix.
        """
        if self.namespace is None:
            return True
        return self.namespace.is_prefix_of(str(filename))


@dataclass(frozen=True, slots=True)
class Governance:
    """The specs that govern one document, broad to narrow.

    Attributes:
        ref: The governed document.
        specs: The corpus spec first, then every matching namespace spec. Never empty.
    """

    ref: DocumentRef
    specs: tuple[Spec, ...]

    def __post_init__(self) -> None:
        """Reject a governance with no specs: the corpus spec is always there.

        Raises:
            ValueError: If ``specs`` is empty.
        """
        if not self.specs:
            raise ValueError(f'document {self.ref.path} must be governed by at least its corpus spec')

    def structure_specs(self) -> tuple[StructureAspect, ...]:
        """Structure aspects to apply in order; ``()`` means ungoverned for the structure aspect.

        A corpus spec without a structure aspect leaves the document ungoverned even when a matching namespace
        spec carries one: a namespace narrows a base, it cannot supply one.
        """
        if self.specs[0].structure is None:
            return ()
        aspects: list[StructureAspect] = []
        for spec in self.specs:
            if spec.structure is not None:
                aspects.append(spec.structure)
        return tuple(aspects)

    def frontmatter_schemas(self) -> tuple[FrontmatterSchema, ...]:
        """Frontmatter schemas to apply in order; ``()`` means ungoverned for frontmatter.

        Each comes from the ``frontmatter`` key of a structure aspect. As with ``structure_specs``, a corpus spec
        whose structure aspect states no frontmatter schema leaves the document ungoverned even when a matching
        namespace spec states one.
        """
        corpus_structure = self.specs[0].structure
        if corpus_structure is None or corpus_structure.frontmatter is None:
            return ()
        schemas: list[FrontmatterSchema] = []
        for aspect in self.structure_specs():
            if aspect.frontmatter is not None:
                schemas.append(aspect.frontmatter)
        return tuple(schemas)


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
class Corpus:
    """One corpus: its spec, the namespace specs narrowing it, and its document refs.

    Attributes:
        name: Directory name under docs/.
        spec: The corpus stem; always present (discovery is spec-first), possibly prose only.
        namespace_specs: Narrowing stems, sorted broad to narrow by (segment count, value).
        documents: Refs of the Markdown files directly inside docs/<name>/, sorted by filename.
    """

    name: CorpusName
    spec: Spec
    namespace_specs: tuple[Spec, ...]
    documents: tuple[DocumentRef, ...]

    def __post_init__(self) -> None:
        """Reject a corpus whose parts do not all belong to it.

        Raises:
            ValueError: If ``spec.name != (name,)``, a namespace spec has no namespace or another corpus,
                ``namespace_specs`` is not broad-to-narrow, or a ref names another corpus.
        """
        if self.spec.name != (self.name,):
            raise ValueError(f'corpus {self.name} must carry its own corpus spec, got stem {self.spec.name}')
        order_keys: list[tuple[int, str]] = []
        for namespace_spec in self.namespace_specs:
            if namespace_spec.namespace is None:
                raise ValueError(f'corpus {self.name} lists corpus stem {namespace_spec.name} as a namespace spec')
            if namespace_spec.corpus != self.name:
                raise ValueError(f'corpus {self.name} lists namespace spec {namespace_spec.name} of another corpus')
            order_keys.append(namespace_order_key(namespace_spec.namespace))
        if order_keys != sorted(order_keys):
            raise ValueError(f'corpus {self.name} namespace specs are not broad to narrow: {order_keys}')
        for ref in self.documents:
            if ref.corpus != self.name:
                raise ValueError(f'corpus {self.name} lists document {ref.path} of another corpus')

    @property
    def directory(self) -> RootRelativePath:
        """Root-relative ``docs/<name>``, the directory the corpus's documents sit directly inside."""
        return DOCS_DIR / str(self.name)

    def governance(self, ref: DocumentRef) -> Governance:
        """Corpus spec, then every namespace spec that matches, in stored order. Pure.

        Args:
            ref: Document whose governing specs are wanted; it must belong to this corpus.

        Raises:
            ValueError: If `ref.corpus != name`.
        """
        if ref.corpus != self.name:
            raise ValueError(f'document {ref.path} is not in corpus {self.name}')
        specs: list[Spec] = [self.spec]
        for namespace_spec in self.namespace_specs:
            if namespace_spec.is_governing(ref.filename):
                specs.append(namespace_spec)
        return Governance(ref, tuple(specs))


@dataclass(frozen=True, slots=True)
class WorkspaceModel:
    """Immutable snapshot of structure and config; holds no root path and no document content.

    Attributes:
        corpora: Every corpus, sorted by name.
        skills_dirs: Every project skills directory an agent reads that the repository has, one record per
            agent and directory, sorted by agent then path. Two agents reading one real directory are two
            records with the same ``resolves_to``.
        skill_locations: The location of every skill directly inside the real directories those resolve to,
            each once, sorted by directory; ``skills()`` lists the refs alone, and ``skill_agents`` says which
            agents read one. A skill belongs to no corpus, so no spec governs it and ``documents()`` does not
            list it. The locations, not the refs, record where each link leads, so two models differ when a
            link is retargeted even though every ref is the same.
        outside_symlinks: Every skills directory an agent declares, entry in a real skills directory, and
            ``SKILL.md`` of such an entry, whose symlink chain leaves the repository, sorted by path. None of them
            is a skills directory or a skill of the model; a symlink inside a skill is in its resource listing.
    """

    corpora: tuple[Corpus, ...]
    skills_dirs: tuple[SkillsDir, ...]
    skill_locations: tuple[SkillLocation, ...]
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
        """Every skill's ref, in directory order."""
        refs: list[SkillRef] = []
        for location in self.skill_locations:
            refs.append(location.ref)
        return tuple(refs)

    def skill_location(self, ref: SkillRef) -> SkillLocation:
        """Where the files of a skill this model lists live.

        Args:
            ref: Skill to look up; it must be one of this model's.

        Raises:
            ValueError: If the model lists no skill with this ref (refs from the model never trigger it).
        """
        for location in self.skill_locations:
            if location.ref == ref:
                return location
        raise ValueError(f'skill {ref.directory} is not a skill of this model')

    def locate_skills(self, path: RootRelativePath) -> tuple[SkillRef, ...]:
        """The skills whose files are at this real path: the directory they lead to, or their ``SKILL.md``.

        Args:
            path: A real path, root-relative, with no symlink on the way to it.

        Returns:
            Every such skill, in the model's order, or ``()`` when none is there. Two entries that lead to one
            directory are both returned.
        """
        refs: list[SkillRef] = []
        for location in self.skill_locations:
            if path == location.resolves_to or path == location.file_resolves_to:
                refs.append(location.ref)
        return tuple(refs)

    def skill_agents(self, ref: SkillRef) -> tuple[AgentName, ...]:
        """The agents that read a skill: those with a skills directory that leads to the one holding it.

        Args:
            ref: Skill whose directory's parent is matched against each skills directory's real directory.

        Returns:
            The agents in name order, each once, or ``()`` when no skills directory leads there.
        """
        agents: list[AgentName] = []
        for skills_dir in self.skills_dirs:
            if skills_dir.resolves_to == ref.directory.parent and skills_dir.agent not in agents:
                agents.append(skills_dir.agent)
        return tuple(agents)

    def governance(self, ref: DocumentRef) -> Governance:
        """The specs governing a document this model lists.

        Args:
            ref: Document to look up; its corpus must be one of this model's.

        Raises:
            ValueError: If `ref.corpus` is not a corpus of this model (refs from the model never trigger it).
        """
        corpus = self.find_corpus(ref.corpus)
        if corpus is None:
            raise ValueError(f'document {ref.path} is in no corpus of this model')
        return corpus.governance(ref)
