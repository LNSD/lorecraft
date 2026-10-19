"""The link-group queries over one document and the documents it points to."""

import logging

from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.item import ItemReadError, ItemRef
from lorecraft.project.link_target import DocumentDirectory, DocumentLink, document_links_of
from lorecraft.project.query import ItemPrimitives, item_name, linked_paths
from lorecraft.project.workspace.model import find_document_at

logger = logging.getLogger(__name__)


def linked_documents(primitives: ItemPrimitives) -> tuple[DocumentLink, ...]:
    """The links to other documents and whether each destination links back. Raises nothing.

    Paths and destination answers are queries, so cross-item dependencies are recorded by ref.

    Args:
        primitives: The model state of the document.
    """
    base = primitives.link_base()
    name = primitives.query(item_name)
    if not isinstance(base, DocumentDirectory) or name is None:
        return ()
    source = base.directory / RootRelativePath.parse(f'{name}.md')
    linked = primitives.query(linked_paths)
    documents: dict[RootRelativePath, tuple[CorpusName, AspectFilename]] = {
        link.path: (document.corpus, document.filename)
        for link in linked
        if (document := find_document_at(ItemRef(link.path))) is not None
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
