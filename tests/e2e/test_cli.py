"""The CLI as a user runs it: a real process, the installed package, and whatever git is on the box.

`version --verbose` shells out to `git describe`, so this is the only tier that can observe the probe
at all. This suite runs from the checkout, so the verbose command must report its Git description as
well as the installed version and environment; run from a copy of the package outside the checkout, or with a
`PATH` holding no git, a git that fails or one that hangs, it must leave the commit line out. Every version
output, and `inspect`, `check`, `check frontmatter`, `check structure`, `check budget` and `check skills` over a
checked-in workspace fixture, is compared to a reviewed snapshot file under `__snapshots__/`. So is what `check` and
`inspect` print for a root whose `docs/` or `docs/__meta__/` is a symlink into that fixture, what `check frontmatter`
and `check skills` print for a root whose frontmatter writes a key twice, what `check skills` prints for the fixture's
skills named one at a time (an entry another entry links to, a linked entry, and the directory no agent reads that a
linked entry leads to) and named by their skills directory (the canonical one, the one linked to it, and `skills/`,
which no agent reads), how it refuses a directory holding no skill, and what it prints for a skill linking to an
absolute path, for one linking to a heading it does not have, for one whose `SKILL.md` and a resource link outside the
skill, for one whose `SKILL.md` and a resource link a file the skill does not hold, for one whose resource links to an
absolute path and to a heading it does not have, for one whose `SKILL.md` and a resource link to an absolute path,
named by its directory and by its `SKILL.md`, which checks that file alone, for one whose `metadata` repeats a file
name, lists a path outside what the command reads, or lists a file the repository does not have, and for one holding a
symlink that leads outside the repository.
"""

import os
import shutil
from pathlib import Path
from textwrap import dedent
from typing import Final

import pytest
from syrupy.assertion import SnapshotAssertion

import lorecraft
from lib.cli import run_alias, run_cli
from lib.snapshot import JsonTextSnapshotExtension, TextSnapshotExtension
from lorecraft import __version__

# The labelled lines of `version --verbose` whose values differ per checkout, interpreter, machine and install.
_VARYING_FIELDS: Final[tuple[str, ...]] = ('Commit', 'Python', 'Platform', 'Install')

# A checked-in workspace root holding each part of the model `inspect` draws: a corpus with a structure
# specification that states a frontmatter schema, a namespace spec with a structure layer, a document each governs,
# a README beside the specifications that is not one, and a skills directory two agents read, one through a
# link, holding a skill, a link to it and a link to a skill kept outside it.
# Resolved, because the CLI prints the resolved root and the tests swap exactly that string for a placeholder.
WORKSPACE_FIXTURE: Final[Path] = (Path(__file__).parent / 'fixtures' / 'workspace').resolve()
_ROOT_PLACEHOLDER: Final[str] = '<workspace>'


def _redact(output: str) -> str:
    """Swap every value that differs per build, checkout or machine for a placeholder naming it.

    The version becomes `<version>` wherever it appears, and each varying labelled line keeps its label and
    its alignment, so the snapshot still pins the layout: `Commit:   <commit>`.

    Args:
        output: Text the command printed. Lines labelled with a per-machine field are rewritten; the rest pass through.
    """
    lines: list[str] = []
    for line in output.replace(__version__, '<version>').splitlines():
        label, separator, value = line.partition(':')
        if separator and label in _VARYING_FIELDS:
            padding = value[: len(value) - len(value.lstrip())]
            line = f'{label}:{padding}<{label.lower()}>'
        lines.append(line)
    return '\n'.join(lines) + '\n'


@pytest.mark.e2e
class TestInstalledCommandLine:
    def test_no_arguments_prints_the_help_and_exits_nonzero(self) -> None:
        #: Given
        arguments: tuple[str, ...] = ()

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode != 0, 'a bare invocation is a usage error, not a success'
        assert 'Usage:' in result.stdout, 'no_args_is_help prints the help rather than nothing'

    def test_lc_alias_runs_the_same_command_line(self) -> None:
        #: Given
        expected = run_cli('--version')

        #: When
        result = run_alias('--version')

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout == expected.stdout, '`lc` is the same entry point as `lorecraft`'


def _environment_searching(directory: Path) -> dict[str, str]:
    """The test's own environment, with `PATH` holding `directory` alone, so `git` is whatever it holds.

    The console script is run by its full path, and starts its interpreter by one, so neither needs `PATH`.

    Args:
        directory: The one directory a command run by name is looked up in.
    """
    return {**os.environ, 'PATH': str(directory)}


def _write_git(directory: Path, script: str) -> Path:
    """Write an executable `git` into a new `directory`, standing in for the real one, and return the directory.

    Args:
        directory: Directory created to hold the stand-in, which must not exist yet.
        script: The shell script the stand-in runs, without its `#!/bin/sh` line.
    """
    directory.mkdir()
    git = directory / 'git'
    git.write_text(f'#!/bin/sh\n{script}', encoding='utf-8')
    git.chmod(0o755)
    return directory


@pytest.fixture(scope='function')
def installed_copy(tmp_path: Path) -> Path:
    """A `site-packages` directory outside any checkout, holding a copy of the package where a wheel puts it.

    First on `PYTHONPATH`, the copy is imported in place of the checkout's `src/lorecraft`, so the console script
    runs from a package no checkout holds.

    Args:
        tmp_path: Directory the `site-packages` directory is created in.
    """
    site_packages = tmp_path / 'site-packages'
    package = Path(lorecraft.__file__).parent
    shutil.copytree(package, site_packages / 'lorecraft', ignore=shutil.ignore_patterns('__pycache__'))
    return site_packages


@pytest.fixture(scope='function')
def directory_without_git(tmp_path: Path) -> Path:
    """An empty directory, so a `PATH` holding it alone finds no git.

    Args:
        tmp_path: Directory the empty directory is created in.
    """
    directory = tmp_path / 'bin'
    directory.mkdir()
    return directory


@pytest.fixture(scope='function')
def directory_with_a_failing_git(tmp_path: Path) -> Path:
    """A directory holding a `git` that prints an error and exits 128, as git does when it cannot describe.

    Args:
        tmp_path: Directory the directory holding the stand-in is created in.
    """
    script = dedent(
        """\
        echo 'fatal: not a git repository' >&2
        exit 128
        """
    )
    return _write_git(tmp_path / 'bin', script)


@pytest.fixture(scope='function')
def directory_with_a_hanging_git(tmp_path: Path) -> Path:
    """A directory holding a `git` that runs for a minute, far past the five seconds the probe waits.

    It is longer than the 30 seconds `run_cli` waits as well, so a probe that never gives up fails the test rather
    than passing slowly.

    Args:
        tmp_path: Directory the directory holding the stand-in is created in.
    """
    sleep = shutil.which('sleep')
    assert sleep is not None, 'the stand-in git hangs by running sleep, which must be installed'
    # `exec` replaces the shell with `sleep`, so the kill that ends the probe ends the process holding its pipes.
    return _write_git(tmp_path / 'bin', f'exec {sleep} 60\n')


@pytest.mark.e2e
class TestVersionSnapshots:
    # The version, the commit and the environment differ per build and per machine, so each test redacts them
    # before comparing, the way an insta filter would; everything else is compared byte for byte.

    def test_version_option_with_long_form_prints_the_short_version(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('--version',)

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert _redact(result.stdout) == expected, 'the option prints the one-line version'

    def test_version_option_with_short_form_prints_the_short_version(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('-V',)

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert _redact(result.stdout) == expected, '-V prints the same line as --version'

    def test_version_command_without_verbose_prints_the_short_version(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('version',)

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert _redact(result.stdout) == expected, 'the plain subcommand prints the same line as the option'

    def test_version_command_with_verbose_reports_the_checkout_commit_and_environment(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('version', '--verbose')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert _redact(result.stdout) == expected, (
            'run from the checkout, the block carries the commit line as well as the environment'
        )

    def test_version_command_with_verbose_outside_a_checkout_omits_the_commit_line(
        self, snapshot: SnapshotAssertion, installed_copy: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('version', '--verbose')
        environment = {**os.environ, 'PYTHONPATH': str(installed_copy)}

        #: When
        result = run_cli(*arguments, env=environment)

        #: Then
        assert result.returncode == 0, result.stderr
        assert _redact(result.stdout) == expected, 'a package no checkout holds has no commit to report'

    def test_version_command_with_verbose_without_git_omits_the_commit_line(
        self, snapshot: SnapshotAssertion, directory_without_git: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('version', '--verbose')
        environment = _environment_searching(directory_without_git)

        #: When
        result = run_cli(*arguments, env=environment)

        #: Then
        assert result.returncode == 0, result.stderr
        assert _redact(result.stdout) == expected, 'with no git to run, the checkout cannot be described'

    def test_version_command_with_verbose_when_git_fails_omits_the_commit_line(
        self, snapshot: SnapshotAssertion, directory_with_a_failing_git: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('version', '--verbose')
        environment = _environment_searching(directory_with_a_failing_git)

        #: When
        result = run_cli(*arguments, env=environment)

        #: Then
        assert result.returncode == 0, result.stderr
        assert _redact(result.stdout) == expected, 'a git that fails describes nothing, and the version still prints'

    def test_version_command_with_verbose_when_git_hangs_omits_the_commit_line(
        self, snapshot: SnapshotAssertion, directory_with_a_hanging_git: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('version', '--verbose')
        environment = _environment_searching(directory_with_a_hanging_git)

        #: When
        result = run_cli(*arguments, env=environment)

        #: Then
        assert result.returncode == 0, result.stderr
        assert _redact(result.stdout) == expected, (
            'the probe gives up on a git that hangs, and the version still prints'
        )


@pytest.mark.e2e
class TestInspectSnapshots:
    # The CLI prints the resolved root, which differs per checkout, so each test swaps it for a placeholder
    # before comparing, the way an insta filter would; everything else is compared byte for byte.

    def test_inspect_without_a_root_in_the_workspace_fixture_prints_the_model_tree(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('inspect',)

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout.replace(str(WORKSPACE_FIXTURE), _ROOT_PLACEHOLDER) == expected, (
            'the tree drawn from the working directory matches the reviewed snapshot'
        )

    def test_inspect_with_json_over_the_workspace_fixture_prints_the_model_document(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(JsonTextSnapshotExtension)
        arguments = ('inspect', str(WORKSPACE_FIXTURE), '--format', 'json')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout.replace(str(WORKSPACE_FIXTURE), _ROOT_PLACEHOLDER) == expected, (
            'the JSON document matches the reviewed snapshot'
        )


@pytest.fixture(scope='function')
def duplicate_key_root(tmp_path: Path) -> Path:
    """A root holding one document and one skill, each of whose frontmatter writes a key twice.

    Apart from the repetition both are clean, so the duplicate-key finding is the only one either check prints.

    Args:
        tmp_path: Directory the document, its specification and the skill are written into, as the repository root.
    """
    (tmp_path / 'docs' / '__meta__').mkdir(parents=True)
    (tmp_path / 'docs' / '__meta__' / 'code.structure.json').write_text(
        '{"frontmatter": {"type": "object"}}\n', encoding='utf-8'
    )
    (tmp_path / 'docs' / 'code').mkdir()
    (tmp_path / 'docs' / 'code' / 'guide.md').write_text(
        '---\nname: guide\ntype: rule\ntype: pattern\n---\n', encoding='utf-8'
    )
    (tmp_path / '.agents' / 'skills' / 'review').mkdir(parents=True)
    (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').write_text(
        '---\nname: review\ndescription: Review a change\ndescription: Audit a change\n---\n', encoding='utf-8'
    )
    return tmp_path


@pytest.fixture(scope='function')
def absolute_link_root(tmp_path: Path) -> Path:
    """A root holding one skill whose `SKILL.md` links to a file from the filesystem root.

    Apart from the link the skill is clean, so the link-absolute finding is the only one the check prints.

    Args:
        tmp_path: Directory the skill is written into, as the repository root.
    """
    (tmp_path / '.agents' / 'skills' / 'review').mkdir(parents=True)
    (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').write_text(
        '---\nname: review\ndescription: Review a change\n---\n# Review\n\nRead [the guide](/docs/guide.md).\n',
        encoding='utf-8',
    )
    return tmp_path


@pytest.fixture(scope='function')
def missing_fragment_root(tmp_path: Path) -> Path:
    """A root holding one skill whose `SKILL.md` links to a heading of its own that it does not have.

    Apart from the link the skill is clean, so the link-fragment finding is the only one the check prints.

    Args:
        tmp_path: Directory the skill is written into, as the repository root.
    """
    (tmp_path / '.agents' / 'skills' / 'review').mkdir(parents=True)
    (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').write_text(
        '---\nname: review\ndescription: Review a change\n---\n# Review\n\nSee [the checklist](#checklist).\n',
        encoding='utf-8',
    )
    return tmp_path


@pytest.fixture(scope='function')
def escaping_link_root(tmp_path: Path) -> Path:
    """A root holding one skill whose `SKILL.md` and a resource each link outside the skill directory.

    The resource links its own skill as `../SKILL.md`, which, read from the skill root, leaves the skill. Apart
    from the two links the skill is clean, so the two link-escapes findings are the only ones the check prints.

    Args:
        tmp_path: Directory the skill is written into, as the repository root.
    """
    (tmp_path / '.agents' / 'skills' / 'review' / 'references').mkdir(parents=True)
    (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').write_text(
        '---\nname: review\ndescription: Review a change\n---\n# Review\n\nRead [the guide](../../../docs/guide.md).\n',
        encoding='utf-8',
    )
    (tmp_path / '.agents' / 'skills' / 'review' / 'references' / 'steps.md').write_text(
        '# Steps\n\nBack to [the skill](../SKILL.md).\n', encoding='utf-8'
    )
    return tmp_path


@pytest.fixture(scope='function')
def broken_link_root(tmp_path: Path) -> Path:
    """A root holding one skill whose `SKILL.md` and a resource each link a file the skill does not hold.

    The resource links `steps.md` beside it, which, read from the skill root, names nothing; its link to
    `references/steps.md` resolves. Apart from the two broken links the skill is clean, so the two link-broken
    findings are the only ones the check prints.

    Args:
        tmp_path: Directory the skill is written into, as the repository root.
    """
    (tmp_path / '.agents' / 'skills' / 'review' / 'references').mkdir(parents=True)
    (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').write_text(
        '---\nname: review\ndescription: Review a change\n---\n# Review\n\n'
        'Follow [the steps](references/steps.md) and [the checklist](references/checklist.md).\n',
        encoding='utf-8',
    )
    (tmp_path / '.agents' / 'skills' / 'review' / 'references' / 'guide.md').write_text(
        '# Guide\n\nSee [the steps](references/steps.md), not [the steps](steps.md).\n', encoding='utf-8'
    )
    (tmp_path / '.agents' / 'skills' / 'review' / 'references' / 'steps.md').write_text('# Steps\n', encoding='utf-8')
    return tmp_path


@pytest.fixture(scope='function')
def resource_absolute_and_fragment_link_root(tmp_path: Path) -> Path:
    """A root holding one skill whose resource links to a file from the filesystem root and to a missing heading.

    The resource links `#usage`, a heading of the `SKILL.md` but not of the resource, and `#guide`, its own. Apart
    from the two links the skill is clean, so the link-absolute and link-fragment findings, both in the resource,
    are the only ones the check prints.

    Args:
        tmp_path: Directory the skill is written into, as the repository root.
    """
    (tmp_path / '.agents' / 'skills' / 'review' / 'references').mkdir(parents=True)
    (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').write_text(
        '---\nname: review\ndescription: Review a change\n---\n# Review\n\n## Usage\n', encoding='utf-8'
    )
    (tmp_path / '.agents' / 'skills' / 'review' / 'references' / 'guide.md').write_text(
        '# Guide\n\nRead [the docs](/docs/guide.md).\n\nSee [the usage](#usage), not [the guide](#guide).\n',
        encoding='utf-8',
    )
    return tmp_path


@pytest.fixture(scope='function')
def skill_and_resource_absolute_link_root(tmp_path: Path) -> Path:
    """A root holding one skill whose `SKILL.md` and whose resource each link to a file from the filesystem root.

    Apart from the two links the skill is clean, so a run over the whole skill prints two link-absolute findings,
    one per file, and a run over its `SKILL.md` alone prints the one in the `SKILL.md`.

    Args:
        tmp_path: Directory the skill is written into, as the repository root.
    """
    (tmp_path / '.agents' / 'skills' / 'review' / 'references').mkdir(parents=True)
    (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').write_text(
        '---\nname: review\ndescription: Review a change\n---\n# Review\n\nRead [the steps](/steps.md).\n',
        encoding='utf-8',
    )
    (tmp_path / '.agents' / 'skills' / 'review' / 'references' / 'guide.md').write_text(
        '# Guide\n\nRead [the docs](/docs/guide.md).\n', encoding='utf-8'
    )
    return tmp_path


@pytest.fixture(scope='function')
def long_skill_root(tmp_path: Path) -> Path:
    """A root holding one skill whose `SKILL.md` is 501 lines, its four lines of frontmatter included.

    Apart from its length the skill is clean, so the lines-budget finding is the only one the check prints.

    Args:
        tmp_path: Directory the skill is written into, as the repository root.
    """
    (tmp_path / '.agents' / 'skills' / 'review').mkdir(parents=True)
    (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').write_text(
        '---\nname: review\ndescription: Review a change\n---\n' + 'Body.\n' * 497, encoding='utf-8'
    )
    return tmp_path


@pytest.fixture(scope='function')
def outside_link_root(tmp_path: Path) -> Path:
    """A root holding one clean skill whose `references` directory links out of the repository, climbing above it.

    The root is `tmp_path/repository`, and `references -> ../../../../shared/refs` leads to `tmp_path/shared/refs`,
    a relative target so the printed note is the same on every machine. The symlink-outside finding is the only one
    the check prints.

    Args:
        tmp_path: Directory the repository and the directory outside it are written into.

    Returns:
        The repository root.
    """
    (tmp_path / 'shared' / 'refs').mkdir(parents=True)
    (tmp_path / 'shared' / 'refs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    root = tmp_path / 'repository'
    (root / '.agents' / 'skills' / 'review').mkdir(parents=True)
    (root / '.agents' / 'skills' / 'review' / 'SKILL.md').write_text(
        '---\nname: review\ndescription: Review a change\n---\n', encoding='utf-8'
    )
    (root / '.agents' / 'skills' / 'review' / 'references').symlink_to('../../../../shared/refs')
    return root


def _write_review_skill(root: Path, metadata: str) -> None:
    """Write the skill `.agents/skills/review/` and give it `metadata`.

    Apart from what `metadata` lists the skill is clean, so a metadata finding is the only one the check prints.

    Args:
        root: Repository root the skill directory is created under.
        metadata: The lines of the `metadata` mapping, each indented and ending in a newline.
    """
    (root / '.agents' / 'skills' / 'review').mkdir(parents=True)
    (root / '.agents' / 'skills' / 'review' / 'SKILL.md').write_text(
        f'---\nname: review\ndescription: Review a change\nmetadata:\n{metadata}---\n# Review\n', encoding='utf-8'
    )


@pytest.fixture(scope='function')
def duplicate_name_root(tmp_path: Path) -> Path:
    """A root holding one skill whose `metadata` lists two documents with one file name.

    Args:
        tmp_path: Directory the documents and the skill are written into, as the repository root.
    """
    (tmp_path / 'docs' / 'code').mkdir(parents=True)
    (tmp_path / 'docs' / 'code' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    (tmp_path / 'docs' / 'feat').mkdir()
    (tmp_path / 'docs' / 'feat' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    _write_review_skill(tmp_path, '  references: docs/code/guide.md docs/feat/guide.md\n')
    return tmp_path


@pytest.fixture(scope='function')
def outside_scope_root(tmp_path: Path) -> Path:
    """A root holding one skill whose `metadata` lists a source file, which no check reads.

    Args:
        tmp_path: Directory the source file and the skill are written into, as the repository root.
    """
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'tool.py').write_text('', encoding='utf-8')
    _write_review_skill(tmp_path, '  scripts: src/tool.py\n')
    return tmp_path


@pytest.fixture(scope='function')
def missing_file_root(tmp_path: Path) -> Path:
    """A root holding one skill whose `metadata` lists a document `docs/code/` does not hold.

    Args:
        tmp_path: Directory the document and the skill are written into, as the repository root.
    """
    (tmp_path / 'docs' / 'code').mkdir(parents=True)
    (tmp_path / 'docs' / 'code' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    _write_review_skill(tmp_path, '  references: docs/code/gone.md\n')
    return tmp_path


@pytest.mark.e2e
class TestCheckFrontmatterSnapshots:
    # Every finding prints root-relative, so the output is the same in every checkout and nothing is redacted.
    # The fixture's documents carry no frontmatter, so each run reports findings and exits 1.

    def test_check_frontmatter_without_a_root_in_the_workspace_fixture_prints_the_findings(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'frontmatter')

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the findings found from the working directory match the reviewed snapshot'

    def test_check_frontmatter_with_json_over_the_workspace_fixture_prints_the_report(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(JsonTextSnapshotExtension)
        arguments = ('check', 'frontmatter', '--root', str(WORKSPACE_FIXTURE), '--format', 'json')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the JSON report matches the reviewed snapshot'

    def test_check_frontmatter_with_a_key_written_twice_prints_the_duplicate_key_finding(
        self, snapshot: SnapshotAssertion, duplicate_key_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'frontmatter', '--root', str(duplicate_key_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the duplicate-key finding matches the reviewed snapshot'


@pytest.mark.e2e
class TestCheckStructureSnapshots:
    # Every finding prints root-relative, so the output is the same in every checkout and nothing is redacted.
    # The fixture's documents are a bare title, so each run reports findings, from both layers, and exits 1.
    # The corpus layer describes its Checklist and gives an example of it, and the python layer describes its
    # References alone, so each missing section prints the notes its entry states.

    def test_check_structure_without_a_root_in_the_workspace_fixture_prints_the_findings(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'structure')

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the findings found from the working directory match the reviewed snapshot'

    def test_check_structure_with_json_over_the_workspace_fixture_prints_the_report(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(JsonTextSnapshotExtension)
        arguments = ('check', 'structure', '--root', str(WORKSPACE_FIXTURE), '--format', 'json')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the JSON report matches the reviewed snapshot'


@pytest.mark.e2e
class TestCheckBudgetSnapshots:
    # The python layer's budget is tighter than its document, so each run reports one finding and exits 1.

    def test_check_budget_without_a_root_in_the_workspace_fixture_prints_the_findings(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'budget')

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the findings found from the working directory match the reviewed snapshot'

    def test_check_budget_with_json_over_the_workspace_fixture_prints_the_report(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(JsonTextSnapshotExtension)
        arguments = ('check', 'budget', '--root', str(WORKSPACE_FIXTURE), '--format', 'json')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the JSON report matches the reviewed snapshot'


@pytest.mark.e2e
class TestCheckSkillsSnapshots:
    # Every finding prints root-relative, so the output is the same in every checkout and nothing is redacted.
    # The fixture's `beta` skill is a link to `alpha` and is named `alpha`, not the `beta` an agent lists it by:
    # each run that checks `beta` reports that finding, with a note naming where the link leads, and exits 1.

    def test_check_skills_without_a_root_in_the_workspace_fixture_prints_the_findings(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills')

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the findings found from the working directory match the reviewed snapshot'

    def test_check_skills_with_json_over_the_workspace_fixture_prints_the_report(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(JsonTextSnapshotExtension)
        arguments = ('check', 'skills', '--root', str(WORKSPACE_FIXTURE), '--format', 'json')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the JSON report matches the reviewed snapshot'

    def test_check_skills_with_the_entry_another_entry_links_to_checks_that_skill_alone(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '.agents/skills/alpha')

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout == expected, 'alpha is clean, and beta, which links to it, is not checked'
        assert result.stderr == 'checked 1 skill(s), 0 finding(s)\n', 'the entry named is the one skill checked'

    def test_check_skills_with_a_linked_entry_checks_that_skill_alone(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '.agents/skills/beta')

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the name-matches-directory finding of beta alone matches the snapshot'
        assert result.stderr == 'checked 1 skill(s), 1 finding(s)\n', (
            'the entry named is the one skill checked, not alpha, the directory it links to'
        )

    def test_check_skills_with_a_skill_directory_no_agent_reads_checks_it_under_that_path(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', 'skills/gamma')

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout == expected, 'gamma, named skills/gamma, matches the name of that directory and is clean'
        assert result.stderr == 'checked 1 skill(s), 0 finding(s)\n', (
            'the directory named is the one skill checked, not the entry linked to it'
        )

    def test_check_skills_with_a_skills_directory_checks_every_skill_listed_in_it(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '.agents/skills')

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the findings of every skill in the directory match the snapshot'
        assert result.stderr == 'checked 3 skill(s), 1 finding(s)\n', 'alpha, beta and gamma are each checked once'

    def test_check_skills_with_a_linked_skills_directory_reports_under_the_real_one(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '.claude/skills')

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, (
            'the findings are reported under .agents/skills, as a run naming no path reports them'
        )
        assert result.stderr == 'checked 3 skill(s), 1 finding(s)\n', 'each skill the link leads to is checked once'

    def test_check_skills_with_a_directory_of_skills_no_agent_reads_checks_each_skill_in_it(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', 'skills')

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout == expected, 'gamma, the one skill in skills/, is clean under skills/gamma'
        assert result.stderr == 'checked 1 skill(s), 0 finding(s)\n', 'each skill directly in the directory is checked'

    def test_check_skills_with_a_directory_holding_no_skill_prints_the_error_and_exits_two(self) -> None:
        #: Given
        arguments = ('check', 'skills', 'docs/code')

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'a run that could not start prints nothing on stdout'
        assert result.stderr == (
            'error: docs/code: no skill there; name a skill directory, a directory of skills, or a SKILL.md\n'
        ), 'no SKILL.md is at the root of docs/code or in a directory directly in it, so the argument is refused'

    def test_check_skills_with_a_key_written_twice_prints_the_duplicate_key_finding(
        self, snapshot: SnapshotAssertion, duplicate_key_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '--root', str(duplicate_key_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the duplicate-key finding matches the reviewed snapshot'

    def test_check_skills_with_an_absolute_link_prints_the_link_absolute_finding(
        self, snapshot: SnapshotAssertion, absolute_link_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '--root', str(absolute_link_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the link-absolute finding matches the reviewed snapshot'

    def test_check_skills_with_a_link_to_a_missing_heading_prints_the_link_fragment_finding(
        self, snapshot: SnapshotAssertion, missing_fragment_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '--root', str(missing_fragment_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the link-fragment finding matches the reviewed snapshot'

    def test_check_skills_with_escaping_links_prints_each_link_escapes_finding_in_its_file(
        self, snapshot: SnapshotAssertion, escaping_link_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '--root', str(escaping_link_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the link-escapes findings, one in the resource, match the reviewed snapshot'

    def test_check_skills_with_broken_links_prints_each_link_broken_finding_in_its_file(
        self, snapshot: SnapshotAssertion, broken_link_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '--root', str(broken_link_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the link-broken findings, one in the resource, match the reviewed snapshot'

    def test_check_skills_with_absolute_and_fragment_links_in_a_resource_prints_both_findings_there(
        self, snapshot: SnapshotAssertion, resource_absolute_and_fragment_link_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '--root', str(resource_absolute_and_fragment_link_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'both link findings, in the resource, match the reviewed snapshot'

    def test_check_skills_with_a_skill_directory_prints_the_findings_of_its_skill_md_and_its_resources(
        self, snapshot: SnapshotAssertion, skill_and_resource_absolute_link_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        root = skill_and_resource_absolute_link_root
        arguments = ('check', 'skills', '--root', str(root), '.agents/skills/review')

        #: When
        result = run_cli(*arguments, cwd=root)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the link-absolute findings of both files match the reviewed snapshot'
        assert result.stderr == 'checked 1 skill(s), 2 finding(s)\n', 'the whole skill is checked'

    def test_check_skills_with_a_skill_md_prints_the_findings_of_that_file_alone(
        self, snapshot: SnapshotAssertion, skill_and_resource_absolute_link_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        root = skill_and_resource_absolute_link_root
        arguments = ('check', 'skills', '--root', str(root), '.agents/skills/review/SKILL.md')

        #: When
        result = run_cli(*arguments, cwd=root)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the link-absolute finding of the SKILL.md alone matches the snapshot'
        assert result.stderr == 'checked 1 skill(s), 1 finding(s)\n', (
            'the skill is checked by its SKILL.md alone, and its resource is not read'
        )

    def test_check_skills_with_a_skill_md_over_500_lines_prints_the_lines_budget_finding(
        self, snapshot: SnapshotAssertion, long_skill_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '--root', str(long_skill_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the lines-budget finding and its help note match the reviewed snapshot'

    def test_check_skills_with_a_directory_linked_outside_the_repository_prints_the_symlink_outside_finding(
        self, snapshot: SnapshotAssertion, outside_link_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '--root', str(outside_link_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the symlink-outside finding and its note match the reviewed snapshot'

    def test_check_skills_with_a_repeated_metadata_file_name_prints_the_duplicate_name_finding(
        self, snapshot: SnapshotAssertion, duplicate_name_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '--root', str(duplicate_name_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the metadata-duplicate-name finding matches the reviewed snapshot'

    def test_check_skills_with_a_metadata_path_outside_the_scope_prints_the_outside_scope_finding(
        self, snapshot: SnapshotAssertion, outside_scope_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '--root', str(outside_scope_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the metadata-outside-scope finding matches the reviewed snapshot'

    def test_check_skills_with_a_missing_metadata_file_prints_the_missing_file_finding(
        self, snapshot: SnapshotAssertion, missing_file_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', 'skills', '--root', str(missing_file_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the metadata-missing-file finding matches the reviewed snapshot'


@pytest.mark.e2e
class TestCheckAllSnapshots:
    # A bare `check` runs every registered check over the fixture, so its output grows by one block per check.

    def test_check_without_a_root_in_the_workspace_fixture_prints_every_check_findings(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check',)

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'every check finding from the working directory matches the snapshot'

    def test_check_with_json_over_the_workspace_fixture_prints_each_check_report(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(JsonTextSnapshotExtension)
        arguments = ('check', '--root', str(WORKSPACE_FIXTURE), '--format', 'json')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the JSON report of every check matches the reviewed snapshot'


@pytest.fixture(scope='function')
def linked_specs_root(tmp_path: Path) -> Path:
    """A root whose `docs/__meta__` is a symlink to the workspace fixture's specifications, beside one document.

    Args:
        tmp_path: Directory the link and the document are created in, as the repository root.
    """
    (tmp_path / 'docs' / 'code').mkdir(parents=True)
    (tmp_path / 'docs' / 'code' / 'logging.md').write_text('# Logging\n', encoding='utf-8')
    (tmp_path / 'docs' / '__meta__').symlink_to(WORKSPACE_FIXTURE / 'docs' / '__meta__')
    return tmp_path


@pytest.fixture(scope='function')
def linked_docs_root(tmp_path: Path) -> Path:
    """A root whose `docs` is a symlink to the workspace fixture's `docs/`.

    Args:
        tmp_path: Directory the link is created in, as the repository root.
    """
    (tmp_path / 'docs').symlink_to(WORKSPACE_FIXTURE / 'docs')
    return tmp_path


@pytest.mark.e2e
class TestLinkedLayoutSnapshots:
    # Read through the link, each root holds the fixture's findings. The snapshot a command takes never reads
    # through it, so the command refuses the root rather than report a clean run over nothing. The error names
    # the directory root-relative, so nothing is redacted.

    def test_check_with_a_linked_specs_directory_prints_the_error_and_exits_two(
        self, snapshot: SnapshotAssertion, linked_specs_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', '--root', str(linked_specs_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'a run that could not start prints nothing on stdout'
        assert result.stderr == expected, 'the error naming the linked directory matches the reviewed snapshot'

    def test_check_with_a_linked_docs_directory_prints_the_error_and_exits_two(
        self, snapshot: SnapshotAssertion, linked_docs_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', '--root', str(linked_docs_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'a run that could not start prints nothing on stdout'
        assert result.stderr == expected, 'the error naming the linked directory matches the reviewed snapshot'

    def test_check_without_a_root_in_a_linked_specs_workspace_prints_the_error_and_exits_two(
        self, snapshot: SnapshotAssertion, linked_specs_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check',)

        #: When
        result = run_cli(*arguments, cwd=linked_specs_root)

        #: Then
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'a run that could not start prints nothing on stdout'
        assert result.stderr == expected, 'the root discovered through the link is refused, as the snapshot shows'

    def test_inspect_with_a_linked_specs_directory_prints_the_error_and_exits_two(
        self, snapshot: SnapshotAssertion, linked_specs_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('inspect', str(linked_specs_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'no model is drawn for a layout the snapshot could not read'
        assert result.stderr == expected, 'the error naming the linked directory matches the reviewed snapshot'

    def test_inspect_with_a_linked_docs_directory_prints_the_error_and_exits_two(
        self, snapshot: SnapshotAssertion, linked_docs_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('inspect', str(linked_docs_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'no model is drawn for a layout the snapshot could not read'
        assert result.stderr == expected, 'the error naming the linked directory matches the reviewed snapshot'
