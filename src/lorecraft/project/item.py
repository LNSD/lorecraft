"""Common identity and model-resolved facts for governed Markdown items.

The ref names an item where the repository lists it. Its descriptor records the
location and origin facts needed by consumers without reading the item's text.
"""

from dataclasses import dataclass
from enum import Enum
from typing import assert_never

from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.project.link_target import LinkBase
from lorecraft.vfs import FileReadFailure, ResolvedPath, UnrecordedFileError


@dataclass(frozen=True, slots=True, order=True)
class MarkdownItemRef:
    """The logical, reportable path of one governed Markdown item.

    Attributes:
        path: Root-relative path where the repository lists the item, also used in reports.
    """

    path: RootRelativePath


class ItemKind(Enum):
    """The kinds of governed Markdown item a rule may apply to."""

    DOCUMENT = 'document'
    SKILL_ENTRY = 'skill-entry'
    SKILL_RESOURCE = 'skill-resource'
    SPECIFICATION = 'specification'


class ItemFacet(Enum):
    """Kinds of checks a model may activate for an item."""

    FRONTMATTER = 'frontmatter'
    STRUCTURE = 'structure'
    OUTLINE = 'outline'
    BUDGET = 'budget'
    MARKDOWN = 'markdown'


@dataclass(frozen=True, slots=True)
class DocumentOrigin:
    """Origin facts for a corpus document.

    Attributes:
        expected_name: Filename stem the document's frontmatter name is checked against.
        corpus: Corpus path component used as the governance target.
        schema_paths: Governing frontmatter schemas, broad to narrow; `()` when none governs the document.
    """

    expected_name: str
    corpus: str
    schema_paths: tuple[RootRelativePath, ...]


@dataclass(frozen=True, slots=True)
class SkillEntryOrigin:
    """Origin facts for a listed skill entry.

    Attributes:
        expected_name: Listed directory name the skill's frontmatter name is checked against.
        link_target: Resolved directory when the listed entry is linked, for compatibility notes; otherwise None.
    """

    expected_name: str
    link_target: ResolvedPath | None


@dataclass(frozen=True, slots=True)
class SkillResourceOrigin:
    """Origin facts for a Markdown resource inside a skill.

    The resource keeps its own ref and read location. The containing skill identifies its provenance only; no
    corpus governance is applied to the resource.

    Attributes:
        skill_entry: Listed directory name of the containing skill.
    """

    skill_entry: str


@dataclass(frozen=True, slots=True)
class SpecificationOrigin:
    """Origin facts for a meta specification, a Markdown file of `docs/__meta__/`.

    Attributes:
        expected_name: Specification name, the file's stem, such as `feat-cli`.
        corpus: Corpus the specification belongs to, the first segment of its name.
    """

    expected_name: str
    corpus: str


type ItemOrigin = DocumentOrigin | SkillEntryOrigin | SkillResourceOrigin | SpecificationOrigin


@dataclass(frozen=True, slots=True)
class MarkdownItemDescriptor:
    """Model-resolved locations and origin metadata for a Markdown item.

    Attributes:
        ref: Common logical identity and report path.
        read_location: Snapshot path from which the item's text is read.
        link_base: Where the item's relative Markdown links are read from, with the climb bound of that base.
        origin: Expected-name and provenance facts specific to the item's origin.
        governance_corpus: Corpus whose specifications govern the item, when it belongs to one; empty otherwise.
        aspect_name: Listed name matched against namespace specifications, when it belongs to a corpus; retained as
            provenance for skills and resources.
        active_facets: Checks enabled for this item. The package's skill checks activate skill-entry frontmatter and
            structure checks, independently of corpus governance. A meta specification is active for structure and
            Markdown checks; a resource activates the structure and Markdown facets.
    """

    ref: MarkdownItemRef
    read_location: ResolvedPath
    link_base: LinkBase
    origin: ItemOrigin
    governance_corpus: str
    aspect_name: str
    active_facets: frozenset[ItemFacet]

    @property
    def kind(self) -> ItemKind:
        """Which kind of item the descriptor is for, read from its origin."""
        match self.origin:
            case DocumentOrigin():
                return ItemKind.DOCUMENT
            case SkillEntryOrigin():
                return ItemKind.SKILL_ENTRY
            case SkillResourceOrigin():
                return ItemKind.SKILL_RESOURCE
            case SpecificationOrigin():
                return ItemKind.SPECIFICATION
            case _:
                assert_never(self.origin)


class UnlistedItemError(Error):
    """A common reference names no document or skill entry the model lists.

    Attributes:
        ref: The reference the model does not list.
    """

    ref: MarkdownItemRef

    def __init__(self, ref: MarkdownItemRef) -> None:
        self.ref = ref
        super().__init__(f'the model lists no Markdown item at {ref.path}')


class ItemReadError(Error):
    """A listed item's file is missing or unreadable.

    Attributes:
        ref: The item that could not be read.
        source: The failure to read its file.
    """

    ref: MarkdownItemRef
    source: FileReadFailure | UnrecordedFileError

    def __init__(self, ref: MarkdownItemRef, *, source: FileReadFailure | UnrecordedFileError) -> None:
        self.ref = ref
        self.source = source
        super().__init__(f'cannot read item {ref.path}')
        self.__cause__ = source
