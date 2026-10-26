"""Where each relative link of a Markdown file leads, read from its link base, and what the snapshot holds there.

Each view answers from a hand-built snapshot that declares the scope a scan of the repository reads, so a path in
`docs/` or in a skill is in the scope and anything else, such as `src/`, is not.
"""

from pathlib import PurePosixPath
from typing import Final

import pytest

from lib.tree import FileTree, from_tree
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber, Link
from lorecraft.vfs import EntryRecord, ScopeIndex, Snapshot, SnapshotRecords, SymlinkRecord, VirtualFileSystem
from lorecraft.vfs.view import AbsoluteSymlinkTarget, RelativeSymlinkTarget, SymlinkTarget

from ..layout import SNAPSHOT_SCOPE
from ..link_target import (
    DirectoryTarget,
    DocumentDirectory,
    EscapingTarget,
    FileTarget,
    LinkTarget,
    LinkTargetEntry,
    LinkTargetFailure,
    MissingTarget,
    OutsideScopeTarget,
    SkillRoot,
    link_targets_of,
)

REVIEW_ROOT: Final[SkillRoot] = SkillRoot(RootRelativePath.parse('.agents/skills/review'))
"""Where the links of every file of the skill `review` are read from."""

GUIDE_DIRECTORY: Final[DocumentDirectory] = DocumentDirectory(RootRelativePath.parse('docs/guide'))
"""Where the links of a document of corpus `guide` are read from."""


def _target(raw: str) -> SymlinkTarget:
    """Wrap a target written as it would be by `os.readlink`."""
    target = PurePosixPath(raw)
    if target.is_absolute():
        return AbsoluteSymlinkTarget(target)
    return RelativeSymlinkTarget(target)


def _tree() -> FileTree:
    """A skill with one resource, two corpora with one document each, and a directory outside every skill."""
    return {
        '.agents': {
            'skills': {
                'review': {
                    'SKILL.md': b'# Review\n',
                    'references': {'a.md': b'# A\n'},
                }
            }
        },
        'docs': {'guide': {'setup.md': b'# Setup\n'}, 'code': {'rules.md': b'# Rules\n'}},
        'shared': {'guides': {'d.md': b'# D\n'}},
    }


def _snapshot(*links: tuple[str, str]) -> Snapshot:
    """`_tree()`, with each symlink given, recorded as a scan of the repository's scope would declare it.

    Args:
        links: Each symlink, as its root-relative path and its target as written.
    """
    records: dict[RootRelativePath, EntryRecord] = dict(from_tree(_tree()).records)
    for path, target in links:
        records[RootRelativePath.parse(path)] = SymlinkRecord(_target(target))
    return Snapshot(SnapshotRecords(records), scope=SNAPSHOT_SCOPE)


def _file_target(path: str) -> LinkTarget:
    """A link target whose root-relative path names a file."""
    target = RootRelativePath.parse(path)
    return LinkTarget(target=FileTarget(target))


def _directory_target(path: str) -> LinkTarget:
    """A link target whose root-relative path names a directory."""
    target = RootRelativePath.parse(path)
    return LinkTarget(target=DirectoryTarget(target))


def _missing_target(path: str) -> LinkTargetEntry:
    """A link target whose root-relative path is missing from the scanned snapshot."""
    return LinkTargetFailure(MissingTarget(RootRelativePath.parse(path)))


def _outside_scope_target(path: str) -> LinkTargetEntry:
    """A link target whose root-relative path is outside the scanned snapshot's scope."""
    return LinkTargetFailure(OutsideScopeTarget(RootRelativePath.parse(path)))


def _find(urls: tuple[str, ...], base: SkillRoot | DocumentDirectory, snapshot: Snapshot) -> dict[str, LinkTargetEntry]:
    """The link targets of a file holding one link per destination, keyed by each normalised path as a string.

    Args:
        urls: Each link's destination, as the parser encodes it.
        base: Where the file's relative links are read from.
        snapshot: The snapshot each target is looked up in.
    """
    links: list[Link] = []
    for url in urls:
        links.append(Link(url, LineNumber(NonZeroUnsignedInt(1))))
    targets = link_targets_of(tuple(links), base, VirtualFileSystem(snapshot), ScopeIndex(snapshot))
    found: dict[str, LinkTargetEntry] = {}
    for path, target in targets.items():
        found[str(path)] = target
    return found


@pytest.mark.unit
class TestFindLinkTargetsInASkill:
    def test_link_targets_of_with_a_file_and_a_directory_of_the_skill_finds_both_present(self) -> None:
        #: Given
        urls = ('references/a.md', 'references/')
        snapshot = _snapshot()

        #: When
        found = _find(urls, REVIEW_ROOT, snapshot)

        #: Then
        assert found == {
            'references/a.md': _file_target('.agents/skills/review/references/a.md'),
            'references': _directory_target('.agents/skills/review/references'),
        }, 'a file and a directory the skill holds are both present, keyed by the normalised path'

    def test_link_targets_of_with_nothing_at_the_path_finds_it_missing(self) -> None:
        #: Given
        urls = ('references/b.md',)
        snapshot = _snapshot()

        #: When
        found = _find(urls, REVIEW_ROOT, snapshot)

        #: Then
        assert found == {'references/b.md': _missing_target('.agents/skills/review/references/b.md')}, (
            'nothing in a directory of the skill is missing, and the entry keeps the path it was looked up at'
        )

    def test_link_targets_of_reads_a_link_from_the_skill_root_whichever_file_holds_it(self) -> None:
        #: Given
        # `a.md` would be the resource itself, read from `references/`; from the skill root it names nothing.
        urls = ('a.md', 'references/../SKILL.md')
        snapshot = _snapshot()

        #: When
        found = _find(urls, REVIEW_ROOT, snapshot)

        #: Then
        assert found == {
            'a.md': _missing_target('.agents/skills/review/a.md'),
            'SKILL.md': _file_target('.agents/skills/review/SKILL.md'),
        }, 'every link is read from the skill root, and a `..` cancels the directory written before it'

    def test_link_targets_of_with_a_link_to_the_skill_root_itself_finds_it_present(self) -> None:
        #: Given
        urls = ('references/..',)
        snapshot = _snapshot()

        #: When
        found = _find(urls, REVIEW_ROOT, snapshot)

        #: Then
        assert found == {'.': _directory_target('.agents/skills/review')}, (
            'references/.. normalises to the skill root itself, which is not above it'
        )

    def test_link_targets_of_with_a_link_out_and_back_in_by_the_repository_path_finds_it_escaping(self) -> None:
        #: Given
        urls = ('../../skills/review/SKILL.md',)
        snapshot = _snapshot()

        #: When
        found = _find(urls, REVIEW_ROOT, snapshot)

        #: Then
        assert found == {'../../skills/review/SKILL.md': LinkTargetFailure(EscapingTarget())}, (
            'the path alone decides, so a link out and back in by where the skill lies in the repository escapes'
        )

    def test_link_targets_of_with_a_link_climbing_above_the_skill_root_finds_it_escaping(self) -> None:
        #: Given
        urls = ('../review/SKILL.md',)
        snapshot = _snapshot()

        #: When
        found = _find(urls, REVIEW_ROOT, snapshot)

        #: Then
        assert found == {'../review/SKILL.md': LinkTargetFailure(EscapingTarget())}, (
            'a link climbing above the skill root names nothing the skill carries, so it is an escaping target'
        )

    def test_link_targets_of_with_links_spelling_no_relative_path_gives_them_no_entry(self) -> None:
        #: Given
        urls = ('https://example.com/a.md', '/a.md', '#usage')
        snapshot = _snapshot()

        #: When
        found = _find(urls, REVIEW_ROOT, snapshot)

        #: Then
        assert found == {}, 'a URL, an absolute link and a fragment-only link name no relative path'

    def test_link_targets_of_through_a_symlinked_directory_in_the_skill_follows_it(self) -> None:
        #: Given
        snapshot = _snapshot(('.agents/skills/review/guides', '../../../shared/guides'))
        urls = ('guides/d.md', 'guides/e.md')

        #: When
        found = _find(urls, REVIEW_ROOT, snapshot)

        #: Then
        assert found == {
            'guides/d.md': _file_target('.agents/skills/review/guides/d.md'),
            'guides/e.md': _missing_target('.agents/skills/review/guides/e.md'),
        }, 'the symlink inside the skill is followed to the files it leads to'


@pytest.mark.unit
class TestFindLinkTargetsInADocument:
    def test_link_targets_of_reads_a_link_from_the_document_directory(self) -> None:
        #: Given
        urls = ('setup.md', 'install.md', '../code/rules.md')
        snapshot = _snapshot()

        #: When
        found = _find(urls, GUIDE_DIRECTORY, snapshot)

        #: Then
        assert found == {
            'setup.md': _file_target('docs/guide/setup.md'),
            'install.md': _missing_target('docs/guide/install.md'),
            '../code/rules.md': _file_target('docs/code/rules.md'),
        }, "a document's links are read from its own directory, and a `..` may climb out of it"

    def test_link_targets_of_with_a_path_the_scan_never_read_finds_it_outside_the_scope(self) -> None:
        #: Given
        urls = ('../../shared/guides/d.md',)
        snapshot = _snapshot()

        #: When
        found = _find(urls, GUIDE_DIRECTORY, snapshot)

        #: Then
        assert found == {'../../shared/guides/d.md': _outside_scope_target('shared/guides/d.md')}, (
            'a path in a directory the scan never read is outside the scope, whatever the snapshot holds there'
        )

    def test_link_targets_of_with_a_link_climbing_above_the_repository_finds_it_escaping(self) -> None:
        #: Given
        urls = ('../../../x.md',)
        snapshot = _snapshot()

        #: When
        found = _find(urls, GUIDE_DIRECTORY, snapshot)

        #: Then
        assert found == {'../../../x.md': LinkTargetFailure(EscapingTarget())}, (
            'a path climbing above the repository root names nothing the snapshot can hold, so it is escaping'
        )
