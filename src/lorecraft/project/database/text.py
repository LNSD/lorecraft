"""The decoded text of a file, as the database's decode queries return it: a witness, or an undecodable marker.

A witness holds a ref and that ref's bytes decoded as UTF-8, one type for every governed item, a skill's resource
included. Every per-file query of the `Database` takes a witness rather than a bare ref, so asking for a property of a
file that does not decode cannot be written: a caller matches the decode query's answer once, and no later reader
carries a branch for an undecodable file.

Only the database builds a witness. Python has no private constructor, so nothing stops another caller from
building one; forged text would still be text, but no longer that ref's bytes. A witness also belongs to the
database that built it, which no type records, so it never leaves the run that asked for it.
"""

from dataclasses import dataclass

from lorecraft.project.item import ItemDescriptor, ItemRef
from lorecraft.vfs import Utf8Failure


@dataclass(frozen=True, slots=True)
class ItemText:
    """One governed Markdown item's bytes, decoded; built only by `Database.item_text`.

    Attributes:
        descriptor: The model's descriptor for the item the text was read from.
        text: The whole file, frontmatter included.
    """

    descriptor: ItemDescriptor
    text: str

    @property
    def ref(self) -> ItemRef:
        """The item whose file the text was read from, the key of every per-file query."""
        return self.descriptor.ref


@dataclass(frozen=True, slots=True)
class Undecodable:
    """A file whose bytes are not UTF-8: what `Database.item_text` returns instead of a witness.

    Attributes:
        ref: The document, skill entry or resource whose file did not decode.
        failure: Where the file's bytes first stop being UTF-8, and why.
    """

    ref: ItemRef
    failure: Utf8Failure
