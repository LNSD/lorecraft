"""One frozen state of a workspace: its snapshot, and the cached data every check, and every command, reads through.

The layering follows an IDE's. The `Snapshot` plays the virtual file system: every byte a
check can see, and never changed once built. Above it sit the queries, each computed on first use and kept for as
long as the database lives (pattern-memoization). They come in two kinds, and the kind decides how a query carries
over to the next revision.

Input queries read the snapshot. Each is the one place its part of the snapshot becomes a value, so only an input
query builds a witness or fails to read, and each states its own carry-over rule against the change set:

- `model()`: the workspace model, like the IDE's project model. It reads the structure of the snapshot, the
  specifications, the corpus directories, the skills directories, the directories a command named to check the
  skills in, as the snapshot's scope records them, and the listing of each skill's directory, nothing deeper inside
  a skill, and no document's contents.
  Among that structure it records each skills directory, skill entry and `SKILL.md` whose symlink chain leaves the
  repository.
- `text(ref)`: one document's bytes decoded as UTF-8, like the IDE's document text for a file: a `DocumentText`
  witness, or an `Undecodable` marker when the bytes are not UTF-8. It is the one place a document's bytes become
  text, and it reads that document's bytes and nothing else.
- `skill_text(ref)`: one skill's `SKILL.md` decoded, the same document text: a `SkillText` witness, or an
  `Undecodable` marker. It reads that skill's bytes and nothing else.
- `skill_resources(skill)`: one skill's resources, the Markdown files inside it other than its top-level `SKILL.md`,
  like the IDE's listing of a content root's children, and the symlinks inside it whose chain leaves the
  repository. It reads the listings and the symlink targets reached from that skill, and where the model locates
  the skill, and no file's content.
- `skill_resource_text(resource)`: one resource decoded, the same document text: a `SkillResourceText` witness, or an
  `Undecodable` marker. It reads that resource's bytes, and where its skill's listing locates it, and nothing else.
- The `ScopeIndex` behind `is_in_scope(path)`: the scope the snapshot records it was taken of, expanded once
  through the links it recorded, like the IDE's index of a project's content roots. It reads the snapshot's
  scope, links and climbed directories and nothing else, and no caller reaches it but `is_in_scope`.

Derived queries read the results of other queries and never the snapshot. Each hands what it read to one function
of this package that computes the value, so its arguments are its read set, and it carries over whenever every query
it read does:

- `frontmatter(source)`: one document's frontmatter node, like a stub: the part of a file the IDE reads without
  building its full syntax tree. It reads the text of the witness `text(ref)` returned and nothing else.
- `parse(source)`: one document's parse tree, like the IDE's syntax tree of a file or a per-file index entry. It
  reads the text of the witness and nothing else.
- `tokens(source)`: what one document's whole file costs an agent that loads it, like another per-file index
  entry: counted from the raw text, frontmatter and code included, without a parse. It reads the text of the
  witness `text(ref)` returned and nothing else.
- `document_lines(source)`: how many lines one document's whole file holds, like `tokens(source)`: counted from the
  raw text, frontmatter included, without a parse. It reads the text of the witness `text(ref)` returned and nothing
  else.
- `schema_problems(source)`: what each frontmatter schema that governs one document rejects in its frontmatter, each
  problem placed on its line, like an analysis the IDE runs once over a file and every inspection then reads. It reads
  `frontmatter(source)` and the frontmatter schemas the model records for the document, and nothing else.
- `outline_divergences(source)`: where one document's sections first stop matching each outline that governs it, the
  same kind of shared analysis. It reads `parse(source)`, `document_lines(source)` and the outlines the model records
  for the document, and nothing else.
- `skill_frontmatter(source)`: one skill's frontmatter node, the same stub for a `SKILL.md`. It reads the text of
  the witness `skill_text(ref)` returned and nothing else.
- `skill_parse(source)`: one skill's parse tree, the same syntax tree for a `SKILL.md`. It reads the text of the
  witness and nothing else.
- `skill_lines(source)`: how many lines one skill's `SKILL.md` holds, like `tokens(source)` for a document: counted
  from the raw text, frontmatter included, without a parse. It reads the text of the witness and nothing else.
- `skill_schema_problems(source)`: what the Agent Skills specification rejects in one skill's frontmatter, the same
  analysis as `schema_problems(source)` for a document. It reads `skill_frontmatter(source)` and nothing else: the
  package states the specification, so no specification in the repository plays a part.
- `skill_resource_parse(source)`: one resource's parse tree, the same syntax tree again. It reads the text of the
  witness `skill_resource_text(resource)` returned and nothing else.

Three questions are asked of the snapshot's records directly and their answers are never cached, since an answer
for one path is cheap:

- `find_path(path)` and `find_file(path)`: where a path leads in the snapshot, like a lookup in the IDE's virtual
  file system. They read the snapshot's records and nothing else and build nothing worth keeping.
- `is_in_scope(path)`: whether the scan reads the directory a path sits in, like the IDE asking whether a file
  is in the project's content roots. It is configuration, not content: answered from the `ScopeIndex` cached
  above, built on the first call, with the path walked through the snapshot's recorded links to tell where it
  leads, and never from which directories the snapshot holds. The index is what costs, so it is kept; the
  answer for one path is cheap, so it is not.

Every query about one file's content takes the witness its decode query returned, never a bare ref, so a fact of a
file that is not UTF-8 cannot be asked for: a reader matches the decode once and no later reader carries a branch for
it. Each still caches by the witness's ref.

Checks are pure functions of the values a run reads for them through the database, like an inspection run over one
file: the run matches each file's decode once and hands a check only the part it judges. It asks for the cheapest
query that holds what a check reads, so a check that needs only the frontmatter never pays for the full
parse, and every check reading the same query shares one computation of it. Their results are not cached; a
check runs again every time.

Nothing here records what a cached value read, so no dependency is tracked. Invalidation is written by hand instead, the
way the IDE drops per-file index entries on a file change event and resets structural caches on a project model change.
Reserved, not implemented: `advance(snapshot) -> Database`, the next state. It would `diff` the two snapshots and carry
over each cached value the change set leaves valid: the decoded text, the frontmatter, the parse, the token count and
the line count of every document whose bytes did not change, and its schema problems and outline divergences too when
the model carries over, the decoded text, the frontmatter, the parse, the line count and the schema problems of every
skill whose bytes did not, the resources of every skill and the decoded text and the parse of every resource as their
own docstrings state, and the model unless one of these changes invalidates it. An entry added or deleted under `docs/`
invalidates it. So does an entry added or deleted in a skills directory, or in a skill's directory, both where the
skill's entry names it and where a link leads it. So does an entry added or deleted at the resolved path a skill's
linked `SKILL.md` leads to, or on the way to it, since the loader resolves that link to find the skill. So does a link
on the way to a skill or to its `SKILL.md` that changed its target, and so does a changed specification. So does a link
that changed its target on the chain of a skills directory an agent declares, of an entry in a skills directory, or of
an entry's `SKILL.md`, a chain leaving the repository included, since the model records the link each such chain leaves
through and its target. So does a directory added or deleted that a `..` on such a chain climbs out of: deleting `tmp`
leaves `x -> tmp/../alpha` leading nowhere, and the change set shows `tmp` go, since the snapshot records each climbed
directory and the next scan, stopping at the missing `tmp`, no longer records it. The directories a command named are
read from the snapshot's scope, so a scope that adds or drops one invalidates the model too, and each counts as a skills
directory for every rule above, a `SKILL.md` at its root as an entry's. Any other change leaves the model valid, an
entry added or deleted anywhere else inside a skill included: the model lists nothing below a skill's directory, and
reads nothing there but the way to its `SKILL.md`. The scope index carries over unless the two snapshots' scopes, links
or climbed directories differ, compared as recorded rather than through the change set, which holds no scope. A change
of scope invalidates nothing else but the model, when it adds or drops a named directory: what the new scope adds or
drops reaches the model and each skill's resources as entries in the change set. That rule holds only while the decoded
text reads its own document, skill or resource, the frontmatter, the parse, the token count and the line count each read
only the decoded text of their own, the schema problems and the outline divergences read only their own document's
frontmatter, or parse and line count, and the model, a skill's schema problems only its own frontmatter, the model and
each skill's resource listing read no document, and the scope index reads only the scope, the links and the climbed
directories, so keep them that way: data drawn from several documents belongs in a new cache with its own rule.

A change names a resolved path, while a ref may name a path through a link: a skill's `SKILL.md` under a linked
skill entry changes at the path the link leads to, not at the ref's. A snapshot maps a linked path to its resolved one
and not back, so the model records each skill's `SkillLocation`, the resolved `SKILL.md` its ref leads to, and
`advance` would look that path up in the change set. A link retargeted to another skill leaves every file's bytes as
they were and the ref as it was, like a file's identity in the IDE, while its location changes. So a skill's
decoded text, its frontmatter, its parse and its line count carry over only when the two models locate its ref at the
same resolved file and that file's bytes did not change. A resource is named the same way, through the symlinks on
the way to it, and its `SkillResourceLocation` records the resolved file: its decoded text and its parse carry over
only when the two databases' `skill_resources` locate its ref at the same resolved file and that file's bytes did not
change.
"""

from lorecraft.core.path import RootRelativePath
from lorecraft.project.document import DocumentDecodeError, DocumentRef
from lorecraft.project.document import Repository as DocumentRepository
from lorecraft.project.layout import named_dirs_of_scope, reject_linked_layout
from lorecraft.project.schemas import (
    OutlineDivergenceSpec,
    SchemaProblems,
    locate_schema_problems,
    locate_skill_schema_problems,
    match_outlines,
)
from lorecraft.project.skill import Repository as SkillRepository
from lorecraft.project.skill import (
    SkillDecodeError,
    SkillLocation,
    SkillRef,
    SkillResourceDecodeError,
    SkillResourceListing,
    SkillResourceLocation,
    SkillResourceRef,
)
from lorecraft.project.syntax import (
    FrontmatterNode,
    ParsedDocument,
    count_lines,
    count_tokens,
    parse_document,
    parse_frontmatter,
)
from lorecraft.project.workspace import WorkspaceModel, load_model
from lorecraft.vfs import ResolvedPath, ScopeIndex, Snapshot, VirtualFileSystem

from .text import DocumentText, SkillResourceText, SkillText, Undecodable


class Database:
    """What the checks read from one snapshot, each computed once and cached for the snapshot's lifetime.

    That is the workspace model, the decoded text, the frontmatter, the parse trees, the token counts, the line
    counts, the schema problems and the outline divergences of the documents, the decoded text, the frontmatter, the
    parse trees, the line counts and the schema problems of the skills, the resources of each skill with their decoded
    text and their parse trees, and the scope index `is_in_scope` answers from.
    """

    def __init__(self, snapshot: Snapshot) -> None:
        """Index the snapshot for reading; performs no I/O and computes nothing yet.

        Args:
            snapshot: The frozen state every query reads; kept for the database's lifetime and never changed.
        """
        self._snapshot = snapshot
        self._fs = VirtualFileSystem(snapshot)
        self._documents = DocumentRepository(self._fs)
        self._skills = SkillRepository(self._fs)
        # `None` until the first `model()` call; a loaded model is never `None`, so the two cannot be confused.
        self._model: WorkspaceModel | None = None
        # `None` until the first `is_in_scope()` call, as `_model` is until the first `model()` call.
        self._scope_index: ScopeIndex | None = None
        self._texts: dict[DocumentRef, DocumentText | Undecodable] = {}
        self._frontmatters: dict[DocumentRef, FrontmatterNode] = {}
        self._parses: dict[DocumentRef, ParsedDocument] = {}
        self._token_counts: dict[DocumentRef, int] = {}
        self._line_counts: dict[DocumentRef, int] = {}
        self._schema_problems: dict[DocumentRef, tuple[SchemaProblems, ...]] = {}
        self._outline_divergences: dict[DocumentRef, tuple[OutlineDivergenceSpec, ...]] = {}
        self._skill_texts: dict[SkillRef, SkillText | Undecodable] = {}
        self._skill_frontmatters: dict[SkillRef, FrontmatterNode] = {}
        self._skill_parses: dict[SkillRef, ParsedDocument] = {}
        self._skill_line_counts: dict[SkillRef, int] = {}
        self._skill_schema_problems: dict[SkillRef, tuple[SchemaProblems, ...]] = {}
        self._skill_resources: dict[SkillRef, SkillResourceListing] = {}
        self._skill_resource_texts: dict[SkillResourceRef, SkillResourceText | Undecodable] = {}
        self._skill_resource_parses: dict[SkillResourceRef, ParsedDocument] = {}

    def model(self) -> WorkspaceModel:
        """The workspace model the snapshot declares, loaded on the first call.

        The directories a command named to check the skills in are read from the scope the snapshot records, the
        roots beyond `SNAPSHOT_SCOPE`'s, so the model is a function of the snapshot alone.

        Carry-over: kept for the next revision unless one of these changed, as the module docstring details:

        - An entry added or deleted under `docs/`, or a changed specification.
        - An entry added or deleted in a skills directory or a named directory, in a skill's directory, or at or
          on the way to the resolved path a skill's linked `SKILL.md` leads to.
        - A link that changed its target on the way to a skill or its `SKILL.md`, or on the chain of a skills
          directory an agent declares, a named directory, an entry of either, or such an entry's `SKILL.md`, a
          chain leaving the repository included; and a directory added or deleted that a `..` on such a chain
          climbs out of.
        - The scope, where a named directory was added or dropped.

        A load that fails is not cached, so each call raises the same error again.

        Raises:
            DirListError: If the specification directory or docs/ cannot be listed.
            CorpusListError: If a corpus directory cannot be listed.
            StructureSchemaReadError: If any structure specification cannot be read.
            StructureSpecDecodeError: If a structure specification is not JSON in the dialect's shape.
            EmptyStructureSpecError: If a structure specification states no rule.
            RepeatedOutlineSectionError: If an outline names a section twice.
            RepeatedForbiddenSectionError: If a specification forbids a section twice.
            ForbiddenOutlineSectionError: If a specification forbids a section its outline names.
            AdjacentAnyRunsError: If an outline places two `any` runs side by side.
            InvalidTitlePatternError: If a title's pattern does not compile.
            InvalidFrontmatterSchemaError: If a frontmatter schema is rejected by the meta-schema.
            FrontmatterSchemaIdError: If a schema in a frontmatter schema carries `$id`.
            ForeignFrontmatterDialectError: If a schema in a frontmatter schema names another dialect.
            UntypedFrontmatterSchemaError: If a frontmatter schema's root does not state an object.
            DirResolveError: If a skills directory or a named directory cannot be resolved.
            EntryInspectError: If an entry on the way to a skills directory cannot be inspected, or a link's
                target read, while looking for where it leaves the repository.
            SkillsDirListError: If a skills directory cannot be listed.
            SkillEntryResolveError: If a symlinked skill entry cannot be resolved.
            SkillDirListError: If a skill directory cannot be listed.
            SkillFileResolveError: If a symlinked SKILL.md cannot be resolved.
        """
        if self._model is None:
            self._model = load_model(self._fs, named_dirs=named_dirs_of_scope(self._snapshot.scope))
        return self._model

    def reject_linked_layout(self) -> None:
        """Refuse a snapshot in which ``docs/`` or ``docs/__meta__/`` is a symlink; never cached.

        Behind a linked ``docs/`` or ``docs/__meta__/`` the snapshot holds no specification, so the model has no
        corpus, and a run over its documents would report success over nothing. Kept apart from ``model()``, which
        also lists the skills: a caller that reads only skills has no reason to refuse a linked ``docs/``.

        Raises:
            LinkedLayoutError: If ``docs/`` is a symlink, or else if ``docs/__meta__/`` is one.
        """
        reject_linked_layout(self._fs)

    def find_path(self, path: RootRelativePath) -> ResolvedPath | None:
        """Where `path` leads in the snapshot, every recorded link on the way followed; never cached.

        Like the IDE's lookup of a path in its virtual file system: a path handed in from outside, such as a
        command line argument, is interpreted in the same frozen tree every check reads, not on the live disk.

        Args:
            path: The path to look up, relative to the snapshot root; it may name a directory or a file.

        Returns:
            The resolved directory or the resolved file, root-relative, or `None` when the snapshot holds
            neither there.
        """
        directory = self._fs.find_dir(path)
        if directory is not None:
            return directory
        return self._fs.find_file(path)

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
        `path` leads. A snapshot that scanned nothing, such as one built by `Snapshot.from_tree`, has no path in
        scope.

        The answer is not cached, but what it is computed from is: the scope expanded through the recorded
        links, a `ScopeIndex` built on the first call and asked on every later one.

        Args:
            path: The entry to ask about, relative to the snapshot root; it need not exist.
        """
        if self._scope_index is None:
            self._scope_index = ScopeIndex(self._snapshot)
        return self._scope_index.is_in_scope(path)

    def text(self, ref: DocumentRef) -> DocumentText | Undecodable:
        """One document's bytes decoded as UTF-8, read from the snapshot on the first call for its ref.

        The one place a document's bytes become text: every other query about the document takes the witness this
        returns. A document that is not UTF-8 is cached as `Undecodable` like any answer, so it is decoded once.

        Carry-over: kept for the next revision only when the document's bytes did not change.

        A document that cannot be read is not cached, so each call raises the same error again.

        Args:
            ref: The document to decode; the cache key, so one ref is decoded once.

        Returns:
            The witness, or `Undecodable` when the document is present but not UTF-8: such bytes are a finding
            about the file, on the same side of the line as invalid YAML, not the failure to read it a missing file
            is.

        Raises:
            DocumentReadError: If the snapshot holds no regular file at the document's path.
        """
        source = self._texts.get(ref)
        if source is None:
            try:
                source = DocumentText(ref, self._documents.get_document(ref).text)
            except DocumentDecodeError:
                source = Undecodable(ref)
            self._texts[ref] = source
        return source

    def frontmatter(self, source: DocumentText) -> FrontmatterNode:
        """The frontmatter of one document, parsed from its decoded text on the first call for its ref. Raises nothing.

        Cached apart from `parse(source)`, which does not hold the frontmatter: the block is decoded here alone.

        Carry-over: kept for the next revision whenever `text(source.ref)` is.

        Args:
            source: The document's text, as `text(ref)` returns it; its ref is the cache key, so one ref is parsed
                once.
        """
        decoded = self._frontmatters.get(source.ref)
        if decoded is None:
            decoded = parse_frontmatter(source.text)
            self._frontmatters[source.ref] = decoded
        return decoded

    def parse(self, source: DocumentText) -> ParsedDocument:
        """The parse tree of one document, parsed from its decoded text on the first call for its ref. Raises nothing.

        Carry-over: kept for the next revision whenever `text(source.ref)` is.

        Args:
            source: The document's text, as `text(ref)` returns it; its ref is the cache key, so one ref is parsed
                once.
        """
        parsed = self._parses.get(source.ref)
        if parsed is None:
            parsed = parse_document(source.text)
            self._parses[source.ref] = parsed
        return parsed

    def tokens(self, source: DocumentText) -> int:
        """The tokens in one document's whole file, counted on the first call for its ref. Raises nothing.

        Cached apart from `parse(source)` and never read from it: the count needs the raw text, not the tree, so
        a check that needs only one of the two never pays for the other.

        Carry-over: kept for the next revision whenever `text(source.ref)` is.

        Args:
            source: The document's text, as `text(ref)` returns it; its ref is the cache key, so one ref is counted
                once.
        """
        count = self._token_counts.get(source.ref)
        if count is None:
            count = count_tokens(source.text)
            self._token_counts[source.ref] = count
        return count

    def document_lines(self, source: DocumentText) -> int:
        """The lines in one document's whole file, counted on the first call for its ref. Raises nothing.

        Cached apart from `parse(source)` and never read from it, as `tokens(source)` is: the count needs the raw
        text, frontmatter included, not the tree.

        Carry-over: kept for the next revision whenever `text(source.ref)` is.

        Args:
            source: The document's text, as `text(ref)` returns it; its ref is the cache key, so one ref is counted
                once.
        """
        count = self._line_counts.get(source.ref)
        if count is None:
            count = count_lines(source.text)
            self._line_counts[source.ref] = count
        return count

    def schema_problems(self, source: DocumentText) -> tuple[SchemaProblems, ...]:
        """What each frontmatter schema that governs one document rejects in its frontmatter, found on the first call.

        Each problem is placed on the line its field is written on, or line 1 when it has none. The frontmatter is
        read only when a schema governs the document.

        Carry-over: kept for the next revision whenever `frontmatter(source)` is and the model is.

        Args:
            source: The document's text, as `text(ref)` returns it; its ref is the cache key, so one ref is
                validated once.

        Returns:
            One entry per frontmatter schema that governs the document, in the order the schemas apply, each naming
            the structure specification that states it; none when no schema governs it, or when its block is
            missing, not YAML or not a mapping, which no schema can hold.

        Raises:
            DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
            CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
            StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
            StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in
                the dialect's shape.
            EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
            RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
            RepeatedForbiddenSectionError: If the model is not loaded yet and a specification forbids a section
                twice.
            ForbiddenOutlineSectionError: If the model is not loaded yet and a specification forbids a section its
                outline names.
            AdjacentAnyRunsError: If the model is not loaded yet and an outline places two `any` runs side by side.
            InvalidTitlePatternError: If the model is not loaded yet and a title's pattern does not compile.
            InvalidFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema is rejected by
                the meta-schema.
            FrontmatterSchemaIdError: If the model is not loaded yet and a schema in a frontmatter schema carries
                `$id`.
            ForeignFrontmatterDialectError: If the model is not loaded yet and a schema in a frontmatter schema
                names another dialect.
            UntypedFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema's root does not
                state an object.
            DirResolveError: If the model is not loaded yet and a skills directory or a named directory cannot be
                resolved.
            EntryInspectError: If the model is not loaded yet and an entry on the way to a skills directory cannot
                be inspected, or a link's target read, while looking for where it leaves the repository.
            SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
            SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
            SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
            SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
        """
        found = self._schema_problems.get(source.ref)
        if found is None:
            schemas = self.model().frontmatter_schemas_of(source.ref)
            if schemas:
                found = locate_schema_problems(self.frontmatter(source), schemas)
            else:
                found = ()
            self._schema_problems[source.ref] = found
        return found

    def outline_divergences(self, source: DocumentText) -> tuple[OutlineDivergenceSpec, ...]:
        """Where one document's sections first stop matching each outline that governs it, found on the first call.

        The document is parsed, and its lines counted, only when a structure specification that governs it states an
        outline.

        Carry-over: kept for the next revision whenever `parse(source)` and `document_lines(source)` are and the model
        is.

        Args:
            source: The document's text, as `text(ref)` returns it; its ref is the cache key, so one ref is matched
                once.

        Returns:
            One entry per structure specification that governs the document and states an outline, in the order the
            specifications apply; none when no outline governs it.

        Raises:
            DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
            CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
            StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
            StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in
                the dialect's shape.
            EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
            RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
            RepeatedForbiddenSectionError: If the model is not loaded yet and a specification forbids a section
                twice.
            ForbiddenOutlineSectionError: If the model is not loaded yet and a specification forbids a section its
                outline names.
            AdjacentAnyRunsError: If the model is not loaded yet and an outline places two `any` runs side by side.
            InvalidTitlePatternError: If the model is not loaded yet and a title's pattern does not compile.
            InvalidFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema is rejected by
                the meta-schema.
            FrontmatterSchemaIdError: If the model is not loaded yet and a schema in a frontmatter schema carries
                `$id`.
            ForeignFrontmatterDialectError: If the model is not loaded yet and a schema in a frontmatter schema
                names another dialect.
            UntypedFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema's root does not
                state an object.
            DirResolveError: If the model is not loaded yet and a skills directory or a named directory cannot be
                resolved.
            EntryInspectError: If the model is not loaded yet and an entry on the way to a skills directory cannot
                be inspected, or a link's target read, while looking for where it leaves the repository.
            SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
            SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
            SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
            SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
        """
        divergences = self._outline_divergences.get(source.ref)
        if divergences is None:
            outline_specs = self.model().outline_specs_of(source.ref)
            if outline_specs:
                divergences = match_outlines(outline_specs, self.parse(source).headings, self.document_lines(source))
            else:
                divergences = ()
            self._outline_divergences[source.ref] = divergences
        return divergences

    def skill_text(self, ref: SkillRef) -> SkillText | Undecodable:
        """One skill's `SKILL.md` decoded as UTF-8, read from the snapshot on the first call for its ref.

        The one place a `SKILL.md`'s bytes become text: every other query about it takes the witness this returns.
        A `SKILL.md` that is not UTF-8 is cached as `Undecodable` like any answer, so it is decoded once.

        Carry-over: kept for the next revision only when the next model locates the ref at the same resolved `SKILL.md`
        and that file's bytes did not change.

        A skill that cannot be read is not cached, so each call raises the same error again.

        Args:
            ref: The skill whose `SKILL.md` is decoded; the cache key, so one ref is decoded once.

        Returns:
            The witness, or `Undecodable` when the `SKILL.md` is present but not UTF-8: such bytes are a finding
            about the file, on the same side of the line as invalid YAML, not the failure to read it a missing file
            is.

        Raises:
            SkillReadError: If the snapshot holds no regular file at the skill's path.
        """
        source = self._skill_texts.get(ref)
        if source is None:
            try:
                source = SkillText(ref, self._skills.get_skill(ref).text)
            except SkillDecodeError:
                source = Undecodable(ref)
            self._skill_texts[ref] = source
        return source

    def skill_frontmatter(self, source: SkillText) -> FrontmatterNode:
        """The frontmatter of one skill's `SKILL.md`, parsed on the first call for its ref. Raises nothing.

        Carry-over: kept for the next revision whenever `skill_text(source.ref)` is.

        Args:
            source: The skill's `SKILL.md` text, as `skill_text(ref)` returns it; its ref is the cache key, so one ref
                is parsed once.
        """
        decoded = self._skill_frontmatters.get(source.ref)
        if decoded is None:
            decoded = parse_frontmatter(source.text)
            self._skill_frontmatters[source.ref] = decoded
        return decoded

    def skill_parse(self, source: SkillText) -> ParsedDocument:
        """The parse tree of one skill's `SKILL.md`, parsed on the first call for its ref. Raises nothing.

        Cached apart from `skill_frontmatter(source)`, and holds no frontmatter, as a document's parse holds none.

        Carry-over: kept for the next revision whenever `skill_text(source.ref)` is.

        Args:
            source: The skill's `SKILL.md` text, as `skill_text(ref)` returns it; its ref is the cache key, so one ref
                is parsed once.
        """
        parsed = self._skill_parses.get(source.ref)
        if parsed is None:
            parsed = parse_document(source.text)
            self._skill_parses[source.ref] = parsed
        return parsed

    def skill_lines(self, source: SkillText) -> int:
        """The lines in one skill's whole `SKILL.md`, counted on the first call for its ref. Raises nothing.

        Cached apart from `skill_parse(source)` and never read from it, as a document's token count is from its
        parse: the count needs the raw text, frontmatter included, not the tree.

        Carry-over: kept for the next revision whenever `skill_text(source.ref)` is.

        Args:
            source: The skill's `SKILL.md` text, as `skill_text(ref)` returns it; its ref is the cache key, so one ref
                is counted once.
        """
        count = self._skill_line_counts.get(source.ref)
        if count is None:
            count = count_lines(source.text)
            self._skill_line_counts[source.ref] = count
        return count

    def skill_schema_problems(self, source: SkillText) -> tuple[SchemaProblems, ...]:
        """What the Agent Skills specification rejects in a skill's frontmatter, found once. Raises nothing.

        Each problem is placed on the line its field is written on, or line 1 when it has none. The package states
        the specification, so every skill is held to it and no specification in the repository plays a part.

        Carry-over: kept for the next revision whenever `skill_frontmatter(source)` is.

        Args:
            source: The skill's `SKILL.md` text, as `skill_text(ref)` returns it; its ref is the cache key, so one ref
                is validated once.

        Returns:
            One entry, for the Agent Skills specification; none when the block is missing, not YAML or not a
            mapping, which no schema can hold.
        """
        found = self._skill_schema_problems.get(source.ref)
        if found is None:
            found = locate_skill_schema_problems(self.skill_frontmatter(source))
            self._skill_schema_problems[source.ref] = found
        return found

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

    # Takes the location its listing issued where `text` and `skill_text` take a ref: the model locates a document
    # or a `SKILL.md` by its ref, but only the skill's resource listing locates a resource's file.
    def skill_resource_text(self, resource: SkillResourceLocation) -> SkillResourceText | Undecodable:
        """One resource of a skill decoded as UTF-8, read from the snapshot on the first call for its ref.

        The resource is read at the resolved file its location records, as `skill_resources` lists it, never at
        `resource.ref.path`. The one place a resource's bytes become text: every other query about it takes the
        witness this returns. A resource that is not UTF-8 is cached as `Undecodable` like any answer, so it is
        decoded once.

        Carry-over: kept for the next revision only when the next `skill_resources` of its skill locates the ref at
        the same resolved file and that file's bytes did not change.

        A resource that cannot be read is not cached, so each call raises the same error again.

        Args:
            resource: The resource to decode, as `skill_resources` locates it; its ref is the cache key, so one ref
                is decoded once.

        Returns:
            The witness, or `Undecodable` when the resource is present but not UTF-8: such bytes are a finding
            about the file, on the same side of the line as invalid YAML, not the failure to read it a missing file
            is.

        Raises:
            SkillResourceReadError: If the snapshot holds no regular file at the resolved file the ref leads to.
        """
        source = self._skill_resource_texts.get(resource.ref)
        if source is None:
            try:
                source = SkillResourceText(resource.ref, self._skills.get_skill_resource(resource).text)
            except SkillResourceDecodeError:
                source = Undecodable(resource.ref)
            self._skill_resource_texts[resource.ref] = source
        return source

    def skill_resource_parse(self, source: SkillResourceText) -> ParsedDocument:
        """The parse tree of one resource of a skill, parsed on the first call for its ref. Raises nothing.

        Carry-over: kept for the next revision whenever `skill_resource_text` keeps the text of `source.ref`.

        Args:
            source: The resource's text, as `skill_resource_text(resource)` returns it; its ref is the cache key, so one
                ref is parsed once.
        """
        parsed = self._skill_resource_parses.get(source.ref)
        if parsed is None:
            parsed = parse_document(source.text)
            self._skill_resource_parses[source.ref] = parsed
        return parsed
