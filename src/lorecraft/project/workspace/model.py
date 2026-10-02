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
from typing import assert_never

from lorecraft.agents import AgentName
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename, AspectNamespace
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document.ref import DocumentRef
from lorecraft.project.layout import DOCS_DIR
from lorecraft.project.schemas.name import CorpusSpecName, NamespaceSpecName, SpecName
from lorecraft.project.schemas.structure import FrontmatterSchema, StructureSpec
from lorecraft.project.skill.named_dir import NamedDir
from lorecraft.project.skill.outside import OutsideSymlink
from lorecraft.project.skill.ref import SkillLocation, SkillRef
from lorecraft.project.skill.skills_dir import SkillsDir


@dataclass(frozen=True, slots=True)
class Spec:
    """One specification name in docs/__meta__ and the structure specification decoded from it.

    Not hashable: a structure specification's `FrontmatterSchema` holds a dict, so instances must not be put in a
    set or used as a key.

    Attributes:
        name: The specification name, parsed.
        files: Every root-relative file at this specification name (prose and JSON), sorted; may be prose only.
        structure: The structure specification, or None when `<name>.structure.json` does not exist.
    """

    name: SpecName
    files: tuple[RootRelativePath, ...]
    structure: StructureSpec | None

    @property
    def corpus(self) -> CorpusName:
        """The corpus this spec belongs to, named first in its specification name."""
        return self.name.corpus

    @property
    def namespace(self) -> AspectNamespace | None:
        """The namespace of a `<corpus>-<namespace>` specification name; None for a corpus spec's name."""
        match self.name:
            case CorpusSpecName():
                return None
            case NamespaceSpecName(namespace=namespace):
                return namespace
            case _:
                assert_never(self.name)

    def is_governing(self, filename: AspectFilename) -> bool:
        """True for a corpus spec always; for a namespace spec when the namespace matches.

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
        corpus_spec: The spec of the document's corpus, which governs every document in it.
        namespace_specs: Every namespace spec whose namespace matches the document, broad to narrow.
    """

    ref: DocumentRef
    corpus_spec: Spec
    namespace_specs: tuple[Spec, ...]

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
        spec: The corpus spec; always present (discovery is spec-first), possibly prose only.
        namespace_specs: Narrowing specs, sorted broad to narrow by (segment count, value).
        documents: Refs of the Markdown files directly inside docs/<name>/, sorted by filename.
    """

    name: CorpusName
    spec: Spec
    namespace_specs: tuple[Spec, ...]
    documents: tuple[DocumentRef, ...]

    def __post_init__(self) -> None:
        """Reject a corpus whose parts do not all belong to it.

        Raises:
            ValueError: If `spec.name` is not `CorpusSpecName(name)`, a namespace spec has no namespace or
                another corpus, `namespace_specs` is not broad-to-narrow, or a ref names another corpus.
        """
        if self.spec.name != CorpusSpecName(self.name):
            raise ValueError(f'corpus {self.name} must carry its own corpus spec, got {self.spec.name}')
        order_keys: list[tuple[int, str]] = []
        for namespace_spec in self.namespace_specs:
            if namespace_spec.namespace is None:
                raise ValueError(f'corpus {self.name} lists corpus spec {namespace_spec.name} as a namespace spec')
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
        matching: list[Spec] = []
        for namespace_spec in self.namespace_specs:
            if namespace_spec.is_governing(ref.filename):
                matching.append(namespace_spec)
        return Governance(ref, self.spec, tuple(matching))


@dataclass(frozen=True, slots=True)
class WorkspaceModel:
    """Immutable snapshot of structure and config; holds no root path and no document content.

    Attributes:
        corpora: Every corpus, sorted by name.
        skills_dirs: Every project skills directory an agent reads that the repository has, one record per
            agent and directory, sorted by agent then path. Two agents reading one canonical directory are two
            records with the same ``resolves_to``.
        skill_locations: The location of every skill directly inside the canonical directories those resolve to,
            each once, sorted by directory; ``skills()`` lists the refs alone, and ``skill_agents`` says which
            agents read one. A skill belongs to no corpus, so no spec governs it and ``documents()`` does not
            list it. The locations, not the refs, record where each link leads, so two models differ when a
            link is retargeted even though every ref is the same.
        named_dirs: Every directory a command names to check the skills in, other than an agent's skills
            directory or an entry in one, which `skills_dirs` and `skill_locations` already read, sorted by path.
            Each holds the locations of its own skills, so `skills()` does not list them and `find_skill` does not
            find them; `skill_location` does. Empty in a run that names none.
        outside_symlinks: Every skills directory an agent declares, entry in a canonical skills directory or a named
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

    def skill_location(self, ref: SkillRef) -> SkillLocation:
        """Where the files of a skill this model lists live.

        Args:
            ref: Skill to look up; it must be one of this model's, in an agent's skills directory or a named one.

        Raises:
            ValueError: If the model lists no skill with this ref (refs from the model never trigger it).
        """
        for location in self.skill_locations:
            if location.ref == ref:
                return location
        for named_dir in self.named_dirs:
            for location in named_dir.skills:
                if location.ref == ref:
                    return location
        raise ValueError(f'skill {ref.directory} is not a skill of this model')

    def find_skill(self, directory: RootRelativePath) -> SkillRef | None:
        """The ref whose `directory` equals this root-relative path, or None.

        Only the agents' skills are looked up, never a named directory's: `find_named_dir` finds those.

        Args:
            directory: Skill directory to look up, `<canonical skills directory>/<entry>`, compared whole and
                lexically: an entry that is a link is found by its own name, never by the directory it leads to.
        """
        for location in self.skill_locations:
            if location.ref.directory == directory:
                return location.ref
        return None

    def has_skills_dir(self, canonical_path: RootRelativePath) -> bool:
        """True when a skills directory the model lists leads to this canonical path.

        Args:
            canonical_path: A canonical directory, root-relative, with no symlink on the way to it, compared whole and
                lexically against each skills directory's `resolves_to`.
        """
        for skills_dir in self.skills_dirs:
            if skills_dir.resolves_to == canonical_path:
                return True
        return False

    def skills_in(self, canonical_path: RootRelativePath) -> tuple[SkillRef, ...]:
        """The skills listed directly inside this canonical directory.

        Args:
            canonical_path: A canonical directory, root-relative, matched against each skill directory's parent.

        Returns:
            Every such skill, in the model's order, or `()` when the directory holds none.
        """
        refs: list[SkillRef] = []
        for location in self.skill_locations:
            if location.ref.directory.parent == canonical_path:
                refs.append(location.ref)
        return tuple(refs)

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

    def locate_skill_files(self, path: RootRelativePath) -> tuple[SkillRef, ...]:
        """The skills whose `SKILL.md` leads to this canonical file, in an agent's skills directory or a named one.

        Args:
            path: A canonical path, root-relative, with no symlink on the way to it.

        Returns:
            Every such skill, each once, the agents' first, then the named directories' in their order, or `()`
            when none is there. Two skills whose `SKILL.md` links lead to one file are both returned.
        """
        refs: list[SkillRef] = []
        for location in self.skill_locations:
            if location.file_resolves_to == path:
                refs.append(location.ref)
        for named_dir in self.named_dirs:
            for location in named_dir.skills:
                # Two named directories may hold one skill, such as `skills` and `skills/review`.
                if location.file_resolves_to == path and location.ref not in refs:
                    refs.append(location.ref)
        return tuple(refs)

    def skill_agents(self, ref: SkillRef) -> tuple[AgentName, ...]:
        """The agents that read a skill: those with a skills directory that leads to the one holding it.

        Args:
            ref: Skill whose directory's parent is matched against each skills directory's canonical directory.

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
