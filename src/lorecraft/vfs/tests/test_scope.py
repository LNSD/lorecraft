"""The declared scope: what a whole scope reads, links included.

Nothing here touches the disk. A snapshot is built by hand with links alone, and no listing, so every answer is
seen to come from the declaration and the recorded links, never from a directory the snapshot holds. The parity
with what `take_snapshot` actually lists is covered in `tests/it/test_filesystem.py`.
"""

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath

from ..scan_root import ScanRoot
from ..scope import is_in_scope
from ..snapshot import Link, Snapshot

DOCS: Final[RootRelativePath] = RootRelativePath.parse('docs')
AGENTS_SKILLS: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills')

# The shape of the layout's scope: docs/ one level deep, links recorded and not followed, and a skills directory
# one level deep through its links.
SCOPE: Final[tuple[ScanRoot, ...]] = (
    ScanRoot(DOCS, depth=1),
    ScanRoot(AGENTS_SKILLS, depth=1, follow_links=True),
)


def _path(raw: str) -> RootRelativePath:
    """Parse a root-relative path written in a test.

    Args:
        raw: The path with `/` separators.
    """
    return RootRelativePath.parse(raw)


def _snapshot_of_links(links: Mapping[str, str]) -> Snapshot:
    """A snapshot recording the given links and nothing else: no listing, no file.

    Args:
        links: Each link's root-relative path, mapped to its target as `os.readlink` would return it.
    """
    records: list[Link] = []
    for path in sorted(links):
        records.append(Link(_path(path), PurePosixPath(links[path])))
    return Snapshot(listings=(), files=(), links=tuple(records))


@pytest.mark.unit
class TestIsInScope:
    def test_is_in_scope_with_an_entry_of_a_covered_directory_that_does_not_exist_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({})
        path = _path('docs/nope/a.md')

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is True, 'docs/nope is within docs/ depth whether or not it exists, so a.md is in the scope'

    def test_is_in_scope_with_an_entry_beyond_the_depth_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({})
        path = _path('docs/feat/deep/a.md')

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is False, 'docs/ is read one level deep, so docs/feat/deep is never entered'

    def test_is_in_scope_with_an_entry_outside_every_root_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({})
        path = _path('src/tool.py')

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is False, 'no root covers src/'

    def test_is_in_scope_with_a_root_directory_itself_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({})
        path = DOCS

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is False, 'the root directory is not listed, so what the name docs holds is not known'

    def test_is_in_scope_through_an_unfollowed_link_leading_out_of_the_scope_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'docs/linked': '../elsewhere'})
        path = _path('docs/linked/a.md')

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is False, 'docs/ does not follow links, and the link leads to elsewhere/, which no root covers'

    def test_is_in_scope_through_an_unfollowed_link_to_a_covered_directory_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'docs/linked': 'feat'})
        path = _path('docs/linked/a.md')

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is True, 'the link leads to docs/feat, which docs/ lists in its own right'

    def test_is_in_scope_through_a_followed_skill_link_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../skills/y'})
        path = _path('.agents/skills/y/absent.md')

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is True, 'the skills root follows the link, so it lists skills/y'

    def test_is_in_scope_at_the_real_path_a_followed_skill_link_leads_to_returns_true(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../skills/y'})
        path = _path('skills/y/absent.md')

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is True, 'skills/y is listed because the link to it is followed, whatever it is spelled'

    def test_is_in_scope_below_the_directory_a_followed_link_leads_to_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../skills/y'})
        path = _path('skills/y/sub/a.md')

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is False, 'the link costs the depth a directory does, so skills/y is listed and not entered'

    def test_is_in_scope_through_a_link_in_a_skill_directory_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/x/lib': '../../../lib'})
        path = _path('lib/a.md')

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is False, 'a skill directory is listed with no depth left, so a linked directory in it is not'

    def test_is_in_scope_through_links_chained_within_the_depth_returns_true(self) -> None:
        #: Given
        scope = (ScanRoot(_path('a'), depth=2, follow_links=True),)
        snapshot = _snapshot_of_links({'a/to-b': '../b', 'b/to-c': '../c'})
        path = _path('c/x.md')

        #: When
        in_scope = is_in_scope(scope, snapshot.links, path)

        #: Then
        assert in_scope is True, 'a/ lists b/ through one link with a level left, and b/ lists c/ through the next'

    def test_is_in_scope_under_a_following_root_reached_through_a_link_returns_true(self) -> None:
        #: Given
        scope = (ScanRoot(_path('.claude/skills'), depth=1, follow_links=True),)
        snapshot = _snapshot_of_links({'.claude/skills': '../.agents/skills'})
        path = _path('.agents/skills/x/a.md')

        #: When
        in_scope = is_in_scope(scope, snapshot.links, path)

        #: Then
        assert in_scope is True, 'the root follows the link on the way to it, so .agents/skills is what it lists'

    def test_is_in_scope_under_a_non_following_root_reached_through_a_link_returns_false(self) -> None:
        #: Given
        scope = (ScanRoot(_path('.claude/skills'), depth=1),)
        snapshot = _snapshot_of_links({'.claude/skills': '../.agents/skills'})
        path = _path('.claude/skills/x/a.md')

        #: When
        in_scope = is_in_scope(scope, snapshot.links, path)

        #: Then
        assert in_scope is False, 'the scan stops at the link on the way to the root, so it lists nothing there'

    def test_is_in_scope_through_a_link_with_an_absolute_target_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '/srv/skills/y'})
        path = _path('.agents/skills/y/a.md')

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is False, 'an absolute target is outside the root, where the scan never goes'

    def test_is_in_scope_through_a_link_climbing_above_the_root_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': '../../../y'})
        path = _path('.agents/skills/y/a.md')

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is False, 'a target above the root is outside it, where the scan never goes'

    def test_is_in_scope_through_a_link_climbing_out_of_a_directory_stepped_into_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': 'tmp/../x'})
        path = _path('.agents/skills/y/a.md')

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is False, 'the scan refuses a `..` out of a directory it stepped into by name, and so does this'

    def test_is_in_scope_through_a_looping_link_returns_false(self) -> None:
        #: Given
        snapshot = _snapshot_of_links({'.agents/skills/y': 'y'})
        path = _path('.agents/skills/y/a.md')

        #: When
        in_scope = is_in_scope(SCOPE, snapshot.links, path)

        #: Then
        assert in_scope is False, 'a chain longer than the link limit leads nowhere, as on disk'
