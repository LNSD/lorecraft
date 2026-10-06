"""Where each relative link of a Markdown file leads, read from its link base, and what the snapshot holds there.

Each view answers from a hand-built snapshot that declares the scope a scan of the repository reads, so a path in
`docs/` or in a skill is in the scope and anything else, such as `src/`, is not.
"""

from pathlib import PurePosixPath

import pytest

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import RootRelativePath
from lorecraft.vfs import EntryRecord, FileTree, ScopeIndex, Snapshot, SymlinkRecord, VirtualFileSystem

from ..layout import SNAPSHOT_SCOPE
from ..link_target import DocumentDirectory, PathLookup, SkillRoot, find_link_targets
from ..syntax import LineNumber, Link

REVIEW_ROOT: SkillRoot = SkillRoot(RootRelativePath.parse('.agents/skills/review'))
"""Where the links of every file of the skill `review` are read from."""

GUIDE_DIRECTORY: DocumentDirectory = DocumentDirectory(RootRelativePath.parse('docs/guide'))
"""Where the links of a document of corpus `guide` are read from."""

TREE: FileTree = {
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
"""A skill with one resource, two corpora with one document each, and a directory outside every skill."""


def _snapshot(*links: tuple[str, str]) -> Snapshot:
    """`TREE`, with each symlink given, recorded as a scan of the repository's scope would declare it.

    Args:
        links: Each symlink, as its root-relative path and its target as written.
    """
    records: dict[RootRelativePath, EntryRecord] = dict(Snapshot.from_tree(TREE).records)
    for path, target in links:
        records[RootRelativePath.parse(path)] = SymlinkRecord(PurePosixPath(target))
    return Snapshot(FrozenMapping(records), scope=SNAPSHOT_SCOPE)


def _find(urls: tuple[str, ...], base: SkillRoot | DocumentDirectory, snapshot: Snapshot) -> dict[str, PathLookup]:
    """The link targets of a file holding one link per destination, keyed by each normalised path as a string.

    Args:
        urls: Each link's destination, as the parser encodes it.
        base: Where the file's relative links are read from.
        snapshot: The snapshot each target is looked up in.
    """
    links: list[Link] = []
    for url in urls:
        links.append(Link(url, LineNumber.from_int(1)))
    targets = find_link_targets(tuple(links), base, VirtualFileSystem(snapshot), ScopeIndex(snapshot))
    found: dict[str, PathLookup] = {}
    for path, lookup in targets.items():
        found[str(path)] = lookup
    return found


@pytest.mark.unit
class TestFindLinkTargetsInASkill:
    def test_find_link_targets_with_a_file_and_a_directory_of_the_skill_finds_both_present(self) -> None:
        #: Given
        urls = ('references/a.md', 'references/')

        #: When
        found = _find(urls, REVIEW_ROOT, _snapshot())

        #: Then
        assert found == {'references/a.md': PathLookup.PRESENT, 'references': PathLookup.PRESENT}, (
            'a file and a directory the skill holds are both present, keyed by the normalised path'
        )

    def test_find_link_targets_with_nothing_at_the_path_finds_it_missing(self) -> None:
        #: Given
        urls = ('references/b.md',)

        #: When
        found = _find(urls, REVIEW_ROOT, _snapshot())

        #: Then
        assert found == {'references/b.md': PathLookup.MISSING}, 'nothing in a directory of the skill is missing'

    def test_find_link_targets_reads_a_link_from_the_skill_root_whichever_file_holds_it(self) -> None:
        #: Given
        # `a.md` would be the resource itself, read from `references/`; from the skill root it names nothing.
        urls = ('a.md', 'references/../SKILL.md')

        #: When
        found = _find(urls, REVIEW_ROOT, _snapshot())

        #: Then
        assert found == {'a.md': PathLookup.MISSING, 'SKILL.md': PathLookup.PRESENT}, (
            'every link is read from the skill root, and a `..` cancels the directory written before it'
        )

    def test_find_link_targets_with_a_link_climbing_above_the_skill_root_gives_it_no_entry(self) -> None:
        #: Given
        urls = ('../review/SKILL.md',)

        #: When
        found = _find(urls, REVIEW_ROOT, _snapshot())

        #: Then
        assert found == {}, 'a link climbing above the skill root names nothing the skill carries, so it has no entry'

    def test_find_link_targets_with_links_spelling_no_relative_path_gives_them_no_entry(self) -> None:
        #: Given
        urls = ('https://example.com/a.md', '/a.md', '#usage')

        #: When
        found = _find(urls, REVIEW_ROOT, _snapshot())

        #: Then
        assert found == {}, 'a URL, an absolute link and a fragment-only link name no relative path'

    def test_find_link_targets_through_a_symlinked_directory_in_the_skill_follows_it(self) -> None:
        #: Given
        snapshot = _snapshot(('.agents/skills/review/guides', '../../../shared/guides'))
        urls = ('guides/d.md', 'guides/e.md')

        #: When
        found = _find(urls, REVIEW_ROOT, snapshot)

        #: Then
        assert found == {'guides/d.md': PathLookup.PRESENT, 'guides/e.md': PathLookup.MISSING}, (
            'the symlink inside the skill is followed to the files it leads to'
        )


@pytest.mark.unit
class TestFindLinkTargetsInADocument:
    def test_find_link_targets_reads_a_link_from_the_document_directory(self) -> None:
        #: Given
        urls = ('setup.md', 'install.md', '../code/rules.md')

        #: When
        found = _find(urls, GUIDE_DIRECTORY, _snapshot())

        #: Then
        assert found == {
            'setup.md': PathLookup.PRESENT,
            'install.md': PathLookup.MISSING,
            '../code/rules.md': PathLookup.PRESENT,
        }, "a document's links are read from its own directory, and a `..` may climb out of it"

    def test_find_link_targets_with_a_path_the_scan_never_read_finds_it_outside_the_scope(self) -> None:
        #: Given
        urls = ('../../shared/guides/d.md',)

        #: When
        found = _find(urls, GUIDE_DIRECTORY, _snapshot())

        #: Then
        assert found == {'../../shared/guides/d.md': PathLookup.OUTSIDE_SCOPE}, (
            'a path in a directory the scan never read is outside the scope, whatever the snapshot holds there'
        )

    def test_find_link_targets_with_a_link_climbing_above_the_repository_gives_it_no_entry(self) -> None:
        #: Given
        urls = ('../../../x.md',)

        #: When
        found = _find(urls, GUIDE_DIRECTORY, _snapshot())

        #: Then
        assert found == {}, 'a path climbing above the repository root names nothing the snapshot can hold'
