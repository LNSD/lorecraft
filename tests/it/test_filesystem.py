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
from typing import Final, assert_never

import pytest

from lorecraft.core.error import Error
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.vfs import (
    Change,
    ChangeKind,
    DirectoryRecord,
    DirEntry,
    DirListError,
    DirResolveError,
    DiskFileSystem,
    EntryInspectError,
    EntryKind,
    EntryRecord,
    FileReadError,
    FileRecord,
    FileResolveError,
    OsRefusal,
    OtherRecord,
    RootExit,
    ScanRoot,
    ScopeIndex,
    Snapshot,
    SnapshotDirListError,
    SnapshotEntryInspectError,
    SnapshotFileReadError,
    SnapshotLinkReadError,
    SymlinkRecord,
    TextDecodeError,
    UnrecordedFileError,
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
    """A directory whose permissions refuse listing, restored afterwards so pytest can clean it up.

    Args:
        tmp_path: Directory the locked directory is created under, as the filesystem root.
    """
    directory = tmp_path / 'locked'
    directory.mkdir()
    directory.chmod(0o000)
    yield directory
    directory.chmod(0o700)


@pytest.fixture(scope='function')
def unreadable_outside_dir(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """A directory outside the root whose permissions refuse searching, restored afterwards for cleanup.

    Args:
        tmp_path_factory: Makes a temporary directory separate from the test's root, so the locked one lies outside it.
    """
    directory = tmp_path_factory.mktemp('outside') / 'locked'
    directory.mkdir()
    directory.chmod(0o000)
    yield directory
    directory.chmod(0o700)


@pytest.fixture(scope='function')
def unsearchable_dir_with_a_link(tmp_path: Path) -> Iterator[Path]:
    """`docs/`, holding the link `linked.md`, readable but not searchable, restored afterwards for cleanup.

    Read permission lets the directory be listed, so the link shows up as an entry; without search permission
    nothing inside it can be reached, so its target cannot be read.

    Args:
        tmp_path: Directory `docs/` is created under, as the filesystem root.
    """
    directory = tmp_path / 'docs'
    directory.mkdir()
    (directory / 'linked.md').symlink_to('missing.md')
    directory.chmod(0o444)
    yield directory
    directory.chmod(0o700)


@pytest.fixture(scope='function')
def unreadable_file(tmp_path: Path) -> Iterator[Path]:
    """A file under `docs/` whose permissions refuse reading, restored afterwards for cleanup.

    Args:
        tmp_path: Directory `docs/` is created under, as the filesystem root.
    """
    (tmp_path / 'docs').mkdir()
    file = tmp_path / 'docs' / 'locked.md'
    file.write_text('', encoding='utf-8')
    file.chmod(0o000)
    yield file
    file.chmod(0o600)


@pytest.fixture(scope='function')
def parity_tree(tmp_path: Path) -> Path:
    """The parity tree under `tmp_path`: the files, links and fifo of the `PARITY_*` tables.

    Args:
        tmp_path: Directory the tree is written into, as the filesystem root. Absolute links target paths under it.
    """
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

    It holds `docs/code/` and `docs/absolute`, a link to `docs/code` by an absolute target spelled
    either through the alias or through the real root.

    Args:
        tmp_path: Directory the real root and the alias link are created in.
        request: Carries the parametrised spelling of the absolute target, through the alias or the real root.
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
    """A root whose `.claude/skills` exists but leads to no directory: a dangling link or a regular file.

    Args:
        tmp_path: Directory `.claude/` is created under, as the filesystem root.
        request: Carries the parametrised form of the unresolved entry, a dangling link or a regular file.
    """
    (tmp_path / '.claude').mkdir()
    if request.param == 'dangling-link':
        (tmp_path / '.claude' / 'skills').symlink_to('missing')
    else:
        (tmp_path / '.claude' / 'skills').write_bytes(b'not a directory\n')
    return tmp_path


@pytest.fixture(scope='function')
def linked_skills_tree(tmp_path: Path) -> Path:
    """A root whose one skill lives outside the skills directories, reached through two links.

    `skills/review/` holds the files, `.agents/skills/review` links to it, and `.claude/skills` links to
    `.agents/skills`: the layout of a repository that ships a skill and also uses it.

    Args:
        tmp_path: Directory the skill and both links are written into, as the filesystem root.
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
    """A directory under `tmp_path` reached through 41 links, one more than Linux follows; returns the first link.

    `real/` holds `SKILL.md`; `link-0` leads to `real` and each later link to the one before it, so
    `link-40` is the head of a chain that does not loop and is still too long to open.

    Args:
        tmp_path: Directory `real/` and the links are created in, as the filesystem root.
    """
    (tmp_path / 'real').mkdir()
    (tmp_path / 'real' / 'SKILL.md').write_bytes(b'---\n')
    target = 'real'
    for index in range(41):
        (tmp_path / f'link-{index}').symlink_to(target)
        target = f'link-{index}'
    return target


@pytest.fixture(scope='function')
def chain_of_40_links(tmp_path: Path) -> str:
    """A directory under `tmp_path` reached through 40 links, as many as Linux follows; returns the first link.

    Laid out as `chain_of_41_links` is, one link shorter: `link-39` is the head of the longest chain that
    still opens `real/`.

    Args:
        tmp_path: Directory `real/` and the links are created in, as the filesystem root.
    """
    (tmp_path / 'real').mkdir()
    (tmp_path / 'real' / 'SKILL.md').write_bytes(b'---\n')
    target = 'real'
    for index in range(40):
        (tmp_path / f'link-{index}').symlink_to(target)
        target = f'link-{index}'
    return target


def _snapshot(records: Mapping[str, EntryRecord], *, scope: tuple[ScanRoot, ...]) -> Snapshot:
    """A snapshot holding `records`, each keyed by its root-relative path as spelled, taken of `scope`.

    Args:
        records: Each record the snapshot holds, keyed by the path it was recorded at.
        scope: The scan roots the snapshot records it was taken of.
    """
    parsed: dict[RootRelativePath, EntryRecord] = {}
    for raw_path, record in records.items():
        parsed[RootRelativePath.parse(raw_path)] = record
    return Snapshot(FrozenMapping(parsed), scope=scope)


def _listed_directories(snapshot: Snapshot) -> set[RootRelativePath]:
    """Every directory the scan of `snapshot` listed.

    Args:
        snapshot: The scan whose directory records are read.
    """
    listed: set[RootRelativePath] = set()
    for path, record in snapshot.records.items():
        match record:
            case DirectoryRecord(listed=True):
                listed.add(path)
            case DirectoryRecord() | FileRecord() | SymlinkRecord() | OtherRecord():
                pass  # no listing
            case _:
                assert_never(record)
    return listed


def _recorded_kinds(snapshot: Snapshot) -> dict[RootRelativePath, EntryKind]:
    """Every path the scan of `snapshot` recorded, with the kind its record gives it.

    Args:
        snapshot: The scan whose records are read.
    """
    kinds: dict[RootRelativePath, EntryKind] = {}
    for path, record in snapshot.records.items():
        kinds[path] = record.kind
    return kinds


# What a failed read answers in a parity comparison. ``FileSystem.read_text`` lists two read failures: the disk
# raises ``FileReadError`` with the operating system's refusal as its source, and a snapshot, which has no
# operating system to refuse, raises ``UnrecordedFileError``. A caller catches both alike, so parity counts them
# as one answer.
UNREADABLE_FILE: Final[str] = 'the path leads to no file that can be read'


def _answer(call: Callable[[RootRelativePath], object], path: RootRelativePath) -> object:
    """What one view answers for `path`: the return value, `UNREADABLE_FILE`, or the class of the `Error`.

    Args:
        call: The view's operation to ask, such as its `read_text` or `list_dir`.
        path: Path the operation is asked about.
    """
    try:
        return call(path)
    except (FileReadError, UnrecordedFileError):
        return UNREADABLE_FILE
    except Error as exc:
        return type(exc)


def _answers(
    disk_call: Callable[[RootRelativePath], object], virtual_call: Callable[[RootRelativePath], object], path: str
) -> tuple[object, object]:
    """The disk view's answer and the virtual view's answer for the same path, in that order.

    Args:
        disk_call: The disk view's operation to ask.
        virtual_call: The snapshot view's operation to ask, the same one as `disk_call`.
        path: Root-relative path, as text, both operations are asked about.
    """
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
            DirEntry(PathComponent.parse('a.md'), EntryKind.FILE),
            DirEntry(PathComponent.parse('b.md'), EntryKind.FILE),
            DirEntry(PathComponent.parse('c'), EntryKind.DIRECTORY),
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
        assert DirEntry(PathComponent.parse('link'), EntryKind.SYMLINK) in entries, (
            'a symlink to a file is SYMLINK, never FILE'
        )

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
        assert DirEntry(PathComponent.parse('link'), EntryKind.SYMLINK) in entries, (
            'a symlink to a directory is SYMLINK, never DIRECTORY'
        )

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
        assert DirEntry(PathComponent.parse('link'), EntryKind.SYMLINK) in entries, (
            'a symlink to nothing is still listed as SYMLINK'
        )

    def test_list_dir_with_a_fifo_returns_other_kind(self, tmp_path: Path) -> None:
        #: Given
        os.mkfifo(tmp_path / 'pipe')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        entries = filesystem.list_dir(RootRelativePath.parse('.'))

        #: Then
        assert entries == (DirEntry(PathComponent.parse('pipe'), EntryKind.OTHER),), (
            'neither a file nor a directory is OTHER'
        )

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
        with pytest.raises(DirListError) as exc_info:
            filesystem.list_dir(locked)

        #: Then
        assert exc_info.value.path == locked, 'the error names the root-relative directory'
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'the refusal is classified from the errno'
        assert isinstance(exc_info.value.source, PermissionError), 'the error keeps the operating system failure'
        assert str(locked) in str(exc_info.value), 'the message names the directory that could not be listed'


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
        with pytest.raises(TextDecodeError) as exc_info:
            filesystem.read_text(latin)

        #: Then
        assert exc_info.value.path == latin, 'the error names the root-relative file'
        assert isinstance(exc_info.value.source, UnicodeDecodeError), 'the error keeps the decoder failure'
        assert str(latin) in str(exc_info.value), 'the message names the file that is not UTF-8'

    def test_read_text_with_a_missing_file_raises_file_read_error(self, tmp_path: Path) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)
        missing = RootRelativePath.parse('missing.md')

        #: When
        with pytest.raises(FileReadError) as exc_info:
            filesystem.read_text(missing)

        #: Then
        assert exc_info.value.path == missing, 'the error names the root-relative file'
        assert exc_info.value.refusal is OsRefusal.NOT_FOUND, 'the refusal is classified from the errno'
        assert isinstance(exc_info.value.source, FileNotFoundError), 'the error keeps the operating system failure'
        assert not isinstance(exc_info.value, TextDecodeError), 'a missing file is not a decode failure'
        assert str(missing) in str(exc_info.value), 'the message names the file that could not be read'


@pytest.mark.it
class TestDiskFileSystemFindEntryKind:
    def test_find_entry_kind_with_a_regular_file_returns_file(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'notes.md').write_text('', encoding='utf-8')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        kind = filesystem.find_entry_kind(RootRelativePath.parse('notes.md'))

        #: Then
        assert kind is EntryKind.FILE, 'a regular file is FILE'

    def test_find_entry_kind_with_a_directory_returns_directory(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs').mkdir()
        filesystem = DiskFileSystem(tmp_path)

        #: When
        kind = filesystem.find_entry_kind(RootRelativePath.parse('docs'))

        #: Then
        assert kind is EntryKind.DIRECTORY, 'a regular directory is DIRECTORY'

    def test_find_entry_kind_with_the_root_returns_directory(self, tmp_path: Path) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)

        #: When
        kind = filesystem.find_entry_kind(RootRelativePath.parse('.'))

        #: Then
        assert kind is EntryKind.DIRECTORY, 'the root is a directory'

    def test_find_entry_kind_with_a_symlink_to_a_directory_returns_symlink(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'real-docs').mkdir()
        (tmp_path / 'docs').symlink_to('real-docs')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        kind = filesystem.find_entry_kind(RootRelativePath.parse('docs'))

        #: Then
        assert kind is EntryKind.SYMLINK, 'a link at the path is SYMLINK, never the directory it leads to'

    def test_find_entry_kind_with_a_dangling_symlink_returns_symlink(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'link').symlink_to('missing')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        kind = filesystem.find_entry_kind(RootRelativePath.parse('link'))

        #: Then
        assert kind is EntryKind.SYMLINK, 'a link to nothing is still an entry, and a SYMLINK'

    def test_find_entry_kind_with_a_fifo_returns_other(self, tmp_path: Path) -> None:
        #: Given
        os.mkfifo(tmp_path / 'pipe')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        kind = filesystem.find_entry_kind(RootRelativePath.parse('pipe'))

        #: Then
        assert kind is EntryKind.OTHER, 'neither a file nor a directory is OTHER'

    def test_find_entry_kind_through_a_linked_parent_returns_the_kind_of_the_entry_it_leads_to(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'real').mkdir()
        (tmp_path / 'real' / 'SKILL.md').write_text('', encoding='utf-8')
        (tmp_path / 'link').symlink_to('real')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        kind = filesystem.find_entry_kind(RootRelativePath.parse('link/SKILL.md'))

        #: Then
        assert kind is EntryKind.FILE, 'a link on the way is followed, so link/SKILL.md is the file in real/'

    def test_find_entry_kind_with_a_missing_path_returns_none(self, tmp_path: Path) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)

        #: When
        kind = filesystem.find_entry_kind(RootRelativePath.parse('missing.md'))

        #: Then
        assert kind is None, 'a missing path has no kind rather than failing'

    def test_find_entry_kind_through_a_file_component_returns_none(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'notes.md').write_text('', encoding='utf-8')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        kind = filesystem.find_entry_kind(RootRelativePath.parse('notes.md/inner'))

        #: Then
        assert kind is None, 'nothing sits inside a file, so the path has no kind'

    def test_find_entry_kind_behind_a_looping_link_returns_none(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'loop').symlink_to('loop')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        kind = filesystem.find_entry_kind(RootRelativePath.parse('loop/inner'))

        #: Then
        assert kind is None, 'a looping parent leads to no directory, so nothing is inside it, like a dangling one'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_find_entry_kind_under_an_unreadable_directory_raises_entry_kind_error(
        self, tmp_path: Path, unreadable_dir: Path
    ) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)
        inside = RootRelativePath.parse(unreadable_dir.name) / 'inner'

        #: When
        with pytest.raises(EntryInspectError) as exc_info:
            filesystem.find_entry_kind(inside)

        #: Then
        assert exc_info.value.path == inside, 'the error names the root-relative path that could not be inspected'
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'the refusal is classified from the errno'
        assert isinstance(exc_info.value.source, PermissionError), 'the error keeps the operating system failure'
        assert str(inside) in str(exc_info.value), 'the message names the entry that could not be inspected'


@pytest.mark.it
class TestDiskFileSystemFindDir:
    def test_find_dir_with_a_regular_directory_returns_itself(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        filesystem = DiskFileSystem(tmp_path)
        skills = RootRelativePath.parse('.agents/skills')

        #: When
        resolved = filesystem.find_dir(skills)

        #: Then
        assert resolved == skills, 'a directory with no link in its path resolves to itself'

    def test_find_dir_with_the_root_returns_dot(self, tmp_path: Path) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_dir(RootRelativePath.parse('.'))

        #: Then
        assert resolved == RootRelativePath.parse('.'), 'the root resolves to the empty root-relative path'

    def test_find_dir_with_a_link_to_a_directory_returns_the_target(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'target').mkdir()
        (tmp_path / 'link').symlink_to(tmp_path / 'target')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_dir(RootRelativePath.parse('link'))

        #: Then
        assert resolved == RootRelativePath.parse('target'), 'a link to a directory resolves to the directory it names'

    def test_find_dir_through_a_linked_parent_returns_the_resolved_directory(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.claude').symlink_to('.agents')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_dir(RootRelativePath.parse('.claude/skills'))

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills'), 'a link on a parent component is followed too'

    def test_find_dir_with_a_relative_link_from_a_subdirectory_returns_the_target(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_dir(RootRelativePath.parse('.claude/skills'))

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills'), 'a relative target is read from the link directory'

    def test_find_dir_with_a_dangling_link_returns_none(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'link').symlink_to('missing')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_dir(RootRelativePath.parse('link'))

        #: Then
        assert resolved is None, 'a link to nothing leads to no directory'

    def test_find_dir_with_a_link_loop_returns_none(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'first').symlink_to('second')
        (tmp_path / 'second').symlink_to('first')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_dir(RootRelativePath.parse('first'))

        #: Then
        assert resolved is None, 'a looping link leads nowhere, like a dangling one'

    def test_find_dir_with_a_chain_longer_than_the_system_follows_returns_none(
        self, tmp_path: Path, chain_of_41_links: str
    ) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_dir(RootRelativePath.parse(chain_of_41_links))

        #: Then
        assert resolved is None, 'nothing opens a directory through a chain the operating system gives up on'

    def test_find_dir_with_a_link_to_a_file_returns_none(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'notes.md').write_text('', encoding='utf-8')
        (tmp_path / 'link').symlink_to('notes.md')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_dir(RootRelativePath.parse('link'))

        #: Then
        assert resolved is None, 'a link whose target is a file is not a directory'

    def test_find_dir_with_a_missing_path_returns_none(self, tmp_path: Path) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_dir(RootRelativePath.parse('.agents/skills'))

        #: Then
        assert resolved is None, 'a missing path resolves to nothing rather than failing'

    def test_find_dir_through_a_file_component_returns_none(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'notes.md').write_text('', encoding='utf-8')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_dir(RootRelativePath.parse('notes.md/skills'))

        #: Then
        assert resolved is None, 'a path through a file resolves to nothing rather than failing'

    def test_find_dir_with_a_link_outside_the_root_returns_none(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        outside = tmp_path_factory.mktemp('outside')
        (tmp_path / 'link').symlink_to(outside)
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_dir(RootRelativePath.parse('link'))

        #: Then
        assert resolved is None, 'a directory outside the root has no root-relative spelling'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_find_dir_under_an_unreadable_directory_raises_resolve_dir_error(
        self, tmp_path: Path, unreadable_dir: Path
    ) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)
        inside_locked = RootRelativePath.parse(unreadable_dir.name) / 'skills'

        #: When
        with pytest.raises(DirResolveError) as exc_info:
            filesystem.find_dir(inside_locked)

        #: Then
        assert exc_info.value.path == inside_locked, 'the error names the root-relative path'
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'the refusal is classified from the errno'
        assert isinstance(exc_info.value.source, PermissionError), 'the error keeps the operating system failure'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_find_dir_with_a_link_into_an_unreadable_directory_outside_the_root_returns_none(
        self, tmp_path: Path, unreadable_outside_dir: Path
    ) -> None:
        #: Given
        (tmp_path / 'link').symlink_to(unreadable_outside_dir / 'skills')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_dir(RootRelativePath.parse('link'))

        #: Then
        assert resolved is None, 'a chain leading outside the root never fails, even where the lookup is refused'


@pytest.mark.it
class TestDiskFileSystemFindFile:
    def test_find_file_with_a_regular_file_returns_itself(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'notes.md').write_text('', encoding='utf-8')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_file(RootRelativePath.parse('notes.md'))

        #: Then
        assert resolved == RootRelativePath.parse('notes.md'), 'a file with no link in its path resolves to itself'

    def test_find_file_with_a_link_to_a_file_returns_the_target(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'shared').mkdir()
        (tmp_path / 'shared' / 'REVIEW.md').write_text('', encoding='utf-8')
        (tmp_path / 'review').mkdir()
        (tmp_path / 'review' / 'SKILL.md').symlink_to('../shared/REVIEW.md')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_file(RootRelativePath.parse('review/SKILL.md'))

        #: Then
        assert resolved == RootRelativePath.parse('shared/REVIEW.md'), (
            'a link to a file resolves to the file it names, whatever that file is called'
        )

    def test_find_file_through_a_linked_parent_returns_the_resolved_file(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / '.agents' / 'skills' / 'review').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').write_text('', encoding='utf-8')
        (tmp_path / '.claude').symlink_to('.agents')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_file(RootRelativePath.parse('.claude/skills/review/SKILL.md'))

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills/review/SKILL.md'), (
            'a link on a parent component is followed too'
        )

    def test_find_file_with_a_directory_returns_none(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs').mkdir()
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_file(RootRelativePath.parse('docs'))

        #: Then
        assert resolved is None, 'a directory is not a file'

    def test_find_file_with_a_dangling_link_returns_none(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'link').symlink_to('missing.md')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_file(RootRelativePath.parse('link'))

        #: Then
        assert resolved is None, 'a link to nothing leads to no file'

    def test_find_file_with_a_link_loop_returns_none(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'first').symlink_to('second')
        (tmp_path / 'second').symlink_to('first')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_file(RootRelativePath.parse('first'))

        #: Then
        assert resolved is None, 'a looping link leads nowhere, like a dangling one'

    def test_find_file_with_a_missing_path_returns_none(self, tmp_path: Path) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_file(RootRelativePath.parse('missing.md'))

        #: Then
        assert resolved is None, 'a missing path resolves to nothing rather than failing'

    def test_find_file_with_a_link_outside_the_root_returns_none(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        outside = tmp_path_factory.mktemp('outside') / 'notes.md'
        outside.write_text('', encoding='utf-8')
        (tmp_path / 'link').symlink_to(outside)
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_file(RootRelativePath.parse('link'))

        #: Then
        assert resolved is None, 'a file outside the root has no root-relative spelling'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_find_file_under_an_unreadable_directory_raises_resolve_file_error(
        self, tmp_path: Path, unreadable_dir: Path
    ) -> None:
        #: Given
        filesystem = DiskFileSystem(tmp_path)
        inside_locked = RootRelativePath.parse(unreadable_dir.name) / 'SKILL.md'

        #: When
        with pytest.raises(FileResolveError) as exc_info:
            filesystem.find_file(inside_locked)

        #: Then
        assert exc_info.value.path == inside_locked, 'the error names the root-relative path'
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'the refusal is classified from the errno'
        assert isinstance(exc_info.value.source, PermissionError), 'the error keeps the operating system failure'
        assert str(inside_locked) in str(exc_info.value), 'the message names the path that could not be resolved'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_find_file_with_a_link_into_an_unreadable_directory_outside_the_root_returns_none(
        self, tmp_path: Path, unreadable_outside_dir: Path
    ) -> None:
        #: Given
        (tmp_path / 'link').symlink_to(unreadable_outside_dir / 'SKILL.md')
        filesystem = DiskFileSystem(tmp_path)

        #: When
        resolved = filesystem.find_file(RootRelativePath.parse('link'))

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
        assert snapshot == _snapshot(
            {
                'docs': DirectoryRecord(listed=True),
                'docs/code': DirectoryRecord(listed=True),
                'docs/code/a.md': FileRecord(b'# A\n'),
                'docs/glossary.md': FileRecord(b'# Glossary\n'),
            },
            scope=SNAPSHOT_SCOPE,
        ), 'each listing down to the depth, and the bytes of every file entry in them'

    def test_take_snapshot_with_a_directory_beyond_the_depth_lists_it_without_entering_it(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs' / 'code' / 'sub').mkdir(parents=True)
        (tmp_path / 'docs' / 'code' / 'sub' / 'x.md').write_bytes(b'# X\n')

        #: When
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot == _snapshot(
            {
                'docs': DirectoryRecord(listed=True),
                'docs/code': DirectoryRecord(listed=True),
                'docs/code/sub': DirectoryRecord(),
            },
            scope=SNAPSHOT_SCOPE,
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
        assert snapshot == _snapshot(
            {
                'docs': DirectoryRecord(listed=True),
                'docs/a.md': FileRecord(b'# A\n'),
                'docs/linked.md': SymlinkRecord(PurePosixPath('a.md')),
            },
            scope=SNAPSHOT_SCOPE,
        ), 'the link is an entry with its target recorded, and no bytes are read through it'

    def test_take_snapshot_with_a_fifo_records_the_entry_without_reading_it(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs').mkdir()
        os.mkfifo(tmp_path / 'docs' / 'pipe')

        #: When
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot == _snapshot(
            {'docs': DirectoryRecord(listed=True), 'docs/pipe': OtherRecord()}, scope=SNAPSHOT_SCOPE
        ), 'a fifo is an OTHER entry, and nothing is read from it'

    def test_take_snapshot_with_missing_scope_roots_returns_an_empty_snapshot(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'README.md').write_bytes(b'# Outside the scope\n')

        #: When
        snapshot = take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot == _snapshot({}, scope=SNAPSHOT_SCOPE), (
            'a missing scope root is simply absent, and still recorded in the scope'
        )

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
        assert snapshot == _snapshot(
            {
                '.agents/skills': DirectoryRecord(listed=True),
                '.agents/skills/alpha': DirectoryRecord(listed=True),
                '.agents/skills/alpha/SKILL.md': FileRecord(b'---\n'),
                '.claude': DirectoryRecord(listed=True, climbed=True),
                '.claude/skills': SymlinkRecord(PurePosixPath('../.agents/skills')),
            },
            scope=SNAPSHOT_SCOPE,
        ), 'the linked agent directory is one link, its chain walked for the record; its skills are listed once'

    def test_take_snapshot_with_an_absolute_link_under_the_root_records_it_relative_to_the_link(
        self, aliased_root_with_an_absolute_link: Path
    ) -> None:
        #: Given
        root = aliased_root_with_an_absolute_link

        #: When
        snapshot = take_snapshot(root, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot.symlink_targets() == {RootRelativePath.parse('docs/absolute'): PurePosixPath('../docs/code')}, (
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
        assert snapshot.symlink_targets() == {RootRelativePath.parse('docs/outside'): PurePosixPath(outside)}, (
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
        assert snapshot == _snapshot(
            {
                'docs': DirectoryRecord(listed=True),
                'docs/code': DirectoryRecord(listed=True),
                'docs/code/sub': DirectoryRecord(listed=True),
                'docs/code/sub/x.md': FileRecord(b'# X\n'),
            },
            scope=scope,
        ), 'a directory two roots reach is listed down to the deeper of their depths'

    def test_take_snapshot_with_overlapping_scope_roots_records_the_scope_as_given(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs' / 'code').mkdir(parents=True)
        scope = (
            ScanRoot(DOCS_DIR / 'code', depth=0),
            ScanRoot(DOCS_DIR, depth=1),
            ScanRoot(DOCS_DIR / 'code', depth=0),
        )

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot.scope == (
            ScanRoot(RootRelativePath.parse('docs/code'), depth=0),
            ScanRoot(RootRelativePath.parse('docs'), depth=1),
            ScanRoot(RootRelativePath.parse('docs/code'), depth=0),
        ), 'the scope is recorded in the order given and unmerged, though the scan lists docs/code once'

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
        assert snapshot == _snapshot(
            {
                '.claude': DirectoryRecord(climbed=True),
                '.claude/skills': SymlinkRecord(PurePosixPath('../skills')),
                'skills': DirectoryRecord(listed=True),
                'skills/review': DirectoryRecord(listed=True),
                'skills/review/SKILL.md': FileRecord(b'---\n'),
            },
            scope=scope,
        ), 'the directory the scope root leads to is listed at its resolved path, down to the depth'

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
        assert snapshot == _snapshot(
            {
                '.agents': DirectoryRecord(climbed=True),
                '.agents/skills': DirectoryRecord(listed=True, climbed=True),
                '.agents/skills/review': SymlinkRecord(PurePosixPath('../../skills/review')),
                'skills/review': DirectoryRecord(listed=True),
                'skills/review/SKILL.md': FileRecord(b'---\n'),
            },
            scope=scope,
        ), 'the entry stays a symlink, and the directory it leads to is listed at its resolved path'

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
        assert snapshot == _snapshot(
            {
                '.agents': DirectoryRecord(climbed=True),
                '.agents/skills': DirectoryRecord(listed=True, climbed=True),
                '.agents/skills/review': SymlinkRecord(PurePosixPath('../../skills/review')),
            },
            scope=scope,
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
        assert snapshot == _snapshot(
            {
                '.claude': DirectoryRecord(climbed=True),
                '.claude/skills': SymlinkRecord(PurePosixPath('../current')),
                'current': SymlinkRecord(PurePosixPath('skills')),
                'skills': DirectoryRecord(listed=True),
                'skills/review': DirectoryRecord(),
            },
            scope=scope,
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
        assert snapshot == _snapshot(
            {
                '.agents/skills': DirectoryRecord(listed=True),
                '.agents/skills/review': SymlinkRecord(PurePosixPath(outside)),
            },
            scope=scope,
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
        assert snapshot == _snapshot(
            {
                '.agents/skills': DirectoryRecord(listed=True),
                '.agents/skills/loop': SymlinkRecord(PurePosixPath('loop')),
            },
            scope=scope,
        ), 'a link that leads back to itself ends the walk instead of the scan never returning'

    def test_take_snapshot_following_a_link_to_a_file_records_its_bytes_at_the_resolved_path(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'REVIEW.md').write_bytes(b'---\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'SKILL.md').symlink_to('../../REVIEW.md')
        scope = (ScanRoot(RootRelativePath.parse('.agents/skills'), depth=0, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == _snapshot(
            {
                '.agents': DirectoryRecord(climbed=True),
                '.agents/skills': DirectoryRecord(listed=True, climbed=True),
                '.agents/skills/SKILL.md': SymlinkRecord(PurePosixPath('../../REVIEW.md')),
                'REVIEW.md': FileRecord(b'---\n'),
            },
            scope=scope,
        ), 'the entry stays a symlink, and the file it leads to is read at its resolved path, whatever the depth'

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
        assert snapshot == _snapshot(
            {
                '.agents/skills': DirectoryRecord(listed=True),
                '.agents/skills/SKILL.md': SymlinkRecord(PurePosixPath(outside)),
            },
            scope=scope,
        ), 'a link leading outside the root is recorded, and no bytes outside the root are read'

    def test_take_snapshot_following_a_link_that_climbs_out_of_a_directory_it_stepped_into_lists_where_it_leads(
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
        assert snapshot == _snapshot(
            {
                '.agents': DirectoryRecord(climbed=True),
                '.agents/skills': DirectoryRecord(listed=True, climbed=True),
                '.agents/skills/review': SymlinkRecord(PurePosixPath('../../skills/tmp/../review')),
                'skills/review': DirectoryRecord(listed=True),
                'skills/review/SKILL.md': FileRecord(b'---\n'),
                'skills/tmp': DirectoryRecord(climbed=True),
            },
            scope=scope,
        ), 'the `..` after skills/tmp is skills, so the link leads to skills/review, and skills/tmp is recorded climbed'

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
        assert snapshot == _snapshot(
            {
                'docs': DirectoryRecord(listed=True, climbed=True),
                'docs/shared': SymlinkRecord(PurePosixPath('../shared')),
                'shared': DirectoryRecord(listed=True),
                'shared/a.md': FileRecord(b'# A\n'),
            },
            scope=scope,
        ), 'a directory two roots reach has its links followed when either root asks for it'

    def test_take_snapshot_with_a_plain_root_under_a_following_one_still_lists_the_roots_before_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'skills').mkdir()
        (tmp_path / 'skills' / 'SKILL.md').write_bytes(b'---\n')
        (tmp_path / 'docs').mkdir()
        (tmp_path / 'docs' / 'a.md').write_bytes(b'# A\n')
        # the roots are scanned last first: the following docs root covers the plain one, which is skipped, and
        # skills, scanned after that skip, must still be listed
        scope = (
            ScanRoot(RootRelativePath.parse('skills'), depth=0),
            ScanRoot(DOCS_DIR, depth=0),
            ScanRoot(DOCS_DIR, depth=1, follow_links=True),
        )

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert _listed_directories(snapshot) == {DOCS_DIR, RootRelativePath.parse('skills')}, (
            'skipping a root another root already covered goes on to the roots left to scan'
        )

    def test_take_snapshot_with_a_plain_root_under_a_deeper_plain_one_still_lists_the_roots_before_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'skills').mkdir()
        (tmp_path / 'skills' / 'SKILL.md').write_bytes(b'---\n')
        (tmp_path / 'docs').mkdir()
        (tmp_path / 'docs' / 'a.md').write_bytes(b'# A\n')
        # as above, with the covering docs root plain too
        scope = (
            ScanRoot(RootRelativePath.parse('skills'), depth=0),
            ScanRoot(DOCS_DIR, depth=0),
            ScanRoot(DOCS_DIR, depth=1),
        )

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert _listed_directories(snapshot) == {DOCS_DIR, RootRelativePath.parse('skills')}, (
            'skipping a root another root already covered goes on to the roots left to scan'
        )

    def test_take_snapshot_following_a_linked_entry_lists_the_directory_it_leads_to_one_level_deeper(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'skills' / 'review' / 'references').mkdir(parents=True)
        (tmp_path / 'skills' / 'review' / 'references' / 'guide.md').write_bytes(b'# Guide\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        scope = (ScanRoot(RootRelativePath.parse('.agents/skills'), depth=1, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == _snapshot(
            {
                '.agents': DirectoryRecord(climbed=True),
                '.agents/skills': DirectoryRecord(listed=True, climbed=True),
                '.agents/skills/review': SymlinkRecord(PurePosixPath('../../skills/review')),
                'skills/review': DirectoryRecord(listed=True),
                'skills/review/references': DirectoryRecord(),
            },
            scope=scope,
        ), 'the link spends the one level of depth, so the directory inside its target is listed and not entered'

    def test_take_snapshot_following_a_link_inside_a_linked_directory_follows_it_too(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'shared' / 'references').mkdir(parents=True)
        (tmp_path / 'shared' / 'references' / 'guide.md').write_bytes(b'# Guide\n')
        (tmp_path / 'skills' / 'review').mkdir(parents=True)
        (tmp_path / 'skills' / 'review' / 'references').symlink_to('../../shared/references')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        scope = (ScanRoot(RootRelativePath.parse('.agents/skills'), depth=2, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == _snapshot(
            {
                '.agents': DirectoryRecord(climbed=True),
                '.agents/skills': DirectoryRecord(listed=True, climbed=True),
                '.agents/skills/review': SymlinkRecord(PurePosixPath('../../skills/review')),
                'shared/references': DirectoryRecord(listed=True),
                'shared/references/guide.md': FileRecord(b'# Guide\n'),
                'skills': DirectoryRecord(climbed=True),
                'skills/review': DirectoryRecord(listed=True, climbed=True),
                'skills/review/references': SymlinkRecord(PurePosixPath('../../shared/references')),
            },
            scope=scope,
        ), 'a directory reached through a followed link has its own links followed as well'

    def test_take_snapshot_following_a_link_that_climbs_out_of_a_missing_directory_lists_nothing_through_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'skills' / 'review').mkdir(parents=True)
        (tmp_path / 'skills' / 'review' / 'SKILL.md').write_bytes(b'---\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        # tmp does not exist, so the operating system fails the lookup at it, before the `..`
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../tmp/../skills/review')
        scope = (ScanRoot(RootRelativePath.parse('.agents/skills'), depth=1, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == _snapshot(
            {
                '.agents': DirectoryRecord(climbed=True),
                '.agents/skills': DirectoryRecord(listed=True, climbed=True),
                '.agents/skills/review': SymlinkRecord(PurePosixPath('../../tmp/../skills/review')),
            },
            scope=scope,
        ), 'a `..` after a missing directory is no step at all, so the link leads nowhere and nothing is listed'

    def test_take_snapshot_following_a_chain_as_long_as_the_system_follows_lists_the_directory_it_leads_to(
        self, tmp_path: Path, chain_of_40_links: str
    ) -> None:
        #: Given
        scope = (ScanRoot(RootRelativePath.parse(chain_of_40_links), depth=0, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert _listed_directories(snapshot) == {RootRelativePath.parse('real')}, (
            'a chain of 40 links is as long as the kernel follows, so the scan lists the directory it leads to'
        )

    def test_take_snapshot_with_no_depth_limit_lists_every_directory_below_and_reads_every_file(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'skills' / 'x' / 'references' / 'deep').mkdir(parents=True)
        (tmp_path / 'skills' / 'x' / 'SKILL.md').write_bytes(b'---\n')
        (tmp_path / 'skills' / 'x' / 'references' / 'a.md').write_bytes(b'# A\n')
        (tmp_path / 'skills' / 'x' / 'references' / 'deep' / 'b.md').write_bytes(b'# B\n')
        scope = (ScanRoot(RootRelativePath.parse('skills'), depth=None),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == _snapshot(
            {
                'skills': DirectoryRecord(listed=True),
                'skills/x': DirectoryRecord(listed=True),
                'skills/x/SKILL.md': FileRecord(b'---\n'),
                'skills/x/references': DirectoryRecord(listed=True),
                'skills/x/references/a.md': FileRecord(b'# A\n'),
                'skills/x/references/deep': DirectoryRecord(listed=True),
                'skills/x/references/deep/b.md': FileRecord(b'# B\n'),
            },
            scope=scope,
        ), 'a root with no depth limit lists every directory below it and reads every file, at any depth'

    def test_take_snapshot_with_no_depth_limit_following_a_link_to_a_directory_lists_it_at_any_depth(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'shared' / 'deep').mkdir(parents=True)
        (tmp_path / 'shared' / 'deep' / 'b.md').write_bytes(b'# B\n')
        (tmp_path / 'skills' / 'x').mkdir(parents=True)
        (tmp_path / 'skills' / 'x' / 'refs').symlink_to('../../shared')
        scope = (ScanRoot(RootRelativePath.parse('skills'), depth=None, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == _snapshot(
            {
                'shared': DirectoryRecord(listed=True),
                'shared/deep': DirectoryRecord(listed=True),
                'shared/deep/b.md': FileRecord(b'# B\n'),
                'skills': DirectoryRecord(listed=True, climbed=True),
                'skills/x': DirectoryRecord(listed=True, climbed=True),
                'skills/x/refs': SymlinkRecord(PurePosixPath('../../shared')),
            },
            scope=scope,
        ), 'the link inside a skill is followed, and the directory it leads to is listed with no depth limit'

    def test_take_snapshot_with_no_depth_limit_following_a_link_to_an_ancestor_lists_each_directory_once(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'skills' / 'x').mkdir(parents=True)
        (tmp_path / 'skills' / 'x' / 'SKILL.md').write_bytes(b'---\n')
        (tmp_path / 'skills' / 'x' / 'up').symlink_to('..')
        scope = (ScanRoot(RootRelativePath.parse('skills'), depth=None, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == _snapshot(
            {
                'skills': DirectoryRecord(listed=True),
                'skills/x': DirectoryRecord(listed=True, climbed=True),
                'skills/x/SKILL.md': FileRecord(b'---\n'),
                'skills/x/up': SymlinkRecord(PurePosixPath('..')),
            },
            scope=scope,
        ), 'the link leads back to skills/, already listed with no limit, so the scan ends instead of looping'

    def test_take_snapshot_with_no_depth_limit_following_two_directories_linked_to_each_other_lists_each_once(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'a').mkdir()
        (tmp_path / 'b').mkdir()
        (tmp_path / 'a' / 'to-b').symlink_to('../b')
        (tmp_path / 'b' / 'to-a').symlink_to('../a')
        scope = (ScanRoot(RootRelativePath.parse('a'), depth=None, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == _snapshot(
            {
                'a': DirectoryRecord(listed=True, climbed=True),
                'a/to-b': SymlinkRecord(PurePosixPath('../b')),
                'b': DirectoryRecord(listed=True, climbed=True),
                'b/to-a': SymlinkRecord(PurePosixPath('../a')),
            },
            scope=scope,
        ), 'a/ leads to b/ and b/ back to a/, already listed with no limit, so the scan ends'

    def test_take_snapshot_with_no_depth_limit_following_a_link_to_itself_records_it_and_lists_nothing_through_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'skills' / 'x').mkdir(parents=True)
        (tmp_path / 'skills' / 'x' / 'self').symlink_to('self')
        scope = (ScanRoot(RootRelativePath.parse('skills'), depth=None, follow_links=True),)

        #: When
        snapshot = take_snapshot(tmp_path, scope)

        #: Then
        assert snapshot == _snapshot(
            {
                'skills': DirectoryRecord(listed=True),
                'skills/x': DirectoryRecord(listed=True),
                'skills/x/self': SymlinkRecord(PurePosixPath('self')),
            },
            scope=scope,
        ), 'a link to itself leads nowhere, so it is recorded and nothing is listed through it'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_take_snapshot_with_an_unreadable_directory_raises_snapshot_dir_list_error(
        self, tmp_path: Path, unreadable_dir: Path
    ) -> None:
        #: Given
        locked = RootRelativePath.parse(unreadable_dir.name)
        scope = (ScanRoot(locked, depth=0),)

        #: When
        with pytest.raises(SnapshotDirListError) as exc_info:
            take_snapshot(tmp_path, scope)

        #: Then
        assert exc_info.value.path == locked, 'the error names the root-relative directory the scan stopped at'
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'the refusal is classified from the errno'
        assert isinstance(exc_info.value.source, PermissionError), 'the error keeps the operating system failure'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores file permissions')
    def test_take_snapshot_with_an_unreadable_file_raises_snapshot_file_read_error(
        self, tmp_path: Path, unreadable_file: Path
    ) -> None:
        #: Given
        locked = RootRelativePath.parse(unreadable_file.relative_to(tmp_path).as_posix())

        #: When
        with pytest.raises(SnapshotFileReadError) as exc_info:
            take_snapshot(tmp_path, SNAPSHOT_SCOPE)

        #: Then
        assert exc_info.value.path == locked, 'the error names the root-relative file the scan stopped at'
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'the refusal is classified from the errno'
        assert isinstance(exc_info.value.source, PermissionError), 'the error keeps the operating system failure'
        assert str(locked) in str(exc_info.value), 'the message names the file the scan stopped at'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_take_snapshot_with_a_scope_root_under_an_unreadable_directory_raises_snapshot_entry_inspect_error(
        self, tmp_path: Path, unreadable_dir: Path
    ) -> None:
        #: Given
        inside_locked = RootRelativePath.parse(unreadable_dir.name) / 'inner'
        scope = (ScanRoot(inside_locked, depth=0),)

        #: When
        with pytest.raises(SnapshotEntryInspectError) as exc_info:
            take_snapshot(tmp_path, scope)

        #: Then
        assert exc_info.value.path == inside_locked, 'the error names the root-relative entry the walk stopped at'
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'the refusal is classified from the errno'
        assert isinstance(exc_info.value.source, PermissionError), 'the error keeps the operating system failure'
        assert str(inside_locked) in str(exc_info.value), 'the message names the entry the walk stopped at'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_take_snapshot_with_a_link_in_an_unsearchable_directory_raises_snapshot_link_read_error(
        self, tmp_path: Path, unsearchable_dir_with_a_link: Path
    ) -> None:
        #: Given
        link = RootRelativePath.parse(unsearchable_dir_with_a_link.relative_to(tmp_path).as_posix()) / 'linked.md'
        scope = (ScanRoot(link.parent, depth=0),)

        #: When
        with pytest.raises(SnapshotLinkReadError) as exc_info:
            take_snapshot(tmp_path, scope)

        #: Then
        assert exc_info.value.path == link, 'the error names the root-relative link the scan stopped at'
        assert exc_info.value.refusal is OsRefusal.PERMISSION_DENIED, 'the refusal is classified from the errno'
        assert isinstance(exc_info.value.source, PermissionError), 'the error keeps the operating system failure'
        assert str(link) in str(exc_info.value), 'the message names the link the scan stopped at'


@pytest.mark.it
class TestVirtualFileSystemMatchesDisk:
    def test_take_snapshot_of_the_parity_tree_records_exactly_the_compared_entries(self, parity_tree: Path) -> None:
        #: Given
        expected = {RootRelativePath.parse(path): kind for path, kind in PARITY_ENTRIES.items()}

        #: When
        snapshot = take_snapshot(parity_tree, SNAPSHOT_SCOPE)

        #: Then
        assert _recorded_kinds(snapshot) == expected, 'the parity tables cover every path the snapshot lists'

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

    # find_entry_kind: a listed entry of every kind, entries recorded outside a listing of their parent, entries behind
    # the linked scope root, and paths neither view holds anything at. An entry inside an unentered directory is
    # left out: the disk sees it, while the snapshot never entered the directory.

    def test_find_entry_kind_over_a_snapshot_with_a_scope_root_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs is a directory on both, though the snapshot never listed the root'

    def test_find_entry_kind_over_a_snapshot_with_the_meta_directory_entry_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/__meta__'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/__meta__ is a directory on both'

    def test_find_entry_kind_over_a_snapshot_with_a_code_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/a.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/code/a.md is a file on both'

    def test_find_entry_kind_over_a_snapshot_with_a_link_to_a_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/linked.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/code/linked.md is a link on both, never the file it leads to'

    def test_find_entry_kind_over_a_snapshot_with_a_fifo_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = PARITY_FIFO

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, 'the fifo is OTHER on both'

    def test_find_entry_kind_over_a_snapshot_with_an_unentered_directory_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/sub'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/code/sub is a directory on both, though the scan never entered it'

    def test_find_entry_kind_over_a_snapshot_with_the_linked_scope_root_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude/skills'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, '.claude/skills is a link on both, though it sits in no listing'

    def test_find_entry_kind_over_a_snapshot_with_a_link_behind_the_linked_scope_root_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude/skills/beta'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, 'the link on the way is followed on both, and beta is a link itself'

    def test_find_entry_kind_over_a_snapshot_with_a_file_behind_the_linked_scope_root_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude/skills/alpha/SKILL.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, 'the link on the way is followed on both, to a file'

    def test_find_entry_kind_over_a_snapshot_behind_a_dangling_link_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/dangling/inner'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, 'nothing is inside a dangling link on either view'

    def test_find_entry_kind_over_a_snapshot_behind_a_looping_link_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/loop/inner'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, 'nothing is inside a looping link on either view'

    def test_find_entry_kind_over_a_snapshot_with_a_missing_path_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/missing.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/missing.md has no kind on either view'

    def test_find_entry_kind_over_a_snapshot_with_a_linked_docs_agrees_with_disk(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'real-docs' / 'code').mkdir(parents=True)
        (tmp_path / 'docs').symlink_to('real-docs')
        disk = DiskFileSystem(tmp_path)
        virtual = VirtualFileSystem(take_snapshot(tmp_path, SNAPSHOT_SCOPE))
        path = 'docs'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, 'a linked scope root the scan does not follow is a link on both'

    # find_file: a skill file, one reached through a linked skill entry, and a directory.

    def test_find_file_over_a_snapshot_with_a_skill_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/alpha/SKILL.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_file, virtual.find_file, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file SKILL.md resolves to itself on both'

    def test_find_file_over_a_snapshot_through_a_skill_link_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/beta/SKILL.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_file, virtual.find_file, path)

        #: Then
        assert virtual_answer == disk_answer, 'the SKILL.md behind the link beta is the one in alpha on both'

    def test_find_file_over_a_snapshot_with_a_skill_directory_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/alpha'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_file, virtual.find_file, path)

        #: Then
        assert virtual_answer == disk_answer, 'the directory alpha is no file on either'

    # find_dir: every entry and listing, plus the chains that run through the recorded links. Three listings
    # are also directory entries, so their paths are checked twice, once as each.

    def test_find_dir_over_a_snapshot_with_the_skill_directory_entry_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/alpha'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the directory entry .agents/skills/alpha resolves to itself on both'

    def test_find_dir_over_a_snapshot_with_a_skill_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/alpha/SKILL.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file SKILL.md leads to no directory on either'

    def test_find_dir_over_a_snapshot_with_a_skill_link_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/beta'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the link beta leads to .agents/skills/alpha on both'

    def test_find_dir_over_a_snapshot_with_the_linked_scope_root_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude/skills'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the linked scope root .claude/skills leads to .agents/skills on both'

    def test_find_dir_over_a_snapshot_with_the_meta_directory_entry_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/__meta__'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the directory entry docs/__meta__ resolves to itself on both'

    def test_find_dir_over_a_snapshot_with_a_meta_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/__meta__/code.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file docs/__meta__/code.md leads to no directory on either'

    def test_find_dir_over_a_snapshot_with_an_absolute_link_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/absolute'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the absolute link docs/absolute leads to docs/code on both'

    def test_find_dir_over_a_snapshot_with_the_code_directory_entry_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the directory entry docs/code resolves to itself on both'

    def test_find_dir_over_a_snapshot_with_a_code_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/a.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file docs/code/a.md leads to no directory on either'

    def test_find_dir_over_a_snapshot_with_a_link_to_a_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/linked.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'linked.md leads to the file a.md, so to no directory on either'

    def test_find_dir_over_a_snapshot_with_a_fifo_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/pipe'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the fifo docs/code/pipe leads to no directory on either'

    def test_find_dir_over_a_snapshot_with_an_unentered_directory_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code/sub'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the unentered docs/code/sub resolves to itself on both'

    def test_find_dir_over_a_snapshot_with_a_relative_link_to_a_directory_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code-link'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the link docs/code-link leads to docs/code on both'

    def test_find_dir_over_a_snapshot_with_a_dangling_link_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/dangling'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the dangling link docs/dangling leads to no directory on either'

    def test_find_dir_over_a_snapshot_with_a_docs_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/glossary.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file docs/glossary.md leads to no directory on either'

    def test_find_dir_over_a_snapshot_with_a_non_utf8_file_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/latin.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the file docs/latin.md leads to no directory on either'

    def test_find_dir_over_a_snapshot_with_a_looping_link_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/loop'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the looping link docs/loop leads to no directory on either'

    def test_find_dir_over_a_snapshot_with_a_link_up_to_the_root_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/up'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the link docs/up leads to the root on both'

    def test_find_dir_over_a_snapshot_with_the_skills_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the listed .agents/skills resolves to itself on both'

    def test_find_dir_over_a_snapshot_with_the_skill_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.agents/skills/alpha'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the listed .agents/skills/alpha resolves to itself on both'

    def test_find_dir_over_a_snapshot_with_the_claude_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the listed .claude resolves to itself on both'

    def test_find_dir_over_a_snapshot_with_the_docs_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the listed docs resolves to itself on both'

    def test_find_dir_over_a_snapshot_with_the_meta_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/__meta__'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the listed docs/__meta__ resolves to itself on both'

    def test_find_dir_over_a_snapshot_with_the_code_listing_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the listed docs/code resolves to itself on both'

    def test_find_dir_over_a_snapshot_with_the_root_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the root resolves to itself on both'

    def test_find_dir_over_a_snapshot_with_a_directory_behind_the_linked_scope_root_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude/skills/alpha'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, '.claude/skills/alpha leads to .agents/skills/alpha on both'

    def test_find_dir_over_a_snapshot_with_a_link_behind_the_linked_scope_root_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = '.claude/skills/beta'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, '.claude/skills/beta follows two links to .agents/skills/alpha on both'

    def test_find_dir_over_a_snapshot_with_a_directory_behind_an_absolute_link_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/absolute/sub'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/absolute/sub leads to docs/code/sub on both'

    def test_find_dir_over_a_snapshot_with_a_directory_behind_a_relative_link_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/code-link/sub'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/code-link/sub leads to docs/code/sub on both'

    def test_find_dir_over_a_snapshot_with_listed_components_after_a_link_up_agrees_with_disk(
        self, parity_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/up/docs/code'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'docs/up/docs/code climbs to the root, then leads to docs/code on both'

    def test_find_dir_over_a_snapshot_with_a_missing_path_agrees_with_disk(self, parity_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(parity_tree)
        virtual = VirtualFileSystem(take_snapshot(parity_tree, SNAPSHOT_SCOPE))
        path = 'docs/missing'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the missing docs/missing leads to no directory on either'

    def test_find_dir_over_a_snapshot_with_an_absolute_link_under_an_aliased_root_agrees_with_disk(
        self, aliased_root_with_an_absolute_link: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(aliased_root_with_an_absolute_link)
        virtual = VirtualFileSystem(take_snapshot(aliased_root_with_an_absolute_link, SNAPSHOT_SCOPE))

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, 'docs/absolute')

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

    def test_find_dir_over_a_snapshot_with_an_unresolved_claude_skills_agrees_with_disk(
        self, unresolved_claude_skills_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(unresolved_claude_skills_tree)
        virtual = VirtualFileSystem(take_snapshot(unresolved_claude_skills_tree, SNAPSHOT_SCOPE))

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, '.claude/skills')

        #: Then
        assert virtual_answer == disk_answer, '.claude/skills leads to no directory over the snapshot either'


@pytest.mark.it
class TestVirtualFileSystemMatchesDiskThroughFollowedLinks:
    def test_find_dir_over_a_following_snapshot_with_a_skill_linked_out_of_the_scope_agrees_with_disk(
        self, linked_skills_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(linked_skills_tree)
        virtual = VirtualFileSystem(take_snapshot(linked_skills_tree, FOLLOWING_SCOPE))
        path = '.agents/skills/review'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'the linked skill leads to skills/review over the snapshot too'

    def test_find_dir_over_a_following_snapshot_with_a_skill_behind_two_links_agrees_with_disk(
        self, linked_skills_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(linked_skills_tree)
        virtual = VirtualFileSystem(take_snapshot(linked_skills_tree, FOLLOWING_SCOPE))
        path = '.claude/skills/review'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

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

    def test_find_dir_over_a_following_snapshot_with_a_chain_longer_than_the_system_follows_agrees_with_disk(
        self, tmp_path: Path, chain_of_41_links: str
    ) -> None:
        #: Given
        scope = (ScanRoot(RootRelativePath.parse(chain_of_41_links), depth=0, follow_links=True),)
        disk = DiskFileSystem(tmp_path)
        virtual = VirtualFileSystem(take_snapshot(tmp_path, scope))

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, chain_of_41_links)

        #: Then
        assert virtual_answer == disk_answer, 'a chain of 41 links leads to no directory on either view'

    def test_find_dir_over_a_following_snapshot_with_a_chain_as_long_as_the_system_follows_reaches_its_end(
        self, tmp_path: Path, chain_of_40_links: str
    ) -> None:
        #: Given
        scope = (ScanRoot(RootRelativePath.parse(chain_of_40_links), depth=0, follow_links=True),)
        disk = DiskFileSystem(tmp_path)
        virtual = VirtualFileSystem(take_snapshot(tmp_path, scope))
        real = RootRelativePath.parse('real')

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, chain_of_40_links)

        #: Then
        assert (disk_answer, virtual_answer) == (real, real), 'a chain of 40 links still leads to real on both views'

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


# The layout's shape of scope: docs/ one level deep with links recorded and not followed, and each skills
# directory with no depth limit through its links.
LAYOUT_SHAPED_SCOPE: Final[tuple[ScanRoot, ...]] = (
    ScanRoot(DOCS_DIR, depth=1),
    ScanRoot(RootRelativePath.parse('.agents/skills'), depth=None, follow_links=True),
    ScanRoot(RootRelativePath.parse('.claude/skills'), depth=None, follow_links=True),
)


@pytest.fixture(scope='function')
def scope_parity_tree(tmp_path: Path) -> Path:
    """A root with a link of every kind the scope must answer for, each leading to a directory that exists.

    Under `docs/`, `linked` leads out to `elsewhere/` and `alias` to its sibling `feat/`, and `feat/deep/` is
    beyond the depth. `.agents/skills/y` leads to `skills/y/`, which holds `sub/`, listed since the skills roots
    have no depth limit; `.agents/skills/x/lib` leads to `lib/` from inside a skill; `.claude/skills` leads to
    `.agents/skills/`; and `src/` is in no root.

    Args:
        tmp_path: Directory the tree is written into, as the repository root.
    """
    files = (
        'docs/feat/a.md',
        'docs/feat/deep/a.md',
        'elsewhere/a.md',
        'skills/y/SKILL.md',
        'skills/y/sub/a.md',
        '.agents/skills/x/SKILL.md',
        'lib/a.md',
        'src/tool.py',
    )
    for path in files:
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_bytes(b'')
    (tmp_path / 'docs' / 'linked').symlink_to('../elsewhere')
    (tmp_path / 'docs' / 'alias').symlink_to('feat')
    (tmp_path / '.agents' / 'skills' / 'y').symlink_to('../../skills/y')
    (tmp_path / '.agents' / 'skills' / 'x' / 'lib').symlink_to('../../../lib')
    (tmp_path / '.claude').mkdir()
    (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')
    return tmp_path


# The scope of the climbing-chain tree: `skills/` one level deep through its links, and `a/` one level deep.
CLIMBING_CHAIN_SCOPE: Final[tuple[ScanRoot, ...]] = (
    ScanRoot(RootRelativePath.parse('skills'), depth=1, follow_links=True),
    ScanRoot(RootRelativePath.parse('a'), depth=1),
)


@pytest.fixture(scope='function')
def climbing_chain_tree(tmp_path: Path) -> Path:
    """A root with link chains whose `..` climbs out of a directory stepped into by name, for `CLIMBING_CHAIN_SCOPE`.

    `skills/l` names `../a/tmp/../b`, which the disk follows to `a/b/`, a directory the root `a/` lists as well.
    `skills/m` names `../a/b` directly. `skills/far` names `../c/tmp/../d`, through `c/tmp/`, a directory no root
    lists. `skills/n` names `../a/missing/../b`, which the disk does not follow, since `a/missing` does not exist.
    `skills/out` names `../a/tmp/../../..`, which climbs above the root after stepping into `a/tmp/`.

    Args:
        tmp_path: Directory the tree is written into, as the repository root.
    """
    (tmp_path / 'a' / 'b').mkdir(parents=True)
    (tmp_path / 'a' / 'b' / 'SKILL.md').write_bytes(b'---\nname: b\n---\n')
    (tmp_path / 'a' / 'tmp').mkdir()
    (tmp_path / 'c' / 'd').mkdir(parents=True)
    (tmp_path / 'c' / 'd' / 'SKILL.md').write_bytes(b'---\nname: d\n---\n')
    (tmp_path / 'c' / 'tmp').mkdir()
    (tmp_path / 'skills').mkdir()
    (tmp_path / 'skills' / 'far').symlink_to('../c/tmp/../d')
    (tmp_path / 'skills' / 'l').symlink_to('../a/tmp/../b')
    (tmp_path / 'skills' / 'm').symlink_to('../a/b')
    (tmp_path / 'skills' / 'n').symlink_to('../a/missing/../b')
    (tmp_path / 'skills' / 'out').symlink_to('../a/tmp/../../..')
    return tmp_path


@pytest.mark.it
class TestVirtualFileSystemMatchesDiskThroughClimbingLinks:
    # A `..` after a directory stepped into by name is that directory's parent on disk, and over the snapshot too.

    def test_list_dir_through_a_climb_out_of_a_directory_stepped_into_agrees_with_disk(
        self, climbing_chain_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(climbing_chain_tree)
        virtual = VirtualFileSystem(take_snapshot(climbing_chain_tree, CLIMBING_CHAIN_SCOPE))
        path = 'skills/l'

        #: When
        disk_answer, virtual_answer = _answers(disk.list_dir, virtual.list_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'both views list a/b through a/tmp/..'

    def test_find_entry_kind_through_a_climb_out_of_a_directory_stepped_into_agrees_with_disk(
        self, climbing_chain_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(climbing_chain_tree)
        virtual = VirtualFileSystem(take_snapshot(climbing_chain_tree, CLIMBING_CHAIN_SCOPE))
        path = 'skills/l/SKILL.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_entry_kind, virtual.find_entry_kind, path)

        #: Then
        assert virtual_answer == disk_answer, 'both views find a/b/SKILL.md a file'

    def test_read_text_through_a_climb_out_of_an_unlisted_directory_agrees_with_disk(
        self, climbing_chain_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(climbing_chain_tree)
        virtual = VirtualFileSystem(take_snapshot(climbing_chain_tree, CLIMBING_CHAIN_SCOPE))
        path = 'skills/far/SKILL.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.read_text, virtual.read_text, path)

        #: Then
        assert virtual_answer == disk_answer, 'the climbed directories show c/tmp, so both views read c/d/SKILL.md'

    def test_find_file_through_a_climb_out_of_an_unlisted_directory_agrees_with_disk(
        self, climbing_chain_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(climbing_chain_tree)
        virtual = VirtualFileSystem(take_snapshot(climbing_chain_tree, CLIMBING_CHAIN_SCOPE))
        path = 'skills/far/SKILL.md'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_file, virtual.find_file, path)

        #: Then
        assert virtual_answer == disk_answer, 'both views resolve skills/far/SKILL.md to c/d/SKILL.md'

    def test_find_dir_through_a_climb_out_of_a_missing_directory_agrees_with_disk(
        self, climbing_chain_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(climbing_chain_tree)
        virtual = VirtualFileSystem(take_snapshot(climbing_chain_tree, CLIMBING_CHAIN_SCOPE))
        path = 'skills/n'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_dir, virtual.find_dir, path)

        #: Then
        assert virtual_answer == disk_answer, 'a/missing does not exist, so neither view climbs out of it'

    def test_find_root_exit_through_a_climb_above_the_root_out_of_a_directory_stepped_into_agrees_with_disk(
        self, climbing_chain_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(climbing_chain_tree)
        virtual = VirtualFileSystem(take_snapshot(climbing_chain_tree, CLIMBING_CHAIN_SCOPE))
        path = 'skills/out'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_root_exit, virtual.find_root_exit, path)

        #: Then
        assert (virtual_answer, disk_answer) == (
            RootExit(RootRelativePath.parse('skills/out'), PurePosixPath('../a/tmp/../../..')),
            RootExit(RootRelativePath.parse('skills/out'), PurePosixPath('../a/tmp/../../..')),
        ), 'both walks climb above the root at skills/out, after stepping into a/tmp'


# A plain root like the layout's `docs/`: one level deep, its links recorded and not followed.
PLAIN_DOCS_SCOPE: Final[tuple[ScanRoot, ...]] = (ScanRoot(DOCS_DIR, depth=1),)


@pytest.fixture(scope='function')
def plain_climbing_tree(tmp_path: Path) -> Path:
    """A root whose `docs/` holds links climbing out of directories they step into, for `PLAIN_DOCS_SCOPE`.

    `docs/linked` names `code/../feat`, and leads to `docs/feat/`, which the root lists. `docs/out` names
    `../src/../../..`, which steps into `src/`, outside the scope, and climbs above the root.

    Args:
        tmp_path: Directory the tree is written into, as the repository root.
    """
    (tmp_path / 'docs' / 'code').mkdir(parents=True)
    (tmp_path / 'docs' / 'feat').mkdir()
    (tmp_path / 'docs' / 'feat' / 'a.md').write_bytes(b'# A\n')
    (tmp_path / 'src').mkdir()
    (tmp_path / 'docs' / 'linked').symlink_to('code/../feat')
    (tmp_path / 'docs' / 'out').symlink_to('../src/../../..')
    return tmp_path


@pytest.mark.it
class TestPlainRootWalksItsLinksForTheRecord:
    # A root that does not follow links still walks each link it records, for the record alone, so the views and
    # the scope query take the same steps through it as the disk.

    def test_take_snapshot_with_a_plain_root_records_the_climbs_on_its_links_and_lists_nothing_through_them(
        self, plain_climbing_tree: Path
    ) -> None:
        #: When
        snapshot = take_snapshot(plain_climbing_tree, PLAIN_DOCS_SCOPE)

        #: Then
        assert snapshot == _snapshot(
            {
                'docs': DirectoryRecord(listed=True, climbed=True),
                'docs/code': DirectoryRecord(listed=True, climbed=True),
                'docs/feat': DirectoryRecord(listed=True),
                'docs/feat/a.md': FileRecord(b'# A\n'),
                'docs/linked': SymlinkRecord(PurePosixPath('code/../feat')),
                'docs/out': SymlinkRecord(PurePosixPath('../src/../../..')),
                'src': DirectoryRecord(climbed=True),
            },
            scope=PLAIN_DOCS_SCOPE,
        ), 'the climbs on both chains are recorded, src/ included, and nothing is listed or read through a link'

    def test_find_root_exit_through_a_link_of_a_plain_root_climbing_above_the_root_agrees_with_disk(
        self, plain_climbing_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(plain_climbing_tree)
        virtual = VirtualFileSystem(take_snapshot(plain_climbing_tree, PLAIN_DOCS_SCOPE))
        path = 'docs/out'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_root_exit, virtual.find_root_exit, path)

        #: Then
        assert (virtual_answer, disk_answer) == (
            RootExit(RootRelativePath.parse('docs/out'), PurePosixPath('../src/../../..')),
            RootExit(RootRelativePath.parse('docs/out'), PurePosixPath('../src/../../..')),
        ), 'the scan recorded the climb out of src/, so both walks leave the root at docs/out'

    def test_is_in_scope_through_a_link_of_a_plain_root_climbing_out_of_a_directory_agrees_with_the_scan(
        self, plain_climbing_tree: Path
    ) -> None:
        #: Given
        snapshot = take_snapshot(plain_climbing_tree, PLAIN_DOCS_SCOPE)
        path = RootRelativePath.parse('docs/linked/a.md')
        virtual = VirtualFileSystem(snapshot)
        reached = virtual.find_file(path)

        #: When
        declared = ScopeIndex(snapshot).is_in_scope(path)

        #: Then
        assert (declared, reached) == (True, RootRelativePath.parse('docs/feat/a.md')), (
            'docs/linked leads to docs/feat, which the scan lists, so the path is in scope and reached'
        )


def _is_listed(snapshot: Snapshot, directory: RootRelativePath) -> bool:
    """Whether `snapshot` holds a listing of the directory `directory` leads to, its recorded links followed.

    What the snapshot observed, against which the declared scope is held: for a directory that exists, the
    scope covers its entries exactly when the scan listed it.

    Args:
        snapshot: The scan whose listings are looked in.
        directory: The root-relative directory to look up, spelled through any link.
    """
    resolved_directory = VirtualFileSystem(snapshot).find_dir(directory)
    return resolved_directory in _listed_directories(snapshot)


@pytest.mark.it
class TestIsInScopeMatchesSnapshot:
    # For a directory that exists, the declared answer and the scan's listing must agree: in the scope exactly
    # where the snapshot holds every entry. Each test asks about an absent file, so presence plays no part.

    def test_is_in_scope_with_the_docs_directory_agrees_with_the_snapshot(self, scope_parity_tree: Path) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        directory = RootRelativePath.parse('docs')
        listed = _is_listed(snapshot, directory)
        index = ScopeIndex(snapshot)

        #: When
        declared = index.is_in_scope(directory / 'absent.md')

        #: Then
        assert (declared, listed) == (True, True), 'docs/ is a root: declared in the scope, and listed'

    def test_is_in_scope_with_a_corpus_directory_agrees_with_the_snapshot(self, scope_parity_tree: Path) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        directory = RootRelativePath.parse('docs/feat')
        listed = _is_listed(snapshot, directory)
        index = ScopeIndex(snapshot)

        #: When
        declared = index.is_in_scope(directory / 'absent.md')

        #: Then
        assert (declared, listed) == (True, True), (
            'docs/feat is one level under docs/: declared in the scope, and listed'
        )

    def test_is_in_scope_beyond_the_docs_depth_agrees_with_the_snapshot(self, scope_parity_tree: Path) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        directory = RootRelativePath.parse('docs/feat/deep')
        listed = _is_listed(snapshot, directory)
        index = ScopeIndex(snapshot)

        #: When
        declared = index.is_in_scope(directory / 'absent.md')

        #: Then
        assert (declared, listed) == (False, False), (
            'docs/feat/deep is two levels under docs/: outside the scope, and unlisted'
        )

    def test_is_in_scope_through_an_unfollowed_docs_link_out_agrees_with_the_snapshot(
        self, scope_parity_tree: Path
    ) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        directory = RootRelativePath.parse('docs/linked')
        listed = _is_listed(snapshot, directory)
        index = ScopeIndex(snapshot)

        #: When
        declared = index.is_in_scope(directory / 'absent.md')

        #: Then
        assert (declared, listed) == (False, False), (
            'docs/ does not follow its link to elsewhere/, which no root covers'
        )

    def test_is_in_scope_through_an_unfollowed_docs_link_to_a_sibling_agrees_with_the_snapshot(
        self, scope_parity_tree: Path
    ) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        directory = RootRelativePath.parse('docs/alias')
        listed = _is_listed(snapshot, directory)
        index = ScopeIndex(snapshot)

        #: When
        declared = index.is_in_scope(directory / 'absent.md')

        #: Then
        assert (declared, listed) == (True, True), (
            'the link is not followed, but docs/feat, where it leads, is listed anyway'
        )

    def test_is_in_scope_through_a_followed_skill_link_agrees_with_the_snapshot(self, scope_parity_tree: Path) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        directory = RootRelativePath.parse('.agents/skills/y')
        listed = _is_listed(snapshot, directory)
        index = ScopeIndex(snapshot)

        #: When
        declared = index.is_in_scope(directory / 'absent.md')

        #: Then
        assert (declared, listed) == (True, True), 'the skills root follows .agents/skills/y to skills/y and lists it'

    def test_is_in_scope_at_the_resolved_path_of_a_followed_skill_link_agrees_with_the_snapshot(
        self, scope_parity_tree: Path
    ) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        directory = RootRelativePath.parse('skills/y')
        listed = _is_listed(snapshot, directory)
        index = ScopeIndex(snapshot)

        #: When
        declared = index.is_in_scope(directory / 'absent.md')

        #: Then
        assert (declared, listed) == (True, True), (
            'skills/y is listed through the link, and is in the scope by its own spelling'
        )

    def test_is_in_scope_below_a_followed_skill_link_agrees_with_the_snapshot(self, scope_parity_tree: Path) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        directory = RootRelativePath.parse('skills/y/sub')
        listed = _is_listed(snapshot, directory)
        index = ScopeIndex(snapshot)

        #: When
        declared = index.is_in_scope(directory / 'absent.md')

        #: Then
        assert (declared, listed) == (True, True), (
            'the skills root has no depth limit, so skills/y is listed and so is its sub/'
        )

    def test_is_in_scope_through_a_linked_skills_directory_agrees_with_the_snapshot(
        self, scope_parity_tree: Path
    ) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        directory = RootRelativePath.parse('.claude/skills/x')
        listed = _is_listed(snapshot, directory)
        index = ScopeIndex(snapshot)

        #: When
        declared = index.is_in_scope(directory / 'absent.md')

        #: Then
        assert (declared, listed) == (True, True), '.claude/skills leads to .agents/skills, whose skill x is listed'

    def test_is_in_scope_through_a_link_inside_a_skill_agrees_with_the_snapshot(self, scope_parity_tree: Path) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        directory = RootRelativePath.parse('.agents/skills/x/lib')
        listed = _is_listed(snapshot, directory)
        index = ScopeIndex(snapshot)

        #: When
        declared = index.is_in_scope(directory / 'absent.md')

        #: Then
        assert (declared, listed) == (True, True), (
            'a link inside a skill is followed, so lib/ is listed through .agents/skills/x/lib'
        )

    def test_is_in_scope_outside_every_root_agrees_with_the_snapshot(self, scope_parity_tree: Path) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        directory = RootRelativePath.parse('src')
        listed = _is_listed(snapshot, directory)
        index = ScopeIndex(snapshot)

        #: When
        declared = index.is_in_scope(directory / 'absent.md')

        #: Then
        assert (declared, listed) == (False, False), 'src/ is in no root: outside the scope, and unlisted'


@pytest.mark.it
class TestFindFileMatchesScan:
    # Whatever `find_file` reaches through a link must be something the scan followed the link to: the view
    # reaches an existing file exactly where the scope query, which retraces the scan, says the scan lists it.

    def test_find_file_through_a_followed_skill_link_agrees_with_the_scope(self, scope_parity_tree: Path) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        path = RootRelativePath.parse('.agents/skills/y/SKILL.md')
        declared = ScopeIndex(snapshot).is_in_scope(path)
        virtual = VirtualFileSystem(snapshot)

        #: When
        reached = virtual.find_file(path)

        #: Then
        assert (reached is not None, declared) == (True, True), (
            'the skills root follows .agents/skills/y to skills/y and reads its SKILL.md'
        )

    def test_find_file_through_a_linked_skills_directory_agrees_with_the_scope(self, scope_parity_tree: Path) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        path = RootRelativePath.parse('.claude/skills/x/SKILL.md')
        declared = ScopeIndex(snapshot).is_in_scope(path)
        virtual = VirtualFileSystem(snapshot)

        #: When
        reached = virtual.find_file(path)

        #: Then
        assert (reached is not None, declared) == (True, True), (
            '.claude/skills leads to .agents/skills, whose skill x is listed'
        )

    def test_find_file_through_an_unfollowed_docs_link_to_a_sibling_agrees_with_the_scope(
        self, scope_parity_tree: Path
    ) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        path = RootRelativePath.parse('docs/alias/a.md')
        declared = ScopeIndex(snapshot).is_in_scope(path)
        virtual = VirtualFileSystem(snapshot)

        #: When
        reached = virtual.find_file(path)

        #: Then
        assert (reached is not None, declared) == (True, True), (
            'the link is not followed, but docs/feat, where it leads, is listed anyway'
        )

    def test_find_file_through_an_unfollowed_docs_link_out_agrees_with_the_scope(self, scope_parity_tree: Path) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        path = RootRelativePath.parse('docs/linked/a.md')
        declared = ScopeIndex(snapshot).is_in_scope(path)
        virtual = VirtualFileSystem(snapshot)

        #: When
        reached = virtual.find_file(path)

        #: Then
        assert (reached is not None, declared) == (False, False), (
            'docs/ does not follow its link to elsewhere/, which no root covers'
        )

    def test_find_file_through_a_link_inside_a_skill_agrees_with_the_scope(self, scope_parity_tree: Path) -> None:
        #: Given
        snapshot = take_snapshot(scope_parity_tree, LAYOUT_SHAPED_SCOPE)
        path = RootRelativePath.parse('.agents/skills/x/lib/a.md')
        declared = ScopeIndex(snapshot).is_in_scope(path)
        virtual = VirtualFileSystem(snapshot)

        #: When
        reached = virtual.find_file(path)

        #: Then
        assert (reached is not None, declared) == (True, True), (
            'a link inside a skill is followed, so lib/a.md is read through .agents/skills/x/lib'
        )

    def test_find_file_through_a_link_climbing_out_of_its_own_directory_agrees_with_the_scope(
        self, climbing_chain_tree: Path
    ) -> None:
        #: Given
        snapshot = take_snapshot(climbing_chain_tree, CLIMBING_CHAIN_SCOPE)
        path = RootRelativePath.parse('skills/m/SKILL.md')
        declared = ScopeIndex(snapshot).is_in_scope(path)
        virtual = VirtualFileSystem(snapshot)

        #: When
        reached = virtual.find_file(path)

        #: Then
        assert (reached is not None, declared) == (True, True), (
            'the target ../a/b climbs only out of skills/, where the link sits, so the scan follows it'
        )

    def test_find_file_through_a_chain_climbing_out_of_a_directory_stepped_into_agrees_with_the_scope(
        self, climbing_chain_tree: Path
    ) -> None:
        #: Given
        snapshot = take_snapshot(climbing_chain_tree, CLIMBING_CHAIN_SCOPE)
        path = RootRelativePath.parse('skills/l/SKILL.md')
        declared = ScopeIndex(snapshot).is_in_scope(path)
        virtual = VirtualFileSystem(snapshot)

        #: When
        reached = virtual.find_file(path)

        #: Then
        assert (reached, declared) == (RootRelativePath.parse('a/b/SKILL.md'), True), (
            'the `..` after a/tmp is a, so skills/l leads to a/b and its SKILL.md is read through it'
        )

    def test_find_file_through_a_chain_climbing_out_of_an_unlisted_directory_agrees_with_the_scope(
        self, climbing_chain_tree: Path
    ) -> None:
        #: Given
        snapshot = take_snapshot(climbing_chain_tree, CLIMBING_CHAIN_SCOPE)
        path = RootRelativePath.parse('skills/far/SKILL.md')
        declared = ScopeIndex(snapshot).is_in_scope(path)
        virtual = VirtualFileSystem(snapshot)

        #: When
        reached = virtual.find_file(path)

        #: Then
        assert (reached, declared) == (RootRelativePath.parse('c/d/SKILL.md'), True), (
            'no root lists c/tmp, but the scan records climbing out of it, so both walks reach c/d'
        )

    def test_find_file_through_a_chain_climbing_out_of_a_missing_directory_agrees_with_the_scope(
        self, climbing_chain_tree: Path
    ) -> None:
        #: Given
        snapshot = take_snapshot(climbing_chain_tree, CLIMBING_CHAIN_SCOPE)
        path = RootRelativePath.parse('skills/n/SKILL.md')
        declared = ScopeIndex(snapshot).is_in_scope(path)
        virtual = VirtualFileSystem(snapshot)
        target_listed = _is_listed(snapshot, RootRelativePath.parse('a/b'))

        #: When
        reached = virtual.find_file(path)

        #: Then
        assert (reached, declared, target_listed) == (None, False, True), (
            'a/missing does not exist, so skills/n leads nowhere, though a/ lists the a/b its `..` would reach'
        )


@pytest.fixture(scope='function')
def leaving_tree(tmp_path: Path) -> Path:
    """A repository at `tmp_path/repository` whose skills layout holds links leaving it, beside `tmp_path/elsewhere`.

    Under `.agents/skills`: `alpha` is a skill, `beta -> alpha` stays inside, `dangling -> missing` dangles inside,
    `out` links to `elsewhere` by its absolute path, `up -> ../../../elsewhere` climbs above the root, and
    `via -> ../../hop/x` leaves through `hop`, a link at the root to `elsewhere`. `.claude/skills` links to
    `elsewhere` by its absolute path.

    Args:
        tmp_path: Directory the repository and the directory outside it are written into.

    Returns:
        The repository root.
    """
    root = tmp_path / 'repository'
    elsewhere = tmp_path / 'elsewhere'
    (elsewhere / 'x').mkdir(parents=True)
    (root / '.agents' / 'skills' / 'alpha').mkdir(parents=True)
    (root / '.agents' / 'skills' / 'alpha' / 'SKILL.md').write_text('---\nname: alpha\n---\n', encoding='utf-8')
    (root / '.agents' / 'skills' / 'beta').symlink_to('alpha')
    (root / '.agents' / 'skills' / 'dangling').symlink_to('missing')
    (root / '.agents' / 'skills' / 'out').symlink_to(elsewhere)
    (root / '.agents' / 'skills' / 'up').symlink_to('../../../elsewhere')
    (root / '.agents' / 'skills' / 'via').symlink_to('../../hop/x')
    (root / 'hop').symlink_to(elsewhere)
    (root / '.claude').mkdir()
    (root / '.claude' / 'skills').symlink_to(elsewhere)
    return root


@pytest.mark.it
class TestDiskFileSystemFindRootExit:
    def test_find_root_exit_with_an_absolute_link_outside_the_root_returns_it_and_its_target(
        self, leaving_tree: Path
    ) -> None:
        #: Given
        filesystem = DiskFileSystem(leaving_tree)
        path = RootRelativePath.parse('.agents/skills/out')

        #: When
        leaves_at = filesystem.find_root_exit(path)

        #: Then
        assert leaves_at == RootExit(path, PurePosixPath(leaving_tree.parent / 'elsewhere')), (
            'the link leaves the root, with its target as read'
        )

    def test_find_root_exit_with_a_link_climbing_above_the_root_returns_it_and_its_target(
        self, leaving_tree: Path
    ) -> None:
        #: Given
        filesystem = DiskFileSystem(leaving_tree)
        path = RootRelativePath.parse('.agents/skills/up')

        #: When
        leaves_at = filesystem.find_root_exit(path)

        #: Then
        assert leaves_at == RootExit(path, PurePosixPath('../../../elsewhere')), 'the third `..` climbs above the root'

    def test_find_root_exit_with_a_chain_leaving_through_another_link_returns_that_link(
        self, leaving_tree: Path
    ) -> None:
        #: Given
        filesystem = DiskFileSystem(leaving_tree)
        path = RootRelativePath.parse('.agents/skills/via')

        #: When
        leaves_at = filesystem.find_root_exit(path)

        #: Then
        assert leaves_at == RootExit(RootRelativePath.parse('hop'), PurePosixPath(leaving_tree.parent / 'elsewhere')), (
            'the chain leaves the root at hop, not at the link it started from'
        )

    def test_find_root_exit_with_a_link_inside_the_root_returns_none(self, leaving_tree: Path) -> None:
        #: Given
        filesystem = DiskFileSystem(leaving_tree)
        path = RootRelativePath.parse('.agents/skills/beta')

        #: When
        leaves_at = filesystem.find_root_exit(path)

        #: Then
        assert leaves_at is None, 'a link to a sibling directory stays under the root'

    def test_find_root_exit_with_a_link_dangling_inside_the_root_returns_none(self, leaving_tree: Path) -> None:
        #: Given
        filesystem = DiskFileSystem(leaving_tree)
        path = RootRelativePath.parse('.agents/skills/dangling')

        #: When
        leaves_at = filesystem.find_root_exit(path)

        #: Then
        assert leaves_at is None, 'a link dangling inside the root does not leave it'


@pytest.mark.it
class TestFindRootExitMatchesDisk:
    def test_find_root_exit_over_a_snapshot_with_an_absolute_link_agrees_with_disk(self, leaving_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(leaving_tree)
        virtual = VirtualFileSystem(take_snapshot(leaving_tree, FOLLOWING_SCOPE))
        path = '.agents/skills/out'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_root_exit, virtual.find_root_exit, path)

        #: Then
        assert virtual_answer == disk_answer, 'the snapshot records the absolute target the disk reads'

    def test_find_root_exit_over_a_snapshot_with_a_climbing_link_agrees_with_disk(self, leaving_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(leaving_tree)
        virtual = VirtualFileSystem(take_snapshot(leaving_tree, FOLLOWING_SCOPE))
        path = '.agents/skills/up'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_root_exit, virtual.find_root_exit, path)

        #: Then
        assert virtual_answer == disk_answer, 'both walks climb above the root at the same link'

    def test_find_root_exit_over_a_snapshot_with_a_chain_leaving_through_another_link_agrees_with_disk(
        self, leaving_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(leaving_tree)
        virtual = VirtualFileSystem(take_snapshot(leaving_tree, FOLLOWING_SCOPE))
        path = '.agents/skills/via'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_root_exit, virtual.find_root_exit, path)

        #: Then
        assert virtual_answer == disk_answer, 'the scan records hop on the chain it followed, so both leave there'

    def test_find_root_exit_over_a_snapshot_with_a_linked_skills_directory_agrees_with_disk(
        self, leaving_tree: Path
    ) -> None:
        #: Given
        disk = DiskFileSystem(leaving_tree)
        virtual = VirtualFileSystem(take_snapshot(leaving_tree, FOLLOWING_SCOPE))
        path = '.claude/skills'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_root_exit, virtual.find_root_exit, path)

        #: Then
        assert virtual_answer == disk_answer, 'the scan records the link on the way to a scope root'

    def test_find_root_exit_over_a_snapshot_with_a_dangling_link_agrees_with_disk(self, leaving_tree: Path) -> None:
        #: Given
        disk = DiskFileSystem(leaving_tree)
        virtual = VirtualFileSystem(take_snapshot(leaving_tree, FOLLOWING_SCOPE))
        path = '.agents/skills/dangling'

        #: When
        disk_answer, virtual_answer = _answers(disk.find_root_exit, virtual.find_root_exit, path)

        #: Then
        assert virtual_answer == disk_answer, 'neither view says a link dangling inside the root leaves it'
