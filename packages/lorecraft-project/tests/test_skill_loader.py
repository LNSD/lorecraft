"""Skill discovery over survey-shaped skills trees.

Each tree mirrors the skills layout of one real target repository (amp, ampup and this one) or one shape the
discovery must tolerate, with every SKILL.md left empty: discovery never reads one, so only names, kinds and
link targets matter. The skill repository is wired to a real ``DiskFileSystem`` over ``tmp_path``, and links are
written relative, the way the target repositories write them. The snapshot cases hold discovery over a
``VirtualFileSystem`` to the disk result for the same tree.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest

from lorecraft_project.layout import SNAPSHOT_SCOPE
from lorecraft_project.skill import AgentName, Sighting, Skill, SkillName
from lorecraft_project.skill.repo import ListSkillEntriesError, Repository
from lorecraft_project.workspace.model import AgentSkillsDir, SkillSet
from lorecraft_project.workspace.skill_loader import load_skills
from lorecraft_vfs import DiskFileSystem, RootRelativePath, VirtualFileSystem, take_snapshot

CANONICAL: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills')
CLAUDE_SKILLS: Final[RootRelativePath] = RootRelativePath.parse('.claude/skills')

CODEX: Final[AgentName] = AgentName('codex')
ANTIGRAVITY: Final[AgentName] = AgentName('antigravity')
OPENCODE: Final[AgentName] = AgentName('opencode')
CLAUDE_CODE: Final[AgentName] = AgentName('claude-code')
UNIVERSAL_AGENTS: Final[tuple[AgentName, ...]] = (CODEX, ANTIGRAVITY, OPENCODE)
ALL_AGENTS: Final[tuple[AgentName, ...]] = (CODEX, ANTIGRAVITY, OPENCODE, CLAUDE_CODE)

# The universal agents read the canonical directory itself, so each is present through it.
UNIVERSAL_AGENT_DIRS: Final[tuple[AgentSkillsDir, ...]] = (
    AgentSkillsDir(CODEX, CANONICAL, CANONICAL),
    AgentSkillsDir(ANTIGRAVITY, CANONICAL, CANONICAL),
    AgentSkillsDir(OPENCODE, CANONICAL, CANONICAL),
)

# The fourteen skills this repository carries under .agents/skills/.
LORECRAFT_SKILLS: Final[tuple[str, ...]] = (
    'code-check',
    'code-format',
    'code-release',
    'code-review',
    'code-rules',
    'code-rules-check',
    'code-test',
    'commit',
    'docs-rules',
    'docs-rules-check',
    'feat-discovery',
    'feat-status',
    'feat-validate',
    'skills-check',
)


@pytest.fixture(scope='function')
def skills(tmp_path: Path) -> Repository:
    """A skill repository over the temporary root; no skills directory exists until a test creates it."""
    return Repository(DiskFileSystem(tmp_path))


@pytest.fixture(scope='function')
def locked_canonical(tmp_path: Path) -> Iterator[Path]:
    """A ``.agents/skills/`` holding one skill, whose permissions refuse listing; restored for cleanup."""
    _canonical_skills(tmp_path, ('deploy',))
    directory = tmp_path / '.agents' / 'skills'
    directory.chmod(0o000)
    yield directory
    directory.chmod(0o700)


def _write(root: Path, relative: str, text: str = '') -> None:
    """Write one file under the root, creating its parents."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _link(root: Path, relative: str, target: str) -> None:
    """Create a symlink at ``relative`` under the root, pointing at ``target`` as written."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(target)


def _canonical_skills(root: Path, names: tuple[str, ...]) -> None:
    """One ``.agents/skills/<name>/SKILL.md`` per name."""
    for name in names:
        _write(root, f'.agents/skills/{name}/SKILL.md')


def _amp_tree(root: Path) -> None:
    """amp: two canonical skills, a README beside them, and ``.claude/skills`` linked to the canonical directory."""
    _canonical_skills(root, ('deploy', 'review'))
    _write(root, '.agents/skills/deploy/scripts/run.py')
    _write(root, '.agents/skills/README.md')
    _link(root, '.claude/skills', '../.agents/skills')


def _ampup_tree(root: Path) -> None:
    """ampup: the amp skills, with the whole ``.claude`` directory linked to ``.agents``."""
    _canonical_skills(root, ('deploy', 'review'))
    _write(root, '.agents/skills/deploy/scripts/run.py')
    _write(root, '.agents/skills/README.md')
    _link(root, '.claude', '.agents')


def _lorecraft_tree(root: Path) -> None:
    """lorecraft: fourteen canonical skills, nested files, and a ``.claude/skills`` link with a trailing slash."""
    _canonical_skills(root, LORECRAFT_SKILLS)
    _write(root, '.agents/skills/commit/references/x.md')
    _write(root, '.agents/skills/feat-status/report.py')
    _link(root, '.claude/skills', '../.agents/skills/')


def _per_skill_link_tree(root: Path) -> None:
    """A real ``.claude/skills/`` linking one canonical skill; the other canonical skill is not linked there."""
    _canonical_skills(root, ('deploy', 'review'))
    _link(root, '.claude/skills/deploy', '../../.agents/skills/deploy')


def _copy_tree(root: Path) -> None:
    """A real ``.claude/skills/deploy/`` holding its own SKILL.md beside the canonical one."""
    _canonical_skills(root, ('deploy', 'review'))
    _write(root, '.claude/skills/deploy/SKILL.md')


def _claude_only_tree(root: Path) -> None:
    """No ``.agents/`` at all; one skill under a real ``.claude/skills/``."""
    _write(root, '.claude/skills/notes/SKILL.md')


def _canonical_skill(name: str, agents: tuple[AgentName, ...]) -> Skill:
    """A skill seen once, under the canonical directory, by the given agents."""
    path = CANONICAL / name
    return Skill(SkillName.parse(name), path, agents, (Sighting(path, path, agents),))


def _names(skill_set: SkillSet) -> tuple[str, ...]:
    """The skill names in stored order, as strings."""
    return tuple(str(skill.name) for skill in skill_set.skills)


@pytest.mark.it
class TestLoadSkills:
    def test_load_skills_with_the_amp_tree_returns_both_skills_seen_by_all_four_agents(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _amp_tree(tmp_path)

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert skill_set == SkillSet(
            agent_dirs=(*UNIVERSAL_AGENT_DIRS, AgentSkillsDir(CLAUDE_CODE, CLAUDE_SKILLS, CANONICAL)),
            skills=(_canonical_skill('deploy', ALL_AGENTS), _canonical_skill('review', ALL_AGENTS)),
        ), 'the linked .claude/skills aliases the canonical directory, which is listed once for all four agents'

    def test_load_skills_with_the_ampup_tree_returns_the_amp_result(self, tmp_path: Path, skills: Repository) -> None:
        #: Given
        _ampup_tree(tmp_path)

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert skill_set == SkillSet(
            agent_dirs=(*UNIVERSAL_AGENT_DIRS, AgentSkillsDir(CLAUDE_CODE, CLAUDE_SKILLS, CANONICAL)),
            skills=(_canonical_skill('deploy', ALL_AGENTS), _canonical_skill('review', ALL_AGENTS)),
        ), 'a directory-level .claude link resolves .claude/skills to the canonical directory'

    def test_load_skills_with_the_lorecraft_tree_returns_fourteen_skills_seen_by_all_four_agents(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _lorecraft_tree(tmp_path)

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert skill_set == SkillSet(
            agent_dirs=(*UNIVERSAL_AGENT_DIRS, AgentSkillsDir(CLAUDE_CODE, CLAUDE_SKILLS, CANONICAL)),
            skills=tuple(_canonical_skill(name, ALL_AGENTS) for name in LORECRAFT_SKILLS),
        ), 'the trailing-slash link resolves like any other, and nested files are never listed'

    def test_load_skills_with_a_per_skill_link_merges_both_sightings_into_one_skill(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _per_skill_link_tree(tmp_path)
        deploy = CANONICAL / 'deploy'

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert skill_set == SkillSet(
            agent_dirs=(*UNIVERSAL_AGENT_DIRS, AgentSkillsDir(CLAUDE_CODE, CLAUDE_SKILLS, CLAUDE_SKILLS)),
            skills=(
                Skill(
                    SkillName.parse('deploy'),
                    deploy,
                    ALL_AGENTS,
                    (
                        Sighting(deploy, deploy, UNIVERSAL_AGENTS),
                        Sighting(CLAUDE_SKILLS / 'deploy', deploy, (CLAUDE_CODE,)),
                    ),
                ),
                _canonical_skill('review', UNIVERSAL_AGENTS),
            ),
        ), 'one skill per name, sightings in scan order, the canonical sighting first and supplying the path'

    def test_missing_agents_with_a_per_skill_link_reports_claude_code_for_the_unlinked_skill(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _per_skill_link_tree(tmp_path)
        skill_set = load_skills(skills)
        review = skill_set.skills[1]  # sorted by name: deploy, review

        #: When
        missing = skill_set.missing_agents(review)

        #: Then
        assert missing == (CLAUDE_CODE,), 'the present .claude/skills directory does not expose review'

    def test_load_skills_with_a_copy_under_claude_keeps_a_sighting_whose_target_is_the_copy(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _copy_tree(tmp_path)
        deploy = CANONICAL / 'deploy'
        copy = CLAUDE_SKILLS / 'deploy'

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert skill_set.skill(SkillName.parse('deploy')) == Skill(
            SkillName.parse('deploy'),
            deploy,
            ALL_AGENTS,
            (Sighting(deploy, deploy, UNIVERSAL_AGENTS), Sighting(copy, copy, (CLAUDE_CODE,))),
        ), 'the copy is a second sighting whose target differs from the skill path'

    def test_load_skills_with_a_claude_only_tree_returns_the_skill_under_claude(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _claude_only_tree(tmp_path)
        notes = CLAUDE_SKILLS / 'notes'

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert skill_set == SkillSet(
            agent_dirs=(AgentSkillsDir(CLAUDE_CODE, CLAUDE_SKILLS, CLAUDE_SKILLS),),
            skills=(Skill(SkillName.parse('notes'), notes, (CLAUDE_CODE,), (Sighting(notes, notes, (CLAUDE_CODE,)),)),),
        ), 'without a canonical directory only claude-code is present, and its skill lives under .claude/skills'
        assert skill_set.skills[0].is_linked, 'a skill claude-code exposes is linked'

    def test_load_skills_with_an_empty_root_returns_an_empty_set(self, skills: Repository) -> None:
        #: Given
        empty_root = skills

        #: When
        skill_set = load_skills(empty_root)

        #: Then
        assert skill_set == SkillSet((), ()), 'no skills directory means no agent present and no skill'

    def test_load_skills_with_an_invalid_directory_name_leaves_it_out(self, tmp_path: Path, skills: Repository) -> None:
        #: Given
        _canonical_skills(tmp_path, ('deploy', 'Bad_Name'))

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert _names(skill_set) == ('deploy',), 'the invalidly named directory is not a skill'

    def test_load_skills_with_no_skill_md_leaves_the_directory_out(self, tmp_path: Path, skills: Repository) -> None:
        #: Given
        _canonical_skills(tmp_path, ('deploy',))
        _write(tmp_path, '.agents/skills/nomd/notes.md')

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert _names(skill_set) == ('deploy',), 'a directory without SKILL.md is not a skill'

    def test_load_skills_with_a_skill_md_directory_leaves_the_skill_out(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _canonical_skills(tmp_path, ('deploy',))
        (tmp_path / '.agents' / 'skills' / 'x' / 'SKILL.md').mkdir(parents=True)

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert _names(skill_set) == ('deploy',), 'a directory named SKILL.md is not a SKILL.md file'

    def test_load_skills_with_a_dangling_skill_link_leaves_it_out(self, tmp_path: Path, skills: Repository) -> None:
        #: Given
        _canonical_skills(tmp_path, ('deploy',))
        _link(tmp_path, '.agents/skills/gone', 'missing')

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert _names(skill_set) == ('deploy',), 'a dangling link is not a skill'

    def test_load_skills_with_a_skill_link_outside_the_root_leaves_it_out(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory, skills: Repository
    ) -> None:
        #: Given
        outside = tmp_path_factory.mktemp('outside')
        _write(outside, 'deploy/SKILL.md')
        _canonical_skills(tmp_path, ('review',))
        _link(tmp_path, '.claude/skills/deploy', str(outside / 'deploy'))

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert _names(skill_set) == ('review',), 'the skill outside the root is not discovered'

    def test_load_skills_with_a_dangling_claude_skills_link_leaves_claude_code_absent(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _canonical_skills(tmp_path, ('deploy',))
        _link(tmp_path, '.claude/skills', 'missing')

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert skill_set.agent_dirs == UNIVERSAL_AGENT_DIRS, 'claude-code is not present'

    def test_load_skills_with_a_file_at_claude_skills_leaves_claude_code_absent(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _canonical_skills(tmp_path, ('deploy',))
        _write(tmp_path, '.claude/skills')

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert skill_set.agent_dirs == UNIVERSAL_AGENT_DIRS, 'claude-code is not present'

    def test_load_skills_with_a_renamed_link_returns_a_second_skill_sharing_the_target(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _canonical_skills(tmp_path, ('deploy',))
        _link(tmp_path, '.claude/skills/alias', '../../.agents/skills/deploy')
        deploy = CANONICAL / 'deploy'

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert skill_set.skill(SkillName.parse('alias')) == Skill(
            SkillName.parse('alias'),
            deploy,
            (CLAUDE_CODE,),
            (Sighting(CLAUDE_SKILLS / 'alias', deploy, (CLAUDE_CODE,)),),
        ), 'identity is the entry name, so the renamed link is its own skill at the target path'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_load_skills_with_an_unlistable_canonical_directory_raises_list_skill_entries_error(
        self, locked_canonical: Path, skills: Repository
    ) -> None:
        #: Given
        repository = skills

        #: When
        with pytest.raises(ListSkillEntriesError) as exc_info:
            load_skills(repository)

        #: Then
        assert exc_info.value.path == CANONICAL, 'the error names the canonical directory'

    def test_load_skills_with_a_claude_skill_sorting_first_returns_skills_by_name(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _canonical_skills(tmp_path, ('review',))
        _write(tmp_path, '.claude/skills/alpha/SKILL.md')

        #: When
        skill_set = load_skills(skills)

        #: Then
        assert _names(skill_set) == ('alpha', 'review'), 'skills sort by name, not by the canonical-first scan'

    def test_load_skills_with_the_only_copy_under_claude_lists_claude_code_alone(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _canonical_skills(tmp_path, ('review',))
        _write(tmp_path, '.claude/skills/alpha/SKILL.md')

        #: When
        skill_set = load_skills(skills)

        #: Then
        alpha = skill_set.skill(SkillName.parse('alpha'))
        assert alpha is not None, 'the skill under .claude/skills is discovered'
        assert alpha.path == CLAUDE_SKILLS / 'alpha', 'with no canonical sighting the claude directory gives the path'
        assert alpha.agents == (CLAUDE_CODE,), 'only claude-code exposes a skill its own directory holds alone'


@pytest.mark.it
class TestLoadSkillsOverASnapshot:
    def test_load_skills_over_a_snapshot_with_a_dangling_claude_skills_link_agrees_with_disk(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _canonical_skills(tmp_path, ('deploy',))
        _link(tmp_path, '.claude/skills', 'missing')
        on_disk = load_skills(skills)
        snapshot_skills = Repository(VirtualFileSystem(take_snapshot(tmp_path, SNAPSHOT_SCOPE)))

        #: When
        on_snapshot = load_skills(snapshot_skills)

        #: Then
        assert on_snapshot == on_disk, 'the dangling agent directory is absent over the snapshot as on disk'

    def test_load_skills_over_a_snapshot_with_a_file_at_claude_skills_agrees_with_disk(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _canonical_skills(tmp_path, ('deploy',))
        _write(tmp_path, '.claude/skills')
        on_disk = load_skills(skills)
        snapshot_skills = Repository(VirtualFileSystem(take_snapshot(tmp_path, SNAPSHOT_SCOPE)))

        #: When
        on_snapshot = load_skills(snapshot_skills)

        #: Then
        assert on_snapshot == on_disk, 'the file at the agent directory is absent over the snapshot as on disk'

    def test_load_skills_over_a_snapshot_with_an_absolute_claude_skills_link_agrees_with_disk(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _canonical_skills(tmp_path, ('deploy',))
        _link(tmp_path, '.claude/skills', str(tmp_path / '.agents' / 'skills'))
        on_disk = load_skills(skills)
        snapshot_skills = Repository(VirtualFileSystem(take_snapshot(tmp_path, SNAPSHOT_SCOPE)))

        #: When
        on_snapshot = load_skills(snapshot_skills)

        #: Then
        assert on_snapshot == on_disk, 'the absolute link into the root resolves over the snapshot as on disk'

    def test_load_skills_over_a_snapshot_with_the_canonical_directory_linked_outside_the_scan_roots_finds_nothing(
        self, tmp_path: Path, skills: Repository
    ) -> None:
        #: Given
        _write(tmp_path, 'vendor/skills/deploy/SKILL.md')
        _link(tmp_path, '.agents/skills', '../vendor/skills')
        on_disk = load_skills(skills)
        snapshot_skills = Repository(VirtualFileSystem(take_snapshot(tmp_path, SNAPSHOT_SCOPE)))

        #: When
        on_snapshot = load_skills(snapshot_skills)

        #: Then
        assert _names(on_disk) == ('deploy',), 'the disk follows the link and finds the vendored skill'
        assert on_snapshot == SkillSet(agent_dirs=(), skills=()), (
            'a link leading outside the scan roots is not followed: the snapshot finds nothing'
        )
