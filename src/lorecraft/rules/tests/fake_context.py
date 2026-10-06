"""Hand-written fakes of the contexts a rule reads, shared by the unit tests of every rule group.

A fake answers every fact of its subject's own file from the subject's text, through the real parsers and analyses of
`lorecraft.project` the database's queries call, so a test cannot hand a rule a parse or a count no file would
produce. Only what no single file states is set by hand: a document's governance, from structure specifications
decoded from their JSON by the real decoder, where a skill is listed and what a link there leads to, and, as a
cross-file state, what the snapshot holds at the target of each relative link, keyed by the link's normalised relative
path. A fake document or skill holds no link target; a test of a rule over links states them on
`FakeDocumentMarkdownContext` or `FakeSkillResourceContext`. A layout entry has no text for a fake to parse: where a
symlink's chain leaves the repository is read from the link targets a scan recorded across the tree, never from one
file, so the test states it by hand too.
"""

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Final

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename, AspectNamespace
from lorecraft.project.context import DocumentFrontmatterOwner, SkillFrontmatterOwner
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.layout import SPECS_DIR
from lorecraft.project.link_target import DocumentDirectory, PathLookup, SkillRoot
from lorecraft.project.schemas import (
    CorpusSpecName,
    NamespaceSpecName,
    OutlineDivergenceSpec,
    SchemaProblems,
    SpecFileType,
    SpecName,
    StructureSchema,
    StructureSpec,
    StructureSpecFile,
    locate_schema_problems,
    locate_skill_schema_problems,
    match_outlines,
    parse_spec_name,
    spec_filename,
)
from lorecraft.project.syntax import (
    FrontmatterNode,
    ParsedDocument,
    count_lines,
    count_tokens,
    parse_document,
    parse_frontmatter,
)
from lorecraft.project.workspace import CorpusSpec, Governance, NamespaceSpec
from lorecraft.vfs import ResolvedPath, RootExit

_DEFAULT_FILENAME: Final[str] = 'setup'
"""The filename a fake document has unless a test names another."""

_DEFAULT_DIRECTORY_NAME: Final[str] = 'review'
"""The directory a fake skill is listed under unless a test names another."""

_SKILLS_DIRECTORY: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills')
"""The skills directory a fake skill is listed in."""


def structure_spec_path(name: str) -> RootRelativePath:
    """Where the structure specification at a specification name lies, such as `docs/__meta__/guide.structure.json`.

    Args:
        name: The specification name, such as `guide` or `guide-cli`.

    Raises:
        EmptyCorpusNameError: If the corpus token is empty.
        InvalidCorpusNameCharacterError: If a character of the corpus token falls outside lowercase snake case.
        EmptyAspectNamespaceError: If a hyphen is followed by no namespace.
        InvalidAspectNamespaceCharacterError: If a character of the namespace token falls outside kebab case.
    """
    return SPECS_DIR / spec_filename(parse_spec_name(name), SpecFileType.STRUCTURE)


def namespace_spec(corpus: str, namespace: str, structure: str) -> NamespaceSpec:
    """A namespace's specification, with its structure specification decoded from JSON by the real decoder.

    Args:
        corpus: The corpus the namespace narrows, such as `guide`.
        namespace: The namespace, such as `cli`.
        structure: The JSON of the namespace's structure specification.

    Raises:
        EmptyCorpusNameError: If the corpus is empty.
        InvalidCorpusNameCharacterError: If a character of the corpus falls outside lowercase snake case.
        EmptyAspectNamespaceError: If the namespace is empty.
        InvalidAspectNamespaceCharacterError: If a character of the namespace falls outside kebab case.
        StructureSpecDecodeError: If the structure specification is not JSON or does not have the dialect's shape.
        InvalidTitlePatternError: If its title's pattern does not compile.
        InvalidFrontmatterSchemaError: If its frontmatter schema is rejected by the meta-schema.
        FrontmatterSchemaIdError: If a schema in its frontmatter schema carries `$id`.
        ForeignFrontmatterDialectError: If a schema in its frontmatter schema names another dialect.
        UntypedFrontmatterSchemaError: If its frontmatter schema's root does not state an object.
        EmptyStructureSpecError: If it states no rule.
        RepeatedOutlineSectionError: If its outline names a section twice.
        RepeatedForbiddenSectionError: If it forbids a section twice.
        ForbiddenOutlineSectionError: If it forbids a section its own outline names.
        AdjacentAnyRunsError: If its outline places two `any` runs side by side.
    """
    spec_name = NamespaceSpecName(CorpusName.parse(corpus), AspectNamespace.parse(namespace))
    return NamespaceSpec(name=spec_name, files=_files(spec_name), structure=_decode_structure(spec_name, structure))


def _files(spec_name: SpecName) -> tuple[RootRelativePath, ...]:
    """The files at a specification name, sorted: its prose, then its structure specification.

    Args:
        spec_name: The specification name.
    """
    return (
        SPECS_DIR / spec_filename(spec_name, SpecFileType.PROSE),
        SPECS_DIR / spec_filename(spec_name, SpecFileType.STRUCTURE),
    )


def _decode_structure(spec_name: SpecName, structure: str) -> StructureSpec:
    """A structure specification decoded from its JSON by the real decoder.

    Args:
        spec_name: The specification name the file lies at.
        structure: The structure specification's JSON.

    Raises:
        StructureSpecDecodeError: If the text is not JSON or does not have the dialect's shape.
        InvalidTitlePatternError: If its title's pattern does not compile.
        InvalidFrontmatterSchemaError: If its frontmatter schema is rejected by the meta-schema.
        FrontmatterSchemaIdError: If a schema in its frontmatter schema carries `$id`.
        ForeignFrontmatterDialectError: If a schema in its frontmatter schema names another dialect.
        UntypedFrontmatterSchemaError: If its frontmatter schema's root does not state an object.
        EmptyStructureSpecError: If it states no rule.
        RepeatedOutlineSectionError: If its outline names a section twice.
        RepeatedForbiddenSectionError: If it forbids a section twice.
        ForbiddenOutlineSectionError: If it forbids a section its own outline names.
        AdjacentAnyRunsError: If its outline places two `any` runs side by side.
    """
    file = StructureSpecFile(path=SPECS_DIR / spec_filename(spec_name, SpecFileType.STRUCTURE), name=spec_name)
    return StructureSpec.parse(file, StructureSchema(structure))


class FakeDocumentContext:
    """A document a test writes as text, governed by the specifications the test states; a `DocumentContext`.

    The governance is set by hand, as the model would find it: the corpus's specification first, then each
    namespace's the test lists, broad to narrow. Nothing checks that a listed namespace matches the filename.
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
        filename: str = _DEFAULT_FILENAME,
    ) -> None:
        """Hold the document's text and the specifications that govern it.

        Args:
            text: The document's whole text, frontmatter included.
            corpus: The document's corpus, which is its specification name, such as `guide`.
            structure: The JSON of the corpus's structure specification; a document's context exists only for a
                corpus that states one.
            namespaces: The namespace specifications that govern the document, broad to narrow, as `namespace_spec`
                builds them.
            filename: The document's filename, without its extension.

        Raises:
            EmptyCorpusNameError: If the corpus is empty.
            InvalidCorpusNameCharacterError: If a character of the corpus falls outside lowercase snake case.
            EmptyAspectNameError: If the filename is empty.
            InvalidAspectNameCharacterError: If a character of the filename is not lowercase with valid separators.
            StructureSpecDecodeError: If the structure specification is not JSON or does not have the dialect's
                shape.
            InvalidTitlePatternError: If its title's pattern does not compile.
            InvalidFrontmatterSchemaError: If its frontmatter schema is rejected by the meta-schema.
            FrontmatterSchemaIdError: If a schema in its frontmatter schema carries `$id`.
            ForeignFrontmatterDialectError: If a schema in its frontmatter schema names another dialect.
            UntypedFrontmatterSchemaError: If its frontmatter schema's root does not state an object.
            EmptyStructureSpecError: If it states no rule.
            RepeatedOutlineSectionError: If its outline names a section twice.
            RepeatedForbiddenSectionError: If it forbids a section twice.
            ForbiddenOutlineSectionError: If it forbids a section its own outline names.
            AdjacentAnyRunsError: If its outline places two `any` runs side by side.
        """
        spec_name = CorpusSpecName(CorpusName.parse(corpus))
        self._text = text
        self._corpus_structure = _decode_structure(spec_name, structure)
        corpus_spec = CorpusSpec(name=spec_name, files=_files(spec_name), structure=self._corpus_structure)
        ref = DocumentRef(spec_name.corpus, AspectFilename.parse(filename))
        self._governance = Governance(ref, corpus_spec, namespaces)

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
        """The document, with its filename and its corpus's structure specification."""
        return DocumentFrontmatterOwner(filename=self.filename(), spec=self._corpus_structure.path)

    def parse(self) -> ParsedDocument:
        """The document's parse tree, as the real parser reads it."""
        return parse_document(self._text)

    def link_base(self) -> DocumentDirectory:
        """The directory holding the document, read from its ref."""
        return DocumentDirectory(self._governance.ref.path.parent)

    def link_targets(self) -> Mapping[PurePosixPath, PathLookup]:
        """None: a fake document holds no link target."""
        return FrozenMapping({})

    def tokens(self) -> UnsignedInt:
        """The tokens in the document's whole text, as the real tokenizer counts them."""
        # A count is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
        return UnsignedInt(count_tokens(self._text))

    def lines(self) -> UnsignedInt:
        """The lines in the document's whole text, as the real counter counts them."""
        # A count is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
        return UnsignedInt(count_lines(self._text))

    def specifications(self) -> Governance:
        """The specifications the test stated."""
        return self._governance

    def corpus_structure(self) -> StructureSpec:
        """The corpus's structure specification, decoded from the JSON the test stated."""
        return self._corpus_structure

    def outline_divergences(self) -> tuple[OutlineDivergenceSpec, ...]:
        """Where the sections stop matching each governing outline, as the real analysis finds it."""
        outlined_specs: list[StructureSpec] = []
        for structure_spec in self._governance.structure_specs():
            if structure_spec.outline:
                outlined_specs.append(structure_spec)
        return match_outlines(tuple(outlined_specs), self.parse().headings, count_lines(self._text))


class FakeSkillContext:
    """A skill whose `SKILL.md` a test writes as text, listed where the test names; a `SkillContext`."""

    _text: str
    _directory_name: str
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
        self._directory_name = directory_name
        self._link_target = link_target

    def directory_name(self) -> str:
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

    def frontmatter_owner(self) -> SkillFrontmatterOwner:
        """The skill, with its directory name and where a link there leads."""
        return SkillFrontmatterOwner(directory_name=self._directory_name, link_target=self._link_target)

    def parse(self) -> ParsedDocument:
        """The parse tree of the `SKILL.md`, as the real parser reads it."""
        return parse_document(self._text)

    def link_base(self) -> SkillRoot:
        """The skill directory, under the skills directory, at the name the test listed it under."""
        return SkillRoot(_SKILLS_DIRECTORY / self._directory_name)

    def link_targets(self) -> Mapping[PurePosixPath, PathLookup]:
        """None: a fake skill holds no link target."""
        return FrozenMapping({})

    def lines(self) -> UnsignedInt:
        """The lines in the whole `SKILL.md`, as the real counter counts them."""
        # A count is never negative, so building the `UnsignedInt` cannot raise `NegativeIntError` here.
        return UnsignedInt(count_lines(self._text))


DEFAULT_SKILL_DIRECTORY: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills/review')
"""The skill directory a fake resource belongs to unless a test names another."""

DEFAULT_DOCUMENT_DIRECTORY: Final[RootRelativePath] = RootRelativePath.parse('docs/guide')
"""The directory a fake document lies in unless a test names another."""


class FakeSkillResourceContext:
    """A resource of a skill a test writes as text; a `SkillResourceContext`."""

    _text: str
    _skill_directory: RootRelativePath
    _link_targets: Mapping[PurePosixPath, PathLookup]

    def __init__(
        self,
        text: str,
        *,
        skill_directory: RootRelativePath = DEFAULT_SKILL_DIRECTORY,
        link_targets: Mapping[PurePosixPath, PathLookup] = FrozenMapping({}),
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

    def link_targets(self) -> Mapping[PurePosixPath, PathLookup]:
        """What the snapshot holds at each link target, as the test stated it."""
        return self._link_targets


class FakeDocumentMarkdownContext:
    """A document a test writes as text, asked only what any Markdown file is asked; a `MarkdownContext`."""

    _text: str
    _directory: RootRelativePath
    _link_targets: Mapping[PurePosixPath, PathLookup]

    def __init__(
        self,
        text: str,
        *,
        directory: RootRelativePath = DEFAULT_DOCUMENT_DIRECTORY,
        link_targets: Mapping[PurePosixPath, PathLookup] = FrozenMapping({}),
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

    def link_targets(self) -> Mapping[PurePosixPath, PathLookup]:
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
