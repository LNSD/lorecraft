"""One frozen state of a workspace: its snapshot and memoized derived values.

`Database.from_snapshot` loads the model for one immutable snapshot. Input queries such as `model()`,
`item_text(ref)`, `skill_resources(skill)` and `item_link_targets(source)` read the snapshot and document their
carry-over rules. Declared queries run through `query(query, ref)`, which memoizes each answer and its typed reads;
item facts such as parsing, frontmatter, counts and structure specifications are declared in `lorecraft.project.query`
and derive from raw primitive state.

The item family shares `MarkdownItemRef` across documents, skill entries and resources. Resource references are
registered from their skill's listing; documents not listed by the model can still be resolved from their corpus and
filename. A new database is created for each snapshot, and no derived value is cached across databases here.

The reserved, unimplemented `advance(snapshot) -> Database` would diff two snapshots and carry cached values only
when their inputs remain valid. The model is kept unless its structure changes; item text requires an equal resolved
descriptor and unchanged bytes; skill resources require the same listing and resolved location; link targets require
the same parse, resolved paths and scope state. The scope index is kept only when the recorded scopes, links and
climbed directories match. Each input query owns its carry-over rule, and declared queries inherit the validity of
their recorded reads. These rules rely on each query reading only the data it owns: text reads one file, governance
reads the model, schema findings read their item's frontmatter and governance, and link targets read one item's links
and the paths they reach. Keep those boundaries; a value drawn from several documents needs its own query and
carry-over rule. A skill's linked `SKILL.md` also needs an equal resolved location, because the ref names the link
while the bytes belong to its target.
"""

import logging
from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import wraps
from types import FunctionType
from typing import Concatenate, Protocol, Self, assert_never, cast, overload

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusDirectoryRef, CorpusName, ReservedCorpusDirectory
from lorecraft.project.document import SpecRef
from lorecraft.project.item import (
    DocumentOrigin,
    ItemOrigin,
    ItemReadError,
    MarkdownItemRef,
    SpecificationOrigin,
    UnlistedItemError,
)
from lorecraft.project.layout import DOCS_DIR, SPECS_DIR, reject_linked_layout
from lorecraft.project.link_target import (
    LinkBase,
    LinkTargetEntry,
    link_targets_of,
)
from lorecraft.project.query import (
    CorpusDirectoryQuery,
    Query,
    SchemaQuery,
    SubjectRef,
    SymlinkQuery,
    item_parse,
)
from lorecraft.project.schemas import (
    SpecName,
    parse_spec_name,
)
from lorecraft.project.skill import (
    OutsideSymlink,
    SkillLocation,
    SkillRef,
    SkillResourceListing,
    SkillResourceLocation,
    SkillResourcesListError,
    SkillResourcesSymlinkResolveError,
    SymlinkRef,
)
from lorecraft.project.skill import Repository as SkillRepository
from lorecraft.project.syntax import (
    NormalisedLinkPath,
    split_lines,
)
from lorecraft.project.workspace import Governance, ResolvedItem, WorkspaceModel, load_model, unreported_refusals
from lorecraft.schemas import SchemaInput, SchemaReference, SchemaReferenceError
from lorecraft.vfs import (
    FILE_READ_FAILURES,
    RefusedRecord,
    RootExit,
    ScopeIndex,
    Snapshot,
    TextDecodeError,
    UnrecordedFileError,
    VirtualFileSystem,
)

from .text import ItemText, Undecodable


def primitive[S: '_PrimitiveReadRecorder', **P, T](
    method: FunctionType,
) -> Callable[Concatenate[S, P], T]:
    """Record a primitive read when its method is called, preserving its exact signature."""

    @wraps(method)
    def wrapper(self: S, *args: P.args, **kwargs: P.kwargs) -> T:
        self._record(self._read_key(method.__name__))
        return method(self, *args, **kwargs)

    return wrapper


@dataclass(frozen=True)
class Read:
    """One primitive or declared query read from a typed subject.

    Query sources use a broad callable type because `ty` cannot correlate `_Reads`' generic same-subject callback with
    the subject-specific arms of `SubjectQuery`; public `Database.query` overloads retain that precision.
    """

    source: str | Callable[..., object]
    subject: SubjectRef


class _PrimitiveReadRecorder(Protocol):
    """The subject-qualified recording operations a primitive wrapper calls."""

    def _read_key(self, method_name: str) -> Read: ...

    def _record(self, *keys: Read) -> None: ...


class _HasRecordedReads(Protocol):
    """The private recording operation a fresh query adapter exposes to the memo cache."""

    def _recorded_reads(self) -> frozenset[Read]: ...


class _Reads[R: SubjectRef, P: _HasRecordedReads](metaclass=ABCMeta):
    """One subject's raw primitives, private read recorder, and memoized query composition."""

    __slots__ = ('__reads', '_database', '_ref')

    def __init__(self, database: 'Database', ref: R) -> None:
        self.__reads: set[Read] = set()
        self._database = database
        self._ref = ref

    def _read_key(self, method_name: str) -> Read:
        """Pair a primitive method name with this adapter's subject."""
        return Read(method_name, self._ref)

    def _record(self, *keys: Read) -> None:
        """Record primitive or nested-query keys without exposing mutable storage."""
        self.__reads.update(keys)

    def _recorded_reads(self) -> frozenset[Read]:
        """Return a frozen copy for the database cache."""
        return frozenset(self.__reads)

    @abstractmethod
    def _fresh(self, ref: R) -> P:
        """Build fresh primitives for this subject when its query is first evaluated."""
        ...

    def _compose[Q: _HasRecordedReads, T](self, key: Read, target: Q, query: Callable[[Q], T]) -> T:
        """Memoize a nested query and include its key and dependencies in this subject's reads."""
        self._record(key)
        answer = self._database._memo_query(key, lambda: query(target), target._recorded_reads)
        self._record(*self._database._query_reads(key))
        return answer

    def query[T](self, query: Callable[[P], T]) -> T:
        """Read another query over this subject and include its dependencies."""
        key = Read(query, self._ref)
        target = self._fresh(self._ref)
        return self._compose(key, target, query)

    def query_at[T](self, ref: MarkdownItemRef, query: Query[T]) -> T:
        """Read an item query and include its dependencies."""
        key = Read(query, ref)
        target = _ItemPrimitives(self._database, ref)
        return self._compose(key, target, query)

    def query_schema[T](self, ref: SchemaReference, query: SchemaQuery[T]) -> T:
        """Read a schema query and include its dependencies."""
        key = Read(query, ref)
        target = _ReadSchemaPrimitives(self._database, ref)
        return self._compose(key, target, query)


class _ReadSchemaPrimitives(_Reads[SchemaReference, '_ReadSchemaPrimitives']):
    """The immutable input of one schema subject, recorded under its typed reference."""

    __slots__ = ()

    def _fresh(self, ref: SchemaReference) -> '_ReadSchemaPrimitives':
        return _ReadSchemaPrimitives(self._database, ref)

    def schema_input(self) -> SchemaInput:
        """Resolve the database-owned schema input, recorded by hand rather than as a primitive method."""
        self._record(Read('schema_input', self._ref))
        return self._database._schema_input(self._ref)


class _ReadSymlinkPrimitives(_Reads[SymlinkRef, '_ReadSymlinkPrimitives']):
    """The primitive reads of one symlink subject, recorded with typed keys."""

    __slots__ = ()

    def _fresh(self, ref: SymlinkRef) -> '_ReadSymlinkPrimitives':
        return _ReadSymlinkPrimitives(self._database, ref)

    @primitive
    def leaves_at(self) -> RootExit:
        """The point where this symlink's chain leaves the repository."""
        return self._database._outside_symlink(self._ref).leaves_at


class _ReadCorpusDirectoryPrimitives(_Reads[CorpusDirectoryRef, '_ReadCorpusDirectoryPrimitives']):
    """The primitive reads of one reserved-corpus directory subject, recorded with typed keys."""

    __slots__ = ()

    def _fresh(self, ref: CorpusDirectoryRef) -> '_ReadCorpusDirectoryPrimitives':
        return _ReadCorpusDirectoryPrimitives(self._database, ref)

    @primitive
    def reserved_corpus(self) -> CorpusName:
        """The reserved corpus whose name this directory takes."""
        return self._database._reserved_corpus_directory(self._ref).corpus


logger = logging.getLogger(__name__)


def _witness_text(
    source: ItemText | Undecodable,
) -> str | None:
    """The text a decode query returned, or None when its file is not UTF-8.

    Args:
        source: The answer of a decode query.
    """
    if isinstance(source, Undecodable):
        return None
    return source.text


class _ItemPrimitives(_Reads[MarkdownItemRef, '_ItemPrimitives']):
    """The primitives of one item as the database answers them, noting each one a query reads.

    A primitive that walks the model or other files, such as `linked_documents` and `item_base`,
    is not cached here: a query over the item is memoized by the database for the function and the ref, so each of
    them is computed once per query, and a cache beside it would only hold the same answer twice.

    """

    __slots__ = ()

    def _fresh(self, ref: MarkdownItemRef) -> '_ItemPrimitives':
        return _ItemPrimitives(self._database, ref)

    @primitive
    def item_origin(self) -> ItemOrigin:
        """The model-resolved origin facts of the item."""
        return self._database._item(self._ref).descriptor.origin

    @primitive
    def item_text(self) -> ItemText | None:
        """The decoded witness of this subject, or none when its bytes are not UTF-8."""
        source = self._database.item_text(self._ref)
        return source if isinstance(source, ItemText) else None

    @primitive
    def item_governance(self) -> Governance | None:
        """The model's governance of the item."""
        return self._database.item_governance(self._ref)

    @primitive
    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """What the snapshot holds at each relative link's target; none for an item that is not UTF-8."""
        self._record(self._read_key('item_text'))
        source = self._database.item_text(self._ref)
        return self._database.item_link_targets(source) if isinstance(source, ItemText) else FrozenMapping({})

    @primitive
    def link_base(self) -> LinkBase | None:
        """Where the item's relative links are read from; `None` for an item that is not UTF-8."""
        source = self._database.item_text(self._ref)
        return source.descriptor.link_base if isinstance(source, ItemText) else None

    @primitive
    def item_base(self) -> AspectFilename | SpecName | None:
        """The typed name of the document or specification the item extends, from the names the model lists.

        A document's base is looked for among the documents of its corpus, a specification's among the specifications;
        `None` for any other item or one that is not UTF-8. A skill entry extends nothing: its name is its directory's,
        which no hyphenated prefix continues.
        """
        source = self._database.item_text(self._ref)
        origin = source.descriptor.origin if isinstance(source, ItemText) else None
        # Keep this dispatch: documents and specifications inherit within separate model hierarchies; skills do not.
        match origin:
            case DocumentOrigin():
                corpus = self._database.model().find_corpus(CorpusName.parse(origin.corpus))
                if corpus is None:
                    return None
                base = corpus.document_base(AspectFilename.parse(origin.expected_name))
                return None if base is None else base.filename
            case SpecificationOrigin():
                base_spec = self._database.model().find_specification_base(SpecRef(self._ref.path))
                return None if base_spec is None else parse_spec_name(base_spec.name)
            case _:
                return None


class Database:
    """What checks read from one snapshot: its model and values computed on first use for the database's lifetime.

    Input queries read the snapshot: `model()`, `skill_resources(skill)`, `item_text(ref)` and
    `item_link_targets(source)`. `model()` loads workspace structure. `skill_resources` lists a skill's resources;
    `item_text` decodes an item's bytes; `item_link_targets` resolves its relative links against the snapshot and
    scope. Their carry-over rules are stated by their methods.

    Declared queries in `lorecraft.project.query` derive item facts from raw primitive state. Other declared queries,
    including `skill_fields_query`, `frontmatter_owner_query` and `schema_problems_query`, run through `query(query,
    ref)`, which memoizes each answer and its reads. Schema queries use the same cache keyed by `(query,
    SchemaReference)` and read immutable inputs from the model.

    The item family is keyed by `MarkdownItemRef`. A resource's
    reference is registered from its listing by `resource_item(location)`. A document outside the model's listing is
    still resolved from its corpus and filename. `from_snapshot(snapshot)` starts a fresh database; it carries no
    cached values from another revision. `resource_item(location)` registers a resource under the ref in its listing.
    The snapshot questions are `source_lines(path)`, `refusals()` and `unreported_docs_refusals()`: the first two are
    answered on each call; the last is cached for this database's lifetime and recomputed from the next revision's
    refusals and model failures. The declared query `query(query, ref)` memoizes its answer and read set;
    `query_reads(query, ref)` holds typed reads and is empty before that query runs.
    """

    def __init__(self, fs: VirtualFileSystem, model: WorkspaceModel) -> None:
        """Index the view's snapshot for reading; performs no I/O and computes nothing yet.

        Only `from_snapshot` calls this; `docs/arch/adr-015-database.md` states why. A caller that builds a database
        from a model loaded through another snapshot's view answers for the mismatch.

        Args:
            fs: The view of the snapshot every query reads; the snapshot is kept for the database's lifetime and
                never changed.
            model: The workspace model loaded through `fs`; kept for the database's lifetime.
        """
        self._snapshot = fs.snapshot
        self._fs = fs
        self._skills = SkillRepository(self._fs)
        self._model = model
        # `None` until the first link-target query, so the index is built only for a run that asks.
        self._scope_index: ScopeIndex | None = None
        self._unreported_docs_refusals: FrozenMapping[RootRelativePath, RefusedRecord] | None = None
        # The unified family's caches, keyed by the common reference: the one implementation of every document and
        # skill entry or resource query.
        self._items: dict[MarkdownItemRef, ResolvedItem] = {}
        self._item_texts: dict[MarkdownItemRef, ItemText | Undecodable] = {}
        self._item_link_targets: dict[MarkdownItemRef, Mapping[NormalisedLinkPath, LinkTargetEntry]] = {}
        # Declared queries: the answer by the function and the item, with the primitive and cross-item query keys
        # it read.
        self._queries: dict[Read, tuple[object, frozenset[Read]]] = {}
        # Each skill's resource listing, found on the first call; a resource is registered from it with `resource_item`.
        self._skill_resources: dict[SkillRef, SkillResourceListing] = {}

    @classmethod
    def from_snapshot(cls, snapshot: Snapshot, *, builtin_skills_schema: bool = True) -> Self:
        """Build the database of one snapshot: build its view, refuse a linked layout and load its model.

        The one way to get a database. The model is the one structure value loaded here; every other query is still
        computed on first use.

        Behind a linked `docs/` or `docs/__meta__/` the snapshot holds no specification, so the model would have
        no corpus, and a run over its documents would report success over nothing; the layout is refused instead.

        A unit of the declaration that cannot be read or used does not stop the build: the model records it, in
        `load_failures` and in the layer it stands in.

        Carry-over: none. Each call creates a fresh database for the supplied snapshot; cached values belong to
        that database and are never transferred from another revision.

        Args:
            snapshot: The frozen state every query reads; kept for the database's lifetime and never changed.
            builtin_skills_schema: Whether to pre-register the Agent Skills floor schema.

        Raises:
            LinkedLayoutError: If `docs/` is a symlink, or else if `docs/__meta__/` is one.
        """
        fs = VirtualFileSystem(snapshot)
        reject_linked_layout(fs)
        return cls(fs, load_model(fs, builtin_skills_schema=builtin_skills_schema))

    # Input query: the model is loaded once from the snapshot.

    def model(self) -> WorkspaceModel:
        """The workspace model the snapshot declares, loaded when the database was opened. Raises nothing.

        Carry-over: kept for the next revision unless the model's structural inputs changed:

        - An entry added or deleted under `docs/`, or a changed specification.
        - An entry added or deleted in a skills directory, in a skill's directory, or at or on the way to the
          resolved path a skill's linked `SKILL.md` leads to.
        - A link that changed its target on the way to a skill or its `SKILL.md`, or on the chain of a skills
          directory an agent declares, an entry of one, or such an entry's `SKILL.md`, a chain leaving the
          repository included; and a directory added or deleted that a `..` on such a chain climbs out of.

        An entry added or deleted anywhere else inside a skill does not invalidate the model: it lists nothing below
        a skill's directory, and reads nothing there but the way to its `SKILL.md`.
        """
        return self._model

    # Snapshot question: an excerpt uses cached input text for items and reads specification text from the view.

    def source_lines(self, path: RootRelativePath) -> tuple[str, ...] | None:
        """The lines of one file under the root, for a diagnostic to excerpt, numbered as the rules number them.

        The lines are those of `split_lines` over the text the file was read as:

        - A document, a skill's `SKILL.md` or a resource: the text its decode query returned, so the excerpt shows
          what the rules numbered and the file is decoded once. The decode query caches it.
        - A specification file: its bytes decoded as UTF-8, as the model reads a structure file; no decode
          query exists for it.

        Any other path has no excerpt. Not cached: an excerpt asks each file once.

        Args:
            path: The root-relative file, as a diagnostic names it: a document's path, a skill's
                `<directory>/SKILL.md`, a resource's `path` or a file directly in `docs/__meta__/`.

        Returns:
            The lines, or None when the path is none of those, the file is missing from the snapshot, or it is not
            UTF-8, so there is nothing to excerpt; a file that does not decode is a diagnostic of its own, reported
            by its decode query.
        """
        try:
            text = self._source_text(path)
        except (
            ItemReadError,
            SkillResourcesListError,
            SkillResourcesSymlinkResolveError,
        ):
            # The failure is the read query's own finding; the excerpt only goes without, so it is logged, not raised.
            logger.debug('excerpt skipped', exc_info=True, extra={'fields': {'path': str(path)}})
            return None
        if text is None:
            return None
        return split_lines(text)

    def _source_text(self, path: RootRelativePath) -> str | None:
        """The text an excerpt of `path` is cut from, or None when the path has none to give.

        Args:
            path: The root-relative file, as `source_lines` is asked for it.

        Raises:
            ItemReadError: If the snapshot holds no regular file at the document's, the skill's `SKILL.md` or the
                resource's resolved file.
            SkillResourcesListError: If a directory the walk over the skill's resources enters cannot be listed.
            SkillResourcesSymlinkResolveError: If a symlink the walk over the skill's resources meets cannot be
                resolved.
        """
        document = self._model.find_document(path)
        if document is not None:
            return _witness_text(self.item_text(MarkdownItemRef(document.path)))

        for location in self._model.skill_locations.values():
            if path == location.ref.path:
                return _witness_text(self.item_text(MarkdownItemRef(location.ref.path)))
            if path.is_relative_to(location.ref.directory):
                for resource in self.skill_resources(location).resources:
                    if path == resource.ref.path:
                        return _witness_text(self.item_text(self.resource_item(resource)))

        if path.parent == SPECS_DIR:
            try:
                return self._fs.read_text(path)
            except (TextDecodeError, *FILE_READ_FAILURES, UnrecordedFileError):
                return None
        return None

    # Input query: each skill's resource listing is read once from the snapshot.

    def skill_resources(self, skill: SkillLocation) -> SkillResourceListing:
        """The resources of one skill and its symlinks leading outside the repository, listed on the first call.

        Each resource is named where an agent reaches it, under the skill's directory, and located at the resolved file
        that path leads to, sorted by ref; `Repository.list_skill_resources` states which files are resources and
        which symlinks the walk follows. Each symlink whose chain leaves the repository is named the same way, with
        the link it leaves through, sorted by path. The walk starts at the location given, the one the model hands
        out for the skill.

        Carry-over: the listing of one skill is kept for the next revision unless one of these changed:

        - An entry was added, deleted or changed kind in a directory the walk entered, or at the path a symlink it
          met leads to, or on the way there.
        - A symlink on any of those ways changed its target, one whose chain leaves the repository included: the
          listing records the link such a chain leaves through, and its target.
        - The next model locates the skill's directory at another resolved directory, its `resolves_to`. Where its
          `SKILL.md` leads plays no part, so a retargeted `SKILL.md` symlink alone leaves the listing valid.

        A change to any file's bytes leaves it valid, and so does any change the walk does not reach, whichever
        skill it is in.

        A listing that fails is not cached, so each call raises the same error again.

        Args:
            skill: Where the skill's files live, as this database's model locates it; its ref is the cache key, so one
                skill is walked once.

        Raises:
            SkillResourcesListError: If a directory the walk enters cannot be listed.
            SkillResourcesSymlinkResolveError: If a symlink the walk meets cannot be resolved.
        """
        resources = self._skill_resources.get(skill.ref)
        if resources is None:
            resources = self._skills.list_skill_resources(skill)
            self._skill_resources[skill.ref] = resources
        return resources

    def _built_scope_index(self) -> ScopeIndex:
        """The scope index the link-target queries answer from, built on the first call.

        Carry-over: kept only when the two snapshots' scopes, links and climbed directories are equal as recorded;
        the change set does not contain scope. A scope change invalidates no other input by itself: additions and
        removals become entries in the model or skill-resource change sets.
        """
        if self._scope_index is None:
            self._scope_index = ScopeIndex(self._snapshot)
        return self._scope_index

    # Item resolution and registration use the common reference; listed resources and unlisted documents enter here.

    def _item(self, ref: MarkdownItemRef) -> ResolvedItem:
        """The descriptor and governance for a listed item, resource or answerable document, found once."""
        resolved = self._items.get(ref)
        if resolved is None:
            resolved = self._model.find_item(ref)
            if resolved is None:
                # A document's path can be answerable even when the model does not list it. Resources are registered
                # here from their skill's listing before any item query asks for them.
                resolved = self._model.resolve_item(ref)
            self._items[ref] = resolved
        return resolved

    # Input query: decode one resolved item's bytes into the witness all content queries read.

    def item_text(self, ref: MarkdownItemRef) -> ItemText | Undecodable:
        """One item's bytes decoded as UTF-8, read from the descriptor's read location on the first call for its ref.

        The one place an item's bytes become text for a rule: every other query about it takes the witness this
        returns. A file that is not UTF-8 is cached as `Undecodable`, so it is decoded once.

        Carry-over: kept for the next revision only when the next model resolves an equal descriptor, and so the
        same read location, and that file's bytes did not change.

        A file that cannot be read is not cached, so each call raises the same error again.

        Args:
            ref: The item to decode; the cache key.

        Raises:
            UnlistedItemError: If the reference is not a listed item, registered resource or answerable document path.
            ItemReadError: If the snapshot holds no regular file at the read location.
        """
        return self._decode(ref)

    def _decode(self, ref: MarkdownItemRef) -> ItemText | Undecodable:
        """Decode an item the database already resolved, listed or not, once."""
        decoded = self._item_texts.get(ref)
        if decoded is None:
            descriptor = self._item(ref).descriptor
            try:
                decoded = ItemText(descriptor, self._fs.read_text(descriptor.read_location))
            except TextDecodeError as exc:
                decoded = Undecodable(ref, exc.failure)
            except (*FILE_READ_FAILURES, UnrecordedFileError) as exc:
                raise ItemReadError(ref, source=exc) from exc
            self._item_texts[ref] = decoded
        return decoded

    def resource_item(self, location: SkillResourceLocation) -> MarkdownItemRef:
        """The common reference of a skill's resource, resolved from the location its skill's listing gives.

        The model lists no resource, so the resource is kept apart from the listed items, as an unlisted document is:
        the `item_*` queries answer for its reference, and the listed items still refuse it. Raises nothing.

        Carry-over: this registration is database-local. In the next revision, the resource's item queries can carry
        over only when its listing resolves the ref to the same file and the relevant query inputs are unchanged.

        Args:
            location: The resource, as `skill_resources` locates it; its resolved file is where the text is read.
        """
        item = MarkdownItemRef(location.ref.path)
        self._register(item, lambda: self._model.resolve_resource(location))
        return item

    def _register(self, item: MarkdownItemRef, resolve: Callable[[], ResolvedItem]) -> None:
        """Keep a resource's resolved item once, before its common-ref queries ask for it.

        Args:
            item: The item to keep.
            resolve: Resolves the item; called only for an item not kept yet.
        """
        if item not in self._items:
            self._items[item] = resolve()

    # Input query: resolve the paths named by one item's links against the snapshot and scope.

    def item_link_targets(self, source: ItemText) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """Where each relative link of one item leads and what the snapshot holds there, found on the first call.

        Each link is read from the descriptor's link base, which carries its own climb bound, as `link_targets_of`
        states. Raises nothing.

        Carry-over: kept for the next revision only when the declared parse query for this item is kept and every path
        looked up, an absent target included, still resolves to the same place and is in the same scope state.

        Args:
            source: The item's text; its ref is the cache key.
        """
        targets = self._item_link_targets.get(source.ref)
        if targets is None:
            links = self.query(item_parse, source.ref).links
            targets = link_targets_of(links, source.descriptor.link_base, self._fs, self._built_scope_index())
            self._item_link_targets[source.ref] = targets
        return targets

    def item_governance(self, ref: MarkdownItemRef) -> Governance | None:
        """The specifications that govern an item, resolved by the model on the first call for its ref.

        A layer whose structure file failed to load is held as the failed structure the model recorded, in the order
        the layers apply. Skill entries use the reserved `skills` corpus; resources have no corpus governance.
        `None` when no specification governs the item.

        Args:
            ref: The item to look up; the cache key.

        Raises:
            UnlistedItemError: If the reference is not a listed item, registered resource or answerable document path.
        """
        return self._item(ref).governance

    @overload
    def query[T](self, query: Query[T], ref: MarkdownItemRef) -> T: ...  # noqa: D102 — implementation documents the overload

    @overload
    def query[T](self, query: SymlinkQuery[T], ref: SymlinkRef) -> T: ...  # noqa: D102 — implementation documents the overload

    @overload
    def query[T](self, query: CorpusDirectoryQuery[T], ref: CorpusDirectoryRef) -> T: ...  # noqa: D102 — implementation documents the overload

    @overload
    def query[T](self, query: SchemaQuery[T], ref: SchemaReference) -> T: ...  # noqa: D102 — implementation documents the overload

    def query[T](
        self,
        query: Callable[..., T],
        ref: MarkdownItemRef | SymlinkRef | CorpusDirectoryRef | SchemaReference,
    ) -> T:
        """The memoized answer of a declared query over a typed subject.

        A query over a Markdown item carries over when each primitive it read does. A query over a symlink carries
        over when the model still lists that outside symlink at the same path. A query over a reserved-corpus
        directory carries over when the model still lists that directory at the same path. A schema query is keyed by
        its typed reference and reads the immutable input retained by the model.

        Args:
            query: The declared query to run.
            ref: The typed subject the query reads.

        Raises:
            UnlistedItemError: If the subject ref is not listed by the model or a skill resource listing.
            SchemaReferenceError: If the schema subject is not present in the loaded model.
        """
        match ref:
            case MarkdownItemRef():
                primitives = _ItemPrimitives(self, ref)
            case SymlinkRef():
                primitives = _ReadSymlinkPrimitives(self, ref)
            case CorpusDirectoryRef():
                primitives = _ReadCorpusDirectoryPrimitives(self, ref)
            case SchemaReference():
                primitives = _ReadSchemaPrimitives(self, ref)
            case _:
                assert_never(ref)
        key = Read(query, ref)
        return self._memo_query(key, lambda: query(primitives), primitives._recorded_reads)

    def _memo_query[T](
        self,
        key: Read,
        answer: Callable[[], T],
        reads: Callable[[], frozenset[Read]],
    ) -> T:
        """Memoize one declared query and its recorded reads."""
        if key not in self._queries:
            result = answer()
            self._queries[key] = (result, reads())
        # SAFETY: _memo_query is the only writer and stores answer() under its query's key.
        return cast('T', self._queries[key][0])

    def query_reads(
        self,
        query: Query[object] | SymlinkQuery[object] | CorpusDirectoryQuery[object] | SchemaQuery[object],
        ref: MarkdownItemRef | SymlinkRef | CorpusDirectoryRef | SchemaReference,
    ) -> frozenset[Read]:
        """The typed read keys recorded for a query; public so nested queries avoid private-cache access.

        Args:
            query: The declared query whose reads are requested.
            ref: The typed subject the query was run against.
        """
        return self._query_reads(Read(query, ref))

    def _query_reads(self, key: Read) -> frozenset[Read]:
        """Find dependencies for one read key, with no overload correlation to recover."""
        return self._queries[key][1] if key in self._queries else frozenset()

    def _schema_input(self, reference: SchemaReference) -> SchemaInput:
        """Resolve a loaded schema input without adding a second cache."""
        schema_input = self._model.schema_inputs.get(reference)
        if schema_input is None:
            raise SchemaReferenceError(reference)
        return schema_input

    def _outside_symlink(self, ref: SymlinkRef) -> OutsideSymlink:
        """Find one symlink by its typed subject reference, including a skill resource link."""
        found = self._model.outside_symlinks.get(ref.path)
        if found is not None:
            return found
        for listing in self._skill_resources.values():
            for outside in listing.outside_symlinks:
                if outside.path == ref.path:
                    return outside
        raise UnlistedItemError(ref)

    def _reserved_corpus_directory(self, ref: CorpusDirectoryRef) -> ReservedCorpusDirectory:
        """Find one reserved-corpus directory by its typed subject reference."""
        found = next((entry for entry in self._model.overlapping_directories if entry.path == ref.path), None)
        if found is None:
            raise UnlistedItemError(ref)
        return found

    # Snapshot questions: `refusals` is read on each call; `unreported_docs_refusals` is memoized for this database.

    def refusals(self) -> dict[RootRelativePath, RefusedRecord]:
        """Every access the operating system refused the scan and the snapshot kept, keyed by path in path order."""
        return self._snapshot.refusals()

    def unreported_docs_refusals(self) -> Mapping[RootRelativePath, RefusedRecord]:
        """Snapshot refusals under `docs/` that no workspace load failure already reports.

        The result is derived from the snapshot and model, and cached for this database's lifetime. It is recomputed
        for the next revision from that revision's refusals and model failures.
        """
        if self._unreported_docs_refusals is None:
            refusals = {
                path: refusal
                for path, refusal in unreported_refusals(self.refusals(), self._model).items()
                if path.is_relative_to(DOCS_DIR)
            }
            self._unreported_docs_refusals = FrozenMapping(refusals)
        return self._unreported_docs_refusals
