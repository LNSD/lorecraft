"""Whose frontmatter block it is: a document a frontmatter schema governs, or a skill."""

from dataclasses import dataclass

from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.schemas.name import SpecName
from lorecraft.vfs import ResolvedPath


@dataclass(frozen=True, slots=True)
class DocumentFrontmatterOwner:
    """A document or spec whose frontmatter a schema governs, and where it is governed.

    Attributes:
        filename: The listed name, without its extension, which its frontmatter `name` must equal. A document has
            an aspect filename; a spec has its typed specification name.
        spec: The structure specification of the document or spec's corpus, whose frontmatter schema
            makes the item governed for its frontmatter. A namespace's schema only narrows the corpus's, so this one
            file is always the specification that states every rule over the block.
    """

    filename: AspectFilename | SpecName
    spec: RootRelativePath


@dataclass(frozen=True, slots=True)
class SkillFrontmatterOwner:
    """A skill, whose frontmatter the package governs after the Agent Skills specification.

    Attributes:
        directory_name: The name of the skill directory as an agent lists it in its skills directory, which the
            frontmatter `name` must equal. An agent never resolves a link itself, so where a link leads plays no
            part in it.
        link_target: The resolved directory the listed directory leads to when it is a link, or `None` when it is
            not; it only words a note, so a reader sees why the name they know is not the one expected.
    """

    directory_name: PathComponent
    link_target: ResolvedPath | None


# Whose frontmatter block it is: a document a frontmatter schema governs, or a skill. A union of two records rather
# than one with a flag, so a document can never carry a link target, nor a skill a specification.
type FrontmatterOwner = DocumentFrontmatterOwner | SkillFrontmatterOwner
