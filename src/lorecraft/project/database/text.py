"""The decoded text of a file, as the database's decode queries return it: a witness, or an undecodable marker.

A witness holds a ref and that ref's bytes decoded as UTF-8, one type per kind of file, so a document's text cannot
be passed where a skill's is asked for. Every per-file query of the `Database` takes a witness rather than a bare
ref, so asking for a fact of a file that does not decode cannot be written: a caller matches the decode query's
answer once, and no later reader carries a branch for an undecodable file.

Only the database builds a witness. Python has no private constructor, so nothing stops another caller from
building one; forged text would still be text, but no longer that ref's bytes. A witness also belongs to the
database that built it, which no type records, so it never leaves the run that asked for it.
"""

from dataclasses import dataclass

from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import SkillRef, SkillResourceRef


@dataclass(frozen=True, slots=True)
class DocumentText:
    """One document's bytes, decoded; built only by `Database.text`.

    Attributes:
        ref: The document the text was read from.
        text: The document's whole file, frontmatter included.
    """

    ref: DocumentRef
    text: str


@dataclass(frozen=True, slots=True)
class SkillText:
    """One skill's `SKILL.md` bytes, decoded; built only by `Database.skill_text`.

    Attributes:
        ref: The skill whose `SKILL.md` the text was read from.
        text: The whole `SKILL.md`, frontmatter included.
    """

    ref: SkillRef
    text: str


@dataclass(frozen=True, slots=True)
class SkillResourceText:
    """One resource's bytes, decoded; built only by `Database.skill_resource_text`.

    Attributes:
        ref: The resource the text was read from, as the skill's resource listing names it.
        text: The resource's whole file.
    """

    ref: SkillResourceRef
    text: str


@dataclass(frozen=True, slots=True)
class Undecodable:
    """A file whose bytes are not UTF-8: what a decode query returns instead of a witness.

    Attributes:
        ref: The document, skill or resource whose file did not decode.
    """

    ref: DocumentRef | SkillRef | SkillResourceRef
