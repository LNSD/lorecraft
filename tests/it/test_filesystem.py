"""The filesystem boundary against a real temporary directory.

These wire ``DiskFileSystem`` and ``take_snapshot`` to the disk they read: entry kinds come from
``os.scandir``, link chains are followed by ``os.path.realpath`` and read by ``os.readlink``, and the error
families come from the operating system refusing a read, so they need a real tree under ``tmp_path`` rather
than an in-memory stand-in. The parity tests hold ``VirtualFileSystem`` over a snapshot to the disk view's
answers for the same tree.
"""

import os
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Final

import pytest

from lorecraft.core.error import Error
from lorecraft.vfs import (
    Change,
    ChangeKind,
    DecodeTextError,
    DirEntry,
    DiskFileSystem,
    EntryKind,
    FileBytes,
    Link,
    ListDirError,
    Listing,
    ReadTextError,
    ResolveDirError,
    RootRelativePath,
    ScanRoot,
    Snapshot,
    TakeSnapshotError,
    VirtualFileSystem,
    diff,
    take_snapshot,
)

DOCS_DIR: Final[RootRelativePath] = RootRelativePath.parse('docs')

# A repository-shaped scope, the same shape the project layout passes: docs/ and each directory in it, the
# skills directories and each skill in them, and `.claude` alone so a probe of `.claude/skills` sees any kind.
SNAPSHOT_SCOPE: Final[tuple[ScanRoot, ...]] = (
    ScanRoot(DOCS_DIR, depth=1),
    ScanRoot(RootRelativePath.parse('.agents/skills'), depth=1),
    ScanRoot(RootRelativePath.parse('.claude'), depth=0),
    ScanRoot(RootRelativePath.parse('.claude/skills'), depth=1),
)

# The skills directories alone, read through their links: what a scope that must see every skill passes.
FOLLOWING_SCOPE: Final[tuple[ScanRoot, ...]] = (
    ScanRoot(RootRelativePath.parse('.agents/skills'), depth=1, follow_links=True),
    ScanRoot(RootRelativePath.parse('.claude/skills'), depth=1, follow_links=True),
)

# The parity tree: every kind of entry the scan records, inside SNAPSHOT_SCOPE. Links stay inside the scope,
# since a chain that leaves it is unknown to a snapshot by design. ``docs/code/sub`` sits beyond the depth.
PARITY_FILES: Final[Mapping[str, bytes]] = MappingProxyType(
    {
        'docs/glossary.md': b'# Glossary\n',
        'docs/latin.md': b'caf\xe9\n',
        'docs/__meta__/code.md': b'# Code\n',
        'docs/code/a.md': b'# A\n',
        'docs/code/sub/deep.md': b'# Deep\n',
        '.agents/skills/alpha/SKILL.md': b'---\nname: alpha\n---\n',
    }
)
PARITY_LINKS: Final[Mapping[str, str]] = MappingProxyType(
    {
        'docs/code/linked.md': 'a.md',
        'docs/code-link': 'code',
        'docs/dangling': 'missing',
        'docs/loop': 'loop',
        'docs/up': '..',
        '.agents/skills/beta': 'alpha',
        '.claude/skills': '../.agents/skills',
    }
)
# Links whose target is absolute and under the root; the fixture joins each root-relative target to the root.
PARITY_ABSOLUTE_LINKS: Final[Mapping[str, str]] = MappingProxyType(
    {
        'docs/absolute': 'docs/code',
    }
)
PARITY_FIFO: Final[str] = 'docs/code/pipe'

# What the snapshot of the parity tree records; the completeness test pins it, so the parity tests cover it.
PARITY_ENTRIES: Final[Mapping[str, EntryKind]] = MappingProxyType(
    {
        '.agents/skills': EntryKind.DIRECTORY,
        '.agents/skills/alpha': EntryKind.DIRECTORY,
        '.agents/skills/alpha/SKILL.md': EntryKind.FILE,
        '.agents/skills/beta': EntryKind.SYMLINK,
        '.claude': EntryKind.DIRECTORY,
        '.claude/skills': EntryKind.SYMLINK,
        'docs': EntryKind.DIRECTORY,
        'docs/__meta__': EntryKind.DIRECTORY,
        'docs/__meta__/code.md': EntryKind.FILE,
        'docs/absolute': EntryKind.SYMLINK,
        'docs/code': EntryKind.DIRECTORY,
        'docs/code/a.md': EntryKind.FILE,
        'docs/code/linked.md': EntryKind.SYMLINK,
        'docs/code/pipe': EntryKind.OTHER,
        'docs/code/sub': EntryKind.DIRECTORY,
        'docs/code-link': EntryKind.SYMLINK,
        'docs/dangling': EntryKind.SYMLINK,
        'docs/glossary.md': EntryKind.FILE,
        'docs/latin.md': EntryKind.FILE,
        'docs/loop': EntryKind.SYMLINK,
        'docs/up': EntryKind.SYMLINK,
    }
)


@pytest.fixture(scope='function')
def unreadable_dir(tmp_path: Path) -> Iterator[Path]:
    """A directory whose permissions refuse listing, restored afterwards so pytest can clean it up."""
    directory = tmp_path / 'locked'
    directory.mkdir()
    directory.chmod(0o000)
    yield directory
    directory.chmod(0o700)


@pytest.fixture(scope='function')
def unreadable_outside_dir(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """A directory outside the root whose permissions refuse searching, restored afterwards for cleanup."""
    directory = tmp_path_factory.mktemp('outside') / 'locked'
    directory.mkdir()
    directory.chmod(0o000)
    yield directory
    directory.chmod(0o700)


@pytest.fixture(scope='function')
def unreadable_file(tmp_path: Path) -> Iterator[Path]:
    """A file under ``docs/`` whose permissions refuse reading, restored afterwards for cleanup."""
    (tmp_path / 'docs').mkdir()
    file = tmp_path / 'docs' / 'locked.md'
    file.write_text('', encoding='utf-8')
    file.chmod(0o000)
    yield file
    file.chmod(0o600)


@pytest.fixture(scope='function')
def parity_tree(tmp_path: Path) -> Path:
    """The parity tree under ``tmp_path``: the files, links and fifo of the ``PARITY_*`` tables."""
    for path, data in PARITY_FILES.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_bytes(data)
    for path, target in PARITY_LINKS.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).symlink_to(target)
    for path, target in PARITY_ABSOLUTE_LINKS.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).symlink_to(tmp_path / target)
    os.mkfifo(tmp_path / PARITY_FIFO)
    return tmp_path


@pytest.fixture(scope='function', params=['through-the-alias', 'through-the-real-root'])
def aliased_root_with_an_absolute_link(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    """A root reached through an alias link, returned as the alias.

    It holds ``docs/code/`` and ``docs/absolute``, a link to ``docs/code`` by an absolute target spelled
    either through the alias or through the real root.
    """
    real_root = tmp_path / 'real'
    (real_root / 'docs' / 'code').mkdir(parents=True)
    alias = tmp_path / 'alias'
    alias.symlink_to(real_root)
    if request.param == 'through-the-alias':
        (real_root / 'docs' / 'absolute').symlink_to(alias / 'docs' / 'code')
    else:
        (real_root / 'docs' / 'absolute').symlink_to(real_root / 'docs' / 'code')
    return alias


@pytest.fixture(scope='function', params=['dangling-link', 'regular-file'])
def unresolved_claude_skills_tree(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    """A root whose ``.claude/skills`` exists but leads to no directory: a dangling link or a regular file."""
    (tmp_path / '.claude').mkdir()
    if request.param == 'dangling-link':
        (tmp_path / '.claude' / 'skills').symlink_to('missing')
    else:
        (tmp_path / '.claude' / 'skills').write_bytes(b'not a directory\n')
    return tmp_path


@pytest.fixture(scope='function')
def linked_skills_tree(tmp_path: Path) -> Path:
    """A root whose one skill lives outside the skills directories, reached through two links.

    ``skills/review/`` holds the files, ``.agents/skills/review`` links to it, and ``.claude/skills`` links to
    ``.agents/skills``: the layout of a repository that ships a skill and also uses it.
    """
    (tmp_path / 'skills' / 'review').mkdir(parents=True)
    (tmp_path / 'skills' / 'review' / 'SKILL.md').write_bytes(b'---\nname: review\n---\n')
    (tmp_path / '.agents' / 'skills').mkdir(parents=True)
    (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
    (tmp_path / '.claude').mkdir()
    (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')
    return tmp_path


@pytest.fixture(scope='function')
def chain_of_41_links(tmp_path: Path) -> str:
    """A directory under ``tmp_path`` reached through 41 links, one more than Linux follows; returns the first link.

    ``real/`` holds ``SKILL.md``; ``link-0`` leads to ``real`` and each later link to the one before it, so
    ``link-40`` is the head of a chain that does not loop and is still too long to open.
    """
    (tmp_path / 'real').mkdir()
    (tmp_path / 'real' / 'SKILL.md').write_bytes(b'---\n')
    target = 'real'
    for index in range(41):
        (tmp_path / f'link-{index}').symlink_to(target)
        target = f'link-{index}'
    return target


def _answer(call: Callable[[RootRelativePath], object], path: RootRelativePath) -> object:
    """What one view answers for ``path``: the return value, or the class of the ``Error`` it raised."""
    try:
        return call(path)
    except Error as exc:
        return type(exc)


def _answers(
    disk_call: Callable[[RootRelativePath], object], virtual_call: Callable[[RootRelativePath], object], path: str
) -> tuple[object, object]:
    """The disk view's answer and the virtual view's answer for the same path, in that order."""
    return _answer(disk_call, RootRelativePath.parse(path)), _answer(virtual_call, RootRelativePath.parse(path))


@pytest.mark.it
class TestDiskFileSystemListDir:
    def test_list_dir_with_files_and_directories_returns_entries_sorted_by_name(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'b.md').write_text('b', encoding='utf-8')
        (tmp_path / 'a.md').write_text('a', encoding='utf-8')
        (tmp_path / 'c').mkdir()
        filesystem = DiskFileSystem(tmp_path)

        #: When
        entries = filesystem.list_dir(RootRelativePath.parse('.'))

        #: Then
        assert entries == (
            DirEntry('a.md', EntryKind.FILE),
            DirEntry('b.md', EntryKind.FILE),
            DirEntry('c', EntryKind.DIRECTORY),
        ), 'entries are listed by name with the kind of the entry itself'

    def test_list_dir_with_a_symlink_to_a_file_returns_symlink_kind(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'file.md').write_text('', encoding='utf-8')
        (tmp_path / 'subdir').mkdir()
        target = 'file.md'
        (tmp_path / 'link').symlink_to(tmp_path / target)
        filesystem = DiskFileSystem(tmp_path)

        #: When
        entries = filesystem.list_dir(RootRelativePath.parse('.'))

        #: Then
        assert DirEntry('link', EntryKind.SYMLINK) in entries, 'a symlink to a file is SYMLINK, never FILE'

    def test_list_dir_with_a_symlink_to_a_directory_returns_symlink_kind(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'file.md').write_text('', encoding='utf-8')
        (tmp_path / 'subdir').mkdir()
        target = 'subdir'
        (tmp_path / 'link').symlink_to(tmp_path / target)
        filesystem = DiskFileSystem(tmp_path)

        #: When
        entries = filesystem.list_dir(RootRelativePath.parse('.'))

        #: Then
        assert DirEntry('link', EntryKind.SYMLINK) in entries, 'a symlink to a directory is SYMLINK, never DIRECTORY'

    def test_list_dir_with_a_dangling_symlink_returns_symlink_kind(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'file.md').write_text('', encoding='utf-8')
        (tmp_path / 'subdir').mkdir()
        target = 'missing'
        (tmp_path / 'link').symlink_to(tmp_path / target)
        filesystem = DiskFileSystem(tmp_path)

        #: When
        entries = filesystem.list_dir(RootRelativePath.parse('.'))

        #: Then
        assert DirEntry('link', EntryKind.SYMLINK) in entries, 'a symlink to nothing is still listed as SYMLINK'

    def test_list_dir_with_a_fifo_returns_other_kind(self, tmp_path: Path) -> None:
        #: Given
        os.mkfifo(tmp_path / 'pipe')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        entries = filesystem.list_dir(RootRelativePath.parse('.'))

        #: Then
        assert entries == (DirEntry('pipe', EntryKind.OTHER),), 'neither a file nor a directory is OTHER'

    def test_list_dir_with_a_missing_directory_returns_empty(self, tmp_path: Path) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)
        missing = RootRelativePath.parse('docs')

        #: When
        entries = filesystem.list_dir(missing)

        #: Then
        assert entries == (), 'a missing directory lists as nothing rather than failing'

    def test_list_dir_with_a_file_path_returns_empty(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'notes.md').write_text('', encoding='utf-8')
        filesystem = DiskFileSystem(tmp_path)
        file_path = RootRelativePath.parse('notes.md')

        #: When
        entries = filesystem.list_dir(file_path)

        #: Then
        assert entries == (), 'a non-directory lists as nothing rather than failing'

    def test_list_dir_with_a_looping_link_returns_empty(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'loop').symlink_to('loop')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        entries = filesystem.list_dir(RootRelativePath.parse('loop'))

        #: Then
        assert entries == (), 'a looping link leads to no directory, so it lists as nothing, like a dangling one'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_list_dir_with_an_unreadable_directory_raises_list_dir_error(
        self, tmp_path: Path, unreadable_dir: Path
    ) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)
        locked = RootRelativePath.parse(unreadable_dir.name)

        #: When
        with pytest.raises(ListDirError) as exc_info:
            filesystem.list_dir(locked)

        #: Then
        assert exc_info.value.path == locked, 'the error names the root-relative directory'


@pytest.mark.it
class TestDiskFileSystemReadText:
    def test_read_text_with_a_utf8_file_returns_its_text(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'guide.md').write_text('# Guía\n', encoding='utf-8')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        text = filesystem.read_text(RootRelativePath.parse('guide.md'))

        #: Then
        assert text == '# Guía\n', 'the file is decoded as UTF-8'

    def test_read_text_with_non_utf8_bytes_raises_decode_text_error(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'latin.md').write_bytes(b'caf\xe9\n')
        filesystem = DiskFileSystem(tmp_path)
        latin = RootRelativePath.parse('latin.md')

        #: When
        with pytest.raises(DecodeTextError) as exc_info:
            filesystem.read_text(latin)

        #: Then
        assert exc_info.value.path == latin, 'the error names the root-relative file'

    def test_read_text_with_a_missing_file_raises_read_text_error(self, tmp_path: Path) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)
        missing = RootRelativePath.parse('missing.md')

        #: When
        with pytest.raises(ReadTextError) as exc_info:
            filesystem.read_text(missing)

        #: Then
        assert exc_info.value.path == missing, 'the error names the root-relative file'
        assert not isinstance(exc_info.value, DecodeTextError), 'a missing file is not a decode failure'


@pytest.mark.it
class TestDiskFileSystemResolveDir:
    def test_resolve_dir_with_a_regular_directory_returns_itself(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        filesystem = DiskFileSystem(tmp_path)
        skills = RootRelativePath.parse('.agents/skills')

        #: When
        resolved = filesystem.resolve_dir(skills)

        #: Then
        assert resolved == skills, 'a directory with no link in its path resolves to itself'

    def test_resolve_dir_with_the_root_returns_dot(self, tmp_path: Path) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.resolve_dir(RootRelativePath.parse('.'))

        #: Then
        assert resolved == RootRelativePath.parse('.'), 'the root resolves to the empty root-relative path'

    def test_resolve_dir_with_a_link_to_a_directory_returns_the_target(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'target').mkdir()
        (tmp_path / 'link').symlink_to(tmp_path / 'target')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.resolve_dir(RootRelativePath.parse('link'))

        #: Then
        assert resolved == RootRelativePath.parse('target'), 'a link to a directory resolves to the directory it names'

    def test_resolve_dir_through_a_linked_parent_returns_the_real_directory(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.claude').symlink_to('.agents')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.resolve_dir(RootRelativePath.parse('.claude/skills'))

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills'), 'a link on a parent component is followed too'

    def test_resolve_dir_with_a_relative_link_from_a_subdirectory_returns_the_target(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.resolve_dir(RootRelativePath.parse('.claude/skills'))

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills'), 'a relative target is read from the link directory'

    def test_resolve_dir_with_a_dangling_link_returns_none(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'link').symlink_to('missing')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.resolve_dir(RootRelativePath.parse('link'))

        #: Then
        assert resolved is None, 'a link to nothing leads to no directory'

    def test_resolve_dir_with_a_link_loop_returns_none(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'first').symlink_to('second')
        (tmp_path / 'second').symlink_to('first')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.resolve_dir(RootRelativePath.parse('first'))

        #: Then
        assert resolved is None, 'a looping link leads nowhere, like a dangling one'

    def test_resolve_dir_with_a_chain_longer_than_the_system_follows_returns_none(
        self, tmp_path: Path, chain_of_41_links: str
    ) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.resolve_dir(RootRelativePath.parse(chain_of_41_links))

        #: Then
        assert resolved is None, 'nothing opens a directory through a chain the operating system gives up on'

    def test_resolve_dir_with_a_link_to_a_file_returns_none(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'notes.md').write_text('', encoding='utf-8')
        (tmp_path / 'link').symlink_to('notes.md')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.resolve_dir(RootRelativePath.parse('link'))

        #: Then
        assert resolved is None, 'a link whose target is a file is not a directory'

    def test_resolve_dir_with_a_missing_path_returns_none(self, tmp_path: Path) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.resolve_dir(RootRelativePath.parse('.agents/skills'))

        #: Then
        assert resolved is None, 'a missing path resolves to nothing rather than failing'

    def test_resolve_dir_through_a_file_component_returns_none(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'notes.md').write_text('', encoding='utf-8')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.resolve_dir(RootRelativePath.parse('notes.md/skills'))

        #: Then
        assert resolved is None, 'a path through a file resolves to nothing rather than failing'

    def test_resolve_dir_with_a_link_outside_the_root_returns_none(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        outside = tmp_path_factory.mktemp('outside')
        (tmp_path / 'link').symlink_to(outside)
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.resolve_dir(RootRelativePath.parse('link'))

        #: Then
        assert resolved is None, 'a directory outside the root has no root-relative spelling'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_resolve_dir_under_an_unreadable_directory_raises_resolve_dir_error(
        self, tmp_path: Path, unreadable_dir: Path
    ) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)
        inside_locked = RootRelativePath.parse(unreadable_dir.name) / 'skills'

        #: When
        with pytest.raises(ResolveDirError) as exc_info:
            filesystem.resolve_dir(inside_locked)

        #: Then
        assert exc_info.value.path == inside_locked, 'the error names the root-relative path'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_resolve_dir_with_a_link_into_an_unreadable_directory_outside_the_root_returns_none(
        self, tmp_path: Path, unreadable_outside_dir: Path
    ) -> None:
        #: Given
        (tmp_path / 'link').symlink_to(unreadable_outside_dir / 'skills')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.resolve_dir(RootRelativePath.parse('link'))

        #: Then
        assert resolved is None, 'a chain leading outside the root never fails, even where the lookup is refused'


@pytest.mark.it
class TestTakeSnapshot:
    def test_take_snapshot_of_a_corpus_records_its_listings_and_file_bytes(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs' / 'code').mkdir(parents=True)
        (tmp_path / 'docs' / 'code' / 'a.md').write_bytes(b'# A\n')
        (tmp_path / 'docs' / 'glossary.md').write_bytes(b'# Glossary\n')

        #: When
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot == Snapshot(
            listings=(
                Listing(
                    RootRelativePath.parse('docs'),
                    (DirEntry('code', EntryKind.DIRECTORY), DirEntry('glossary.md', EntryKind.FILE)),
                ),
                Listing(RootRelativePath.parse('docs/code'), (DirEntry('a.md', EntryKind.FILE),)),
            ),
            files=(
                FileBytes(RootRelativePath.parse('docs/code/a.md'), b'# A\n'),
                FileBytes(RootRelativePath.parse('docs/glossary.md'), b'# Glossary\n'),
            ),
        ), 'each listing down to the depth, and the bytes of every file entry in them'

    def test_take_snapshot_with_a_directory_beyond_the_depth_lists_it_without_entering_it(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs' / 'code' / 'sub').mkdir(parents=True)
        (tmp_path / 'docs' / 'code' / 'sub' / 'x.md').write_bytes(b'# X\n')

        #: When
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot == Snapshot(
            listings=(
                Listing(RootRelativePath.parse('docs'), (DirEntry('code', EntryKind.DIRECTORY),)),
                Listing(RootRelativePath.parse('docs/code'), (DirEntry('sub', EntryKind.DIRECTORY),)),
            ),
            files=(),
        ), 'a directory at depth 2 is an entry of its parent, and nothing inside it is read'

    def test_take_snapshot_with_a_symlink_records_the_entry_and_its_target_without_following_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'docs').mkdir()
        (tmp_path / 'docs' / 'a.md').write_bytes(b'# A\n')
        (tmp_path / 'docs' / 'linked.md').symlink_to('a.md')

        #: When
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot == Snapshot(
            listings=(
                Listing(
                    RootRelativePath.parse('docs'),
                    (DirEntry('a.md', EntryKind.FILE), DirEntry('linked.md', EntryKind.SYMLINK)),
                ),
            ),
            files=(FileBytes(RootRelativePath.parse('docs/a.md'), b'# A\n'),),
            links=(Link(RootRelativePath.parse('docs/linked.md'), PurePosixPath('a.md')),),
        ), 'the link is an entry with its target recorded, and no bytes are read through it'

    def test_take_snapshot_with_a_fifo_records_the_entry_without_reading_it(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs').mkdir()
        os.mkfifo(tmp_path / 'docs' / 'pipe')

        #: When
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot == Snapshot(
            listings=(Listing(RootRelativePath.parse('docs'), (DirEntry('pipe', EntryKind.OTHER),)),),
            files=(),
        ), 'a fifo is an OTHER entry, and nothing is read from it'

    def test_take_snapshot_with_missing_scope_roots_returns_an_empty_snapshot(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'README.md').write_bytes(b'# Outside the scope\n')

        #: When
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot == Snapshot(listings=(), files=(), links=()), 'a missing scope root is simply absent'

    def test_take_snapshot_with_a_linked_scope_root_records_the_link_without_listing_through_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / '.agents' / 'skills' / 'alpha').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'alpha' / 'SKILL.md').write_bytes(b'---\n')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')

        #: When
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot == Snapshot(
            listings=(
                Listing(RootRelativePath.parse('.agents/skills'), (DirEntry('alpha', EntryKind.DIRECTORY),)),
                Listing(RootRelativePath.parse('.agents/skills/alpha'), (DirEntry('SKILL.md', EntryKind.FILE),)),
                Listing(RootRelativePath.parse('.claude'), (DirEntry('skills', EntryKind.SYMLINK),)),
            ),
            files=(FileBytes(RootRelativePath.parse('.agents/skills/alpha/SKILL.md'), b'---\n'),),
            links=(Link(RootRelativePath.parse('.claude/skills'), PurePosixPath('../.agents/skills')),),
        ), 'the linked agent directory is one link; its skills are listed once, at their real path'

    def test_take_snapshot_with_an_absolute_link_under_the_root_records_it_relative_to_the_link(
        self, aliased_root_with_an_absolute_link: Path
    ) -> None:
        #: Given
        root = aliased_root_with_an_absolute_link

        #: When
        snapshot = take_snapshot(root, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot.links == (Link(RootRelativePath.parse('docs/absolute'), PurePosixPath('../docs/code')),), (
            'an absolute target under the root, through either spelling of it, is recorded from the link'
        )

    def test_take_snapshot_with_an_absolute_link_outside_the_root_records_it_unchanged(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        outside = tmp_path_factory.mktemp('outside')
        (tmp_path / 'docs').mkdir()
        (tmp_path / 'docs' / 'outside').symlink_to(outside)

        #: When
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot.links == (Link(RootRelativePath.parse('docs/outside'), PurePosixPath(outside)),), (
            'an absolute target outside the root is recorded as the disk returned it'
        )

    def test_take_snapshot_with_overlapping_scope_roots_lists_to_the_deepest_depth(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs' / 'code' / 'sub').mkdir(parents=True)
        (tmp_path / 'docs' / 'code' / 'sub' / 'x.md').write_bytes(b'# X\n')
        # the shallow root is scanned first, so the deeper one must list docs/code again
        scope = (ScanRoot(DOCS_DIR, depth=2), ScanRoot(DOCS_DIR / 'code', depth=0))

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == Snapshot(
            listings=(
                Listing(RootRelativePath.parse('docs'), (DirEntry('code', EntryKind.DIRECTORY),)),
                Listing(RootRelativePath.parse('docs/code'), (DirEntry('sub', EntryKind.DIRECTORY),)),
                Listing(RootRelativePath.parse('docs/code/sub'), (DirEntry('x.md', EntryKind.FILE),)),
            ),
            files=(FileBytes(RootRelativePath.parse('docs/code/sub/x.md'), b'# X\n'),),
        ), 'a directory two roots reach is listed down to the deeper of their depths'

    def test_take_snapshot_following_a_linked_scope_root_lists_the_directory_it_leads_to(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'skills' / 'review').mkdir(parents=True)
        (tmp_path / 'skills' / 'review' / 'SKILL.md').write_bytes(b'---\n')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../skills')
        scope = (ScanRoot(RootRelativePath.parse('.claude/skills'), depth=1, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == Snapshot(
            listings=(
                Listing(RootRelativePath.parse('skills'), (DirEntry('review', EntryKind.DIRECTORY),)),
                Listing(RootRelativePath.parse('skills/review'), (DirEntry('SKILL.md', EntryKind.FILE),)),
            ),
            files=(FileBytes(RootRelativePath.parse('skills/review/SKILL.md'), b'---\n'),),
            links=(Link(RootRelativePath.parse('.claude/skills'), PurePosixPath('../skills')),),
        ), 'the directory the scope root leads to is listed at its real path, down to the depth'

    def test_take_snapshot_following_a_linked_entry_lists_the_directory_it_leads_to(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'skills' / 'review').mkdir(parents=True)
        (tmp_path / 'skills' / 'review' / 'SKILL.md').write_bytes(b'---\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        scope = (ScanRoot(RootRelativePath.parse('.agents/skills'), depth=1, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == Snapshot(
            listings=(
                Listing(RootRelativePath.parse('.agents/skills'), (DirEntry('review', EntryKind.SYMLINK),)),
                Listing(RootRelativePath.parse('skills/review'), (DirEntry('SKILL.md', EntryKind.FILE),)),
            ),
            files=(FileBytes(RootRelativePath.parse('skills/review/SKILL.md'), b'---\n'),),
            links=(Link(RootRelativePath.parse('.agents/skills/review'), PurePosixPath('../../skills/review')),),
        ), 'the entry stays a symlink, and the directory it leads to is listed at its real path'

    def test_take_snapshot_following_a_linked_entry_beyond_the_depth_records_it_without_entering_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'skills' / 'review').mkdir(parents=True)
        (tmp_path / 'skills' / 'review' / 'SKILL.md').write_bytes(b'---\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        scope = (ScanRoot(RootRelativePath.parse('.agents/skills'), depth=0, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == Snapshot(
            listings=(Listing(RootRelativePath.parse('.agents/skills'), (DirEntry('review', EntryKind.SYMLINK),)),),
            files=(),
            links=(Link(RootRelativePath.parse('.agents/skills/review'), PurePosixPath('../../skills/review')),),
        ), 'a linked entry costs depth as a directory entry does, so at depth 0 it is recorded and not entered'

    def test_take_snapshot_following_a_chain_of_links_records_every_link_of_it(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'skills' / 'review').mkdir(parents=True)
        (tmp_path / 'current').symlink_to('skills')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../current')
        scope = (ScanRoot(RootRelativePath.parse('.claude/skills'), depth=0, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == Snapshot(
            listings=(Listing(RootRelativePath.parse('skills'), (DirEntry('review', EntryKind.DIRECTORY),)),),
            files=(),
            links=(
                Link(RootRelativePath.parse('.claude/skills'), PurePosixPath('../current')),
                Link(RootRelativePath.parse('current'), PurePosixPath('skills')),
            ),
        ), 'both links of the chain are recorded, so the virtual view can walk it to the listed directory'

    def test_take_snapshot_following_a_link_outside_the_root_records_it_without_listing_through_it(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        outside = tmp_path_factory.mktemp('outside')
        (outside / 'SKILL.md').write_bytes(b'---\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to(outside)
        scope = (ScanRoot(RootRelativePath.parse('.agents/skills'), depth=1, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == Snapshot(
            listings=(Listing(RootRelativePath.parse('.agents/skills'), (DirEntry('review', EntryKind.SYMLINK),)),),
            files=(),
            links=(Link(RootRelativePath.parse('.agents/skills/review'), PurePosixPath(outside)),),
        ), 'a link leading outside the root is recorded, and nothing outside the root is read'

    def test_take_snapshot_following_a_looping_link_records_it_and_lists_nothing_through_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'loop').symlink_to('loop')
        scope = (ScanRoot(RootRelativePath.parse('.agents/skills'), depth=1, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == Snapshot(
            listings=(Listing(RootRelativePath.parse('.agents/skills'), (DirEntry('loop', EntryKind.SYMLINK),)),),
            files=(),
            links=(Link(RootRelativePath.parse('.agents/skills/loop'), PurePosixPath('loop')),),
        ), 'a link that leads back to itself ends the walk instead of the scan never returning'

    def test_take_snapshot_following_a_link_to_a_file_records_its_bytes_at_the_real_path(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'REVIEW.md').write_bytes(b'---\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'SKILL.md').symlink_to('../../REVIEW.md')
        scope = (ScanRoot(RootRelativePath.parse('.agents/skills'), depth=0, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == Snapshot(
            listings=(Listing(RootRelativePath.parse('.agents/skills'), (DirEntry('SKILL.md', EntryKind.SYMLINK),)),),
            files=(FileBytes(RootRelativePath.parse('REVIEW.md'), b'---\n'),),
            links=(Link(RootRelativePath.parse('.agents/skills/SKILL.md'), PurePosixPath('../../REVIEW.md')),),
        ), 'the entry stays a symlink, and the file it leads to is read at its real path, whatever the depth'

    def test_take_snapshot_following_a_link_to_a_file_outside_the_root_records_it_without_reading_through_it(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        outside = tmp_path_factory.mktemp('outside') / 'REVIEW.md'
        outside.write_bytes(b'---\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'SKILL.md').symlink_to(outside)
        scope = (ScanRoot(RootRelativePath.parse('.agents/skills'), depth=0, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == Snapshot(
            listings=(Listing(RootRelativePath.parse('.agents/skills'), (DirEntry('SKILL.md', EntryKind.SYMLINK),)),),
            files=(),
            links=(Link(RootRelativePath.parse('.agents/skills/SKILL.md'), PurePosixPath(outside)),),
        ), 'a link leading outside the root is recorded, and no bytes outside the root are read'

    def test_take_snapshot_following_a_link_that_climbs_out_of_a_directory_it_stepped_into_lists_nothing_through_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'skills' / 'review').mkdir(parents=True)
        (tmp_path / 'skills' / 'review' / 'SKILL.md').write_bytes(b'---\n')
        (tmp_path / 'skills' / 'tmp').mkdir()
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/tmp/../review')
        scope = (ScanRoot(RootRelativePath.parse('.agents/skills'), depth=1, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == Snapshot(
            listings=(Listing(RootRelativePath.parse('.agents/skills'), (DirEntry('review', EntryKind.SYMLINK),)),),
            files=(),
            links=(Link(RootRelativePath.parse('.agents/skills/review'), PurePosixPath('../../skills/tmp/../review')),),
        ), 'the snapshot records nothing in skills/tmp, so the view could not walk this chain: the scan does not either'

    def test_take_snapshot_with_a_following_root_over_a_plain_one_follows_the_links_it_lists(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'shared').mkdir()
        (tmp_path / 'shared' / 'a.md').write_bytes(b'# A\n')
        (tmp_path / 'docs').mkdir()
        (tmp_path / 'docs' / 'shared').symlink_to('../shared')
        # the plain root is scanned first, so the following one must list docs again to follow its link
        scope = (ScanRoot(DOCS_DIR, depth=1, follow_links=True), ScanRoot(DOCS_DIR, depth=1))

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == Snapshot(
            listings=(
                Listing(RootRelativePath.parse('docs'), (DirEntry('shared', EntryKind.SYMLINK),)),
                Listing(RootRelativePath.parse('shared'), (DirEntry('a.md', EntryKind.FILE),)),
            ),
            files=(FileBytes(RootRelativePath.parse('shared/a.md'), b'# A\n'),),
            links=(Link(RootRelativePath.parse('docs/shared'), PurePosixPath('../shared')),),
        ), 'a directory two roots reach has its links followed when either root asks for it'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_take_snapshot_with_an_unreadable_directory_raises_take_snapshot_error(
        self, tmp_path: Path, unreadable_dir: Path
    ) -> None:
        #: Given
        locked = RootRelativePath.parse(unreadable_dir.name)
        scope = (ScanRoot(locked, depth=0),)

        #: When
        with pytest.raises(TakeSnapshotError) as exc_info:
            take_snapshot(tmp_path, scope)

        #: Then
        assert exc_info.value.path == locked, 'the error names the root-relative directory the scan stopped at'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores file permissions')
    def test_take_snapshot_with_an_unreadable_file_raises_take_snapshot_error(
        self, tmp_path: Path, unreadable_file: Path
    ) -> None:
        #: Given
        locked = RootRelativePath.parse(unreadable_file.relative_to(tmp_path).as_posix())

        #: When
        with pytest.raises(TakeSnapshotError) as exc_info:
            take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: Then
        assert exc_info.value.path == locked, 'the error names the root-relative file the scan stopped at'


@pytest.mark.it
class TestVirtualFileSystemMatchesDisk:
    def test_take_snapshot_of_the_parity_tree_records_exactly_the_compared_entries(self, parity_tree: Path) -> None:
        #: Given
        expected = {RootRelativePath.parse(path): kind for path, kind in PARITY_ENTRIES.items()}

        #: When
        snapshot = take_snapshot(parity_tree, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot.entries() == expected, 'the parity tables cover every path the snapshot lists'

    # list_dir: every listing, every entry that is no directory, and a link to a listed directory. A link to a
    # directory the scan did not list and an unentered directory are left out: the disk lists them, while the
    # snapshot never entered them.

    def test_list_dir_over_a_snapshot_with_the_skills_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, '.agents/skills lists the same alpha and beta over the snapshot'

    def test_list_dir_over_a_snapshot_with_a_skill_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/alpha'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, '.agents/skills/alpha lists the same SKILL.md over the snapshot'

    def test_list_dir_over_a_snapshot_with_the_claude_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, '.claude lists the same skills link over the snapshot'

    def test_list_dir_over_a_snapshot_with_the_docs_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs lists the same files, directories and links over the snapshot'

    def test_list_dir_over_a_snapshot_with_the_meta_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/__meta__'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/__meta__ lists the same code.md over the snapshot'

    def test_list_dir_over_a_snapshot_with_the_code_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/code lists the same file, link, fifo and sub over the snapshot'

    def test_list_dir_over_a_snapshot_with_a_skill_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/alpha/SKILL.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file SKILL.md lists as nothing over the snapshot too'

    def test_list_dir_over_a_snapshot_with_a_meta_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/__meta__/code.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file docs/__meta__/code.md lists as nothing over the snapshot too'

    def test_list_dir_over_a_snapshot_with_a_code_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/a.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file docs/code/a.md lists as nothing over the snapshot too'

    def test_list_dir_over_a_snapshot_with_a_fifo_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/pipe'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the fifo docs/code/pipe lists as nothing over the snapshot too'

    def test_list_dir_over_a_snapshot_with_a_docs_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/glossary.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file docs/glossary.md lists as nothing over the snapshot too'

    def test_list_dir_over_a_snapshot_with_a_non_utf8_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/latin.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file docs/latin.md lists as nothing over the snapshot too'

    def test_list_dir_over_a_snapshot_with_a_missing_directory_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/missing'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the missing docs/missing lists as nothing over the snapshot too'

    def test_list_dir_over_a_snapshot_with_the_linked_scope_root_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude/skills'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, '.claude/skills lists as .agents/skills, where it leads, on both'

    def test_list_dir_over_a_snapshot_with_a_link_to_a_listed_directory_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code-link'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/code-link lists as docs/code, where it leads, on both'

    # read_text: every file and directory entry, a file behind a linked directory, and a link to a recorded file.
    # The fifo is left out (reading it on disk would block).

    def test_read_text_over_a_snapshot_with_a_link_to_a_recorded_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/linked.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'linked.md leads to a.md, whose bytes are recorded, so it reads the same'

    def test_read_text_over_a_snapshot_with_a_skill_directory_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/alpha'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, (
            'reading the directory .agents/skills/alpha fails the same over the snapshot'
        )

    def test_read_text_over_a_snapshot_with_a_skill_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/alpha/SKILL.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'SKILL.md reads as the same text over the snapshot'

    def test_read_text_over_a_snapshot_with_a_file_behind_a_linked_directory_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude/skills/alpha/SKILL.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'SKILL.md behind the linked .claude/skills reads as the same text'

    def test_read_text_over_a_snapshot_with_the_meta_directory_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/__meta__'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'reading the directory docs/__meta__ fails the same over the snapshot'

    def test_read_text_over_a_snapshot_with_a_meta_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/__meta__/code.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/__meta__/code.md reads as the same text over the snapshot'

    def test_read_text_over_a_snapshot_with_the_code_directory_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'reading the directory docs/code fails the same over the snapshot'

    def test_read_text_over_a_snapshot_with_a_code_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/a.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/code/a.md reads as the same text over the snapshot'

    def test_read_text_over_a_snapshot_with_an_unentered_directory_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/sub'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'reading the unentered docs/code/sub fails the same over the snapshot'

    def test_read_text_over_a_snapshot_with_a_docs_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/glossary.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/glossary.md reads as the same text over the snapshot'

    def test_read_text_over_a_snapshot_with_a_non_utf8_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/latin.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/latin.md fails to decode the same way over the snapshot'

    def test_read_text_over_a_snapshot_with_a_missing_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/missing.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'reading the missing docs/missing.md fails the same over the snapshot'

    # resolve_dir: every entry and listing, plus the chains that run through the recorded links. Three listings
    # are also directory entries, so their paths are checked twice, once as each.

    def test_resolve_dir_over_a_snapshot_with_the_skill_directory_entry_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/alpha'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the directory entry .agents/skills/alpha resolves to itself on both'

    def test_resolve_dir_over_a_snapshot_with_a_skill_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/alpha/SKILL.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file SKILL.md leads to no directory on either'

    def test_resolve_dir_over_a_snapshot_with_a_skill_link_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/beta'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the link beta leads to .agents/skills/alpha on both'

    def test_resolve_dir_over_a_snapshot_with_the_linked_scope_root_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude/skills'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the linked scope root .claude/skills leads to .agents/skills on both'

    def test_resolve_dir_over_a_snapshot_with_the_meta_directory_entry_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/__meta__'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the directory entry docs/__meta__ resolves to itself on both'

    def test_resolve_dir_over_a_snapshot_with_a_meta_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/__meta__/code.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file docs/__meta__/code.md leads to no directory on either'

    def test_resolve_dir_over_a_snapshot_with_an_absolute_link_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/absolute'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the absolute link docs/absolute leads to docs/code on both'

    def test_resolve_dir_over_a_snapshot_with_the_code_directory_entry_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the directory entry docs/code resolves to itself on both'

    def test_resolve_dir_over_a_snapshot_with_a_code_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/a.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file docs/code/a.md leads to no directory on either'

    def test_resolve_dir_over_a_snapshot_with_a_link_to_a_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/linked.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'linked.md leads to the file a.md, so to no directory on either'

    def test_resolve_dir_over_a_snapshot_with_a_fifo_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/pipe'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the fifo docs/code/pipe leads to no directory on either'

    def test_resolve_dir_over_a_snapshot_with_an_unentered_directory_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/sub'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the unentered docs/code/sub resolves to itself on both'

    def test_resolve_dir_over_a_snapshot_with_a_relative_link_to_a_directory_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code-link'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the link docs/code-link leads to docs/code on both'

    def test_resolve_dir_over_a_snapshot_with_a_dangling_link_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/dangling'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the dangling link docs/dangling leads to no directory on either'

    def test_resolve_dir_over_a_snapshot_with_a_docs_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/glossary.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file docs/glossary.md leads to no directory on either'

    def test_resolve_dir_over_a_snapshot_with_a_non_utf8_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/latin.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file docs/latin.md leads to no directory on either'

    def test_resolve_dir_over_a_snapshot_with_a_looping_link_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/loop'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the looping link docs/loop leads to no directory on either'

    def test_resolve_dir_over_a_snapshot_with_a_link_up_to_the_root_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/up'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the link docs/up leads to the root on both'

    def test_resolve_dir_over_a_snapshot_with_the_skills_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the listed .agents/skills resolves to itself on both'

    def test_resolve_dir_over_a_snapshot_with_the_skill_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/alpha'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the listed .agents/skills/alpha resolves to itself on both'

    def test_resolve_dir_over_a_snapshot_with_the_claude_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the listed .claude resolves to itself on both'

    def test_resolve_dir_over_a_snapshot_with_the_docs_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the listed docs resolves to itself on both'

    def test_resolve_dir_over_a_snapshot_with_the_meta_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/__meta__'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the listed docs/__meta__ resolves to itself on both'

    def test_resolve_dir_over_a_snapshot_with_the_code_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the listed docs/code resolves to itself on both'

    def test_resolve_dir_over_a_snapshot_with_the_root_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the root resolves to itself on both'

    def test_resolve_dir_over_a_snapshot_with_a_directory_behind_the_linked_scope_root_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude/skills/alpha'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, '.claude/skills/alpha leads to .agents/skills/alpha on both'

    def test_resolve_dir_over_a_snapshot_with_a_link_behind_the_linked_scope_root_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude/skills/beta'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, '.claude/skills/beta follows two links to .agents/skills/alpha on both'

    def test_resolve_dir_over_a_snapshot_with_a_directory_behind_an_absolute_link_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/absolute/sub'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/absolute/sub leads to docs/code/sub on both'

    def test_resolve_dir_over_a_snapshot_with_a_directory_behind_a_relative_link_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code-link/sub'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/code-link/sub leads to docs/code/sub on both'

    def test_resolve_dir_over_a_snapshot_with_listed_components_after_a_link_up_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/up/docs/code'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/up/docs/code climbs to the root, then leads to docs/code on both'

    def test_resolve_dir_over_a_snapshot_with_a_missing_path_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/missing'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the missing docs/missing leads to no directory on either'

    def test_resolve_dir_over_a_snapshot_with_an_absolute_link_under_an_aliased_root_agrees_with_disk(
        self, aliased_root_with_an_absolute_link: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(aliased_root_with_an_absolute_link)
        virtual = VirtualFileSystem(take_snapshot(aliased_root_with_an_absolute_link, SNAPSHOT_SCOPE))

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, 'docs/absolute')

        #: Then
        assert virtual_answer == disk_answer, 'the absolute link leads to the same directory over the snapshot'

    def test_list_dir_over_a_snapshot_with_an_unresolved_claude_skills_agrees_with_disk(
        self, unresolved_claude_skills_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(unresolved_claude_skills_tree)
        virtual = VirtualFileSystem(take_snapshot(unresolved_claude_skills_tree, SNAPSHOT_SCOPE))

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, '.claude')

        #: Then
        assert virtual_answer == disk_answer, 'the parent listing shows .claude/skills over the snapshot too'

    def test_resolve_dir_over_a_snapshot_with_an_unresolved_claude_skills_agrees_with_disk(
        self, unresolved_claude_skills_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(unresolved_claude_skills_tree)
        virtual = VirtualFileSystem(take_snapshot(unresolved_claude_skills_tree, SNAPSHOT_SCOPE))

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, '.claude/skills')

        #: Then
        assert virtual_answer == disk_answer, '.claude/skills leads to no directory over the snapshot either'


@pytest.mark.it
class TestVirtualFileSystemMatchesDiskThroughFollowedLinks:
    def test_resolve_dir_over_a_following_snapshot_with_a_skill_linked_out_of_the_scope_agrees_with_disk(
        self, linked_skills_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(linked_skills_tree)
        virtual = VirtualFileSystem(take_snapshot(linked_skills_tree, FOLLOWING_SCOPE))
        path = '.agents/skills/review'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the linked skill leads to skills/review over the snapshot too'

    def test_resolve_dir_over_a_following_snapshot_with_a_skill_behind_two_links_agrees_with_disk(
        self, linked_skills_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(linked_skills_tree)
        virtual = VirtualFileSystem(take_snapshot(linked_skills_tree, FOLLOWING_SCOPE))
        path = '.claude/skills/review'

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, path)

        #: Then
        assert virtual_answer == disk_answer, (
            'through the linked skills directory and the linked skill, both views reach skills/review'
        )

    def test_list_dir_over_a_following_snapshot_with_a_skill_linked_out_of_the_scope_agrees_with_disk(
        self, linked_skills_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(linked_skills_tree)
        virtual = VirtualFileSystem(take_snapshot(linked_skills_tree, FOLLOWING_SCOPE))
        path = '.claude/skills/review'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the linked skill lists its SKILL.md over the snapshot too'

    def test_read_text_over_a_following_snapshot_with_a_file_in_a_skill_linked_out_of_the_scope_agrees_with_disk(
        self, linked_skills_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(linked_skills_tree)
        virtual = VirtualFileSystem(take_snapshot(linked_skills_tree, FOLLOWING_SCOPE))
        path = '.claude/skills/review/SKILL.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'SKILL.md reads as the same text through the path an agent uses'

    def test_read_text_over_a_following_snapshot_with_a_linked_skill_file_agrees_with_disk(
        self, linked_skills_tree: Path
    ) -> None:
        #: Given
        (linked_skills_tree / 'REVIEW.md').write_bytes(b'---\nname: shared\n---\n')
        (linked_skills_tree / '.agents' / 'skills' / 'shared').mkdir()
        (linked_skills_tree / '.agents' / 'skills' / 'shared' / 'SKILL.md').symlink_to('../../../REVIEW.md')
        disk = DiskFileSystem(linked_skills_tree)
        virtual = VirtualFileSystem(take_snapshot(linked_skills_tree, FOLLOWING_SCOPE))
        path = '.claude/skills/shared/SKILL.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'a SKILL.md that is itself a link reads as the file it leads to on both'

    def test_resolve_dir_over_a_following_snapshot_with_a_chain_longer_than_the_system_follows_agrees_with_disk(
        self, tmp_path: Path, chain_of_41_links: str
    ) -> None:
        #: Given
        scope = (ScanRoot(RootRelativePath.parse(chain_of_41_links), depth=0, follow_links=True),)
        disk = DiskFileSystem(tmp_path)
        virtual = VirtualFileSystem(take_snapshot(tmp_path, scope))

        #: When
        disk_answer, virtual_answer = _answers(disk.resolve_dir, virtual.resolve_dir, chain_of_41_links)

        #: Then
        assert virtual_answer == disk_answer, 'a chain of 41 links leads to no directory on either view'

    def test_list_dir_over_a_following_snapshot_with_a_looping_link_agrees_with_disk(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'loop').symlink_to('loop')
        disk = DiskFileSystem(tmp_path)
        virtual = VirtualFileSystem(take_snapshot(tmp_path, FOLLOWING_SCOPE))
        path = '.agents/skills/loop'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'a looping link lists as nothing on both'


@pytest.mark.it
class TestDiffOfFollowingSnapshots:
    def test_diff_with_an_empty_linked_directory_removed_returns_it_deleted(self, linked_skills_tree: Path) -> None:
        #: Given
        (linked_skills_tree / 'skills' / 'review' / 'SKILL.md').unlink()
        old = take_snapshot(linked_skills_tree, FOLLOWING_SCOPE)
        (linked_skills_tree / 'skills' / 'review').rmdir()
        new = take_snapshot(linked_skills_tree, FOLLOWING_SCOPE)

        #: When
        changes = diff(old, new)

        #: Then
        assert changes == frozenset({Change(RootRelativePath.parse('skills/review'), ChangeKind.DELETED)}), (
            'the directory the link led to is gone, and no listing of its parent was there to say so'
        )
