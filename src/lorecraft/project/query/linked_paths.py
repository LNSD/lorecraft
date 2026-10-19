"""The paths an item's links reach, shared by queries that follow links between items."""

from lorecraft.project.link_target import DocumentDirectory, LinkedDocument, linked_files_of
from lorecraft.project.query.item_facts import item_parse
from lorecraft.project.query.primitives import Primitives


def linked_paths(primitives: Primitives) -> tuple[LinkedDocument, ...]:
    """The existing Markdown files a document links to, in link order. Raises nothing.

    A skill entry or resource has no document links. The result records the resolved root-relative path, so a query
    can ask that item's database for another derived value without resolving the link again.

    Args:
        primitives: The model state of the document.
    """
    base = primitives.link_base()
    if not isinstance(base, DocumentDirectory):
        return ()
    return linked_files_of(primitives.query(item_parse).links, primitives.link_targets(), base)
