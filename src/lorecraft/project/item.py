"""Common identity and model state for governed Markdown items.

The ref names an item where the repository lists it. Its descriptor records the
location and origin metadata needed by consumers without reading the item's text.
"""

from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, assert_never

from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename, AspectName
from lorecraft.project.corpus import CorpusName, ReservedCorpusDirectoryRef
from lorecraft.project.link_target import LinkBase
from lorecraft.project.skill import OutsideSymlinkRef
from lorecraft.schemas import SchemaRef
from lorecraft.vfs import FileReadFailure, ResolvedPath, UnrecordedFileError

if TYPE_CHECKING:
    from lorecraft.project.schemas.name import SpecName


@dataclass(frozen=True, slots=True, order=True)
class ItemRef:
    """The logical, reportable path of one governed Markdown item.

    Attributes:
        path: Root-relative path where the repository lists the item, also used in reports.
    """

    path: RootRelativePath


type SubjectRef = ItemRef | OutsideSymlinkRef | ReservedCorpusDirectoryRef


class WrongItemTypeError(TypeError):
    """An item value of the wrong type was requested, which a rule never does for its type."""

    def __init__(self, expected: str) -> None:
        super().__init__(f'expected {expected}')


class ItemType(Enum):
    """The types of governed Markdown file a rule may apply to."""

    DOCUMENT = 'document'
    SKILL_ENTRYPOINT = 'skill-entry'
    SKILL_RESOURCE = 'skill-resource'
    META_SPEC = 'specification'


class MetaSpecPart(StrEnum):
    """A part of a meta spec that may govern checks of an item."""

    FRONTMATTER = 'frontmatter'
    """The item's frontmatter: a loaded structure layer states a frontmatter schema."""
    STRUCTURE = 'structure'
    """The item's structure: a loaded corpus layer states a structure file."""
    OUTLINE = 'outline'
    """The item's sections: a loaded structure layer states an outline."""
    BUDGET = 'budget'
    """The item's length in tokens: a loaded structure layer sets a token budget."""


@dataclass(frozen=True, slots=True)
class DocumentOrigin:
    """A corpus document, whose identity and governance are on its descriptor."""


@dataclass(frozen=True, slots=True)
class SkillEntrypointOrigin:
    """Origin metadata for a skill entrypoint.

    Attributes:
        link_target: Resolved directory when the listed entry is linked, for compatibility notes; otherwise None.
    """

    link_target: ResolvedPath | None


@dataclass(frozen=True, slots=True)
class SkillResourceOrigin:
    """Origin metadata for a Markdown resource inside a skill.

    The resource keeps its own ref and read location. The containing skill identifies its provenance only; no
    corpus governance is applied to the resource.

    Attributes:
        skill_entry: Listed directory name of the containing skill.
    """

    skill_entry: str


@dataclass(frozen=True, slots=True)
class MetaSpecOrigin:
    """A meta spec, a Markdown file of `docs/__meta__/`."""


type ItemOrigin = DocumentOrigin | SkillEntrypointOrigin | SkillResourceOrigin | MetaSpecOrigin


@dataclass(frozen=True, slots=True)
class ItemDescriptor:
    """Model-resolved locations and origin metadata for a Markdown item.

    Attributes:
        ref: Common logical identity and report path.
        read_location: Snapshot path from which the item's text is read.
        link_base: Where the item's relative Markdown links are read from, with the climb bound of that base.
        origin: Provenance metadata specific to the item's origin.
        name: Typed name in the hierarchy used to find its base.
        listed_name: Original name used by governance and frontmatter ownership.
        corpus: Typed corpus whose meta specs govern the item, or none.
        schema_paths: Repository paths of governing frontmatter schemas, broad to narrow; bundled schemas have no path.
        frontmatter_schema_refs: Applicable frontmatter schema registry subjects, broad to narrow.
        governed_parts: Meta spec parts stated by loaded layers that govern this item.
    """

    ref: ItemRef
    read_location: ResolvedPath
    link_base: LinkBase
    origin: ItemOrigin
    name: AspectName | AspectFilename | SpecName | None
    listed_name: str
    corpus: CorpusName | None
    schema_paths: tuple[RootRelativePath, ...]
    frontmatter_schema_refs: tuple[SchemaRef, ...]
    governed_parts: frozenset[MetaSpecPart]

    @property
    def type(self) -> ItemType:
        """Which type of item the descriptor is for, read from its origin."""
        match self.origin:
            case DocumentOrigin():
                return ItemType.DOCUMENT
            case SkillEntrypointOrigin():
                return ItemType.SKILL_ENTRYPOINT
            case SkillResourceOrigin():
                return ItemType.SKILL_RESOURCE
            case MetaSpecOrigin():
                return ItemType.META_SPEC
            case _:
                assert_never(self.origin)


class UnlistedItemError(Error):
    """A common reference names no Markdown item or layout subject the model lists.

    Attributes:
        ref: The reference the model does not list.
    """

    ref: SubjectRef

    def __init__(self, ref: SubjectRef) -> None:
        self.ref = ref
        super().__init__(f'the model lists no subject at {ref.path}')


class ItemReadError(Error):
    """A listed item's file is missing or unreadable.

    Attributes:
        ref: The item that could not be read.
        source: The failure to read its file.
    """

    ref: ItemRef
    source: FileReadFailure | UnrecordedFileError

    def __init__(self, ref: ItemRef, *, source: FileReadFailure | UnrecordedFileError) -> None:
        self.ref = ref
        self.source = source
        super().__init__(f'cannot read item {ref.path}')
        self.__cause__ = source
