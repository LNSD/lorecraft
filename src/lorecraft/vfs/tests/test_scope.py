"""The declared scope: what a whole scope reads, links included.

Nothing here touches the disk. A snapshot is built by hand with links alone, and no listing, so every answer is
seen to come from the declaration and the recorded links, never from a directory the snapshot holds. The parity
with what `take_snapshot` actually lists is covered in `tests/it/test_filesystem.py`.

`ScopeIndex.is_in_scope` is covered case by case in `TestScopeIndexIsInScope`, each building its own index.
`TestScopeIndex` covers what only a reused index can show: that one index, once built, answers each path the same
whatever was asked before.
"""

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath

from ..scan_root import ScanRoot
from ..scope import ScopeIndex
from ..snapshot import Link, Snapshot

DOCS: Final[RootRelativePath] = RootRelativePath.parse('docs')
AGENTS_SKILLS: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills')

# The shape of the layout's scope: docs/ one level deep, links recorded and not followed, and a skills directory
# with no depth limit through its links.
SCOPE: Final[tuple[ScanRoot, ...]] = (
    ScanRoot(DOCS, depth=1),
    ScanRoot(AGENTS_SKILLS, depth=None, follow_links=True),
)

# The same skills directory one level deep through its links, where a followed link costs the depth it uses up.
DEPTH_ONE_SCOPE: Final[tuple[ScanRoot, ...]] = (ScanRoot(AGENTS_SKILLS, depth=1, follow_links=True),)


def _path(raw: str) -> RootRelativePath:
    """Parse a root-relative path written in a test.

    Args:
        raw: The path with `/` separators.
    """
    return RootRelativePath.parse(raw)


def _snapshot_of_links(links: Mapping[str, str], climbed_directories: tuple[str, ...] = ()) -> Snapshot:
    """A snapshot recording the given links and climbed directories and nothing else: no listing, no file.

    Args:
        links: Each link's root-relative path, mapped to its target as `os.readlink` would return it.
        climbed_directories: Each directory the scan climbed out of with a `..`, as it records them.
    """
    records: list[Link] = []
    for path in sorted(links):
        records.append(Link(_path(path), PurePosixPath(links[path])))
    climbed: list[RootRelativePath] = []
    for raw in sorted(climbed_directories):
        climbed.append(_path(raw))
    return Snapshot(listings=(), files=(), links=tuple(records), climbed_directories=tuple(climbed))


@pytest.mark.unit
class TestScopeIndexIsInScope:
    def test_is_in_scope_with_an_entry_of_a_covered_directory_that_does_not_exist_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({})
        path = _path('docs/nope/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'docs/nope is within docs/ depth whether or not it exists, so a.md is in the scope'

    def test_is_in_scope_with_an_entry_beyond_the_depth_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({})
        path = _path('docs/feat/deep/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is False, 'docs/ is read one level deep, so docs/feat/deep is never entered'

    def test_is_in_scope_with_an_entry_outside_every_root_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({})
        path = _path('src/tool.py')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is False, 'no root covers src/'

    def test_is_in_scope_with_a_root_directory_itself_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({})
        path = DOCS
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is False, 'the root directory is not listed, so what the name docs holds is not known'

    def test_is_in_scope_through_an_unfollowed_link_leading_out_of_the_scope_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'docs/linked': '../elsewhere'})
        path = _path('docs/linked/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is False, 'docs/ does not follow links, and the link leads to elsewhere/, which no root covers'

    def test_is_in_scope_through_an_unfollowed_link_to_a_covered_directory_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'docs/linked': 'feat'})
        path = _path('docs/linked/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'the link leads to docs/feat, which docs/ lists in its own right'

    def test_is_in_scope_through_a_followed_skill_link_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../skills/y'})
        path = _path('.agents/skills/y/absent.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'the skills root follows the link, so it lists skills/y'

    def test_is_in_scope_at_the_resolved_path_a_followed_skill_link_leads_to_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../skills/y'})
        path = _path('skills/y/absent.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'skills/y is listed because the link to it is followed, whatever it is spelled'

    def test_is_in_scope_below_the_directory_a_followed_link_leads_to_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../skills/y'})
        path = _path('skills/y/sub/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'the skills root has no depth limit, so skills/y is listed at any depth below'

    def test_is_in_scope_below_the_directory_a_followed_link_leads_to_at_depth_one_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../skills/y'})
        path = _path('skills/y/sub/a.md')
        index = ScopeIndex(DEPTH_ONE_SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is False, 'the link costs the depth a directory does, so skills/y is listed and not entered'

    def test_is_in_scope_through_a_link_in_a_skill_directory_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/x/lib': '../../../lib'})
        path = _path('lib/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'a link inside a skill is followed, and lib/ is listed with no depth limit'

    def test_is_in_scope_through_a_link_in_a_skill_directory_at_depth_one_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/x/lib': '../../../lib'})
        path = _path('lib/a.md')
        index = ScopeIndex(DEPTH_ONE_SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is False, 'a skill directory is listed with no depth left, so a linked directory in it is not'

    def test_is_in_scope_with_an_entry_deep_inside_a_skill_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({})
        path = _path('.agents/skills/x/references/deep/b.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'the skills root lists every directory of a skill, whether or not it exists'

    def test_is_in_scope_below_a_link_deep_inside_a_skill_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/x/references/shared': '../../../../shared'})
        path = _path('.agents/skills/x/references/shared/deep/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'the link two levels inside the skill leads to shared/, listed with no depth limit'

    def test_is_in_scope_through_a_link_to_an_ancestor_inside_a_skill_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/x/references/up': '..'})
        path = _path('.agents/skills/x/references/up/references/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'the link leads back to the skill directory, which the root lists; the index ends'

    def test_is_in_scope_for_a_path_outside_the_skills_through_a_link_to_the_root_inside_a_skill_returns_true(
        self,
    ) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/x/root': '../../..'})
        path = _path('src/tool.py')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'a followed link to an ancestor brings its whole subtree into the scope, root included'

    def test_is_in_scope_through_links_between_two_skills_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/x/to-y': '../y', '.agents/skills/y/to-x': '../x'})
        path = _path('.agents/skills/x/to-y/to-x/to-y/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'two skills linking to each other expand to two roots, and the index ends'

    def test_is_in_scope_through_a_self_loop_inside_a_skill_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/x/self': 'self'})
        path = _path('.agents/skills/x/self/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is False, 'a link to itself leads nowhere, as on disk, so nothing is listed through it'

    def test_is_in_scope_through_links_chained_within_the_depth_returns_true(self) -> None:
        #: Given
        scope = (ScanRoot(_path('a'), depth=2, follow_links=True),)
        snapshot = _snapshot_of_links({'a/to-b': '../b', 'b/to-c': '../c'})
        path = _path('c/x.md')
        index = ScopeIndex(scope, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'a/ lists b/ through one link with a level left, and b/ lists c/ through the next'

    def test_is_in_scope_under_a_following_root_reached_through_a_link_returns_true(self) -> None:
        #: Given
        scope = (ScanRoot(_path('.claude/skills'), depth=1, follow_links=True),)
        snapshot = _snapshot_of_links({'.claude/skills': '../.agents/skills'})
        path = _path('.agents/skills/x/a.md')
        index = ScopeIndex(scope, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'the root follows the link on the way to it, so .agents/skills is what it lists'

    def test_is_in_scope_under_a_non_following_root_reached_through_a_link_returns_false(self) -> None:
        #: Given
        scope = (ScanRoot(_path('.claude/skills'), depth=1),)
        snapshot = _snapshot_of_links({'.claude/skills': '../.agents/skills'})
        path = _path('.claude/skills/x/a.md')
        index = ScopeIndex(scope, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is False, 'the scan stops at the link on the way to the root, so it lists nothing there'

    def test_is_in_scope_through_a_link_with_an_absolute_target_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '/srv/skills/y'})
        path = _path('.agents/skills/y/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is False, 'an absolute target is outside the root, where the scan never goes'

    def test_is_in_scope_through_a_link_climbing_above_the_root_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../../y'})
        path = _path('.agents/skills/y/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is False, 'a target above the root is outside it, where the scan never goes'

    def test_is_in_scope_through_a_link_climbing_out_of_a_climbed_directory_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': 'tmp/../x'}, climbed_directories=('.agents/skills/tmp',))
        path = _path('.agents/skills/y/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'the scan climbed out of tmp, so y leads to .agents/skills/x, which the root lists'

    def test_is_in_scope_through_a_link_climbing_out_of_a_directory_the_scan_never_climbed_returns_false(
        self,
    ) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': 'tmp/../x'})
        path = _path('.agents/skills/y/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is False, 'tmp may be missing or a file, where the scan stops, so the climb is not taken'

    def test_is_in_scope_under_a_link_climbing_out_of_a_climbed_directory_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links(
            {'.agents/skills/y': '../../skills/tmp/../y'}, climbed_directories=('skills/tmp',)
        )
        path = _path('skills/y/absent.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is True, 'the followed link adds a root at skills/y, its resolved path'

    def test_is_in_scope_under_a_link_climbing_out_of_a_directory_the_scan_never_climbed_returns_false(
        self,
    ) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../skills/tmp/../y'})
        path = _path('skills/y/absent.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is False, 'the scan did not reach skills/y through the link, so the link adds no root there'

    def test_is_in_scope_through_a_looping_link_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': 'y'})
        path = _path('.agents/skills/y/a.md')
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(path)

        #: Then
        assert in_scope is False, 'a chain longer than the link limit leads nowhere, as on disk'


@pytest.mark.unit
class TestScopeIndex:
    def test_is_in_scope_through_a_followed_skill_link_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../skills/y'})
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(_path('skills/y/absent.md'))

        #: Then
        assert in_scope is True, 'the index expands the skills root through the link it follows, to skills/y'

    def test_is_in_scope_after_a_path_outside_the_scope_was_asked_returns_true_for_a_covered_path(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../skills/y'})
        index = ScopeIndex(SCOPE, snapshot.links, snapshot.climbed_directories)
        index.is_in_scope(_path('src/tool.py'))

        #: When
        in_scope = index.is_in_scope(_path('skills/y/absent.md'))

        #: Then
        assert in_scope is True, 'a question answered false leaves the expanded roots as they were built'

    def test_is_in_scope_after_a_covered_path_was_asked_returns_false_beyond_the_depth(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../skills/y'})
        index = ScopeIndex(DEPTH_ONE_SCOPE, snapshot.links, snapshot.climbed_directories)
        index.is_in_scope(_path('skills/y/absent.md'))

        #: When
        in_scope = index.is_in_scope(_path('skills/y/sub/a.md'))

        #: Then
        assert in_scope is False, 'a question answered true widens nothing: skills/y is still listed and not entered'

    def test_is_in_scope_with_an_empty_scope_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../skills/y'})
        index = ScopeIndex((), snapshot.links, snapshot.climbed_directories)

        #: When
        in_scope = index.is_in_scope(_path('skills/y/absent.md'))

        #: Then
        assert in_scope is False, 'with no root declared no link is followed, so nothing is in scope'
