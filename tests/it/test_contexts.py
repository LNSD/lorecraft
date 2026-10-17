"""The database-backed contexts, held to the protocols of `lorecraft.project` they implement.

Each method of `DocumentContext`, `SkillContext`, `SkillResourceContext` and `SymlinkContext` is asked through a
value typed as the protocol, over a database opened on an in-memory snapshot, or on a scan of a real tree where the
query needs a path in scope, and compared with what the database's matching query returns; a fact the database
memoizes is the very value the query keeps, so a context computes nothing of its own. The static hold of each class
to its protocol is in `lorecraft.project.database.tests.test_context`, where the type-checking gate reaches it.
"""

from collections.abc import Mapping
from pathlib import Path
from textwrap import dedent
from typing import Final, assert_never

from lib.tree import FileTree, from_tree
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.context import (
    DocumentContext,
    SkillContext,
    SkillResourceContext,
)
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import (
    Database,
    DatabaseItemContext,
    ItemText,
)
from lorecraft.project.document import DocumentRef, SpecRef
from lorecraft.project.item import MarkdownItemRef
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.link_target import (
    LinkBase,
    LinkTarget,
    LinkTargetEntry,
    PathLookup,
)
from lorecraft.project.query import Primitives
from lorecraft.project.schemas import (
    FrontmatterOwner,
    SchemaProblems,
    SkillFields,
)
from lorecraft.project.skill import SkillLocation, SkillRef
from lorecraft.project.syntax import Anchor, NormalisedLinkPath
from lorecraft.vfs import (
    ResolvedPath,
    Snapshot,
    take_snapshot,
)

TYPING: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))
"""A document of corpus `code` its `python` namespace governs too."""

TYPING_TEXT: Final[str] = (
    '---\nname: python-typing\nowner: 7\n---\n# Typing\n\n## Rule\n\nAnnotate every signature, as [the code corpus]'
    '(../__meta__/code.md) says, not [gone](gone.md), [the source](../../src/main.py) or [up](../../../x.md).\n'
)
"""The text of `TYPING`: a frontmatter whose `owner` the corpus schema rejects, a title and one section."""

CORPUS_STRUCTURE: Final[bytes] = (
    b'{"tokens": 400, "outline": [{"section": "Rule"}, {"section": "Checklist"}], '
    b'"frontmatter": {"type": "object", "properties": {"owner": {"type": "string"}}}}'
)
"""The corpus structure specification: a budget, an outline `TYPING` lacks a section of, and a frontmatter schema."""

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.spec.json')
"""Where the corpus structure specification lies."""

SPEC: Final[SpecRef] = SpecRef(RootRelativePath.parse('docs/__meta__/code-python.md'))
"""A meta specification, the namespace spec `python` of corpus `code`."""

SPEC_TEXT: Final[str] = dedent(
    """\
    # Code Python

    Read [the code spec](code.md), not [gone](gone.md).
    """
)
"""The text of `SPEC`: a title and two links, one to the corpus spec beside it and one to nothing."""

REVIEW: Final[SkillRef] = SkillRef(
    ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review')
)
"""A skill an agent reaches under `.agents/skills`."""

REVIEW_TEXT: Final[str] = (
    '---\nname: reviewer\n---\n# Review\n\nRead [the checklist](references/checklist.md), not '
    '[gone](references/gone.md) or [up](../x.md).\n'
)
"""The `SKILL.md` of `REVIEW`: a frontmatter missing the `description` the Agent Skills specification requires."""

CHECKLIST_TEXT: Final[str] = '# Checklist\n\nRead [the review](SKILL.md), not [gone](gone.md).\n'
"""The text of `REVIEW`'s one resource, `references/checklist.md`: a title and a link."""


def _tree() -> FileTree:
    """Corpus `code`, with a `python` namespace, holding `TYPING`, and `REVIEW` with one resource, as files."""
    return {
        '.agents': {
            'skills': {
                'review': {
                    'SKILL.md': REVIEW_TEXT.encode(),
                    'references': {'checklist.md': CHECKLIST_TEXT.encode()},
                }
            }
        },
        'docs': {
            '__meta__': {
                'code.md': b'# Code\n',
                'code.spec.json': CORPUS_STRUCTURE,
                'code-python.md': SPEC_TEXT.encode(),
                'code-python.spec.json': b'{"tokens": 200}',
            },
            'code': {'python-typing.md': TYPING_TEXT.encode()},
        },
    }


def _snapshot() -> Snapshot:
    """A snapshot of `_tree`, built in memory, so no path is in its scope."""
    return from_tree(_tree())


def _link_target(path: str, lookup: PathLookup) -> LinkTarget:
    """The target of a link: the root-relative path it leads to, and what the snapshot holds there.

    Args:
        path: The root-relative path the link leads to.
        lookup: What the snapshot holds at the path.
    """
    return LinkTarget(path=RootRelativePath.parse(path), lookup=lookup)


def _document_context(database: Database) -> DocumentContext:
    """The context of `TYPING`, typed as the protocol, so the type checker holds the class to it.

    Args:
        database: The database `TYPING` is read from.
    """
    return DatabaseItemContext(database, _document_item(database))


def _document_item(database: Database) -> ItemText:
    """The witness of `TYPING`, as the database decodes it by its common reference.

    Args:
        database: The database the document is decoded by.
    """
    source = database.item_text(MarkdownItemRef(TYPING.path))
    assert isinstance(source, ItemText), f'{TYPING.path} was written as UTF-8, so it decodes'
    return source


def _spec_item(database: Database) -> ItemText:
    """The witness of `SPEC`, as the database decodes it by its common reference.

    Args:
        database: The database the specification is decoded by.
    """
    source = database.item_text(MarkdownItemRef(SPEC.path))
    assert isinstance(source, ItemText), f'{SPEC.path} was written as UTF-8, so it decodes'
    return source


def _skill_item(database: Database) -> ItemText:
    """The witness of `REVIEW`'s `SKILL.md`, as the database decodes it by its common reference.

    Args:
        database: The database the `SKILL.md` is decoded by.
    """
    source = database.item_text(MarkdownItemRef(REVIEW.path))
    assert isinstance(source, ItemText), f'{REVIEW.path} was written as UTF-8, so it decodes'
    return source


def _location(database: Database) -> SkillLocation:
    """Where the database's model locates `REVIEW`.

    Args:
        database: The database whose model lists the skill.
    """
    location = database.model().find_skill_location(REVIEW.directory)
    assert location is not None, f'the model lists the skill {REVIEW.directory}'
    return location


def _resource_text(database: Database) -> ItemText:
    """The witness of `REVIEW`'s one resource, as the database decodes it at the file its listing locates.

    Args:
        database: The database the resource is listed and decoded by.
    """
    (resource,) = database.skill_resources(_location(database)).resources
    source = database.item_text(database.resource_item(resource))
    assert isinstance(source, ItemText), f'{resource.ref.path} was written as UTF-8, so it decodes'
    return source


def _resource_context(database: Database) -> SkillResourceContext:
    """The context of `REVIEW`'s one resource, typed as the protocol, so the type checker holds the class to it.

    Args:
        database: The database the resource is read from.
    """
    return DatabaseItemContext(database, _resource_text(database))


def _skill_context(database: Database) -> SkillContext:
    """The context of `REVIEW`, typed as the protocol, so the type checker holds the class to it.

    Args:
        database: The database `REVIEW` is read from.
    """
    return DatabaseItemContext(database, _skill_item(database))


def _scanned(root: Path) -> Database:
    """A database over a scan of a real tree holding what `_snapshot` holds, so the scope covers `docs/` and the skill.

    `Snapshot.from_tree` scans nothing, so no path is in its scope; asking what the snapshot holds at a path needs a
    scan.

    Args:
        root: Directory the tree is written into, as the repository root.
    """
    _write_tree(root, _tree())
    return Database.from_snapshot(take_snapshot(root, SNAPSHOT_SCOPE))


def _write_tree(directory: Path, tree: FileTree) -> None:
    """Write a tree of files under a directory, a nested mapping a directory each, as `Snapshot.from_tree` reads one.

    Args:
        directory: The directory the tree's entries are written into; created if absent.
        tree: Each entry's name, mapped to a file's bytes or to the tree of a directory.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for name, entry in tree.items():
        match entry:
            case bytes():
                (directory / name).write_bytes(entry)
            case Mapping():
                _write_tree(directory / name, entry)
            case _:
                assert_never(entry)


def _schema_problems(primitives: Primitives) -> tuple[SchemaProblems, ...]:
    """What each schema that governs the item rejects in its frontmatter."""
    return primitives.schema_problems()


def _skill_fields(primitives: Primitives) -> SkillFields:
    """The fields of the skill's frontmatter that parse."""
    return primitives.skill_fields()


def _link_base(primitives: Primitives) -> LinkBase | None:
    """Where the item's relative links are read from."""
    return primitives.link_base()


def _link_targets(primitives: Primitives) -> Mapping[NormalisedLinkPath, LinkTargetEntry]:
    """What the snapshot holds at the target of each relative link of the item."""
    return primitives.link_targets()


def _anchors(primitives: Primitives) -> frozenset[Anchor]:
    """The anchor of every heading of the item's parse."""
    return primitives.anchors()


def _document_base(primitives: Primitives) -> str | None:
    """The stem of the document or specification the item extends."""
    return primitives.document_base()


def _frontmatter_owner(primitives: Primitives) -> FrontmatterOwner:
    """Whose frontmatter block the item opens, with the name its frontmatter must carry."""
    return primitives.frontmatter_owner()
