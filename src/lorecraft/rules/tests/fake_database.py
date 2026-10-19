"""Hand-written fakes of the database a rule's query reads, shared by the unit tests of every rule group.

A fake answers every fact of its subject's own file from the subject's text, through the real parsers and analyses of
`lorecraft.project` the database's queries call, so a test cannot hand a rule a parse or a count no file would
produce. Only what no single file states is set by hand: a document's governance, from structure files
decoded from their JSON by the real decoder, where a skill is listed and what a link there leads to, and, as a
cross-file state, what the snapshot holds at the target of each relative link, keyed by the link's normalised relative
path. A fake document or skill holds no link target; a test of a rule over links states them on
`FakeDocumentMarkdownDatabase` or `FakeSkillResourceDatabase`. A layout entry has no text for a fake to parse: where a
symlink's chain leaves the repository is read from the link targets a scan recorded across the tree, never from one
file, so the test states it by hand too.
"""

from collections.abc import Callable, Mapping
from typing import Any, Final, Protocol, cast, overload

from lib.primitives import StructurePrimitives
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import (
    AspectFilename,
    AspectNamespace,
    EmptyAspectNameError,
    InvalidAspectNameCharacterError,
)
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.item import DocumentOrigin, SkillEntrypointOrigin
from lorecraft.project.layout import DOCS_DIR, SPECS_DIR
from lorecraft.project.link_target import (
    DocumentDirectory,
    DocumentLink,
    LinkBase,
    LinkTargetEntry,
    SkillRoot,
)
from lorecraft.project.query import (
    CorpusDirectoryPrimitives,
    ItemQuery,
    Query,
    QueryTargetRef,
    SubjectQuery,
    SymlinkPrimitives,
)
from lorecraft.project.schemas import (
    CorpusSpecName,
    NamespaceSpecName,
    SpecFileType,
    SpecName,
    StructureSchema,
    StructureSpec,
    StructureSpecFile,
    parse_spec_name,
    spec_filename,
)
from lorecraft.project.syntax import (
    FrontmatterNode,
    Heading,
    NormalisedLinkPath,
    ParsedDocument,
    SectionHeading,
    TokenCount,
    count_lines,
    count_tokens,
    parse_document,
    parse_frontmatter,
    section_headings,
)
from lorecraft.project.workspace import Corpus, CorpusNamespace, CorpusSpec, Governance, NamespaceSpec
from lorecraft.rules.declaration import Rule
from lorecraft.rules.subject import Queried, QueriedCorpusDirectoryRule, QueriedItemRule, QueriedSymlinkRule
from lorecraft.vfs import ResolvedPath, RootExit

_DEFAULT_FILENAME: Final[str] = 'setup'
"""The filename a fake document has unless a test names another."""

_DEFAULT_DIRECTORY_NAME: Final[str] = 'review'
"""The directory a fake skill is listed under unless a test names another."""

_SKILLS_DIRECTORY: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills')
"""The skills directory a fake skill is listed in."""


def _skill_aspect_filename(entry: str) -> AspectFilename | None:
    """Return the skill entry as an aspect filename when its name has that format."""
    try:
        return AspectFilename.parse(entry)
    except EmptyAspectNameError, InvalidAspectNameCharacterError:
        return None


def structure_spec_path(name: str) -> RootRelativePath:
    """Where the structure file at a meta spec name lies, such as `docs/__meta__/guide.spec.json`.

    Args:
        name: The meta spec name, such as `guide` or `guide-cli`.

    Raises:
        EmptyCorpusNameError: If the corpus token is empty.
        InvalidCorpusNameCharacterError: If a character of the corpus token falls outside lowercase snake case.
        EmptyAspectNamespaceError: If a hyphen is followed by no namespace.
        InvalidAspectNamespaceCharacterError: If a character of the namespace token falls outside kebab case.
    """
    return SPECS_DIR / PathComponent.parse(spec_filename(parse_spec_name(name), SpecFileType.SPEC))


def heading_in(text: str, heading_text: str) -> Heading:
    """The first top-level heading with this text, as the real parser reads it from a document's text.

    A rule that carries a heading is tested against the parser's own, so the test cannot hand it one no document
    would produce.

    Args:
        text: Markdown document to parse, frontmatter included.
        heading_text: The heading's plain text.

    Raises:
        AssertionError: If the document holds no such heading.
    """
    for heading in parse_document(text).headings:
        if heading.text == heading_text:
            return heading
    raise AssertionError(f'the document holds a heading `{heading_text}`')


def section_in(text: str, heading_text: str) -> SectionHeading:
    """The first H2 section with this heading text, as the real parser reads it from a document's text.

    Args:
        text: Markdown document to parse, frontmatter included.
        heading_text: The heading's plain text.

    Raises:
        AssertionError: If the document holds no such section.
    """
    for section in section_headings(parse_document(text).headings):
        if section.text == heading_text:
            return section
    raise AssertionError(f'the document holds a section `{heading_text}`')


def namespace_spec(corpus: str, namespace: str, structure: str) -> NamespaceSpec:
    """A namespace's meta spec, with its structure file decoded from JSON by the real decoder.

    Args:
        corpus: The corpus the namespace narrows, such as `guide`.
        namespace: The namespace, such as `cli`.
        structure: The JSON of the namespace's structure file.

    Raises:
        EmptyCorpusNameError: If the corpus is empty.
        InvalidCorpusNameCharacterError: If a character of the corpus falls outside lowercase snake case.
        EmptyAspectNamespaceError: If the namespace is empty.
        InvalidAspectNamespaceCharacterError: If a character of the namespace falls outside kebab case.
    """
    spec_name = NamespaceSpecName(CorpusName.parse(corpus), AspectNamespace.parse(namespace))
    return NamespaceSpec(name=spec_name, files=_files(spec_name), structure=_decode_structure(spec_name, structure))


def _files(spec_name: SpecName) -> tuple[RootRelativePath, ...]:
    """The files at a meta spec name, sorted: its prose, then its structure file.

    Args:
        spec_name: The meta spec name.
    """
    return (
        SPECS_DIR / PathComponent.parse(spec_filename(spec_name, SpecFileType.PROSE)),
        SPECS_DIR / PathComponent.parse(spec_filename(spec_name, SpecFileType.SPEC)),
    )


def _decode_structure(spec_name: SpecName, structure: str) -> StructureSpec:
    """A structure file decoded from its JSON by the real decoder.

    Args:
        spec_name: The meta spec name the file lies at.
        structure: The structure file's JSON.
    """
    file = StructureSpecFile(
        path=SPECS_DIR / PathComponent.parse(spec_filename(spec_name, SpecFileType.SPEC)), name=spec_name
    )
    spec = StructureSpec.parse(file, StructureSchema(structure))
    assert isinstance(spec, StructureSpec), f'a test states a usable structure specification, got {spec!r}'
    return spec


def structure_spec(spec_name: str, text: str) -> StructureSpec:
    """A structure specification decoded from its JSON by the real decoder, for a test of a query over specifications.

    Args:
        spec_name: The specification's name, such as `code` or `code-python`.
        text: The structure specification's JSON.
    """
    return _decode_structure(parse_spec_name(spec_name), text)


class FakeDocumentDatabase:
    """A document a test writes as text, governed by the meta specs the test states.

    The governance is set by hand, as the model would find it: the corpus's meta spec first, then each
    namespace's the test lists, broad to narrow. The meta specs are built through a `Corpus`, as the model builds
    them, so a namespace the filename does not match is refused rather than dropped.
    """

    _text: str
    _governance: Governance
    _corpus_structure: StructureSpec
    _link_targets: Mapping[NormalisedLinkPath, LinkTargetEntry]
    _corpus: Corpus
    _document_links: tuple[DocumentLink, ...]

    def __init__(
        self,
        text: str,
        *,
        corpus: str,
        structure: str,
        namespaces: tuple[NamespaceSpec, ...] = (),
        filename: str | None = None,
        link_targets: Mapping[NormalisedLinkPath, LinkTargetEntry] = FrozenMapping({}),
        siblings: tuple[str, ...] = (),
        document_links: tuple[DocumentLink, ...] = (),
    ) -> None:
        """Hold the document's text and the meta specs that govern it.

        Args:
            text: The document's whole text, frontmatter included.
            corpus: The document's corpus, which is its meta spec name, such as `guide`.
            structure: The JSON of the corpus's structure file; a document's structure exists only for a
                corpus that states one.
            namespaces: The namespace meta specs that govern the document, broad to narrow, as `namespace_spec`
                builds them.
            filename: The document's filename, without its extension; `setup`, or `<namespace>-setup` for the
                narrowest namespace listed, which every namespace listed then governs.
            link_targets: What the snapshot holds at the target of each relative link, keyed by the link's
                normalised relative path, as the database's link-target query would find it; none by default.
            siblings: The filenames, without extension, of the other documents the corpus holds; none by default.
            document_links: The links to other documents the document holds, as the database would find them; none by
                default.

        Raises:
            ValueError: If a listed namespace does not govern the filename, or is of another corpus.
            EmptyCorpusNameError: If the corpus is empty.
            InvalidCorpusNameCharacterError: If a character of the corpus falls outside lowercase snake case.
            EmptyAspectNameError: If the filename is empty.
            InvalidAspectNameCharacterError: If a character of the filename is not lowercase with valid separators.
        """
        spec_name = CorpusSpecName(CorpusName.parse(corpus))
        self._text = text
        self._link_targets = link_targets
        self._document_links = document_links
        self._corpus_structure = _decode_structure(spec_name, structure)
        corpus_spec = CorpusSpec(name=spec_name, files=_files(spec_name), structure=self._corpus_structure)
        if filename is None:
            filename = f'{namespaces[-1].name.namespace}-{_DEFAULT_FILENAME}' if namespaces else _DEFAULT_FILENAME
        document = AspectFilename.parse(filename)
        corpus_namespaces: dict[AspectNamespace, CorpusNamespace] = {}
        for namespace in namespaces:
            if namespace.name.corpus != spec_name.corpus or not namespace.is_governing(document):
                raise ValueError(f'the namespace spec {namespace.name} does not govern {spec_name.corpus}/{document}')
            corpus_namespaces[namespace.name.namespace] = CorpusNamespace(namespace.files, namespace.structure)
        filenames = frozenset({document, *(AspectFilename.parse(sibling) for sibling in siblings)})
        self._corpus = Corpus(corpus_spec, FrozenMapping(corpus_namespaces), filenames)
        self._governance = Governance(self._corpus, document)
        self._ref = DocumentRef(corpus=spec_name.corpus, filename=document)

    def _parse(self) -> ParsedDocument:
        """The document's parse tree, as the real parser reads it."""
        return parse_document(self._text)

    def token_count(self) -> TokenCount:
        """The tokens in the document's whole text, as the real tokenizer counts them."""
        return count_tokens(self._text)

    def query[T](self, query: ItemQuery[T]) -> T:
        """The answer of a declared query over the governing meta specs, as the real database finds it."""
        return query(
            StructurePrimitives(
                self._governance.structure_specs(),
                self._parse().headings,
                self.token_count(),
                self._parse().links,
                self._link_targets,
                DocumentDirectory(self._ref.path.parent),
                self._ref.filename,
                count_lines(self._text),
                parse_frontmatter(self._text),
                anchor_set=self._parse().anchors,
                base_name=self._base_name(),
                document_link_list=self._document_links,
                corpus=self._ref.corpus,
                origin_value=DocumentOrigin(),
                governance_value=self._governance,
            )
        )

    def _base_name(self) -> AspectFilename | None:
        """The typed base the corpus the test stated gives the document, as the real model derives it."""
        base = self._corpus.document_base(self._ref.filename)
        return None if base is None else base.filename


class FakeSkillDatabase:
    """A skill whose `SKILL.md` a test writes as text, listed where the test names."""

    _text: str
    _directory_name: PathComponent
    _link_target: ResolvedPath | None

    def __init__(
        self, text: str, *, directory_name: str = _DEFAULT_DIRECTORY_NAME, link_target: ResolvedPath | None = None
    ) -> None:
        """Hold the skill's `SKILL.md` text, and where the skill is listed.

        Args:
            text: The whole `SKILL.md`, frontmatter included.
            directory_name: The name of the skill's directory as an agent lists it.
            link_target: The resolved directory the listed directory leads to when it is a link, or `None`.
        """
        self._text = text
        self._directory_name = PathComponent.parse(directory_name)
        self._link_target = link_target

    def frontmatter(self) -> FrontmatterNode:
        """The skill's frontmatter block, as the real parser reads it."""
        return parse_frontmatter(self._text)

    def query[T](self, query: ItemQuery[T]) -> T:
        """The answer of a declared query over the skill, as the real database finds it."""
        return query(
            StructurePrimitives(
                (),
                link_list=parse_document(self._text).links,
                link_base_value=SkillRoot(_SKILLS_DIRECTORY / self._directory_name),
                line_total=count_lines(self._text),
                frontmatter_node=self.frontmatter(),
                name=_skill_aspect_filename(str(self._directory_name)),
                origin_value=SkillEntrypointOrigin(link_target=self._link_target),
            )
        )


DEFAULT_SKILL_DIRECTORY: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills/review')
"""The skill directory a fake resource belongs to unless a test names another."""

DEFAULT_DOCUMENT_DIRECTORY: Final[RootRelativePath] = RootRelativePath.parse('docs/guide')
"""The directory a fake document lies in unless a test names another."""


def _markdown_primitives(
    text: str, base: LinkBase, link_targets: Mapping[NormalisedLinkPath, LinkTargetEntry]
) -> StructurePrimitives:
    """The primitives of a Markdown file, from its text through the real parser and the targets the test stated.

    Args:
        text: The file's whole text.
        base: Where its relative links are read from.
        link_targets: What the snapshot holds at the target of each relative link.
    """
    parsed = parse_document(text)
    return StructurePrimitives(
        (),
        parsed.headings,
        link_list=parsed.links,
        anchor_set=parsed.anchors,
        target_map=link_targets,
        link_base_value=base,
    )


class FakeSkillResourceDatabase:
    """A resource of a skill a test writes as text."""

    _text: str
    _skill_directory: RootRelativePath
    _link_targets: Mapping[NormalisedLinkPath, LinkTargetEntry]

    def __init__(
        self,
        text: str,
        *,
        skill_directory: RootRelativePath = DEFAULT_SKILL_DIRECTORY,
        link_targets: Mapping[NormalisedLinkPath, LinkTargetEntry] = FrozenMapping({}),
    ) -> None:
        """Hold the resource's text, its skill's directory and what the snapshot holds at each link target.

        Args:
            text: The resource's whole file.
            skill_directory: The skill directory where an agent reaches it, which its relative links are read from.
            link_targets: What the snapshot holds at the target of each relative link, keyed by the link's
                normalised relative path, as the database's link-target query would find it; none by default.
        """
        self._text = text
        self._skill_directory = skill_directory
        self._link_targets = link_targets

    def query[T](self, query: ItemQuery[T]) -> T:
        """The answer of a declared query over the resource, as the real database finds it."""
        return query(_markdown_primitives(self._text, SkillRoot(self._skill_directory), self._link_targets))


class FakeDocumentMarkdownDatabase:
    """A document a test writes as text, asked only what any Markdown file is asked."""

    _text: str
    _directory: RootRelativePath
    _link_targets: Mapping[NormalisedLinkPath, LinkTargetEntry]

    def __init__(
        self,
        text: str,
        *,
        directory: RootRelativePath = DEFAULT_DOCUMENT_DIRECTORY,
        link_targets: Mapping[NormalisedLinkPath, LinkTargetEntry] = FrozenMapping({}),
    ) -> None:
        """Hold the document's text, its directory and what the snapshot holds at each link target.

        Args:
            text: The document's whole file.
            directory: The directory holding the document, which its relative links are read from.
            link_targets: What the snapshot holds at the target of each relative link, keyed by the link's
                normalised relative path, as the database's link-target query would find it; none by default.
        """
        self._text = text
        self._directory = directory
        self._link_targets = link_targets

    def query[T](self, query: ItemQuery[T]) -> T:
        """The answer of a declared query over the document, as the real database finds it."""
        return query(_markdown_primitives(self._text, DocumentDirectory(self._directory), self._link_targets))


class FakeSymlinkDatabase:
    """A symlink of the skill layout whose chain leaves the repository where the test states."""

    _leaves_at: RootExit

    def __init__(self, leaves_at: RootExit) -> None:
        """Hold where the symlink's chain leaves the repository.

        Args:
            leaves_at: The link the chain leaves through, and that link's target, as a scan would record them.
        """
        self._leaves_at = leaves_at

    def path(self) -> RootRelativePath:
        """The symlink's path: the link the chain leaves through, as the test stated it."""
        return self._leaves_at.link

    def leaves_at(self) -> RootExit:
        """Where the chain leaves the repository, as the test stated it."""
        return self._leaves_at

    def query[T](self, query: Query[SymlinkPrimitives, T]) -> T:
        """The answer of a declared query over the symlink, read through this fake's primitives."""
        return query(self)

    def query_at[T](self, ref: QueryTargetRef, query: Callable[..., T]) -> T:
        """Cross-subject reads are outside the symlink fake's declared facts."""
        raise AssertionError(f'no query is available for {ref}')


class FakeCorpusDirectoryDatabase:
    """A directory under `docs/` that takes a reserved corpus's name, as the test states."""

    def __init__(self, corpus: str) -> None:
        """Hold the reserved corpus the directory takes.

        Args:
            corpus: The reserved corpus name, such as `skills`.
        """
        self._corpus = CorpusName.parse(corpus)

    def path(self) -> RootRelativePath:
        """The directory, `docs/` and the corpus name."""
        return DOCS_DIR / PathComponent.parse(str(self._corpus))

    def reserved_corpus(self) -> CorpusName:
        """The reserved corpus the directory takes, as the test stated it."""
        return self._corpus

    def query[T](self, query: Query[CorpusDirectoryPrimitives, T]) -> T:
        """The answer of a declared query over the directory, read through this fake's primitives."""
        return query(self)

    def query_at[T](self, ref: QueryTargetRef, query: Callable[..., T]) -> T:
        """Cross-subject reads are outside the directory fake's declared facts."""
        raise AssertionError(f'no query is available for {ref}')


class _Queryable(Protocol):
    """A fake that answers a declared query over its subject."""

    def query[T](self, query: ItemQuery[T]) -> T:
        """The answer of the query over the fake's subject."""
        ...


@overload
def judged[R: QueriedItemRule[Any]](rule: type[R], database: _Queryable) -> tuple[R, ...]: ...


@overload
def judged[R: QueriedSymlinkRule[Any]](rule: type[R], database: FakeSymlinkDatabase) -> tuple[R, ...]: ...


@overload
def judged[R: QueriedCorpusDirectoryRule[Any]](
    rule: type[R], database: FakeCorpusDirectoryDatabase
) -> tuple[R, ...]: ...


def judged(rule: type[Rule], database: object) -> tuple[Rule, ...]:
    """Every occurrence of a queried rule over a fake database, resolved as the runner does: its query, then its facts.

    One entry serves every kind of rule: over an item, a symlink or a corpus directory.

    Args:
        rule: The queried rule to run.
        database: The fake database that answers the rule's query.
    """
    # SAFETY: the overloads admit only queried rule classes, whose query and judge share this facts parameter
    queried = cast('type[Queried[object, SubjectQuery[object]]]', rule)
    query = queried.query()
    if isinstance(database, FakeSymlinkDatabase):
        # SAFETY: the fake database variant determines the matching query protocol for this branch
        facts = database.query(cast('Query[SymlinkPrimitives, object]', query))
    elif isinstance(database, FakeCorpusDirectoryDatabase):
        # SAFETY: the fake database variant determines the matching query protocol for this branch
        facts = database.query(cast('Query[CorpusDirectoryPrimitives, object]', query))
    else:
        # SAFETY: remaining overload is the item database, whose protocol exposes query(Query)
        item_database = cast('_Queryable', database)
        # SAFETY: remaining overload is the item database, whose query method accepts Query
        item_query = cast('ItemQuery[object]', query)
        facts = item_database.query(item_query)
    # SAFETY: judge returns the rules represented by the declared queried rule class
    return cast('tuple[Rule, ...]', queried.judge(facts))
