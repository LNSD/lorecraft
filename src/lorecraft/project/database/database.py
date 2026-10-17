"""One frozen state of a workspace: its snapshot, and the cached data every check, and every command, reads through.

The layering follows an IDE's. The `Snapshot` plays the virtual file system: every byte a
check can see, and never changed once built. `Database.from_snapshot` builds the database from a snapshot and loads the
model; every other query sits above it, computed on first use and kept for as long as the database lives
(pattern-memoization). Queries come in two kinds, and the kind decides how a query carries over to the next revision.

Documents and skill entries share one query family keyed by the common `MarkdownItemRef`: `item_text(ref)` decodes the
file at the descriptor's read location into one `ItemText` witness or an `Undecodable` marker, and `item_frontmatter`,
`item_parse`, `item_token_count`, `item_line_count`, `item_link_targets`, `item_governance` and `item_schema_problems`
take that witness and are computed on first demand. Link targets
read the descriptor's link base, so no query tells a document from a skill entry; the analyses read
`item_governance(ref)`, never the whole model. A document the model does not list is answered for by the corpus and
filename its path names. A skill's resource is answered for by the reference `resource_item` registers from its
skill's listing.

Input queries read the snapshot. Each is the one place its part of the snapshot becomes a value for a rule, so only an
input query builds a witness or fails to read, and each states its own carry-over rule against the change set:

- `model()`: the workspace model, like the IDE's project model, loaded when the database is opened, so no query that
  reads it raises a load error. It reads the structure of the snapshot, the
  specifications, the corpus directories, the skills directories and the listing of each skill's directory, nothing
  deeper inside a skill, and no document's contents. Among that structure it records each skills directory, skill
  entry and `SKILL.md` whose symlink chain leaves the repository.
- `item_text(ref)`: one document's, skill entry's or skill resource's bytes decoded as UTF-8, like the IDE's document
  text for a file: an `ItemText` witness, or an `Undecodable` marker when the bytes are not UTF-8. It is the one place
  their bytes become text for a rule, and it reads that file's bytes and nothing else.
- `skill_resources(skill)`: one skill's resources, the Markdown files inside it other than its top-level `SKILL.md`,
  like the IDE's listing of a content root's children, and the symlinks inside it whose chain leaves the
  repository. It reads the listings and the symlink targets reached from that skill, and where the model locates
  the skill, and no file's content.
- The `ScopeIndex` behind `is_in_scope(path)`: the scope the snapshot records it was taken of, expanded once
  through the links it recorded, like the IDE's index of a project's content roots. It reads the snapshot's
  scope, links and climbed directories and nothing else, and no caller reaches it but `is_in_scope` and the
  link-target queries.
- `item_link_targets(source)`: what the snapshot holds at the target of each relative link of one item, like the IDE's
  index of a file's references resolved against the virtual file system. It hands the file's parse, where its links
  are read from, the snapshot's view and the scope index to `link_targets_of`, which reads, for each path a link names,
  the snapshot's records on the way to it, so it is an input query: it is kept only when its parse is kept and every
  path it looked up, an absent target included, still resolves to the same place and is in the same scope state.

Derived queries read the results of other queries and never the snapshot. Each hands what it read to one function
of this package that computes the value, so its arguments are its read set, and it carries over whenever every query
it read does, `item_governance(ref)` excepted, as its bullet states:

- `item_frontmatter(source)`: one item's frontmatter node, like a stub: the part of a file the IDE reads without
  building its full syntax tree. It reads the text of the witness and nothing else.
- `item_parse(source)`: one item's parse tree, like the IDE's syntax tree of a file. It reads the text of the witness
  and nothing else.
- `item_token_count(source)` and `item_line_count(source)`: what one item's whole file costs an agent that loads it,
  and how many lines it holds, counted from the raw text, frontmatter included, without a parse.
- `item_governance(ref)`: the specifications that govern one item, its corpus's first and then each namespace's that
  matches it, like the IDE's resolution of which inspection profile a file falls under. It reads `model()` and
  nothing else, and it is the one place an item's governance is computed, so the model's corpus is searched once per
  item for the revision. It is the exception to the rule above: the model is dropped by any entry added or deleted
  under `docs/`, so it is recomputed from the next model and kept when it compares equal to the one it replaces. It
  can carry over when `model()` does not, and so can every analysis that reads it.
- `item_schema_problems(source)`: what each frontmatter schema that governs one document rejects, the shared analysis
  every frontmatter inspection reads. It reads the item's frontmatter and governance and nothing else.
- `item_skill_schema_problems(source)` and `item_skill_fields(source)`: what the Agent Skills specification rejects in
  one skill entry's frontmatter and the fields of it that parse, each on its own. They read `item_frontmatter(source)`
  and nothing else: the package states the specification, so no specification in the repository plays a part.

Three questions are asked of the snapshot's records directly and their answers are never cached, since an answer for
one path is cheap:

- `find_file(path)`: where a path leads in the snapshot, like a lookup in the IDE's virtual file system. It reads the
  snapshot's records and nothing else and builds nothing worth keeping.
- `is_in_scope(path)`: whether the scan reads the directory a path sits in, like the IDE asking whether a file
  is in the project's content roots. It is configuration, not content: answered from the `ScopeIndex` cached
  above, built on the first call, with the path walked through the snapshot's recorded links to tell where it
  leads, and never from which directories the snapshot holds. The index is what costs, so it is kept; the
  answer for one path is cheap, so it is not.
- `source_lines(path)`: the lines of one file for a diagnostic to excerpt, numbered as the rules number them. It takes
  a bare path, since a diagnostic names a file by its path, and finds the decode query the path belongs to: the
  excerpt of a document, a `SKILL.md` or a resource is cut from the text that decode query returned, so it shows what
  the rules numbered and no other code path decodes those files. A specification file has no decode query, as the
  model reads it itself, so its excerpt is cut from its bytes decoded as UTF-8, as the model reads a structure
  file. It returns `None` for a path it holds no such file at, or a file that is missing or not UTF-8, and no rule
  reads it.

Every query about one file's content takes the witness its decode query returned, never a bare ref, so a fact of a
file that is not UTF-8 cannot be asked for: a reader matches the decode once and no later reader carries a branch for
it. Each still caches by the witness's ref.

Rules are pure functions of the values a subject's context reads for them through the database, like an inspection
run over one file: the runner matches each file's decode once and hands a rule the context of the part it judges. A
context asks for the cheapest query that holds what a rule reads, so a rule that needs only the frontmatter never pays
for the full parse, and every rule reading the same query shares one computation of it. Their results are not cached;
a rule runs again every time.

Nothing here records what a cached value read, so no dependency is tracked. Invalidation is written by hand instead, the
way the IDE drops per-file index entries on a file change event and resets structural caches on a project model change.
Reserved, not implemented: `advance(snapshot) -> Database`, the next state. It would `diff` the two snapshots and carry
over each cached value the change set leaves valid: the decoded text, the frontmatter, the parse, the token count and
the line count of every item whose bytes did not change, and its schema problems, outline alignment and outline
divergences too when its governance carries over, the governance of every item the next model governs by equal
specifications, the resources of every skill and the decoded text and the parse of every resource as their own
docstrings state, and the model unless one of these changes invalidates it. An entry added or deleted under `docs/`
invalidates it. So does an entry added or deleted in a skills directory, or in a skill's directory, both where the
skill's entry names it and where a link leads it. So does an entry added or deleted at the resolved path a skill's
linked `SKILL.md` leads to, or on the way to it, since the loader resolves that link to find the skill. So does a link
on the way to a skill or to its `SKILL.md` that changed its target, and so does a changed specification. So does a link
that changed its target on the chain of a skills directory an agent declares, of an entry in a skills directory, or of
an entry's `SKILL.md`, a chain leaving the repository included, since the model records the link each such chain leaves
through and its target. So does a directory added or deleted that a `..` on such a chain climbs out of: deleting `tmp`
leaves `x -> tmp/../alpha` leading nowhere, and the change set shows `tmp` go, since the snapshot records each climbed
directory and the next scan, stopping at the missing `tmp`, no longer records it. Any other change leaves the model
valid, an entry added or deleted anywhere else inside a skill included: the model lists nothing below a skill's
directory, and reads nothing there but the way to its `SKILL.md`. The scope index carries over unless the two snapshots'
scopes, links or climbed directories differ, compared as recorded rather than through the change set, which holds no
scope. A change of scope invalidates nothing else: what the new scope adds or drops reaches the model and each skill's
resources as entries in the change set. That rule holds only while the decoded text reads its own document, skill or
resource, the frontmatter, the parse, the token count and the line count each read only the decoded text of their own,
the governance reads only the model, the schema problems read only their own document's frontmatter and its governance,
the outline alignment only its own document's parse and its governance, the outline divergences only that alignment and
the line count, a skill's schema problems only its own frontmatter, the model and each skill's resource listing read no
document, and the scope index reads only the scope, the links and the climbed directories, so keep them that way: data
drawn from several documents belongs in a new cache with its own rule.

The link targets of a Markdown file are such a cache: each reads where every path its links name leads, so each
carries over only as its own docstring states.

A change names a resolved path, while a ref may name a path through a link: a skill's `SKILL.md` under a linked
skill entry changes at the path the link leads to, not at the ref's. A snapshot maps a linked path to its resolved one
and not back, so the model records each skill's `SkillLocation`, the resolved `SKILL.md` its ref leads to, and
`advance` would look that path up in the change set. A link retargeted to another skill leaves every file's bytes as
they were and the ref as it was, like a file's identity in the IDE, while its location changes. So a skill's
decoded text, its frontmatter, its parse and its line count carry over only when the two models hand out an equal
location for its ref (its resolved directory and its resolved `SKILL.md`) and that file's bytes did not change; the
link target a skill's context reads is the one in the location its witness carries. A resource is named the same
way, through the symlinks on the way to it, and its `SkillResourceLocation` records the resolved file: its decoded
text and its parse carry over only when the two databases' `skill_resources` locate its ref at the same resolved file
and that file's bytes did not change.
"""

import logging
from collections.abc import Mapping
from typing import Self, cast

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename, EmptyAspectNameError, InvalidAspectNameCharacterError
from lorecraft.project.corpus import (
    CorpusName,
    EmptyCorpusNameError,
    InvalidCorpusNameCharacterError,
    ReservedCorpusNameError,
)
from lorecraft.project.document import DocumentRef
from lorecraft.project.item import (
    DocumentOrigin,
    ItemReadError,
    MarkdownItemDescriptor,
    MarkdownItemRef,
    SpecificationOrigin,
    UnlistedItemError,
)
from lorecraft.project.layout import DOCS_DIR, DOCUMENT_SUFFIX, SPECS_DIR, reject_linked_layout
from lorecraft.project.link_target import (
    DocumentLink,
    LinkBase,
    LinkTargetEntry,
    document_links_of,
    has_link_to,
    link_targets_of,
    linked_files_of,
)
from lorecraft.project.schemas import (
    Query,
    SchemaProblems,
    SkillFields,
    StructureSpec,
    locate_schema_problems,
    locate_skill_schema_problems,
    parse_skill_fields,
)
from lorecraft.project.skill import Repository as SkillRepository
from lorecraft.project.skill import (
    SkillLocation,
    SkillRef,
    SkillResourceListing,
    SkillResourceLocation,
    SkillResourcesListError,
    SkillResourcesSymlinkResolveError,
)
from lorecraft.project.syntax import (
    FrontmatterNode,
    Heading,
    LineCount,
    Link,
    NormalisedLinkPath,
    ParsedDocument,
    TokenCount,
    count_lines,
    count_tokens,
    parse_document,
    parse_frontmatter,
    split_lines,
)
from lorecraft.project.workspace import Governance, ResolvedItem, WorkspaceModel, load_model, unreported_refusals
from lorecraft.vfs import (
    FILE_READ_FAILURES,
    RefusedRecord,
    ResolvedPath,
    ScopeIndex,
    Snapshot,
    TextDecodeError,
    UnrecordedFileError,
    VirtualFileSystem,
)

from .text import ItemText, Undecodable

logger = logging.getLogger(__name__)


def _document_at(ref: MarkdownItemRef) -> DocumentRef | None:
    """The document whose path an item reference is, or None when it is no `docs/<corpus>/<name>.md` path.

    Args:
        ref: The reference to read the corpus and filename from.
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


class _ReadPrimitives:
    """The primitives of one item as the database answers them, noting each one a query reads.

    Attributes:
        read: The names of the primitives read so far.
    """

    def __init__(self, database: 'Database', ref: MarkdownItemRef) -> None:
        self._database = database
        self._ref = ref
        self.read: frozenset[str] = frozenset()

    def structure_specs(self) -> tuple[StructureSpec, ...]:
        """The structure specifications of the layers that loaded for the item."""
        self.read |= {'structure_specs'}
        return self._database.structure_specs(self._ref)

    def headings(self) -> tuple[Heading, ...]:
        """The headings of the item's parse; none for an item that is not UTF-8."""
        self.read |= {'headings'}
        source = self._database.item_text(self._ref)
        return self._database.item_parse(source).headings if isinstance(source, ItemText) else ()

    def token_count(self) -> TokenCount:
        """The tokens in the item's whole file; none for an item that is not UTF-8."""
        self.read |= {'token_count'}
        source = self._database.item_text(self._ref)
        return self._database.item_token_count(source) if isinstance(source, ItemText) else TokenCount(UnsignedInt(0))

    def line_count(self) -> LineCount:
        """The lines in the item's whole file; none for an item that is not UTF-8."""
        self.read |= {'line_count'}
        source = self._database.item_text(self._ref)
        return self._database.item_line_count(source) if isinstance(source, ItemText) else LineCount(UnsignedInt(0))

    def query[T](self, query: Query[T]) -> T:
        """The memoized answer of another query over the item; what it read counts as this query's reads."""
        answer = self._database.query(query, self._ref)
        self.read |= self._database.query_reads(query, self._ref)
        return answer

    def links(self) -> tuple[Link, ...]:
        """The links of the item's parse; none for an item that is not UTF-8."""
        self.read |= {'links'}
        source = self._database.item_text(self._ref)
        return self._database.item_parse(source).links if isinstance(source, ItemText) else ()

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """What the snapshot holds at each relative link's target; none for an item that is not UTF-8."""
        self.read |= {'link_targets'}
        source = self._database.item_text(self._ref)
        return self._database.item_link_targets(source) if isinstance(source, ItemText) else FrozenMapping({})

    def link_base(self) -> LinkBase | None:
        """Where the item's relative links are read from; `None` for an item that is not UTF-8."""
        self.read |= {'link_base'}
        source = self._database.item_text(self._ref)
        return source.descriptor.link_base if isinstance(source, ItemText) else None

    def document_name(self) -> str | None:
        """The stem of a document or meta specification; `None` for any other item or one that is not UTF-8."""
        self.read |= {'document_name'}
        source = self._database.item_text(self._ref)
        origin = source.descriptor.origin if isinstance(source, ItemText) else None
        return origin.expected_name if isinstance(origin, DocumentOrigin | SpecificationOrigin) else None


class Database:
    """What the checks read from one snapshot: its model, built by `from_snapshot`, and every other value computed once.

    `from_snapshot` loads the workspace model; every other value is computed on first use and cached for the snapshot's
    lifetime. Those are the decoded text, the frontmatter, the parse trees, the token counts, the line counts, the
    governance, the schema problems, the outline alignment and the outline divergences of the documents, the decoded
    text, the frontmatter, the parse trees, the line counts and the schema problems of the skills, the resources of each
    skill with their decoded text and their parse trees, the link targets of every one of those Markdown files, and the
    scope index `is_in_scope` answers from.
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
        # `None` until the first `is_in_scope()` call, so the index is built only for a run that asks.
        self._scope_index: ScopeIndex | None = None
        self._unreported_docs_refusals: FrozenMapping[RootRelativePath, RefusedRecord] | None = None
        # The unified family's caches, keyed by the common reference: the one implementation of every document and
        # skill entry query.
        self._items: dict[MarkdownItemRef, ResolvedItem] = {}
        # What the compatibility entry points resolved for a document the model does not list; never an item's answer.
        self._unlisted_items: dict[MarkdownItemRef, ResolvedItem] = {}
        self._item_texts: dict[MarkdownItemRef, ItemText | Undecodable] = {}
        self._item_link_targets: dict[MarkdownItemRef, Mapping[NormalisedLinkPath, LinkTargetEntry]] = {}
        self._item_frontmatters: dict[MarkdownItemRef, FrontmatterNode] = {}
        self._item_parses: dict[MarkdownItemRef, ParsedDocument] = {}
        self._item_token_counts: dict[MarkdownItemRef, TokenCount] = {}
        self._item_line_counts: dict[MarkdownItemRef, LineCount] = {}
        # An item no corpus governs is governed by nothing, so `None` is an answer and is cached too.
        self._item_governances: dict[MarkdownItemRef, Governance | None] = {}
        self._item_schema_problems: dict[MarkdownItemRef, tuple[SchemaProblems, ...]] = {}
        # Declared queries: the answer by the function and the item, with the primitives it read.
        self._queries: dict[tuple[Query[object], MarkdownItemRef], tuple[object, frozenset[str]]] = {}
        self._item_document_links: dict[MarkdownItemRef, tuple[DocumentLink, ...]] = {}
        # Each skill's resource listing, found on the first call; a resource is registered from it with `resource_item`.
        self._skill_resources: dict[SkillRef, SkillResourceListing] = {}
        self._item_skill_schema_problems: dict[MarkdownItemRef, tuple[SchemaProblems, ...]] = {}
        self._item_skill_fields: dict[MarkdownItemRef, SkillFields] = {}

    @classmethod
    def from_snapshot(cls, snapshot: Snapshot) -> Self:
        """Build the database of one snapshot: build its view, refuse a linked layout and load its model.

        The one way to get a database. The model is the one structure value loaded here; every other query is still
        computed on first use.

        Behind a linked `docs/` or `docs/__meta__/` the snapshot holds no specification, so the model would have
        no corpus, and a run over its documents would report success over nothing; the layout is refused instead.

        A unit of the declaration that cannot be read or used does not stop the build: the model records it, in
        `load_failures` and in the layer it stands in.

        Args:
            snapshot: The frozen state every query reads; kept for the database's lifetime and never changed.

        Raises:
            LinkedLayoutError: If `docs/` is a symlink, or else if `docs/__meta__/` is one.
        """
        fs = VirtualFileSystem(snapshot)
        reject_linked_layout(fs)
        return cls(fs, load_model(fs))

    # Input queries: each reads the snapshot and states its own carry-over rule.

    def model(self) -> WorkspaceModel:
        """The workspace model the snapshot declares, loaded when the database was opened. Raises nothing.

        Carry-over: kept for the next revision unless one of these changed, as the module docstring details:

        - An entry added or deleted under `docs/`, or a changed specification.
        - An entry added or deleted in a skills directory, in a skill's directory, or at or on the way to the
          resolved path a skill's linked `SKILL.md` leads to.
        - A link that changed its target on the way to a skill or its `SKILL.md`, or on the chain of a skills
          directory an agent declares, an entry of one, or such an entry's `SKILL.md`, a chain leaving the
          repository included; and a directory added or deleted that a `..` on such a chain climbs out of.
        """
        return self._model

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
        """The scope index `is_in_scope` and the link-target queries answer from, built on the first call."""
        if self._scope_index is None:
            self._scope_index = ScopeIndex(self._snapshot)
        return self._scope_index

    # The unified family: one query per fact for a document or a skill entry, keyed by the common reference.

    def item(self, ref: MarkdownItemRef) -> MarkdownItemDescriptor:
        """The facts the model resolved for one listed document or skill entry, found on the first call for its ref.

        Carry-over: kept for the next revision only when the next model resolves an equal descriptor.

        Args:
            ref: The item to look up; the cache key.

        Raises:
            UnlistedItemError: If the model lists no document or skill entry there.
        """
        return self._resolved(ref).descriptor

    def _resolved(self, ref: MarkdownItemRef) -> ResolvedItem:
        """The descriptor and governance the model resolved for a listed item, found on the first call."""
        resolved = self._items.get(ref)
        if resolved is None:
            resolved = self._model.find_item(ref)
            if resolved is None:
                raise UnlistedItemError(ref)
            self._items[ref] = resolved
        return resolved

    def item_text(self, ref: MarkdownItemRef) -> ItemText | Undecodable:
        """One item's bytes decoded as UTF-8, read from the descriptor's read location on the first call for its ref.

        The one place a document's or skill entry's bytes become text for a rule: every other query about the item
        takes the witness this returns. A file that is not UTF-8 is cached as `Undecodable`, so it is decoded once.

        Carry-over: kept for the next revision only when the next model resolves an equal descriptor, and so the
        same read location, and that file's bytes did not change.

        A file that cannot be read is not cached, so each call raises the same error again.

        Args:
            ref: The item to decode; the cache key.

        Raises:
            UnlistedItemError: If the model lists no document or skill entry there.
            ItemReadError: If the snapshot holds no regular file at the read location.
        """
        self._answerable(ref)
        return self._decode(ref)

    def _answerable(self, ref: MarkdownItemRef) -> ResolvedItem:
        """What the database resolves for an item a query answers for: a listed one, or a document by its path.

        A document in a corpus the model lacks, or beyond its corpus's listing, is not an item `item(ref)` hands out,
        but it is read and judged like any other: it is resolved by the corpus and filename its path names, and kept
        apart from the listed items.

        Args:
            ref: The item to look up: a listed document or skill entry, or a `docs/<corpus>/<name>.md` path whose
                corpus and filename are valid names.

        Raises:
            UnlistedItemError: If the model lists no skill entry there and the path names no document.
        """
        try:
            return self._resolved(ref)
        except UnlistedItemError:
            if ref in self._unlisted_items:
                return self._unlisted_items[ref]
            document = _document_at(ref)
            if document is None:
                raise
            self._document_item(document)
            return self._known(ref)

    def _decode(self, ref: MarkdownItemRef) -> ItemText | Undecodable:
        """Decode an item the database already resolved, listed or not, once."""
        decoded = self._item_texts.get(ref)
        if decoded is None:
            descriptor = self._known(ref).descriptor
            try:
                decoded = ItemText(descriptor, self._fs.read_text(descriptor.read_location))
            except TextDecodeError as exc:
                decoded = Undecodable(ref, exc.failure)
            except (*FILE_READ_FAILURES, UnrecordedFileError) as exc:
                raise ItemReadError(ref, source=exc) from exc
            self._item_texts[ref] = decoded
        return decoded

    def _known(self, ref: MarkdownItemRef) -> ResolvedItem:
        """What the database resolved for an item, listed or not; the item was resolved before it is asked for."""
        resolved = self._items.get(ref)
        return resolved if resolved is not None else self._unlisted_items[ref]

    def resource_item(self, location: SkillResourceLocation) -> MarkdownItemRef:
        """The common reference of a skill's resource, resolved from the location its skill's listing gives.

        The model lists no resource, so the resource is kept apart from the listed items, as an unlisted document is:
        the `item_*` queries answer for its reference, and `item(ref)` still refuses it. Raises nothing.

        Args:
            location: The resource, as `skill_resources` locates it; its resolved file is where the text is read.
        """
        item = MarkdownItemRef(location.ref.path)
        if item not in self._unlisted_items:
            self._unlisted_items[item] = self._model.resolve_resource(location)
        return item

    def _document_item(self, ref: DocumentRef) -> MarkdownItemRef:
        """The common reference of a document ref, resolved by ref without scanning the model's items.

        A document the model lists is kept as an item. One it does not list, in a corpus it lacks or beyond the
        corpus's listing, is kept apart, so `item(ref)` still refuses it.
        """
        item = MarkdownItemRef(ref.path)
        if item not in self._items and item not in self._unlisted_items:
            corpus = self._model.find_corpus(ref.corpus)
            listed = corpus is not None and ref.filename in corpus.filenames
            (self._items if listed else self._unlisted_items)[item] = self._model.resolve_item(ref)
        return item

    def item_link_targets(self, source: ItemText) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """Where each relative link of one item leads and what the snapshot holds there, found on the first call.

        Each link is read from the descriptor's link base, which carries its own climb bound, as `link_targets_of`
        states. Raises nothing.

        Carry-over: kept for the next revision only when `item_parse(source)` is kept and every path the query
        looked up, an absent target included, still resolves to the same place and is in the same scope state.

        Args:
            source: The item's text; its ref is the cache key.
        """
        targets = self._item_link_targets.get(source.ref)
        if targets is None:
            links = self.item_parse(source).links
            targets = link_targets_of(links, source.descriptor.link_base, self._fs, self._built_scope_index())
            self._item_link_targets[source.ref] = targets
        return targets

    def item_frontmatter(self, source: ItemText) -> FrontmatterNode:
        """The frontmatter of one item, parsed from its decoded text on the first call. Raises nothing.

        Cached apart from `item_parse(source)`: the block is decoded here alone.

        Carry-over: kept for the next revision whenever `item_text(source.ref)` is.

        Args:
            source: The item's text; its ref is the cache key.
        """
        decoded = self._item_frontmatters.get(source.ref)
        if decoded is None:
            decoded = parse_frontmatter(source.text)
            self._item_frontmatters[source.ref] = decoded
        return decoded

    def item_parse(self, source: ItemText) -> ParsedDocument:
        """The parse tree of one item, parsed from its decoded text on the first call. Raises nothing.

        Carry-over: kept for the next revision whenever `item_text(source.ref)` is.

        Args:
            source: The item's text; its ref is the cache key.
        """
        parsed = self._item_parses.get(source.ref)
        if parsed is None:
            parsed = parse_document(source.text)
            self._item_parses[source.ref] = parsed
        return parsed

    def item_token_count(self, source: ItemText) -> TokenCount:
        """The tokens in one item's whole file, counted from the raw text on the first call. Raises nothing.

        Carry-over: kept for the next revision whenever `item_text(source.ref)` is.

        Args:
            source: The item's text; its ref is the cache key.
        """
        count = self._item_token_counts.get(source.ref)
        if count is None:
            count = count_tokens(source.text)
            self._item_token_counts[source.ref] = count
        return count

    def item_line_count(self, source: ItemText) -> LineCount:
        """The lines in one item's whole file, counted from the raw text on the first call. Raises nothing.

        Carry-over: kept for the next revision whenever `item_text(source.ref)` is.

        Args:
            source: The item's text; its ref is the cache key.
        """
        count = self._item_line_counts.get(source.ref)
        if count is None:
            count = count_lines(source.text)
            self._item_line_counts[source.ref] = count
        return count

    def item_governance(self, ref: MarkdownItemRef) -> Governance | None:
        """The specifications that govern one item, resolved by the model on the first call for its ref.

        A layer whose structure file failed to load is held as the failed structure the model recorded, in the order
        the layers apply, so the governance hands out what loaded and what failed and decides no skip or partial
        policy. `None` when no specification governs the item.

        Carry-over: kept for the next revision whenever the next model's governance of the ref is equal to it, as
        compared by value, so a change elsewhere in the model leaves it, and every analysis reading it, valid.

        Args:
            ref: The item to look up; the cache key.

        Raises:
            UnlistedItemError: If the model lists no document or skill entry there.
        """
        self._answerable(ref)
        return self._governance_of(ref)

    def _governance_of(self, ref: MarkdownItemRef) -> Governance | None:
        """The governance of an item the database already resolved, listed or not, found once."""
        if ref not in self._item_governances:
            self._item_governances[ref] = self._known(ref).governance
        return self._item_governances[ref]

    def item_schema_problems(self, source: ItemText) -> tuple[SchemaProblems, ...]:
        """What each frontmatter schema that governs one item rejects in its frontmatter, found on the first call.

        Typed problems, each placed on its line; severity is a rule's. The frontmatter is read only when a schema
        governs the item, and only the layers that loaded state a schema.

        Carry-over: kept for the next revision whenever `item_frontmatter(source)` and `item_governance(source.ref)`
        are.

        Args:
            source: The item's text; its ref is the cache key.
        """
        found = self._item_schema_problems.get(source.ref)
        if found is None:
            governance = self._governance_of(source.ref)
            schemas = governance.frontmatter_schemas() if governance is not None else ()
            found = locate_schema_problems(self.item_frontmatter(source), schemas) if schemas else ()
            self._item_schema_problems[source.ref] = found
        return found

    def structure_specs(self, ref: MarkdownItemRef) -> tuple[StructureSpec, ...]:
        """The structure specifications of the layers that loaded for an item the model lists.

        Raises:
            UnlistedItemError: If the model lists no document or skill entry there.
        """
        governance = self.item_governance(ref)
        return governance.structure_specs() if governance is not None else ()

    def query[T](self, query: Query[T], ref: MarkdownItemRef) -> T:
        """The answer of a declared query over one item, found on the first call for the function and the ref.

        The query runs over the item's primitives and reads nothing else; the database notes which it read.

        Carry-over: kept for the next revision whenever every primitive the query read is kept, such as
        `item_governance(ref)` for the structure specifications.

        Args:
            query: The pure function to run; with the ref, the cache key.
            ref: The item to run it over.

        Raises:
            UnlistedItemError: If the model lists no document or skill entry there.
        """
        key = (query, ref)
        if key not in self._queries:
            primitives = _ReadPrimitives(self, ref)
            answer = query(primitives)
            self._queries[key] = (answer, primitives.read)
        return cast('T', self._queries[key][0])

    def query_reads(self, query: Query[object], ref: MarkdownItemRef) -> frozenset[str]:
        """The primitives a query read over one item, by method name, once it has been run. Raises nothing.

        Args:
            query: The query asked for.
            ref: The item it ran over.
        """
        return self._queries[(query, ref)][1] if (query, ref) in self._queries else frozenset()

    def item_document_links(self, source: ItemText) -> tuple[DocumentLink, ...]:
        """The links of one document to another document, with its corpus and filename and whether it links back.

        A skill's file has none. A destination that cannot be read or decoded is logged and has no back link.

        Carry-over: kept for the next revision whenever `item_parse(source)`, `item_link_targets(source)` and, for each
        destination, `item_text` (its decode or refusal outcome) and `item_link_targets` are.

        Args:
            source: The item's text; its ref is the cache key.

        Returns:
            One entry per link to an existing document of the layout, in document order; `has_back_link` is false
            for a destination that cannot be read or decoded, as for one that does not link back.
        """
        found = self._item_document_links.get(source.ref)
        if found is None:
            linked = linked_files_of(
                self.item_parse(source).links, self.item_link_targets(source), source.descriptor.link_base
            )
            documents: dict[RootRelativePath, tuple[str, str]] = {}
            for link in linked:
                destination = _document_at(MarkdownItemRef(link.path))
                if destination is not None:
                    documents[link.path] = (str(destination.corpus), str(destination.filename))
            back_links = {
                path: self._has_link_to(MarkdownItemRef(path), source.ref.path)
                for path in documents
                if path != source.ref.path
            }
            found = document_links_of(linked, source.ref.path, documents, back_links)
            self._item_document_links[source.ref] = found
        return found

    def _has_link_to(self, ref: MarkdownItemRef, path: RootRelativePath) -> bool:
        """Whether the document at a ref links to an existing file at a path; false, logged, when it cannot be read.

        Args:
            ref: The document to read.
            path: The root-relative path to look for among its links.
        """
        try:
            text = self.item_text(ref)
        except ItemReadError:
            logger.warning('cannot read %s to look for a link back to %s', ref.path, path, exc_info=True)
            return False
        if isinstance(text, Undecodable):
            logger.warning('%s is not UTF-8, so it holds no link back to %s', ref.path, path)
            return False
        return has_link_to(self.item_link_targets(text), path)

    # Derived queries: each reads only other queries and carries over whenever they do.

    def item_skill_schema_problems(self, source: ItemText) -> tuple[SchemaProblems, ...]:
        """What the Agent Skills specification rejects in a skill entry's frontmatter, found once. Raises nothing.

        Each problem is placed on the line its field is written on, or line 1 when it has none. The package states
        the specification, so every skill is held to it and no specification in the repository plays a part.

        Carry-over: kept for the next revision whenever `item_frontmatter(source)` is.

        Args:
            source: The skill entry's text; its ref is the cache key.

        Returns:
            One entry, for the Agent Skills specification; none when the block is missing, not YAML or not a
            mapping, which no schema can hold.
        """
        found = self._item_skill_schema_problems.get(source.ref)
        if found is None:
            found = locate_skill_schema_problems(self.item_frontmatter(source))
            self._item_skill_schema_problems[source.ref] = found
        return found

    def item_skill_fields(self, source: ItemText) -> SkillFields:
        """The fields of one skill entry's frontmatter that parse, parsed once. Raises nothing.

        A field that is not written or is rejected has no entry, so a rule over one field reads it whatever the
        others hold.

        Carry-over: kept for the next revision whenever `item_frontmatter(source)` is.

        Args:
            source: The skill entry's text; its ref is the cache key.
        """
        found = self._item_skill_fields.get(source.ref)
        if found is None:
            found = parse_skill_fields(self.item_frontmatter(source))
            self._item_skill_fields[source.ref] = found
        return found

    # Not queries: each is answered from the snapshot on every call and never cached.

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

    def find_file(self, path: RootRelativePath) -> ResolvedPath | None:
        """The file `path` leads to in the snapshot, every recorded link on the way followed; never cached.

        Args:
            path: The path to look up, relative to the snapshot root; a directory leads to no file.

        Returns:
            The resolved file, root-relative, or `None` when the snapshot holds no file there: nothing, a
            directory, or a link it did not follow.
        """
        return self._fs.find_file(path)

    def is_in_scope(self, path: RootRelativePath) -> bool:
        """Whether the scan lists the directory `path` sits in, as the snapshot's scope declares it.

        Like the IDE's question whether a file is in the project's content, answered from the roots the snapshot
        records it was taken of rather than from what the virtual file system holds: a path in a directory the
        scope covers is in it even where the directory does not exist, and then whatever the path names is
        missing. Only the links and climbed directories the snapshot recorded are read besides, to tell where
        `path` leads. A snapshot that scanned nothing, such as one a test built by hand, has no path in
        scope.

        The answer is not cached, but what it is computed from is: the scope expanded through the recorded
        links, a `ScopeIndex` built on the first call and asked on every later one.

        Args:
            path: The entry to ask about, relative to the snapshot root; it need not exist.
        """
        return self._built_scope_index().is_in_scope(path)
