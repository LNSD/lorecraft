"""The link-group queries over one document and the documents it points to."""

import logging
from dataclasses import dataclass
from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.item import ItemReadError, ItemRef
from lorecraft.project.link_target import DocumentDirectory, DocumentLink, document_links_of
from lorecraft.project.query import ItemPrimitives, item_base, item_name, linked_paths
from lorecraft.project.schemas import CorpusSpecName, NamespaceSpecName
from lorecraft.project.workspace.model import find_document_at

logger = logging.getLogger(__name__)

type ExtensionDocumentName = AspectFilename | CorpusSpecName | NamespaceSpecName


@dataclass(frozen=True, slots=True)
class ExtensionDocument:
    """The typed identity and link directory shared by rules over extending documents."""

    base: ExtensionDocumentName | None
    name: ExtensionDocumentName
    directory: RootRelativePath


@dataclass(frozen=True, slots=True)
class NotExtensionDocument:
    """The queried item is not a decoded aspect document or specification."""


type ExtensionDocumentQuery = ExtensionDocument | NotExtensionDocument


def extension_document(primitives: ItemPrimitives) -> ExtensionDocumentQuery:
    """The name, nearest extension base and directory of a decoded aspect document or spec."""
    name = primitives.query(item_name)
    link_base = primitives.link_base()
    if not isinstance(name, AspectFilename | CorpusSpecName | NamespaceSpecName) or not isinstance(
        link_base, DocumentDirectory
    ):
        return NotExtensionDocument()
    return ExtensionDocument(base=primitives.query(item_base), name=name, directory=link_base.directory)


def linked_documents(primitives: ItemPrimitives) -> tuple[DocumentLink, ...]:
    """The links to other documents and whether each destination links back. Raises nothing.

    Paths and destination answers are queries, so cross-item dependencies are recorded by ref.

    Args:
        primitives: The model state of the document.
    """
    extension = primitives.query(extension_document)
    match extension:
        case ExtensionDocument():
            pass
        case NotExtensionDocument():
            return ()
        case _:
            assert_never(extension)
    source = extension.directory / RootRelativePath.parse(f'{extension.name}.md')
    linked = primitives.query(linked_paths)
    documents: dict[RootRelativePath, tuple[CorpusName, AspectFilename]] = {
        link.path: (found.corpus, found.filename)
        for link in linked
        if (found := find_document_at(ItemRef(link.path))) is not None
    }
    back_links = {}
    for link in linked:
        if link.path not in documents or link.path == source:
            continue
        ref = ItemRef(link.path)
        try:
            paths = primitives.query_at(ref, linked_paths)
        except ItemReadError:
            logger.warning(
                'link destination read failed',
                exc_info=True,
                extra={'fields': {'destination': str(ref.path), 'source': str(source)}},
            )
            continue
        back_links[link.path] = any(candidate.path == source for candidate in paths)
    return document_links_of(linked, source, documents, back_links)
