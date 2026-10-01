"""One frozen state of a workspace: its snapshot, and the cached data every check, and every command, reads through.

The layering follows the IntelliJ Platform's. The `Snapshot` plays the virtual file system: every byte a
check can see, and never changed once built. Above it sit two kinds of cached data, each computed on first
use and kept for as long as the database lives (pattern-memoization):

- `model()`: the workspace model, like the IDE's project model. It reads the structure of the snapshot, the
  specifications, the corpus directories, the skills directories and the listing of each skill's directory,
  nothing deeper inside a skill, and no document's contents.
- `frontmatter(ref)`: one document's frontmatter node, like a stub: the part of a file the IDE reads without
  building its full syntax tree. It reads that document's bytes and nothing else.
- `parse(ref)`: one document's parse tree, like a PSI file or a per-file index entry. It reads that
  document's bytes and nothing else.
- `skill_frontmatter(ref)`: one skill's frontmatter node, the same stub for a `SKILL.md`. It reads that
  skill's bytes and nothing else.
- `skill_parse(ref)`: one skill's parse tree, the same PSI file for a `SKILL.md`. It reads that skill's bytes
  and nothing else.
- `skill_resources(ref)`: one skill's resources, the Markdown files inside it other than its top-level `SKILL.md`,
  like the IDE's listing of a content root's children. It reads the listings and the symlink targets reached from
  that skill, and where the model locates the skill, and no file's content.
- `skill_resource_parse(ref)`: one resource's parse tree, the same PSI file again. It reads that resource's bytes,
  and where its skill's listing locates it, and nothing else.
- `tokens(ref)`: what one document's whole file costs an agent that loads it, like another per-file index
  entry: counted from the raw text, frontmatter and code included, without a parse. It reads that document's
  bytes and nothing else.
- The `ScopeIndex` behind `is_in_scope(path)`: the scope the snapshot records it was taken of, expanded once
  through the links it recorded, like the IDE's index of a project's content roots. It reads the snapshot's
  scope and links and nothing else, and no caller reaches it but `is_in_scope`.

Three questions are asked of the snapshot's records directly and their answers are never cached, since an answer
for one path is cheap:

- `resolve(path)` and `find_real_file(path)`: where a path leads in the snapshot, like a lookup in the IDE's
  virtual file system. They read the snapshot's records and nothing else and build nothing worth keeping.
- `is_in_scope(path)`: whether the scan reads the directory a path sits in, like the IDE asking whether a file
  is in the project's content roots. It is configuration, not content: answered from the `ScopeIndex` cached
  above, built on the first call, with the path walked through the snapshot's recorded links to tell where it
  leads, and never from which directories the snapshot holds. The index is what costs, so it is kept; the
  answer for one path is cheap, so it is not.

Checks are plain functions of a database and a ref, like an inspection run over one file. Each asks for the
cheapest query that holds what it reads, so a check that needs only the frontmatter never pays for the full
parse, and every check reading the same query shares one computation of it. Their results are not cached; a
check runs again every time.

Nothing here records what a cached value read, so no dependency is tracked. Invalidation is written by hand instead,
the way the IDE drops per-file index entries on a file change event and resets structural caches on a project model
change. Reserved, not implemented: `advance(snapshot) -> Database`, the next state. It would `diff` the two
snapshots and carry over each cached value the change set leaves valid: the frontmatter, the parse and the token
count of every document whose bytes did not change, the frontmatter and the parse of every skill whose bytes did
not, the resources of every skill and the parse of every resource as their own docstrings state, and the
model unless one of these changes invalidates it. An entry added or deleted under `docs/` invalidates it. So does
an entry added or deleted in a skills directory, or in a skill's directory, both where the skill's entry names it
and where a link leads it. So does an entry added or deleted at the real path a skill's linked `SKILL.md` leads to,
or on the way to it, since the loader resolves that link to find the skill. So does a link on the way to a skill or
to its `SKILL.md` that changed its target, and so does a changed specification. Any other change leaves the model
valid, an entry added or deleted anywhere else inside a skill included: the model lists nothing below a skill's
directory, and reads nothing there but the way to its `SKILL.md`. The scope index carries over unless the two
snapshots' scopes or their links differ, compared as recorded rather than through the change set, which holds no
scope. A change of scope invalidates nothing else: what the new scope adds or drops reaches the model and each
skill's resources as entries in the change set. That rule holds only while the frontmatter, the parse and the token
count each read their own document, skill or resource, the model and each skill's resource listing read no
document, and the scope index reads only the scope and the links, so keep them that way: data drawn from several
documents belongs in a new cache with its own rule.

A change names a real path, while a ref may name a path through a link: a skill's `SKILL.md` under a linked
skill entry changes at the path the link leads to, not at the ref's. A snapshot maps a linked path to its real
one and not back, so the model records each skill's `SkillLocation`, the real `SKILL.md` its ref leads to,
and `advance` would look that path up in the change set. A link retargeted to another skill leaves every file's
bytes as they were and the ref as it was, like a file's identity in the IDE, while its location changes. So a
skill's frontmatter and its parse carry over only when the two models locate its ref at the same real file and that
file's bytes did not change. A resource is named the same way, through the symlinks on the way to it, and its
`SkillResourceLocation` records the real file: its parse carries over only when the two databases'
`skill_resources` locate its ref at the same real file and that file's bytes did not change.
"""

from lorecraft.core.path import RootRelativePath
from lorecraft.project.document import DocumentRef
from lorecraft.project.document import Repository as DocumentRepository
from lorecraft.project.layout import require_real_layout
from lorecraft.project.skill import Repository as SkillRepository
from lorecraft.project.skill import SkillRef, SkillResourceLocation, SkillResourceRef
from lorecraft.project.syntax import FrontmatterNode, ParsedDocument, count_tokens, parse_document, parse_frontmatter
from lorecraft.project.workspace import WorkspaceModel, load_model
from lorecraft.vfs import ScopeIndex, Snapshot, VirtualFileSystem


class Database:
    """What the checks read from one snapshot, each computed once and cached for the snapshot's lifetime.

    That is the workspace model, the frontmatter, the parse trees and the token counts of the documents, the
    frontmatter and the parse trees of the skills, the resources of each skill and their parse trees, and
    the scope index `is_in_scope` answers from.
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
        self._frontmatters: dict[DocumentRef, FrontmatterNode] = {}
        self._parses: dict[DocumentRef, ParsedDocument] = {}
        self._token_counts: dict[DocumentRef, int] = {}
        self._skill_frontmatters: dict[SkillRef, FrontmatterNode] = {}
        self._skill_parses: dict[SkillRef, ParsedDocument] = {}
        self._skill_resources: dict[SkillRef, tuple[SkillResourceLocation, ...]] = {}
        self._skill_resource_parses: dict[SkillResourceRef, ParsedDocument] = {}

    def model(self) -> WorkspaceModel:
        """The workspace model the snapshot declares, loaded on the first call.

        A load that fails is not cached, so each call raises the same error again.

        Raises:
            DirListError: If the specification directory or docs/ cannot be listed.
            CorpusListError: If a corpus directory cannot be listed.
            StructureSchemaReadError: If any structure specification cannot be read.
            StructureSpecDecodeError: If a structure specification is not JSON in the dialect's shape.
            StructureSpecFilenameError: If a structure specification is not at a specification filename.
            EmptyStructureSpecError: If a structure specification states no rule.
            InvalidTitleCountError: If a title count is below 1.
            InvalidTokenBudgetError: If a token budget is below 1.
            InvalidWordCapError: If an outline word cap is below 1.
            RepeatedOutlineSectionError: If an outline names a section twice.
            ForbiddenOutlineSectionError: If a specification forbids a section its outline names.
            AdjacentAnyRunsError: If an outline places two ``any`` runs side by side.
            InvalidFrontmatterSchemaError: If a frontmatter schema is rejected by the meta-schema.
            FrontmatterSchemaIdError: If a schema in a frontmatter schema carries ``$id``.
            ForeignFrontmatterDialectError: If a schema in a frontmatter schema names another dialect.
            UntypedFrontmatterSchemaError: If a frontmatter schema's root does not state an object.
            DirResolveError: If a skills directory cannot be resolved.
            SkillsDirListError: If a skills directory cannot be listed.
            SkillEntryResolveError: If a symlinked skill entry cannot be resolved.
            SkillDirListError: If a skill directory cannot be listed.
            SkillFileResolveError: If a symlinked SKILL.md cannot be resolved.
        """
        if self._model is None:
            self._model = load_model(self._fs)
        return self._model

    def require_real_layout(self) -> None:
        """Refuse a snapshot in which ``docs/`` or ``docs/__meta__/`` is a symlink; never cached.

        Behind a linked ``docs/`` or ``docs/__meta__/`` the snapshot holds no specification, so the model has no
        corpus, and a run over its documents would report success over nothing. Kept apart from ``model()``, which
        also lists the skills: a caller that reads only skills has no reason to refuse a linked ``docs/``.

        Raises:
            LinkedLayoutError: If ``docs/`` is a symlink, or else if ``docs/__meta__/`` is one.
        """
        require_real_layout(self._fs)

    def find_real_path(self, path: RootRelativePath) -> RootRelativePath | None:
        """Where `path` leads in the snapshot, every recorded link on the way followed; never cached.

        Like the IDE's lookup of a path in its virtual file system: a path handed in from outside, such as a
        command line argument, is interpreted in the same frozen tree every check reads, not on the live disk.

        Args:
            path: The path to look up, relative to the snapshot root; it may name a directory or a file.

        Returns:
            The real directory or the real file, root-relative, or ``None`` when the snapshot holds neither there.
        """
        directory = self._fs.find_real_dir(path)
        if directory is not None:
            return directory
        return self._fs.find_real_file(path)

    def find_real_file(self, path: RootRelativePath) -> RootRelativePath | None:
        """The file `path` leads to in the snapshot, every recorded link on the way followed; never cached.

        Args:
            path: The path to look up, relative to the snapshot root; a directory leads to no file.

        Returns:
            The real file, root-relative, or ``None`` when the snapshot holds no file there: nothing, a
            directory, or a link it did not follow.
        """
        return self._fs.find_real_file(path)

    def is_in_scope(self, path: RootRelativePath) -> bool:
        """Whether the scan lists the directory `path` sits in, as the snapshot's scope declares it.

        Like the IDE's question whether a file is in the project's content, answered from the roots the snapshot
        records it was taken of rather than from what the virtual file system holds: a path in a directory the
        scope covers is in it even where the directory does not exist, and then whatever the path names is
        missing. Only the links the snapshot recorded are read besides, to tell where `path` leads. A snapshot
        that scanned nothing, such as one built by `Snapshot.from_files`, has no path in scope.

        The answer is not cached, but what it is computed from is: the scope expanded through the recorded
        links, a `ScopeIndex` built on the first call and asked on every later one.

        Args:
            path: The entry to ask about, relative to the snapshot root; it need not exist.
        """
        if self._scope_index is None:
            self._scope_index = ScopeIndex(self._snapshot.scope, self._snapshot.links)
        return self._scope_index.is_in_scope(path)

    def frontmatter(self, ref: DocumentRef) -> FrontmatterNode:
        """The frontmatter of one document, parsed from the snapshot on the first call for its ref.

        Cached apart from `parse(ref)` and never read from it, so the answer does not depend on which of the two
        was asked first; `parse_frontmatter` guarantees the two agree.

        A document that cannot be read is not cached, so each call raises the same error again.

        Args:
            ref: The document to read; the cache key, so one ref is parsed once.

        Raises:
            DocumentDecodeError: If the document's bytes are not UTF-8.
            DocumentReadError: If the snapshot holds no regular file at the document's path.
        """
        decoded = self._frontmatters.get(ref)
        if decoded is None:
            text = self._documents.get_document(ref).text
            decoded = parse_frontmatter(text)
            self._frontmatters[ref] = decoded
        return decoded

    def parse(self, ref: DocumentRef) -> ParsedDocument:
        """The parse tree of one document, parsed from the snapshot on the first call for its ref.

        A document that cannot be read is not cached, so each call raises the same error again.

        Args:
            ref: The document to parse; the cache key, so one ref is parsed once.

        Raises:
            DocumentDecodeError: If the document's bytes are not UTF-8.
            DocumentReadError: If the snapshot holds no regular file at the document's path.
        """
        parsed = self._parses.get(ref)
        if parsed is None:
            text = self._documents.get_document(ref).text
            parsed = parse_document(text)
            self._parses[ref] = parsed
        return parsed

    def tokens(self, ref: DocumentRef) -> int:
        """The tokens in one document's whole file, counted from the snapshot on the first call for its ref.

        Cached apart from `parse(ref)` and never read from it: the count needs the raw text, not the tree, so
        a check that needs only one of the two never pays for the other.

        A document that cannot be read is not cached, so each call raises the same error again.

        Args:
            ref: The document whose whole file is counted; the cache key, so one ref is counted once.

        Raises:
            DocumentDecodeError: If the document's bytes are not UTF-8.
            DocumentReadError: If the snapshot holds no regular file at the document's path.
        """
        count = self._token_counts.get(ref)
        if count is None:
            text = self._documents.get_document(ref).text
            count = count_tokens(text)
            self._token_counts[ref] = count
        return count

    def skill_frontmatter(self, ref: SkillRef) -> FrontmatterNode:
        """The frontmatter of one skill's `SKILL.md`, parsed from the snapshot on the first call for its ref.

        A skill that cannot be read is not cached, so each call raises the same error again.

        Args:
            ref: The skill whose `SKILL.md` is read; the cache key, so one ref is parsed once.

        Raises:
            SkillDecodeError: If the skill's bytes are not UTF-8.
            SkillReadError: If the snapshot holds no regular file at the skill's path.
        """
        decoded = self._skill_frontmatters.get(ref)
        if decoded is None:
            text = self._skills.get_skill(ref).text
            decoded = parse_frontmatter(text)
            self._skill_frontmatters[ref] = decoded
        return decoded

    def skill_parse(self, ref: SkillRef) -> ParsedDocument:
        """The parse tree of one skill's `SKILL.md`, parsed from the snapshot on the first call for its ref.

        Cached apart from `skill_frontmatter(ref)` and never read from it, as a document's parse is from its
        frontmatter.

        A skill that cannot be read is not cached, so each call raises the same error again.

        Args:
            ref: The skill whose `SKILL.md` is parsed; the cache key, so one ref is parsed once.

        Raises:
            SkillDecodeError: If the skill's bytes are not UTF-8.
            SkillReadError: If the snapshot holds no regular file at the skill's path.
        """
        parsed = self._skill_parses.get(ref)
        if parsed is None:
            text = self._skills.get_skill(ref).text
            parsed = parse_document(text)
            self._skill_parses[ref] = parsed
        return parsed

    def skill_resources(self, ref: SkillRef) -> tuple[SkillResourceLocation, ...]:
        """The resources of one skill, listed from the snapshot on the first call for its ref.

        Each is named where an agent reaches it, under the skill's directory, and located at the real file that
        path leads to, sorted by ref; `Repository.list_skill_resources` states which files are resources and which
        symlinks the walk follows. The skill's location is the model's, so the model is loaded first if it is not yet.

        Carry-over: the resources of one skill are kept for the next revision unless one of these changed:

        - An entry was added, deleted or changed kind in a directory the walk entered, or at the path a symlink it
          met leads to, or on the way there.
        - A symlink on any of those ways changed its target.
        - The next model locates the skill's directory at another real directory, its `resolves_to`. Where its
          `SKILL.md` leads plays no part, so a retargeted `SKILL.md` symlink alone leaves the listing valid.

        A change to any file's bytes leaves it valid, and so does any change the walk does not reach, whichever
        skill it is in.

        A listing that fails is not cached, so each call raises the same error again.

        Args:
            ref: The skill whose resources are listed; the cache key, so one skill is walked once.

        Raises:
            ValueError: If the model lists no skill with this ref (refs from the model never trigger it).
            SkillResourcesListError: If a directory the walk enters cannot be listed.
            SkillResourcesSymlinkResolveError: If a symlink the walk meets cannot be resolved.
            DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
            CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
            StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
            StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in
                the dialect's shape.
            StructureSpecFilenameError: If the model is not loaded yet and a structure specification is not at a
                specification filename.
            EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
            InvalidTitleCountError: If the model is not loaded yet and a title count is below 1.
            InvalidTokenBudgetError: If the model is not loaded yet and a token budget is below 1.
            InvalidWordCapError: If the model is not loaded yet and an outline word cap is below 1.
            RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
            ForbiddenOutlineSectionError: If the model is not loaded yet and a specification forbids a section its
                outline names.
            AdjacentAnyRunsError: If the model is not loaded yet and an outline places two `any` runs side by
                side.
            InvalidFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema is rejected by
                the meta-schema.
            FrontmatterSchemaIdError: If the model is not loaded yet and a schema in a frontmatter schema carries
                `$id`.
            ForeignFrontmatterDialectError: If the model is not loaded yet and a schema in a frontmatter schema
                names another dialect.
            UntypedFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema's root does not
                state an object.
            DirResolveError: If the model is not loaded yet and a skills directory cannot be resolved.
            SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
            SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
            SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
            SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
        """
        resources = self._skill_resources.get(ref)
        if resources is None:
            location = self.model().skill_location(ref)
            resources = self._skills.list_skill_resources(location)
            self._skill_resources[ref] = resources
        return resources

    def skill_resource_parse(self, ref: SkillResourceRef) -> ParsedDocument:
        """The parse tree of one resource of a skill, parsed from the snapshot on the first call for its ref.

        The resource is read at the real file `skill_resources(ref.skill)` locates the ref at, never at `ref.path`,
        so the skill's resources are listed first if they are not yet.

        Carry-over: kept for the next revision only when the next `skill_resources(ref.skill)` locates the ref at the
        same real file and that file's bytes did not change.

        A resource that cannot be read is not cached, so each call raises the same error again.

        Args:
            ref: The resource to parse, as `skill_resources` names it; the cache key, so one ref is parsed once.

        Raises:
            ValueError: If `skill_resources(ref.skill)` lists no resource with this ref (refs from it never trigger
                it).
            SkillResourceDecodeError: If the resource's bytes are not UTF-8.
            SkillResourceReadError: If the snapshot holds no regular file at the real file the ref leads to.
            SkillResourcesListError: If the skill's resources are not listed yet and a directory the walk enters
                cannot be listed.
            SkillResourcesSymlinkResolveError: If the skill's resources are not listed yet and a symlink the walk
                meets cannot be resolved.
            DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
            CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
            StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
            StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in
                the dialect's shape.
            StructureSpecFilenameError: If the model is not loaded yet and a structure specification is not at a
                specification filename.
            EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
            InvalidTitleCountError: If the model is not loaded yet and a title count is below 1.
            InvalidTokenBudgetError: If the model is not loaded yet and a token budget is below 1.
            InvalidWordCapError: If the model is not loaded yet and an outline word cap is below 1.
            RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
            ForbiddenOutlineSectionError: If the model is not loaded yet and a specification forbids a section its
                outline names.
            AdjacentAnyRunsError: If the model is not loaded yet and an outline places two `any` runs side by
                side.
            InvalidFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema is rejected by
                the meta-schema.
            FrontmatterSchemaIdError: If the model is not loaded yet and a schema in a frontmatter schema carries
                `$id`.
            ForeignFrontmatterDialectError: If the model is not loaded yet and a schema in a frontmatter schema
                names another dialect.
            UntypedFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema's root does not
                state an object.
            DirResolveError: If the model is not loaded yet and a skills directory cannot be resolved.
            SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
            SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
            SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
            SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
        """
        parsed = self._skill_resource_parses.get(ref)
        if parsed is None:
            location = _skill_resource_location(self.skill_resources(ref.skill), ref)
            text = self._skills.get_skill_resource(location).text
            parsed = parse_document(text)
            self._skill_resource_parses[ref] = parsed
        return parsed


def _skill_resource_location(
    resources: tuple[SkillResourceLocation, ...], ref: SkillResourceRef
) -> SkillResourceLocation:
    """The location of one resource among a skill's resources.

    Args:
        resources: The skill's resources, as `Database.skill_resources` lists them.
        ref: The resource to look up.

    Raises:
        ValueError: If no location in `resources` is the ref's.
    """
    for location in resources:
        if location.ref == ref:
            return location
    raise ValueError(f'{ref.path} is not a resource of skill {ref.skill.directory}')
