"""One frozen state of a workspace: its snapshot, and the cached data every check, and every command, reads through.

The layering follows an IDE's. The `Snapshot` plays the virtual file system: every byte a
check can see, and never changed once built. `Database.from_snapshot` builds the database from a snapshot and loads the
model; every other query sits above it, computed on first use and kept for as long as the database lives
(pattern-memoization). Queries come in two kinds, and the kind decides how a query carries over to the next revision.

The item queries share one family keyed by `MarkdownItemRef`.
`item_text(ref)` decodes the descriptor's read location into an `ItemText` witness or an `Undecodable` marker.
`item_link_targets(source)` is an input query; `item_frontmatter`, `item_parse`, `item_token_count`,
`item_line_count` and `item_governance` are derived queries. A
resource's `resource_item(location)` registers the reference from its skill's listing, and its item queries read the
descriptor at the resolved location. A document the model does not list is resolved by its corpus and filename.

The declared `query(query, ref)` memoizes a rule-owned query over a Markdown item, symlink, reserved-corpus directory
or schema subject. `query_reads(query, ref)` reports typed primitive and cross-subject reads, each retaining its
subject reference. A query's result carries over when each primitive or query dependency it read does.
`item_governance(ref)` reads the model, and a declared item query reads common primitives without distinguishing item
origins.

Database construction and resource registration have no separate carry-over cache. `from_snapshot(snapshot)` creates
a fresh database for that snapshot. `resource_item(location)` registers the ref from the skill resource listing in
that database; in a later revision, the listing must locate the resource at the same ref and resolved file for its
item query results to carry over.

Input queries read the snapshot. Each is the one place its part of the snapshot becomes a value for a rule, so only an
input query builds a witness or fails to read, and each states its own carry-over rule against the change set:

- `model()`: the workspace model, like the IDE's project model, loaded when the database is opened, so no query that
  reads it raises a load error. It reads the structure of the snapshot, the
  specifications, the corpus directories, the skills directories and the listing of each skill's directory, nothing
  deeper inside a skill, and no document's contents. Among that structure it records each skills directory, skill
  entry and `SKILL.md` whose symlink chain leaves the repository.
- `item_text(ref)`: one item's bytes decoded as UTF-8, like the IDE's document text for a file: an `ItemText` witness,
  or an `Undecodable` marker when the bytes are not UTF-8. It is the one place those bytes become text for a rule, and
  it reads that file's bytes and nothing else.
- `skill_resources(skill)`: one skill's resources, the Markdown files inside it other than its top-level `SKILL.md`,
  like the IDE's listing of a content root's children, and the symlinks inside it whose chain leaves the
  repository. It reads the listings and the symlink targets reached from that skill, and where the model locates
  the skill, and no file's content.
- The `ScopeIndex` the link-target queries answer from: the scope the snapshot records it was taken of, expanded once
  through the links it recorded, like the IDE's index of a project's content roots. It reads the snapshot's
  scope, links and climbed directories and nothing else, and no caller reaches it but the link-target queries.
  Whether the scan reads the directory a path sits in is configuration, not content: it is answered from this
  index and never from which directories the snapshot holds.
- `item_link_targets(source)`: what the snapshot holds at the target of each relative link of one item. It reads the
  item's parse and link base, the snapshot's view and the scope index. Carry-over requires the parse to carry and
  every looked-up path, including an absent target, to resolve to the same place in the same scope state.

Derived queries read the results of other queries and never the snapshot. Each hands what it read to one function
of this package that computes the value, so its arguments are its read set, and it carries over whenever every query
it read does, `item_governance(ref)` excepted, as its bullet states:

- `item_frontmatter(source)`: one item's frontmatter node, like a stub: the part of a file the IDE reads without
  building its full syntax tree. It reads the text of the witness and nothing else.
- `item_parse(source)`: one item's parse tree, like the IDE's syntax tree of a file. It reads the text of the witness
  and nothing else.
- `item_token_count(source)` and `item_line_count(source)`: what one item's whole file costs an agent that loads it,
  and how many lines it holds, counted from the raw text, frontmatter included, without a parse.
- `item_governance(ref)`: the specifications that govern a corpus document or skill entry, its corpus's first and
  then each namespace's that matches it. Skill entries use the reserved `skills` corpus; resources have no corpus
  governance.
  It reads `model()` and nothing else, and it is the one place an item's governance is
  computed, so the model's corpus is searched once per item for the revision. It is the exception to the rule above:
  the model is dropped by any entry added or deleted
  under `docs/`, so it is recomputed from the next model and kept when it compares equal to the one it replaces. It
  can carry over when `model()` does not, and so can every analysis that reads it.

Other public methods either answer from queries or inspect the snapshot. Their section and carry-over rules are:

- `item_structure_specs(ref)` reads `item_governance(ref)` for documents and skill entries. Resources and
  specifications have no corpus structure specs; it is not cached separately and carries over with that governance.
- `query(query, ref)` runs a declared query over a Markdown item, symlink or reserved-corpus directory subject and
  caches its answer and read set. It carries over whenever every primitive or cross-item query it read does.
- `query_reads(query, ref)` reports recorded primitive and cross-item reads, paired with their source refs; it is empty
  before that query has run and is not cached.

Snapshot questions are answered on each call, except `unreported_docs_refusals()`, which is cached for this database's
lifetime:

- `refusals()` returns all access refusals recorded in the snapshot.
- `unreported_docs_refusals()` filters snapshot refusals under `docs/` to those not already reported by model load
  failures, and is recomputed from the next revision's refusals and model failures.
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

Rules are pure functions of the values a subject's query reads for them through the database, like an inspection
run over one file: the runner matches each file's decode once and hands a rule the facts of the part it judges. A
query asks for the cheapest query that holds what a rule reads, so a rule that needs only the frontmatter never pays
for the full parse, and every rule reading the same query shares one computation of it. Their results are not cached;
a rule runs again every time.

Nothing here records what a cached value read, so no dependency is tracked. Invalidation is written by hand instead, the
way the IDE drops per-file index entries on a file change event and resets structural caches on a project model change.
Reserved, not implemented: `advance(snapshot) -> Database`, the next state. It would `diff` the two snapshots and carry
over each cached value the change set leaves valid: the decoded text, the frontmatter, the parse, the token count and
the line count of every item whose bytes did not change, and its schema problems when its governance carries over;
the governance of every item the next model governs by equal specifications; the resources of every skill and the
decoded text and the parse of every resource as their own
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
a skill's schema problems only its own frontmatter, the model and each skill's resource listing read no document, and
the scope index reads only the scope, the links and the climbed directories, so keep them that way: data drawn from
several documents belongs in a new cache with its own rule.

The link targets of a Markdown file are such a cache: each reads where every path its links name leads, so each
carries over only as its own docstring states.

A change names a resolved path, while a ref may name a path through a link: a skill's `SKILL.md` under a linked
skill entry changes at the path the link leads to, not at the ref's. A snapshot maps a linked path to its resolved one
and not back, so the model records each skill's `SkillLocation`, the resolved `SKILL.md` its ref leads to, and
`advance` would look that path up in the change set. A link retargeted to another skill leaves every file's bytes as
they were and the ref as it was, like a file's identity in the IDE, while its location changes. So a skill's
decoded text, its frontmatter, its parse and its line count carry over only when the two models hand out an equal
location for its ref (its resolved directory and its resolved `SKILL.md`) and that file's bytes did not change; the
link targets also require the same resolved link base and scope state. A resource is named through the symlinks on
the way to it, and its `SkillResourceLocation` records the resolved file. Its decoded text, frontmatter, parse, token
count and line count carry over only when both databases' resource listings locate its ref at the same resolved file
and its bytes did not change. Its link targets additionally require the parse, link base and scope state to carry
over. Its schema problems and governance carry over by the same rules as for other items: equal frontmatter and the
governance those problems read; equal governance, respectively.
"""

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Self, assert_never, cast, overload

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import UnsignedInt
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
    CorpusDirectoryQueryRead,
    Query,
    SchemaQuery,
    SchemaQueryRead,
    SymlinkQuery,
    SymlinkQueryRead,
)
from lorecraft.project.schemas import (
    SpecName,
    StructureSpec,
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
    Anchor,
    FrontmatterNode,
    Heading,
    LineCount,
    Link,
    MissingFrontmatter,
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


class PrimitiveRead(StrEnum):
    """A primitive that a declared query read, named by its method."""

    STRUCTURE_SPECS = 'structure_specs'
    HEADINGS = 'headings'
    TOKEN_COUNT = 'token_count'
    LINE_COUNT = 'line_count'
    FRONTMATTER = 'frontmatter'
    ITEM_ORIGIN = 'item_origin'
    ITEM_GOVERNANCE = 'item_governance'
    BUILTIN_SKILLS_SCHEMA = 'builtin_skills_schema'
    LINKS = 'links'
    ANCHORS = 'anchors'
    LINK_TARGETS = 'link_targets'
    LINK_BASE = 'link_base'
    ITEM_NAME = 'item_name'
    ITEM_CORPUS = 'item_corpus'
    ITEM_BASE = 'item_base'
    SYMLINK_LEAVES_AT = 'symlink_leaves_at'
    RESERVED_CORPUS = 'reserved_corpus'


@dataclass(frozen=True)
class QueryRead:
    """One primitive or declared query read from one Markdown item."""

    source: PrimitiveRead | Query[object]
    ref: MarkdownItemRef


@dataclass(frozen=True)
class SchemaInputRead:
    """The immutable raw schema input read by a schema query.

    Attributes:
        reference: The typed schema identity the query reads.
    """

    reference: SchemaReference


type QueryKey = tuple[Query[object], MarkdownItemRef] | SymlinkQueryRead | CorpusDirectoryQueryRead | SchemaQueryRead
type ReadKey = (
    PrimitiveRead | QueryRead | SymlinkQueryRead | CorpusDirectoryQueryRead | SchemaQueryRead | SchemaInputRead
)


class _ReadSet:
    """A practical in-process guard around reads shared by database primitive adapters.

    Name-mangled storage and the repository source guard keep ordinary callers on `_record`; deliberate Python
    reflection can still bypass that boundary.
    """

    __slots__ = ('__reads',)

    def __init__(self) -> None:
        self.__reads: set[ReadKey] = set()

    def _record(self, *keys: ReadKey) -> None:
        """Record primitive or nested-query keys without exposing mutable storage."""
        self.__reads.update(keys)

    def _recorded_reads(self) -> frozenset[ReadKey]:
        """Return a frozen copy for the database cache."""
        return frozenset(self.__reads)

    def _nested_query[T](
        self,
        key: ReadKey,
        answer: Callable[[], T],
        reads: Callable[[], frozenset[ReadKey]],
    ) -> T:
        """Record a nested query key before running it, then add its reads when it succeeds.

        The key remains recorded if the nested query raises, so failed references remain dependencies too.
        """
        self._record(key)
        result = answer()
        self._record(*reads())
        return result


class _ReadSchemaPrimitives(_ReadSet):
    """The immutable input of one schema subject, recorded under its typed reference."""

    __slots__ = ('_database', '_ref')

    def __init__(self, database: 'Database', ref: SchemaReference) -> None:
        super().__init__()
        self._database = database
        self._ref = ref

    def schema_input(self) -> SchemaInput:
        """Resolve the subject from this database's loaded model."""
        self._record(SchemaInputRead(self._ref))
        return self._database._schema_input(self._ref)

    def query_schema[T](self, ref: SchemaReference, query: SchemaQuery[T]) -> T:
        """Read a memoized schema query and retain its key even when it raises."""
        key = (cast('SchemaQuery[object]', query), ref)
        return self._nested_query(
            key,
            lambda: self._database.query(query, ref),
            lambda: self._database.query_reads(query, ref),
        )


class _ReadSymlinkPrimitives(_ReadSet):
    """The primitive reads of one symlink subject, recorded with typed keys."""

    def __init__(self, database: 'Database', ref: SymlinkRef) -> None:
        super().__init__()
        self._database = database
        self._ref = ref

    __slots__ = ('_database', '_ref')

    def leaves_at(self) -> RootExit:
        """The point where this symlink's chain leaves the repository."""
        self._record(PrimitiveRead.SYMLINK_LEAVES_AT)
        return self._database._outside_symlink(self._ref).leaves_at


class _ReadCorpusDirectoryPrimitives(_ReadSet):
    """The primitive reads of one reserved-corpus directory subject, recorded with typed keys."""

    def __init__(self, database: 'Database', ref: CorpusDirectoryRef) -> None:
        super().__init__()
        self._database = database
        self._ref = ref

    __slots__ = ('_database', '_ref')

    def reserved_corpus(self) -> CorpusName:
        """The reserved corpus whose name this directory takes."""
        self._record(PrimitiveRead.RESERVED_CORPUS)
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


class _ReadPrimitives(_ReadSet):
    """The primitives of one item as the database answers them, noting each one a query reads.

    A primitive that walks the model or other files, such as `linked_documents` and `item_base`,
    is not cached here: a query over the item is memoized by the database for the function and the ref, so each of
    them is computed once per query, and a cache beside it would only hold the same answer twice.

    """

    __slots__ = ('_database', '_ref')

    def __init__(self, database: 'Database', ref: MarkdownItemRef) -> None:
        super().__init__()
        self._database = database
        self._ref = ref

    def item_origin(self) -> ItemOrigin:
        """The model-resolved origin facts of the item."""
        self._record(QueryRead(PrimitiveRead.ITEM_ORIGIN, self._ref))
        self._database._answerable(self._ref)
        return self._database._known(self._ref).descriptor.origin

    def item_governance(self) -> Governance | None:
        """The model's governance of the item."""
        self._record(QueryRead(PrimitiveRead.ITEM_GOVERNANCE, self._ref))
        return self._database.item_governance(self._ref)

    def builtin_skills_schema(self) -> bool:
        """Whether the package's Agent Skills frontmatter schema is enabled."""
        self._record(QueryRead(PrimitiveRead.BUILTIN_SKILLS_SCHEMA, self._ref))
        return self._database.model().builtin_skills_schema

    def structure_specs(self) -> tuple[StructureSpec, ...]:
        """The structure specifications of the layers that loaded for the item."""
        self._record(QueryRead(PrimitiveRead.STRUCTURE_SPECS, self._ref))
        return self._database.item_structure_specs(self._ref)

    def headings(self) -> tuple[Heading, ...]:
        """The headings of the item's parse; none for an item that is not UTF-8."""
        self._record(QueryRead(PrimitiveRead.HEADINGS, self._ref))
        source = self._database.item_text(self._ref)
        return self._database.item_parse(source).headings if isinstance(source, ItemText) else ()

    def token_count(self) -> TokenCount:
        """The tokens in the item's whole file; none for an item that is not UTF-8."""
        self._record(QueryRead(PrimitiveRead.TOKEN_COUNT, self._ref))
        source = self._database.item_text(self._ref)
        return self._database.item_token_count(source) if isinstance(source, ItemText) else TokenCount(UnsignedInt(0))

    def line_count(self) -> LineCount:
        """The lines in the item's whole file; none for an item that is not UTF-8."""
        self._record(QueryRead(PrimitiveRead.LINE_COUNT, self._ref))
        source = self._database.item_text(self._ref)
        return self._database.item_line_count(source) if isinstance(source, ItemText) else LineCount(UnsignedInt(0))

    def frontmatter(self) -> FrontmatterNode:
        """The item's frontmatter block; missing for an item that is not UTF-8."""
        self._record(QueryRead(PrimitiveRead.FRONTMATTER, self._ref))
        source = self._database.item_text(self._ref)
        return self._database.item_frontmatter(source) if isinstance(source, ItemText) else MissingFrontmatter()

    def query[T](self, query: Query[T]) -> T:
        """The memoized answer of another query over the item; what it read counts as this query's reads."""
        return self._record_nested(query, self._ref)

    def _record_nested[T](self, query: Query[T], ref: MarkdownItemRef) -> T:
        """Run a nested query and record its dependency chain, including when it fails."""
        key = QueryRead(cast('Query[object]', query), ref)
        return self._nested_query(
            key,
            lambda: self._database.query(query, ref),
            lambda: self._database.query_reads(query, ref),
        )

    def query_at[T](self, ref: MarkdownItemRef, query: Query[T]) -> T:
        """The memoized answer of a query over another item, recorded as a read dependency.

        Args:
            ref: The item whose primitives the query reads.
            query: The pure function to run over that item's primitives.
        """
        return self._record_nested(query, ref)

    def query_schema[T](self, ref: SchemaReference, query: SchemaQuery[T]) -> T:
        """Read a memoized schema query and retain its key even when it raises."""
        key = (cast('SchemaQuery[object]', query), ref)
        return self._nested_query(
            key,
            lambda: self._database.query(query, ref),
            lambda: self._database.query_reads(query, ref),
        )

    def links(self) -> tuple[Link, ...]:
        """The links of the item's parse; none for an item that is not UTF-8."""
        self._record(QueryRead(PrimitiveRead.LINKS, self._ref))
        source = self._database.item_text(self._ref)
        return self._database.item_parse(source).links if isinstance(source, ItemText) else ()

    def anchors(self) -> frozenset[Anchor]:
        """The anchor of every heading of the item's parse; none for an item that is not UTF-8."""
        self._record(QueryRead(PrimitiveRead.ANCHORS, self._ref))
        source = self._database.item_text(self._ref)
        return self._database.item_parse(source).anchors if isinstance(source, ItemText) else frozenset()

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """What the snapshot holds at each relative link's target; none for an item that is not UTF-8."""
        self._record(QueryRead(PrimitiveRead.LINK_TARGETS, self._ref))
        source = self._database.item_text(self._ref)
        return self._database.item_link_targets(source) if isinstance(source, ItemText) else FrozenMapping({})

    def link_base(self) -> LinkBase | None:
        """Where the item's relative links are read from; `None` for an item that is not UTF-8."""
        self._record(QueryRead(PrimitiveRead.LINK_BASE, self._ref))
        source = self._database.item_text(self._ref)
        return source.descriptor.link_base if isinstance(source, ItemText) else None

    def item_name(self) -> AspectFilename | SpecName | None:
        """The typed name of a document or meta specification; `None` for any other item or one that is not UTF-8."""
        self._record(QueryRead(PrimitiveRead.ITEM_NAME, self._ref))
        source = self._database.item_text(self._ref)
        origin = source.descriptor.origin if isinstance(source, ItemText) else None
        # Keep this dispatch: documents and specifications have different name formats; skills and resources have none.
        match origin:
            case DocumentOrigin():
                return AspectFilename.parse(origin.expected_name)
            case SpecificationOrigin():
                return parse_spec_name(origin.expected_name)
            case _:
                return None

    def item_corpus(self) -> CorpusName | None:
        """The typed corpus a document lies in; `None` for any other item or one that is not UTF-8."""
        self._record(QueryRead(PrimitiveRead.ITEM_CORPUS, self._ref))
        source = self._database.item_text(self._ref)
        origin = source.descriptor.origin if isinstance(source, ItemText) else None
        # Keep this dispatch: this query answers for user documents; a specification's `corpus` is a prefix of its
        # name, and a skill has none.
        return CorpusName.parse(origin.corpus) if isinstance(origin, DocumentOrigin) else None

    def item_base(self) -> AspectFilename | SpecName | None:
        """The typed name of the document or specification the item extends, from the names the model lists.

        A document's base is looked for among the documents of its corpus, a specification's among the specifications;
        `None` for any other item or one that is not UTF-8. A skill entry extends nothing: its name is its directory's,
        which no hyphenated prefix continues.
        """
        self._record(QueryRead(PrimitiveRead.ITEM_BASE, self._ref))
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

    Derived queries read other queries: `item_frontmatter(source)`, `item_parse(source)`,
    `item_token_count(source)`, `item_line_count(source)` derive values from decoded text;
    `item_governance(ref)` reads the model.
    `skill_fields_query`, `frontmatter_owner_query` and `schema_problems_query`
    (`lorecraft.project.schemas`) run through `query(query, ref)`, which memoizes each answer and its reads. Schema
    queries use the same cache keyed by `(query, SchemaReference)` and read immutable inputs from the model.

    The item family is keyed by `MarkdownItemRef`. A resource's
    reference is registered from its listing by `resource_item(location)`. A document outside the model's listing is
    still resolved from its corpus and filename. `from_snapshot(snapshot)` starts a fresh database; it carries no
    cached values from another revision. `resource_item(location)` registers a resource under the ref in its listing.
    The snapshot questions are `source_lines(path)`, `refusals()` and `unreported_docs_refusals()`: the first two are
    answered on each call; the last is cached for this database's lifetime and recomputed from the next revision's
    refusals and model failures. The declared query `query(query, ref)` memoizes its answer and read set;
    `query_reads(query, ref)` holds typed reads and is empty before that query runs. `item_structure_specs` and
    `item_has_link_to` are not cached separately and carry over with the query results they read.
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
        # What a query resolved for a document the model does not list; kept apart from listed items.
        self._unlisted_items: dict[MarkdownItemRef, ResolvedItem] = {}
        self._item_texts: dict[MarkdownItemRef, ItemText | Undecodable] = {}
        self._item_link_targets: dict[MarkdownItemRef, Mapping[NormalisedLinkPath, LinkTargetEntry]] = {}
        self._item_frontmatters: dict[MarkdownItemRef, FrontmatterNode] = {}
        self._item_parses: dict[MarkdownItemRef, ParsedDocument] = {}
        self._item_token_counts: dict[MarkdownItemRef, TokenCount] = {}
        self._item_line_counts: dict[MarkdownItemRef, LineCount] = {}
        # An item no corpus governs is governed by nothing, so `None` is an answer and is cached too.
        self._item_governances: dict[MarkdownItemRef, Governance | None] = {}
        # Declared queries: the answer by the function and the item, with the primitive and cross-item query keys
        # it read.
        self._queries: dict[QueryKey, tuple[object, frozenset[ReadKey]]] = {}
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
            builtin_skills_schema: Whether skills use the Agent Skills floor and its contradiction preflight.

        Raises:
            LinkedLayoutError: If `docs/` is a symlink, or else if `docs/__meta__/` is one.
        """
        fs = VirtualFileSystem(snapshot)
        reject_linked_layout(fs)
        return cls(fs, load_model(fs, builtin_skills_schema=builtin_skills_schema))

    # Input query: the model is loaded once from the snapshot.

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
        """The scope index the link-target queries answer from, built on the first call."""
        if self._scope_index is None:
            self._scope_index = ScopeIndex(self._snapshot)
        return self._scope_index

    # Item resolution and registration use the common reference; listed resources and unlisted documents enter here.

    def _resolved(self, ref: MarkdownItemRef) -> ResolvedItem:
        """The descriptor and governance the model resolved for a listed item, found on the first call."""
        resolved = self._items.get(ref)
        if resolved is None:
            resolved = self._model.find_item(ref)
            if resolved is None:
                raise UnlistedItemError(ref)
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
        self._answerable(ref)
        return self._decode(ref)

    def _answerable(self, ref: MarkdownItemRef) -> ResolvedItem:
        """What the database resolves for an item a query answers for: a listed one, or a document by its path.

        A document in a corpus the model lacks, or beyond its corpus's listing, is not an item the model lists,
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
            # The ref is unlisted, so model resolution validates its document path without checking the listing again.
            resolved = self._model.resolve_item(ref)
            self._unlisted_items[ref] = resolved
            return resolved

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
        the `item_*` queries answer for its reference, and the listed items still refuse it. Raises nothing.

        Carry-over: this registration is database-local. In the next revision, the resource's item queries can carry
        over only when its listing resolves the ref to the same file and the relevant query inputs are unchanged.

        Args:
            location: The resource, as `skill_resources` locates it; its resolved file is where the text is read.
        """
        item = MarkdownItemRef(location.ref.path)
        self._register(item, lambda: self._model.resolve_resource(location), listed=False)
        return item

    def _register(self, item: MarkdownItemRef, resolve: Callable[[], ResolvedItem], *, listed: bool) -> None:
        """Keep what an item resolves to, once: the one route by which a document or a resource enters the database.

        A listed item is kept with the model's, so the listed items answer for it; any other is kept apart, so they
        still refuse it. The item is resolved only when it is not kept yet.

        Args:
            item: The item to keep.
            resolve: Resolves the item; called only for an item not kept yet.
            listed: Whether the model lists the item.
        """
        if item not in self._items and item not in self._unlisted_items:
            (self._items if listed else self._unlisted_items)[item] = resolve()

    # Input query: resolve the paths named by one item's links against the snapshot and scope.

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

    # Derived queries: each reads other queries and carries over with the queries it reads.

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
        """The specifications that govern an item, resolved by the model on the first call for its ref.

        A layer whose structure file failed to load is held as the failed structure the model recorded, in the order
        the layers apply. Skill entries use the reserved `skills` corpus; resources have no corpus governance.
        `None` when no specification governs the item.

        Carry-over: kept for the next revision whenever the next model's governance of the ref is equal to it, as
        compared by value, so a change elsewhere in the model leaves it, and every analysis reading it, valid.

        Args:
            ref: The item to look up; the cache key.

        Raises:
            UnlistedItemError: If the reference is not a listed item, registered resource or answerable document path.
        """
        self._answerable(ref)
        return self._governance_of(ref)

    def _governance_of(self, ref: MarkdownItemRef) -> Governance | None:
        """The governance of an item the database already resolved, listed or not, found once."""
        if ref not in self._item_governances:
            self._item_governances[ref] = self._known(ref).governance
        return self._item_governances[ref]

    def item_structure_specs(self, ref: MarkdownItemRef) -> tuple[StructureSpec, ...]:
        """The structure specifications of the layers that loaded for a corpus document or skill entry.

        Not cached: the answer is read off `item_governance(ref)`, which is, so it carries over with it. Resources
        and specifications have no corpus structure specs.

        Raises:
            UnlistedItemError: If the reference is not a listed item, registered resource or answerable document path.
        """
        governance = self.item_governance(ref)
        return governance.structure_specs() if governance is not None else ()

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
        query: Query[T] | SymlinkQuery[T] | CorpusDirectoryQuery[T] | SchemaQuery[T],
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
        key = cast('QueryKey', (query, ref))
        if key not in self._queries:
            match ref:
                case MarkdownItemRef():
                    primitives = _ReadPrimitives(self, ref)
                    answer = cast('Query[T]', query)(primitives)
                case SymlinkRef():
                    primitives = _ReadSymlinkPrimitives(self, ref)
                    answer = cast('SymlinkQuery[T]', query)(primitives)
                case CorpusDirectoryRef():
                    primitives = _ReadCorpusDirectoryPrimitives(self, ref)
                    answer = cast('CorpusDirectoryQuery[T]', query)(primitives)
                case SchemaReference():
                    primitives = _ReadSchemaPrimitives(self, ref)
                    answer = cast('SchemaQuery[T]', query)(primitives)
                case _:
                    assert_never(ref)
            self._queries[key] = (answer, primitives._recorded_reads())
        return cast('T', self._queries[key][0])

    def query_reads(
        self,
        query: Query[object] | SymlinkQuery[object] | CorpusDirectoryQuery[object] | SchemaQuery[object],
        ref: MarkdownItemRef | SymlinkRef | CorpusDirectoryRef | SchemaReference,
    ) -> frozenset[ReadKey]:
        """The typed read keys recorded for a query; public so nested queries avoid private-cache access.

        Args:
            query: The declared query whose reads are requested.
            ref: The typed subject the query was run against.
        """
        key = cast('QueryKey', (query, ref))
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
