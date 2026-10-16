"""Common identity and model-resolved facts for governed Markdown items.

The ref names an item where the repository lists it. Its descriptor records the
location and origin facts needed by consumers without reading the item's text.
"""

from dataclasses import dataclass
from enum import Enum

from lorecraft.core.path import RootRelativePath
from lorecraft.vfs import ResolvedPath


@dataclass(frozen=True, slots=True, order=True)
class MarkdownItemRef:
    """The logical, reportable path of one governed Markdown item.

    Attributes:
        path: Root-relative path where the repository lists the item, also used in reports.
    """

    path: RootRelativePath


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


type ItemOrigin = DocumentOrigin | SkillEntryOrigin


@dataclass(frozen=True, slots=True)
class MarkdownItemDescriptor:
    """Model-resolved locations and origin metadata for a Markdown item.

    Attributes:
        ref: Common logical identity and report path.
        read_location: Snapshot path from which the item's text is read.
        link_base: Root-relative directory for resolving relative Markdown links.
        origin: Expected-name and provenance facts specific to the item's origin.
        governance_corpus: Corpus whose specifications govern the item.
        aspect_name: Listed name matched against namespace specifications.
        active_facets: Checks the model has enabled for this item.
    """

    ref: MarkdownItemRef
    read_location: ResolvedPath
    link_base: RootRelativePath
    origin: ItemOrigin
    governance_corpus: str
    aspect_name: str
    active_facets: frozenset[ItemFacet]
