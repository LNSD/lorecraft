"""Questions a test asks of a `Database` that no check does, answered from its internals."""

from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database
from lorecraft.project.item import ItemDescriptor, MarkdownItemRef, UnlistedItemError
from lorecraft.vfs import ResolvedPath


def find_file(database: Database, path: RootRelativePath) -> ResolvedPath | None:
    """The file `path` leads to in the database's snapshot, every recorded link on the way followed."""
    return database._fs.find_file(path)  # noqa: SLF001


def is_in_scope(database: Database, path: RootRelativePath) -> bool:
    """Whether the scan lists the directory `path` sits in, as the snapshot's scope declares it."""
    return database._built_scope_index().is_in_scope(path)  # noqa: SLF001


def listed_item(database: Database, ref: MarkdownItemRef) -> ItemDescriptor:
    """The descriptor the model resolved for a listed item; raises `UnlistedItemError` for any other."""
    item = database.model().find_item(ref)
    if item is None:
        raise UnlistedItemError(ref)
    return item.descriptor
