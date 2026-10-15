"""Hand-written fakes of the contexts a rule reads, shared by the unit tests of every rule group.

A fake answers every fact of its subject's own file from the subject's text, through the real parsers and analyses of
`lorecraft.project` the database's queries call, so a test cannot hand a rule a parse or a count no file would
produce. Only what no single file states is set by hand: a document's governance, from structure files
decoded from their JSON by the real decoder, where a skill is listed and what a link there leads to, and, as a
cross-file state, what the snapshot holds at the target of each relative link, keyed by the link's normalised relative
path. A fake document or skill holds no link target; a test of a rule over links states them on
`FakeDocumentMarkdownContext` or `FakeSkillResourceContext`. A layout entry has no text for a fake to parse: where a
symlink's chain leaves the repository is read from the link targets a scan recorded across the tree, never from one
file, so the test states it by hand too.
"""

from collections.abc import Mapping
from typing import Final

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename, AspectNamespace
from lorecraft.project.context import DocumentFrontmatterOwner, SkillFrontmatterOwner
from lorecraft.project.corpus import CorpusName
from lorecraft.project.layout import SPECS_DIR
from lorecraft.project.link_target import DocumentDirectory, LinkTargetEntry, SkillRoot
from lorecraft.project.schemas import (
    CorpusSpecName,
    NamespaceSpecName,
    OutlineAlignmentSpec,
    OutlineDivergenceSpec,
    SchemaProblems,
    SkillFields,
    SpecFileType,
    SpecName,
    StructureSchema,
    StructureSpec,
    StructureSpecFile,
    align_outlines,
    locate_schema_problems,
    locate_skill_schema_problems,
    match_outlines,
    parse_skill_fields,
    parse_spec_name,
    spec_filename,
)
from lorecraft.project.syntax import (
    FrontmatterNode,
    Heading,
    LineCount,
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
from lorecraft.vfs import ResolvedPath, RootExit

_DEFAULT_FILENAME: Final[str] = 'setup'
"""The filename a fake document has unless a test names another."""

_DEFAULT_DIRECTORY_NAME: Final[str] = 'review'
"""The directory a fake skill is listed under unless a test names another."""

_SKILLS_DIRECTORY: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills')
"""The skills directory a fake skill is listed in."""


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


class FakeDocumentContext:
    """A document a test writes as text, governed by the meta specs the test states; a `DocumentContext`.

    The governance is set by hand, as the model would find it: the corpus's meta spec first, then each
    namespace's the test lists, broad to narrow. The meta specs are built through a `Corpus`, as the model builds
    them, so a namespace the filename does not match is refused rather than dropped.
    """

    _text: str
    _governance: Governance
    _corpus_structure: StructureSpec

    def __init__(
        self,
        text: str,
        *,
        corpus: str,
        structure: str,
        namespaces: tuple[NamespaceSpec, ...] = (),
        filename: str | None = None,
    ) -> None:
        """Hold the document's text and the meta specs that govern it.

        Args:
            text: The document's whole text, frontmatter included.
            corpus: The document's corpus, which is its meta spec name, such as `guide`.
            structure: The JSON of the corpus's structure file; a document's context exists only for a
                corpus that states one.
            namespaces: The namespace meta specs that govern the document, broad to narrow, as `namespace_spec`
                builds them.
            filename: The document's filename, without its extension; `setup`, or `<namespace>-setup` for the
                narrowest namespace listed, which every namespace listed then governs.

        Raises:
            ValueError: If a listed namespace does not govern the filename, or is of another corpus.
            EmptyCorpusNameError: If the corpus is empty.
            InvalidCorpusNameCharacterError: If a character of the corpus falls outside lowercase snake case.
            EmptyAspectNameError: If the filename is empty.
            InvalidAspectNameCharacterError: If a character of the filename is not lowercase with valid separators.
        """
        spec_name = CorpusSpecName(CorpusName.parse(corpus))
        self._text = text
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
        held_corpus = Corpus(corpus_spec, FrozenMapping(corpus_namespaces), frozenset())
        self._governance = Governance(held_corpus, document)

    def filename(self) -> AspectFilename:
        """The document's filename, without its extension."""
        return self._governance.ref.filename

    def frontmatter(self) -> FrontmatterNode:
        """The document's frontmatter block, as the real parser reads it."""
        return parse_frontmatter(self._text)

    def schema_problems(self) -> tuple[SchemaProblems, ...]:
        """What each governing frontmatter schema rejects, as the real analysis finds it."""
        return locate_schema_problems(self.frontmatter(), self._governance.frontmatter_schemas())

    def frontmatter_owner(self) -> DocumentFrontmatterOwner:
        """The document, with its filename and its corpus's structure file."""
        return DocumentFrontmatterOwner(filename=self.filename(), spec=self._corpus_structure.path)

    def parse(self) -> ParsedDocument:
        """The document's parse tree, as the real parser reads it."""
        return parse_document(self._text)

    def link_base(self) -> DocumentDirectory:
        """The directory holding the document, read from its ref."""
        return DocumentDirectory(self._governance.ref.path.parent)

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """None: a fake document holds no link target."""
        return FrozenMapping({})

    def token_count(self) -> TokenCount:
        """The tokens in the document's whole text, as the real tokenizer counts them."""
        return count_tokens(self._text)

    def line_count(self) -> LineCount:
        """The lines in the document's whole text, as the real counter counts them."""
        return count_lines(self._text)

    def specifications(self) -> Governance:
        """The meta specs the test stated."""
        return self._governance

    def corpus_structure(self) -> StructureSpec:
        """The corpus's structure file, decoded from the JSON the test stated."""
        return self._corpus_structure

    def outline_alignment(self) -> tuple[OutlineAlignmentSpec, ...]:
        """Where the sections fall in each governing meta spec's outline, as the real analysis finds it."""
        return align_outlines(self._governance.structure_specs(), self.parse().headings)

    def outline_divergences(self) -> tuple[OutlineDivergenceSpec, ...]:
        """Where the sections stop matching each governing outline, as the real analysis finds it."""
        return match_outlines(self.outline_alignment(), count_lines(self._text))


class FakeSkillContext:
    """A skill whose `SKILL.md` a test writes as text, listed where the test names; a `SkillContext`."""

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

    def directory_name(self) -> PathComponent:
        """The name of the skill's directory, as the test named it."""
        return self._directory_name

    def link_target(self) -> ResolvedPath | None:
        """Where the listed directory leads, as the test named it."""
        return self._link_target

    def frontmatter(self) -> FrontmatterNode:
        """The skill's frontmatter block, as the real parser reads it."""
        return parse_frontmatter(self._text)

    def schema_problems(self) -> tuple[SchemaProblems, ...]:
        """What the Agent Skills specification rejects, as the real analysis finds it."""
        return locate_skill_schema_problems(self.frontmatter())

    def skill_fields(self) -> SkillFields:
        """The fields that parse, as the real analysis finds them."""
        return parse_skill_fields(self.frontmatter())

    def frontmatter_owner(self) -> SkillFrontmatterOwner:
        """The skill, with its directory name and where a link there leads."""
        return SkillFrontmatterOwner(directory_name=self._directory_name, link_target=self._link_target)

    def parse(self) -> ParsedDocument:
        """The parse tree of the `SKILL.md`, as the real parser reads it."""
        return parse_document(self._text)

    def link_base(self) -> SkillRoot:
        """The skill directory, under the skills directory, at the name the test listed it under."""
        return SkillRoot(_SKILLS_DIRECTORY / self._directory_name)

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """None: a fake skill holds no link target."""
        return FrozenMapping({})

    def line_count(self) -> LineCount:
        """The lines in the whole `SKILL.md`, as the real counter counts them."""
        return count_lines(self._text)


DEFAULT_SKILL_DIRECTORY: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills/review')
"""The skill directory a fake resource belongs to unless a test names another."""

DEFAULT_DOCUMENT_DIRECTORY: Final[RootRelativePath] = RootRelativePath.parse('docs/guide')
"""The directory a fake document lies in unless a test names another."""


class FakeSkillResourceContext:
    """A resource of a skill a test writes as text; a `SkillResourceContext`."""

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

    def parse(self) -> ParsedDocument:
        """The resource's parse tree, as the real parser reads it."""
        return parse_document(self._text)

    def link_base(self) -> SkillRoot:
        """The skill root, at the directory the test named."""
        return SkillRoot(self._skill_directory)

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """What the snapshot holds at each link target, as the test stated it."""
        return self._link_targets


class FakeDocumentMarkdownContext:
    """A document a test writes as text, asked only what any Markdown file is asked; a `MarkdownContext`."""

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

    def parse(self) -> ParsedDocument:
        """The document's parse tree, as the real parser reads it."""
        return parse_document(self._text)

    def link_base(self) -> DocumentDirectory:
        """The document's own directory, as the test named it."""
        return DocumentDirectory(self._directory)

    def link_targets(self) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
        """What the snapshot holds at each link target, as the test stated it."""
        return self._link_targets


class FakeLayoutContext:
    """A symlink of the skill layout whose chain leaves the repository where the test states; a `LayoutContext`."""

    _leaves_at: RootExit

    def __init__(self, leaves_at: RootExit) -> None:
        """Hold where the symlink's chain leaves the repository.

        Args:
            leaves_at: The link the chain leaves through, and that link's target, as a scan would record them.
        """
        self._leaves_at = leaves_at

    def leaves_at(self) -> RootExit:
        """Where the chain leaves the repository, as the test stated it."""
        return self._leaves_at
