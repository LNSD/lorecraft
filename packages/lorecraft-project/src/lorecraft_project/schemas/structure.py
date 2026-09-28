"""The decoded, unvalidated JSON of a structure specification file.

The structure check still runs as a vendored script, so nothing in the library gives this JSON a meaning yet,
and nothing here claims it has one. When that check migrates, its rules are decoded at load into a
``StructureAspect`` whose construction validates them, the way ``HeaderAspect`` validates a header schema, and
this type stays what the repository returns before that step.
"""

from typing import NewType

# A NewType only keeps structure JSON apart from header and budget JSON; it proves nothing about its content.
StructureSchema = NewType('StructureSchema', dict[str, object])
