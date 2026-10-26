"""Selecting the whole workspace against a database over a snapshot of a real tree.

Each case writes a tree under `tmp_path`, takes the snapshot the command line takes, and asserts the whole tuple
`select_workspace` returns: which subjects it holds, and the order of the paths each is reported at.
"""

from pathlib import Path, PurePosixPath
from typing import Final

import pytest

from lorecraft.cli.subjects import select_workspace
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.database import Database
from lorecraft.project.item import ItemRef
from lorecraft.project.layout import SNAPSHOT_SCOPE, SPECS_DIR
from lorecraft.project.skill import (
    OutsideSymlink,
    SkillRef,
    SkillRelativePath,
    SkillResourceRef,
)
from lorecraft.project.workspace.builtin import AGENT_SKILLS_SPEC_LAYER as SKILLS_LAYER
from lorecraft.vfs import ResolvedPath, RootExit, take_snapshot
from lorecraft.vfs.view import AbsoluteSymlinkTarget, RelativeSymlinkTarget, SymlinkTarget

REVIEW: Final[SkillRef] = SkillRef(
    ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review')
)


def _target(raw: str | Path | PurePosixPath) -> SymlinkTarget:
    """Wrap a target written as it would be by `os.readlink`."""
    target = PurePosixPath(raw)
    if target.is_absolute():
        return AbsoluteSymlinkTarget(target)
    return RelativeSymlinkTarget(target)


def _write(root: Path, relative: str, text: str = '') -> Path:
    """Write one file under the root, creating its parents, and return its path.

    Args:
        root: Directory the file is written under, as the repository root.
        relative: Path of the file below `root`, with `/` separators.
        text: Content of the file, written as UTF-8. Empty by default.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def _specification(name: str) -> ItemRef:
    """The specification `docs/__meta__/<name>.md`.

    Args:
        name: The specification's name without its `.md` suffix.
    """
    return ItemRef(SPECS_DIR / PathComponent.parse(f'{name}.md'))


def _document(corpus: str, filename: str) -> ItemRef:
    """The document `docs/<corpus>/<filename>.md`.

    Args:
        corpus: The corpus directory's name.
        filename: The file's name without its `.md` suffix.
    """
    return ItemRef(RootRelativePath.parse(f'docs/{corpus}/{filename}.md'))


def _skill(ref: SkillRef) -> ItemRef:
    """The skill's entrypoint, reported at the path an agent reaches.

    Args:
        ref: Where the skill's directory sits.
    """
    return ItemRef(ref.path)


def _resource(skill: SkillRef, path: str) -> ItemRef:
    """The resource at `path` inside `skill`, identified by its report path.

    Args:
        skill: The skill the resource belongs to.
        path: The resource, spelled from the skill's directory.
    """
    ref = SkillResourceRef(skill, SkillRelativePath.parse(path))
    return ItemRef(ref.path)


def _outside(path: str, target: Path) -> OutsideSymlink:
    """The symlink at `path` whose own target, `target`, leaves the repository.

    Args:
        path: Where an agent reaches the symlink, root-relative; the link the chain leaves through is this one.
        target: The link's target, as written.
    """
    entry = RootRelativePath.parse(path)
    return OutsideSymlink(entry, leaves_at=RootExit(ResolvedPath(entry), _target(target)))


@pytest.mark.it
class TestSelectWorkspace:
    def test_select_workspace_with_documents_and_a_skill_selects_each_sorted_by_report_path(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.md')
        _write(tmp_path, 'docs/__meta__/arch.md')
        _write(tmp_path, 'docs/code/typing.md')
        _write(tmp_path, 'docs/code/logging.md')
        _write(tmp_path, 'docs/arch/adr-001.md')
        _write(tmp_path, '.agents/skills/review/SKILL.md')
        _write(tmp_path, '.agents/skills/review/references/guide.md')
        _write(tmp_path, '.agents/skills/review/LINT.md')
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))

        #: When
        subjects = select_workspace(database)

        #: Then
        assert subjects == (
            _resource(REVIEW, 'LINT.md'),
            _skill(REVIEW),
            _resource(REVIEW, 'references/guide.md'),
            _specification('arch'),
            _specification('code'),
            _document('arch', 'adr-001'),
            _document('code', 'logging'),
            _document('code', 'typing'),
        ), 'every document, specification, skill and resource is selected once, by its report path by code point'

    def test_select_workspace_with_symlinks_leading_outside_selects_each_at_its_place(self, tmp_path: Path) -> None:
        #: Given
        root = tmp_path / 'repository'
        elsewhere = tmp_path / 'elsewhere'
        _write(elsewhere, 'x/SKILL.md')
        _write(elsewhere, 'shared/notes.md')
        _write(root, '.agents/skills/review/SKILL.md')
        (root / '.agents' / 'skills' / 'outside').symlink_to(elsewhere / 'x')
        (root / '.agents' / 'skills' / 'review' / 'shared').symlink_to(elsewhere / 'shared')
        database = Database.from_snapshot(take_snapshot(root, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))

        #: When
        subjects = select_workspace(database)

        #: Then
        assert subjects == (
            _outside('.agents/skills/outside', elsewhere / 'x'),
            _skill(REVIEW),
            _outside('.agents/skills/review/shared', elsewhere / 'shared'),
        ), "the model's symlink leading outside and the one inside a skill are each selected where an agent meets it"

    def test_select_workspace_with_a_skills_directory_two_agents_read_selects_each_skill_once(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))

        #: When
        subjects = select_workspace(database)

        #: Then
        assert subjects == (_skill(REVIEW),), 'a skill two agents reach is one subject'

    def test_select_workspace_with_an_empty_root_selects_nothing(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))

        #: When
        subjects = select_workspace(database)

        #: Then
        assert subjects == (), 'a root holding no document and no skill has no subject'
