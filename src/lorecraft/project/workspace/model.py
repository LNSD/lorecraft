"""The workspace model: an immutable snapshot of which corpora, specs, documents and skills a repository declares.

The loader builds one model per run from `docs/__meta__/`, the corpus directories and the project skills
directories; every query here is pure. The model holds structure (corpora, document refs, skills directories, skill
refs) and configuration (decoded specs and immutable raw schema inputs), never document content: text stays behind
the document repository and is read on demand through a `DocumentRef`, and the model reads no `SKILL.md`.

Governance is the one computation the model owns. A document is governed by its corpus spec first, then by
every namespace spec whose namespace matches its filename, broad to narrow. A skill is governed by the
reserved `skills` corpus and its listed directory name. A namespace spec narrows a base; it never supplies one, so a
corpus spec that states no rule of one kind, a structure specification or a frontmatter schema, leaves the item
ungoverned for that kind whatever the namespace specs carry.
"""

from collections.abc import Iterable
from dataclasses import InitVar, dataclass, field
from typing import Self, assert_never

from lorecraft.agents import AgentName
from lorecraft.core.error import Error
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import (
    AspectFilename,
    AspectName,
    AspectNamespace,
    EmptyAspectNameError,
    InvalidAspectNameCharacterError,
)
from lorecraft.project.corpus import (
    META_CORPUS_NAME,
    SKILLS_CORPUS_NAME,
    CorpusName,
    EmptyCorpusNameError,
    InvalidCorpusNameCharacterError,
    ReservedCorpusDirectory,
    ReservedCorpusNameError,
)
from lorecraft.project.document import DocumentRef, SpecRef
from lorecraft.project.item import (
    DocumentOrigin,
    ItemDescriptor,
    ItemRef,
    ItemType,
    SkillEntrypointOrigin,
    SkillResourceOrigin,
    SpecOrigin,
    SpecPart,
    UnlistedItemError,
)
from lorecraft.project.layout import DOCS_DIR, DOCUMENT_SUFFIX, SPECS_DIR
from lorecraft.project.link_target import DocumentDirectory, SkillRoot
from lorecraft.project.schemas import (
    CorpusSpecName,
    NamespaceSpecName,
    SpecName,
    StatedFrontmatterSchema,
    parse_spec_name,
)
from lorecraft.project.schemas.structure import BuiltinLineBudget, StructureSpec
from lorecraft.project.skill import (
    OutsideSymlink,
    SkillLocation,
    SkillRef,
    SkillResourceLocation,
    SkillsDir,
)
from lorecraft.schemas import (
    BuiltinOrigin,
    DuplicateSchemaRefError,
    FrontmatterSchemaInput,
    RepositorySchemaInput,
    SchemaInput,
    SchemaKind,
    SchemaRef,
)
from lorecraft.schemas.builtin import AGENT_SKILLS_LAYER_ORIGIN
from lorecraft.vfs import ResolvedPath

from .failure import FailedStructure, LoadFailure


class DuplicateCorpusNameError(Error):
    """Two corpus values in a workspace model have the same name.

    Attributes:
        name: The corpus name repeated by the values.
    """

    name: CorpusName

    def __init__(self, name: CorpusName) -> None:
        self.name = name
        super().__init__(f'more than one corpus is named {name}')


class DuplicateSkillLocationRefError(Error):
    """Two skill locations in a workspace model have the same ref.

    Attributes:
        ref: The skill ref repeated by the locations.
    """

    ref: SkillRef

    def __init__(self, ref: SkillRef) -> None:
        self.ref = ref
        super().__init__(f'more than one skill location has ref {ref.directory}')


class DuplicateOutsideSymlinkPathError(Error):
    """Two outside symlinks in a workspace model have the same path.

    Attributes:
        path: The path repeated by the outside symlinks.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'more than one outside symlink has path {path}')


def agent_skills_floor_enabled(builtin_layers: tuple[BuiltinSpecLayer, ...]) -> bool:
    """Whether the enabled layers include the builtin Agent Skills floor."""
    return any(layer.origin == AGENT_SKILLS_LAYER_ORIGIN for layer in builtin_layers)


def find_document_at(ref: ItemRef) -> DocumentRef | None:
    """The document represented by a ref's path, or None when it is not a valid document path.

    Args:
        ref: Common item reference whose path may name a document.
    """
    parts = ref.path.value.parts
    if len(parts) != 3 or parts[0] != DOCS_DIR.value.name or not parts[2].endswith(DOCUMENT_SUFFIX):
        return None
    try:
        return DocumentRef(CorpusName.parse(parts[1]), AspectFilename.parse(parts[2].removesuffix(DOCUMENT_SUFFIX)))
    except (
        EmptyCorpusNameError,
        InvalidCorpusNameCharacterError,
        ReservedCorpusNameError,
        EmptyAspectNameError,
        InvalidAspectNameCharacterError,
    ):
        return None


def _skill_aspect_filename(entry: str) -> AspectFilename | None:
    """Return the skill entry as an aspect filename when its name has that format."""
    try:
        return AspectFilename.parse(entry)
    except EmptyAspectNameError, InvalidAspectNameCharacterError:
        return None


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
class BuiltinSpecLayer:
    """A builtin source of a frontmatter schema and a line budget for selected item kinds.

    Attributes:
        origin: Stable identity of the builtin layer.
        applies_to: Item kinds the layer governs, independently of repository corpora.
        frontmatter_schema: Optional frontmatter schema the layer contributes to the workspace registry.
        lines: Optional builtin line budget.
    """

    origin: BuiltinOrigin
    applies_to: frozenset[ItemType]
    frontmatter_schema: FrontmatterSchemaInput | None = None
    lines: NonZeroUnsignedInt | None = None

    @property
    def schema_refs(self) -> tuple[SchemaRef, ...]:
        """Schema identities in declaration order."""
        return tuple(schema_input.reference for schema_input in self.registered_schema_inputs)

    @property
    def registered_schema_inputs(self) -> tuple[SchemaInput, ...]:
        """The schema inputs registered by this layer, derived from its content fields."""
        if self.frontmatter_schema is None:
            return ()
        return (self.frontmatter_schema,)


@dataclass(frozen=True, slots=True)
class Governance:
    """The specs that govern one document or skill, broad to narrow.

    A layer whose structure file failed to load is held as it is, with its `FailedStructure`. The queries below read
    only the layers that loaded; `failed_layers` names the others, so a consumer decides what a failed layer means.

    The governance is built from a corpus and a filename and keeps only the specs they yield, so it cannot hold a spec
    of another corpus, one whose namespace does not match the filename, or one twice. Two governances are equal when
    they govern the same listed name with the same specs, whatever else their corpora hold.

    Attributes:
        ref: The governed document, or None when a listed name that is no valid filename stem, such as a skill's
            directory name, was matched.
        corpus_spec: The corpus spec that governs every document or skill in it.
        namespace_specs: Every namespace spec whose namespace matches the name, broad to narrow.
    """

    # Construction arguments, not fields: neither is kept, so neither takes part in equality or hashing.
    corpus: InitVar[Corpus]  # defined below: a corpus builds its governance, and the governance reads it
    filename: InitVar[AspectFilename | str]  # matched by hyphen-delimited prefix; the item is the corpus's
    ref: DocumentRef | None = field(init=False)
    corpus_spec: CorpusSpec = field(init=False)
    namespace_specs: tuple[NamespaceSpec, ...] = field(init=False)

    def __post_init__(self, corpus: Corpus, filename: AspectFilename | str) -> None:
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

        A corpus spec without a loaded structure specification leaves the item ungoverned even when a
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

        Each comes from the `frontmatter` key of a loaded governing structure specification. An applicable tuple is
        empty when no loaded governing layer states a schema.
        """
        corpus_structure = self.corpus_structure()
        if corpus_structure is None or corpus_structure.frontmatter is None:
            return ()
        schemas: list[StatedFrontmatterSchema] = []
        for structure_spec in self.structure_specs():
            if structure_spec.frontmatter is not None:
                schemas.append(StatedFrontmatterSchema(spec=structure_spec.path, schema=structure_spec.frontmatter))
        return tuple(schemas)

    def applicable_frontmatter_schema_refs(self) -> tuple[SchemaRef, ...]:
        """The applicable loaded frontmatter registry subjects, broad to narrow."""
        corpus_structure = self.corpus_structure()
        if corpus_structure is None or corpus_structure.frontmatter_schema_ref is None:
            return ()
        return tuple(
            schema_ref
            for structure in self.structure_specs()
            if (schema_ref := structure.frontmatter_schema_ref) is not None
        )

    def outline_specs(self) -> tuple[StructureSpec, ...]:
        """Structure specifications that state an outline, in order; `()` means ungoverned for the outline.

        They are the ones among `structure_specs` that state one, so a namespace outline never governs alone either.
        """
        outline_specs: list[StructureSpec] = []
        for structure_spec in self.structure_specs():
            if structure_spec.outline:
                outline_specs.append(structure_spec)
        return tuple(outline_specs)


def find_narrowest_ancestor(name: str, names: Iterable[str]) -> str | None:
    """The narrowest of the names whose hyphen-delimited prefix the name continues, or `None` when none is.

    A name `a` is an ancestor of `b` when `b` starts with `a-`; the narrowest has the most hyphen-delimited segments,
    so no two ancestors tie. Names are compared as spelled, never parsed, so any name a corpus or a namespace can
    take is comparable.

    Args:
        name: Stem whose base is wanted; it need not be one of the names.
        names: The stems to look for an ancestor among.
    """
    ancestors = [candidate for candidate in names if candidate != name and name.startswith(f'{candidate}-')]
    if not ancestors:
        return None
    return max(ancestors, key=lambda candidate: candidate.count('-'))


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
        by_name = {str(candidate): candidate for candidate in self.filenames}
        narrowest = find_narrowest_ancestor(str(filename), by_name)
        if narrowest is None:
            return None
        return DocumentRef(corpus=self.name, filename=by_name[narrowest])

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
class MetaCorpus(Corpus):
    """The reserved meta corpus, with a name fixed by the workspace model.

    Attributes:
        corpus_spec: The reserved corpus spec, possibly prose only.
        namespaces: The namespace specs narrowing the reserved corpus.
        filenames: The Markdown files listed for the corpus; empty for the reserved meta corpus.
    """

    @classmethod
    def from_corpus(cls, corpus: Corpus) -> Self:
        """Build the meta-corpus value from the reserved corpus's contents."""
        return cls(corpus.corpus_spec, corpus.namespaces, corpus.filenames)

    @property
    def name(self) -> CorpusName:
        """The fixed reserved meta corpus name."""
        return CorpusName.parse(META_CORPUS_NAME)


@dataclass(frozen=True, slots=True)
class ResolvedItem:
    """A listed item's descriptor and the specifications governing it, resolved together.

    Attributes:
        descriptor: The item's model-resolved locations and origin metadata.
        governance: The governing specs, or `None` when none governs the item.
    """

    descriptor: ItemDescriptor
    governance: Governance | None


@dataclass(frozen=True, slots=True)
class WorkspaceModel:
    """Immutable snapshot of structure and config; holds no root path and no document content.

    Corpus values, skill locations, and outside symlinks are unordered collections with unique keys; the `sorted_*`
    properties list them in the order a consumer reads them in. Other ordered collections preserve the order named
    by their fields below. Corpus values and repository schema inputs are stored once, with their keyed views derived
    from their own identities.

    A skill location records where its entry and files resolve, so two models can differ when a link is retargeted
    even if every skill ref is the same. The reserved `skills` corpus governs skill entrypoints but not resources;
    `documents()` does not list it. An outside symlink is not a skills directory or a skill in the model; symlinks
    inside a skill are part of its resource listing.

    Attributes:
        corpus_values: Every distinct corpus value; `corpora` is derived by corpus name.
        corpora: Every corpus, by name.
        skills_dirs: Every project skills directory an agent reads that the repository has, one record per
            agent and directory. Two agents reading one resolved directory are two records with the same
            `resolves_to`.
        skill_location_values: Every distinct skill location, stored without an order.
        skill_locations: Every skill location, keyed by ref and inserted in ref order.
        skills_corpus: The reserved `skills` corpus, available to its own specification checks, or None when no
            `skills` spec exists. It governs skill entrypoints but not resources; no directory
            under `docs/` backs it.
        meta_corpus: The reserved `meta` corpus governing spec items, or None when no `meta` spec exists.
        listed_specifications: Every valid prose spec file in `docs/__meta__/`, including specs whose document corpus
            is absent.
        overlapping_directories: The directories under `docs/` that take a reserved corpus's name, which the model
            ignores: none of their documents is listed.
        outside_symlink_values: Every distinct outside symlink, stored without an order.
        outside_symlinks: Every outside symlink, keyed by path and inserted in path order.
        load_failures: Every unit of the declaration that could not be read or used, each once, in the order the
            loader met them: a structure file, whose `FailedStructure` also stands in its layer, a corpus directory,
            a skills directory, a listed skill directory or a `SKILL.md`,
            and a `docs/` or `docs/__meta__/` that cannot be
            listed. Nothing a failure touches is in the model beyond that record; every other unit is loaded.
        repository_schema_inputs: Raw repository inputs, each carrying repository provenance in its type.
        builtin_layers: Enabled builtin schema inputs and governance parts, in registration order.
        schema_inputs: Derived registry combining builtin layer inputs before repository inputs.
    """

    corpus_values: frozenset[Corpus]
    skills_dirs: frozenset[SkillsDir]
    skill_location_values: frozenset[SkillLocation]
    outside_symlink_values: frozenset[OutsideSymlink]
    load_failures: tuple[LoadFailure, ...]
    skills_corpus: Corpus | None = None
    meta_corpus: MetaCorpus | None = None
    listed_specifications: tuple[SpecRef, ...] = ()
    overlapping_directories: frozenset[ReservedCorpusDirectory] = frozenset()
    unchecked_symlinks: tuple[RootRelativePath, ...] = ()
    repository_schema_inputs: tuple[RepositorySchemaInput, ...] = ()
    builtin_layers: tuple[BuiltinSpecLayer, ...] = ()
    corpora: FrozenMapping[CorpusName, Corpus] = field(init=False, default=FrozenMapping({}))
    skill_locations: FrozenMapping[SkillRef, SkillLocation] = field(init=False, default=FrozenMapping({}))
    outside_symlinks: FrozenMapping[RootRelativePath, OutsideSymlink] = field(init=False, default=FrozenMapping({}))
    # Derived from builtin_layers and repository_schema_inputs, never passed in; replace() recomputes it.
    schema_inputs: FrozenMapping[SchemaRef, SchemaInput] = field(init=False, default=FrozenMapping({}))

    def __post_init__(self) -> None:
        """Derive the corpus, skill and symlink lookups, and check the reserved meta corpus.

        Raises:
            DuplicateCorpusNameError: If two corpus values have the same name.
            DuplicateSkillLocationRefError: If two skill locations have the same ref.
            DuplicateOutsideSymlinkPathError: If two outside symlinks have the same path.
            DuplicateSchemaRefError: If builtin layers or repository inputs repeat a schema reference.
        """
        corpora: dict[CorpusName, Corpus] = {}
        for corpus in sorted(self.corpus_values, key=lambda value: str(value.name)):
            if corpus.name in corpora:
                raise DuplicateCorpusNameError(corpus.name)
            corpora[corpus.name] = corpus
        object.__setattr__(self, 'corpora', FrozenMapping(corpora))
        skill_locations: dict[SkillRef, SkillLocation] = {}
        for location in sorted(self.skill_location_values):
            if location.ref in skill_locations:
                raise DuplicateSkillLocationRefError(location.ref)
            skill_locations[location.ref] = location
        object.__setattr__(self, 'skill_locations', FrozenMapping(skill_locations))
        outside_symlinks: dict[RootRelativePath, OutsideSymlink] = {}
        for outside in sorted(self.outside_symlink_values, key=lambda value: value.path):
            if outside.path in outside_symlinks:
                raise DuplicateOutsideSymlinkPathError(outside.path)
            outside_symlinks[outside.path] = outside
        object.__setattr__(self, 'outside_symlinks', FrozenMapping(outside_symlinks))
        schema_inputs: dict[SchemaRef, SchemaInput] = {}
        for layer in self.builtin_layers:
            for schema_input in layer.registered_schema_inputs:
                if schema_input.reference in schema_inputs:
                    raise DuplicateSchemaRefError(schema_input.reference)
                schema_inputs[schema_input.reference] = schema_input
        for schema_input in self.repository_schema_inputs:
            if schema_input.reference in schema_inputs:
                raise DuplicateSchemaRefError(schema_input.reference)
            schema_inputs[schema_input.reference] = schema_input
        object.__setattr__(self, 'schema_inputs', FrozenMapping(schema_inputs))

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
        """The Markdown file of every corpus and namespace spec, sorted by path; no README."""
        specs: list[Spec] = []
        for corpus in (
            *self.sorted_corpora,
            *([self.skills_corpus] if self.skills_corpus is not None else []),
            *([self.meta_corpus] if self.meta_corpus is not None else []),
        ):
            specs.append(corpus.corpus_spec)
            specs.extend(corpus.namespace_specs)
        refs: set[SpecRef] = set()
        for spec in specs:
            for file in spec.files:
                if file.value.name.endswith(DOCUMENT_SUFFIX) and file.parent == SPECS_DIR:
                    refs.add(SpecRef(file))
        refs.update(self.listed_specifications)
        return tuple(sorted(refs))

    def find_specification_base(self, ref: SpecRef) -> SpecRef | None:
        """The spec this one extends: the narrowest whose name continues into this one's, or `None`.

        Args:
            ref: The spec whose base is wanted.
        """
        by_name = {spec.name: spec for spec in self.specifications()}
        base = find_narrowest_ancestor(ref.name, by_name)
        return None if base is None else by_name[base]

    def name_base(
        self, corpus: CorpusName | None, name: AspectFilename | AspectName | SpecName | None
    ) -> AspectFilename | SpecName | None:
        """Find the typed ancestor of a descriptor name in its declared corpus hierarchy."""
        if corpus is None or name is None:
            return None
        if isinstance(name, AspectFilename):
            found = self.find_corpus(corpus)
            base = found.document_base(name) if found is not None else None
            return None if base is None else base.filename
        if isinstance(name, (CorpusSpecName, NamespaceSpecName)):
            ref = next((spec for spec in self.specifications() if spec.name == str(name)), None)
            if ref is None:
                return None
            base = self.find_specification_base(ref)
            return None if base is None else parse_spec_name(base.name)
        return None

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

    def skill_governance(self, ref: SkillRef) -> Governance | None:
        """The specs governing a skill's listed name, or None when no skills corpus is declared."""
        corpus = self.skills_corpus
        if corpus is None:
            return None
        return corpus.governance(ref.entry.value)

    def meta_governance(self, ref: SpecRef) -> Governance | None:
        """The meta specs governing a spec item, or None when no `meta` corpus is declared."""
        if self.meta_corpus is None:
            return None
        return self.meta_corpus.governance(ref.name)

    def builtin_layers_for(self, item_type: ItemType) -> tuple[BuiltinSpecLayer, ...]:
        """Builtin layers applicable to an item kind, in registration order."""
        return tuple(layer for layer in self.builtin_layers if item_type in layer.applies_to)

    @property
    def agent_skills_floor_enabled(self) -> bool:
        """Whether the builtin Agent Skills layer is enabled."""
        return agent_skills_floor_enabled(self.builtin_layers)

    def _builtin_frontmatter_refs(self, item_type: ItemType) -> tuple[SchemaRef, ...]:
        """Frontmatter schemas contributed by builtin layers, in registration order."""
        return tuple(
            reference
            for layer in self.builtin_layers_for(item_type)
            for reference in layer.schema_refs
            if reference.kind is SchemaKind.FRONTMATTER
        )

    def builtin_structure_sources_for(self, item_type: ItemType) -> tuple[tuple[BuiltinOrigin, BuiltinLineBudget], ...]:
        """Line budgets supplied by applicable builtin layers, in registration order."""
        sources: list[tuple[BuiltinOrigin, BuiltinLineBudget]] = []
        for layer in self.builtin_layers_for(item_type):
            if layer.lines is not None:
                sources.append((layer.origin, BuiltinLineBudget(layer.lines)))
        return tuple(sources)

    def find_item(self, ref: ItemRef) -> ResolvedItem | None:
        """The descriptor of the document or skill the model lists at this reference, or None.

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

    def describe_item(self, ref: DocumentRef | SkillRef | SpecRef) -> ItemDescriptor:
        """Resolve the shared location and origin metadata for a document or skill.

        The existing references remain accepted by repositories and database queries. This descriptor is the
        common model contract for callers that need to handle either kind without classifying its origin.
        """
        return self.resolve_item(ref).descriptor

    def resolve_resource(self, location: SkillResourceLocation) -> ResolvedItem:
        """Resolve a skill resource ref's descriptor without corpus governance.

        The model lists no resource: only the skill's resource listing locates one, so the caller hands the location
        over. The resource keeps its own ref and read location. Its containing skill is provenance, not a governance
        identity. No skills-corpus schema or structure spec applies; only its Markdown checks are active.

        Args:
            location: The matching resource location from its skill's listing.
        """
        ref = location.ref
        skill = ref.skill
        return self._describe(
            ref=ItemRef(ref.path),
            read_location=location.resolves_to,
            link_base=SkillRoot(skill.directory),
            origin=SkillResourceOrigin(skill_entry=str(skill.entry)),
            name=_skill_aspect_filename(str(skill.entry)),
            listed_name=str(skill.entry),
            corpus=None,
            governance=None,
            frontmatter_schema_refs=(),
        )

    @staticmethod
    def _governed_parts(
        governance: Governance | None,
        schema_refs: tuple[SchemaRef, ...] = (),
        builtin_layers: tuple[BuiltinSpecLayer, ...] = (),
    ) -> frozenset[SpecPart]:
        """The spec parts named by loaded layers and the item's applicable schema inputs."""
        parts: set[SpecPart] = set()
        if any(reference.kind is SchemaKind.FRONTMATTER for reference in schema_refs):
            parts.add(SpecPart.FRONTMATTER)
        for layer in builtin_layers:
            if layer.lines is not None:
                parts.add(SpecPart.BUDGET)
        if governance is not None and governance.corpus_structure() is not None:
            parts.add(SpecPart.STRUCTURE)
        if governance is not None and governance.outline_specs():
            parts.add(SpecPart.OUTLINE)
        if governance is not None and any(
            spec.tokens is not None or spec.lines is not None for spec in governance.structure_specs()
        ):
            parts.add(SpecPart.BUDGET)
        return frozenset(parts)

    @classmethod
    def _describe(
        cls,
        *,
        ref: ItemRef,
        read_location: ResolvedPath,
        link_base: DocumentDirectory | SkillRoot,
        origin: DocumentOrigin | SkillEntrypointOrigin | SkillResourceOrigin | SpecOrigin,
        name: AspectFilename | AspectName | SpecName | None,
        listed_name: str,
        corpus: CorpusName | None,
        governance: Governance | None,
        frontmatter_schema_refs: tuple[SchemaRef, ...],
        builtin_layers: tuple[BuiltinSpecLayer, ...] = (),
    ) -> ResolvedItem:
        """Build every governed-item descriptor from its listing and governing inputs."""
        descriptor = ItemDescriptor(
            ref=ref,
            read_location=read_location,
            link_base=link_base,
            origin=origin,
            name=name,
            listed_name=listed_name,
            corpus=corpus,
            frontmatter_schema_refs=frontmatter_schema_refs,
            governed_parts=cls._governed_parts(governance, frontmatter_schema_refs, builtin_layers),
        )
        return ResolvedItem(descriptor, governance)

    def resolve_item(self, ref: DocumentRef | ItemRef | SkillRef | SpecRef) -> ResolvedItem:
        """Resolve an item's descriptor together with the specs governing it, finding the governance once.

        A corpus document is governed by the specs of its corpus and matching namespaces. Skill entrypoints are governed
        by the reserved `skills` corpus and matching namespaces; specs are governed by the reserved `meta` corpus.
        Resources remain outside corpus governance.

        Args:
            ref: Document, skill or spec to resolve, whether or not the model lists a document's corpus, or a
                common ref naming a document.

        Raises:
            UnlistedItemError: If a common ref does not name a valid document path.
        """
        match ref:
            case ItemRef():
                document = find_document_at(ref)
                if document is None:
                    raise UnlistedItemError(ref)
                return self._resolve_document_item(ref, document)
            case DocumentRef():
                return self._resolve_document_item(ItemRef(ref.path), ref)
            case SkillRef():
                location = self.skill_locations[ref]
                link_target = location.resolves_to if location.resolves_to != ref.directory else None
                governance = self.skill_governance(ref)
                builtin_layers = self.builtin_layers_for(ItemType.SKILL_ENTRYPOINT)
                schema_refs = self._builtin_frontmatter_refs(ItemType.SKILL_ENTRYPOINT) + (
                    governance.applicable_frontmatter_schema_refs() if governance is not None else ()
                )
                return self._describe(
                    ref=ItemRef(ref.path),
                    read_location=location.file_resolves_to,
                    link_base=SkillRoot(ref.directory),
                    origin=SkillEntrypointOrigin(link_target=link_target),
                    name=_skill_aspect_filename(str(ref.entry)),
                    listed_name=str(ref.entry),
                    corpus=CorpusName.parse(SKILLS_CORPUS_NAME) if governance is not None else None,
                    governance=governance,
                    frontmatter_schema_refs=schema_refs,
                    builtin_layers=builtin_layers,
                )
            case SpecRef():
                governance = self.meta_governance(ref)
                builtin_layers = self.builtin_layers_for(ItemType.SPEC)
                schema_refs = self._builtin_frontmatter_refs(ItemType.SPEC) + (
                    governance.applicable_frontmatter_schema_refs() if governance is not None else ()
                )
                return self._describe(
                    ref=ItemRef(ref.path),
                    read_location=ResolvedPath(ref.path),
                    link_base=DocumentDirectory(SPECS_DIR),
                    origin=SpecOrigin(ref.corpus),
                    name=parse_spec_name(ref.name),
                    listed_name=ref.name,
                    corpus=CorpusName.parse(META_CORPUS_NAME),
                    governance=governance,
                    frontmatter_schema_refs=schema_refs,
                    builtin_layers=builtin_layers,
                )
            case _:
                assert_never(ref)

    def _resolve_document_item(self, item: ItemRef, document: DocumentRef) -> ResolvedItem:
        """Resolve a document using its common identity and validated corpus and filename.

        Args:
            item: The common identity to preserve on the resolved descriptor.
            document: The validated corpus and filename the item path names.
        """
        governance = self.find_governance(document)
        builtin_layers = self.builtin_layers_for(ItemType.DOCUMENT)
        schema_refs = self._builtin_frontmatter_refs(ItemType.DOCUMENT) + (
            governance.applicable_frontmatter_schema_refs() if governance is not None else ()
        )
        return self._describe(
            ref=item,
            read_location=ResolvedPath(document.path),
            link_base=DocumentDirectory(RootRelativePath(document.path.value.parent)),
            origin=DocumentOrigin(),
            name=document.filename,
            listed_name=str(document.filename),
            corpus=document.corpus,
            governance=governance,
            frontmatter_schema_refs=schema_refs,
            builtin_layers=builtin_layers,
        )
