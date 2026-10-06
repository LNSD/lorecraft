"""The CLI as a user runs it: a real process, the installed package, and whatever git is on the box.

`version --verbose` shells out to `git describe`, so this is the only tier that can observe the probe
at all. This suite runs from the checkout, so the verbose command must report its Git description as
well as the installed version and environment; run from a copy of the package outside the checkout, or with a
`PATH` holding no git, a git that fails or one that hangs, it must leave the commit line out. Every version
output, `inspect` over a checked-in workspace fixture, and the diagnostics `check` prints over that fixture are
compared to a reviewed snapshot file under `__snapshots__/`. So are the diagnostics `check` prints for a root holding
a subject of each kind the fixture lacks (a resource of a skill, a symlink leading outside the repository, a file
that is not UTF-8, and a document no budget governs, whose coverage goes to stderr), for a root whose frontmatter
writes a key twice or a key that is not a string, and for a skill and a resource each linking to an absolute path;
and what `check` and `inspect` print for a root whose `docs/` or `docs/__meta__/` is a symlink into that fixture.
The JSON document `check` prints is asserted whole, once parsed. A root written from `lib.workspace` holding one
skill whose every field but its name is generated must pass `check` with no diagnostic, and so must one holding a
specification and a document under it, every field generated but their names, since every test writing such a root
sets only the fields its case turns on.
"""

import json
import os
import shutil
from pathlib import Path
from textwrap import dedent
from typing import Final

import pytest
from faker import Faker
from syrupy.assertion import SnapshotAssertion

import lorecraft
from lib.cli import run_alias, run_cli
from lib.snapshot import JsonTextSnapshotExtension, TextSnapshotExtension
from lib.workspace import Document, File, Link, RawDocument, RawFrontmatter, Skill, Spec, Workspace
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
def duplicate_key_root(tmp_path: Path, faker: Faker) -> Path:
    """A root holding one document and one skill, each of whose frontmatter writes a key twice.

    Args:
        tmp_path: Directory the document, its specification and the skill are written into, as the repository root.
        faker: The test's seeded generator, which fills what each part leaves unset.
    """
    # The frontmatter check governs a document only when its corpus specification states a frontmatter schema; this
    # one accepts any mapping, so the repeated key is all it reports.
    spec = Spec('code', structure={'frontmatter': {'type': 'object'}})
    document = Document('code', 'guide', frontmatter=RawFrontmatter('name: guide\ntype: rule\ntype: pattern\n'))
    skill = Skill(
        'review',
        frontmatter=RawFrontmatter('name: review\ndescription: Review a change\ndescription: Audit a change\n'),
    )
    workspace = Workspace(specs=[spec], documents=[document], skills=[skill])
    return workspace.write(tmp_path, faker)


@pytest.fixture(scope='function')
def non_string_key_root(tmp_path: Path, faker: Faker) -> Path:
    """A root holding one document whose frontmatter writes a key that decodes to a date, under `patternProperties`.

    Args:
        tmp_path: Directory the document and its specification are written into, as the repository root.
        faker: The test's seeded generator, which fills what each part leaves unset.
    """
    # `jsonschema` matches a `patternProperties` pattern against every key, so a key that is not a string would
    # crash the run if the frontmatter decoded with it.
    spec = Spec('code', structure={'frontmatter': {'type': 'object', 'patternProperties': {'^x-': {}}}})
    document = Document('code', 'guide', frontmatter=RawFrontmatter('name: guide\n2026: launch\n'))
    workspace = Workspace(specs=[spec], documents=[document])
    return workspace.write(tmp_path, faker)


@pytest.fixture(scope='function')
def skill_and_resource_absolute_link_root(tmp_path: Path, faker: Faker) -> Path:
    """A root holding one skill whose `SKILL.md` and whose resource each link to a file from the filesystem root.

    A run prints two `LINK001` diagnostics, one in the `SKILL.md` and one in the resource.

    Args:
        tmp_path: Directory the skill is written into, as the repository root.
        faker: The test's seeded generator, which fills what the skill leaves unset.
    """
    skill = Skill(
        'review',
        body='# Review\n\nRead [the steps](/steps.md).\n',
        references={'guide.md': '# Guide\n\nRead [the docs](/docs/guide.md).\n'},
    )
    workspace = Workspace(skills=[skill])
    return workspace.write(tmp_path, faker)


@pytest.fixture(scope='function')
def mixed_root(tmp_path: Path, faker: Faker) -> Path:
    """A root holding one subject of each kind the fixture lacks, each with something to report.

    A document in a corpus whose specification states only a frontmatter schema is ungoverned for its outline and
    its budget, and one is not UTF-8. A skill's resource links to a file the skill does not hold, and the skill holds
    a symlink leading out of the repository, to `tmp_path/shared`.

    Args:
        tmp_path: Directory the repository, `tmp_path/repository`, and the directory outside it are written into.
        faker: The test's seeded generator, which fills what each part leaves unset.
    """
    outside = Workspace(files=[File('shared/guide.md', '# Guide\n')])
    outside.write(tmp_path, faker)
    # The link climbs from the skill's directory out of `tmp_path/repository` to `tmp_path/shared`. Its target is
    # relative, so the note printing it is the same on every machine.
    skill = Skill(
        'review',
        references={'guide.md': '# Guide\n\nRead [the steps](references/missing.md).\n'},
        links={'shared': '../../../../shared'},
    )
    workspace = Workspace(
        specs=[Spec('code'), Spec('notes', structure={'frontmatter': {'type': 'object'}})],
        documents=[RawDocument('code', 'broken', b'\xff\xfe\n'), Document('notes', 'todo')],
        skills=[skill],
    )
    return workspace.write(tmp_path / 'repository', faker)


@pytest.mark.e2e
class TestCheckSnapshots:
    # Every diagnostic prints root-relative, so the output is the same in every checkout and nothing is redacted.
    # The fixture's documents carry no frontmatter and its `beta` skill is a link to `alpha` named `alpha`, so a run
    # over it reports errors and exits 1.

    def test_check_without_a_root_in_the_workspace_fixture_prints_the_diagnostics(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check',)

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the diagnostics found from the working directory match the snapshot'
        assert result.stderr == 'checked 5 subject(s): 9 error(s), 0 warning(s)\n', (
            'every document and skill of the fixture is checked, and each is governed'
        )

    def test_check_without_a_root_in_a_subdirectory_of_the_workspace_fixture_checks_the_whole_workspace(self) -> None:
        #: Given
        from_the_root = run_cli('check', cwd=WORKSPACE_FIXTURE)
        arguments = ('check',)

        #: When
        result = run_cli(*arguments, cwd=WORKSPACE_FIXTURE / 'docs' / 'code')

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == from_the_root.stdout, 'the root found upward is checked whole, not the subdirectory'
        assert result.stderr == from_the_root.stderr, 'the run counts every subject of the workspace'

    def test_check_with_a_root_over_subjects_of_every_kind_prints_each_diagnostic_and_the_coverage(
        self, snapshot: SnapshotAssertion, mixed_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', '--root', str(mixed_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the undecodable file, the broken link and the symlink match the snapshot'
        assert result.stderr == (
            'docs/notes/todo.md: ungoverned for outline, budget\nchecked 5 subject(s): 3 error(s), 0 warning(s)\n'
        ), 'the coverage line and the summary go to stderr'

    def test_check_with_json_over_subjects_of_every_kind_prints_one_document(self, mixed_root: Path) -> None:
        #: Given
        arguments = ('check', '--root', str(mixed_root), '--format', 'json')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stderr == '', 'the JSON run writes nothing beside its document'
        assert json.loads(result.stdout) == {
            'diagnostics': [
                {
                    'path': '.agents/skills/review/references/guide.md',
                    'line': 3,
                    'severity': 'error',
                    'code': 'LINK003',
                    'name': 'broken-link',
                    'message': '`references/missing.md` names nothing in the skill',
                    'labels': [],
                    'children': [
                        {
                            'kind': 'help',
                            'text': 'link a file or a directory the skill holds, relative to the skill root',
                            'path': None,
                            'line': None,
                        }
                    ],
                },
                {
                    'path': '.agents/skills/review/shared',
                    'line': None,
                    'severity': 'error',
                    'code': 'LAY001',
                    'name': 'outside-symlink',
                    'message': 'symlink leads outside the repository',
                    'labels': [],
                    'children': [
                        {
                            'kind': 'note',
                            'text': 'leaves the repository at .agents/skills/review/shared -> ../../../../shared',
                            'path': None,
                            'line': None,
                        },
                        {
                            'kind': 'help',
                            'text': 'keep every file a skill loads inside the repository',
                            'path': None,
                            'line': None,
                        },
                    ],
                },
                {
                    'path': 'docs/code/broken.md',
                    'line': None,
                    'severity': 'error',
                    'code': 'LC001',
                    'name': 'invalid-utf8',
                    'message': 'file is not valid UTF-8',
                    'labels': [],
                    'children': [],
                },
            ],
            'summary': {'subjects': 5, 'errors': 3, 'warnings': 0},
            'coverage': [{'path': 'docs/notes/todo.md', 'ungoverned': ['outline', 'budget']}],
        }, f'the document holds every diagnostic, the summary and the coverage, got {result.stdout!r}'

    def test_check_with_a_key_written_twice_prints_the_duplicate_key_diagnostics(
        self, snapshot: SnapshotAssertion, duplicate_key_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', '--root', str(duplicate_key_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, "the document's and the skill's duplicate key match the reviewed snapshot"

    def test_check_with_a_non_string_key_prints_the_diagnostic_on_its_line(
        self, snapshot: SnapshotAssertion, non_string_key_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', '--root', str(non_string_key_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, "the diagnostic on the key's line matches the reviewed snapshot"

    def test_check_with_absolute_links_in_a_skill_and_its_resource_prints_each_in_its_file(
        self, snapshot: SnapshotAssertion, skill_and_resource_absolute_link_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', '--root', str(skill_and_resource_absolute_link_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the absolute link in the SKILL.md and in the resource match the snapshot'

    def test_check_with_an_invalid_specification_prints_the_error_and_exits_two(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        # The model validates a specification when it loads, but only for a corpus whose directory exists, so the
        # corpus holds a document.
        workspace = Workspace(
            specs=[Spec('code', structure={'frontmatter': {'type': 5}})], documents=[Document('code', 'guide')]
        )
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'a run that could not start prints nothing on stdout'
        assert result.stderr == (
            'error: invalid structure schema docs/__meta__/code.structure.json: frontmatter is not a valid JSON '
            'Schema: 5 is not valid under any of the given schemas\n'
        ), 'the specification that cannot be used is reported, naming it'


@pytest.mark.e2e
class TestWorkspaceDefaults:
    # Every test that writes a workspace sets only the fields its case turns on, and relies on the rest being clean.

    def test_check_with_a_default_skill_reports_no_diagnostic(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(skills=[Skill('review')])
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stdout
        assert result.stdout == '', 'a skill whose every field but its name is generated has nothing to report'
        assert result.stderr == 'checked 1 subject(s): 0 error(s), 0 warning(s)\n', (
            'the one skill written is the one checked'
        )

    def test_check_with_a_default_spec_and_document_reports_no_diagnostic(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(specs=[Spec('code')], documents=[Document('code', 'guide')])
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stdout
        assert result.stdout == '', (
            'a document whose every field but its corpus and name is generated has nothing to report under a '
            'specification whose every field but its name is generated'
        )
        assert result.stderr == 'checked 1 subject(s): 0 error(s), 0 warning(s)\n', (
            'the one document written is the one checked, governed for every facet'
        )


@pytest.fixture(scope='function')
def linked_specs_root(tmp_path: Path, faker: Faker) -> Path:
    """A root whose `docs/__meta__` is a symlink to the workspace fixture's specifications.

    Args:
        tmp_path: Directory the link and the document are written into, as the repository root.
        faker: The test's seeded generator, which fills what the document leaves unset.
    """
    workspace = Workspace(
        documents=[Document('code', 'logging')],
        links=[Link('docs/__meta__', str(WORKSPACE_FIXTURE / 'docs' / '__meta__'))],
    )
    return workspace.write(tmp_path, faker)


@pytest.fixture(scope='function')
def linked_docs_root(tmp_path: Path, faker: Faker) -> Path:
    """A root whose `docs` is a symlink to the workspace fixture's `docs/`.

    Args:
        tmp_path: Directory the link is written into, as the repository root.
        faker: The test's seeded generator; nothing in a link is generated.
    """
    workspace = Workspace(links=[Link('docs', str(WORKSPACE_FIXTURE / 'docs'))])
    return workspace.write(tmp_path, faker)


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
