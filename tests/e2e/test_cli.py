"""The CLI as a user runs it: a real process, the installed package, and whatever git is on the box.

`version --verbose` shells out to `git describe`, so this is the only tier that can observe the probe
at all. This suite runs from the checkout, so the verbose command must report its Git description as
well as the installed version and environment; run from a copy of the package outside the checkout, or with a
`PATH` holding no git, a git that fails or one that hangs, it must leave the commit line out. Every version
output, `inspect` over a checked-in workspace fixture, and the diagnostics `check` prints over that fixture are
compared to a reviewed snapshot file under `__snapshots__/`. So are the diagnostics `check` prints for a root holding
a subject of each kind the fixture lacks (a resource of a skill, a symlink leading outside the repository, a file
that is not UTF-8, and a document no budget governs, whose coverage goes to stderr), for a root checked with
`-W LC102` and `-D warnings`, for a root whose frontmatter writes a key twice or a key that is not a string, and for a
skill and a resource each linking to an absolute path; and what `check` and `inspect` print for a root whose `docs/`
or `docs/__meta__/` is a symlink into that fixture. The JSON document `check` prints is asserted whole, once parsed,
and a selector `check` cannot use exits 2 before any document is printed. A root written from `lib.workspace`
holding one skill whose every field but its name is generated must pass `check` with no diagnostic, and so must one
holding a specification and a document under it, every field generated but their names, since every test writing
such a root sets only the fields its case turns on.
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
from lib.cli import run_alias, run_cli, usage_error_message
from lib.snapshot import JsonTextSnapshotExtension, TextSnapshotExtension
from lib.workspace import Document, File, Link, RawDocument, RawFrontmatter, Skill, Spec, Workspace
from lorecraft import __version__

# The labelled lines of `version --verbose` whose values differ per checkout, interpreter, machine and install.
_VARYING_FIELDS: Final[frozenset[str]] = frozenset({'Commit', 'Python', 'Platform', 'Install'})

# A checked-in workspace root holding each part of the model `inspect` draws: a corpus with a structure
# specification that states a frontmatter schema, a namespace spec with a structure layer, a document each governs,
# a README beside the specifications that is not one, and a skills directory two agents read, one through a
# link, holding a skill, a link to it and a link to a skill kept outside it.
# Resolved, because the CLI prints the resolved root and the tests swap exactly that string for a placeholder.
WORKSPACE_FIXTURE: Final[Path] = (Path(__file__).parent / 'fixtures' / 'workspace').resolve()
NAME_CHAINS_FIXTURE: Final[Path] = (Path(__file__).parent / 'fixtures' / 'name-chains').resolve()
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
    def test_cli_with_no_arguments_prints_the_help_and_exits_with_the_usage_status(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments: tuple[str, ...] = ()

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 2, 'a bare invocation is a usage error, not a success'
        assert result.stdout == expected, 'no_args_is_help prints the help rather than nothing'

    def test_lc_alias_with_the_version_option_prints_what_lorecraft_prints(self) -> None:
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
class TestDegradedVersionIsQuiet:
    # The version and the git description each fall back by design, so a normal run reports nothing on stderr.

    def test_version_option_from_an_uninstalled_tree_prints_the_unknown_version_and_nothing_on_stderr(
        self, tmp_path: Path
    ) -> None:
        #: Given
        # A `sitecustomize` module runs at interpreter start, before `lorecraft` is imported, and hides the
        # distribution's metadata the way a source tree that was never installed has none.
        hiding = tmp_path / 'hiding'
        hiding.mkdir()
        (hiding / 'sitecustomize.py').write_text(
            dedent(
                """\
                import importlib.metadata

                def _not_installed(name):
                    raise importlib.metadata.PackageNotFoundError(name)

                importlib.metadata.version = _not_installed
                """
            ),
            encoding='utf-8',
        )
        environment = {**os.environ, 'PYTHONPATH': str(hiding)}

        #: When
        result = run_cli('--version', env=environment)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout == 'lorecraft 0+unknown\n', 'the fallback version is printed'
        assert result.stderr == '', 'a designed fallback prints no traceback'

    def test_version_command_with_verbose_when_git_fails_prints_nothing_on_stderr(
        self, directory_with_a_failing_git: Path
    ) -> None:
        #: Given
        environment = _environment_searching(directory_with_a_failing_git)

        #: When
        result = run_cli('version', '--verbose', env=environment)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stderr == '', 'a git that cannot describe the checkout prints no traceback'


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

    def test_inspect_with_numbered_documents_governs_those_of_the_same_width_by_a_zero_run_spec(
        self, tmp_path: Path, faker: Faker, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        workspace = Workspace(
            specs=[Spec('adr'), Spec('adr-0000-nspace')],
            documents=[
                Document('adr', '0001-nspace-subject'),
                Document('adr', '0003-nspace-other'),
                Document('adr', '001-nspace-narrow'),
            ],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('inspect', str(root))

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout.replace(str(root), _ROOT_PLACEHOLDER) == expected, (
            'the four-digit documents are governed by the zero-run spec and the three-digit one is not'
        )

    def test_inspect_with_only_a_zero_run_spec_establishes_the_corpus_it_names(
        self, tmp_path: Path, faker: Faker, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        workspace = Workspace(
            specs=[Spec('adr-0000')],
            documents=[Document('adr', '0001-subject'), Document('adr', '001-narrow')],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('inspect', str(root))

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout.replace(str(root), _ROOT_PLACEHOLDER) == expected, (
            'the corpus adr exists and only the four-digit document is governed by the zero-run spec'
        )

    def test_inspect_with_a_zero_run_spec_layers_it_between_the_corpus_and_a_namespace_by_width_and_digits(
        self, tmp_path: Path, faker: Faker, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        workspace = Workspace(
            specs=[Spec('adr'), Spec('adr-0000'), Spec('adr-0000-nspace')],
            documents=[
                Document('adr', '0001-subject'),
                Document('adr', '0002-nspace'),
                Document('adr', '00001-wide'),
                Document('adr', '0a01-letter'),
            ],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('inspect', str(root))

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout.replace(str(root), _ROOT_PLACEHOLDER) == expected, (
            'four-digit documents get the three layers broad to narrow, a name ending at the prefix included, '
            'and the wider and letter-bearing ones get the corpus spec only'
        )

    def test_inspect_with_a_literal_numbered_spec_chains_it_to_the_corpus_and_not_to_other_numbers(
        self, tmp_path: Path, faker: Faker, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        workspace = Workspace(
            specs=[Spec('adr'), Spec('adr-0000'), Spec('adr-0001-x')],
            documents=[Document('adr', '0001-x'), Document('adr', '0000-x-y')],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('inspect', str(root))

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout.replace(str(root), _ROOT_PLACEHOLDER) == expected, (
            'the literal spec has the corpus as its base, and the 0000 document does not chain to 0001'
        )

    def test_inspect_with_timestamp_specs_governs_matching_document_precisions_and_rejects_invalid_values(
        self, tmp_path: Path, faker: Faker, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        workspace = Workspace(
            specs=[
                Spec('adr'),
                Spec('adr-YYYY'),
                Spec('adr-YYYYMM'),
                Spec('adr-YYYYMMDD'),
                Spec('adr-YYYYMMDDHH'),
                Spec('adr-YYYYMMDDHHMM'),
                Spec('adr-YYYYMMDDHHMMSS'),
                Spec('adr-YYYYMMDDHHMMSSZZZ'),
            ],
            documents=[
                Document('adr', '2024-valid'),
                Document('adr', '202402-valid'),
                Document('adr', '20240229-valid'),
                Document('adr', '2024022923-valid'),
                Document('adr', '202402292359-valid'),
                Document('adr', '20240229235959-valid'),
                Document('adr', '20240229235959UTC-valid'),
                Document('adr', '20230229-invalid'),
                Document('adr', '2024022924-invalid'),
                Document('adr', '20240229235960-invalid'),
                Document('adr', '202402292359590-invalid'),
            ],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('inspect', str(root))

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout.replace(str(root), _ROOT_PLACEHOLDER) == expected, (
            'the tree shows every timestamp precision governing its valid document and leaves malformed values '
            'unmatched'
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

    def test_inspect_with_name_chains_prints_their_hierarchies(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('inspect', str(NAME_CHAINS_FIXTURE))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout.replace(str(NAME_CHAINS_FIXTURE), _ROOT_PLACEHOLDER) == expected, (
            'the text tree shows spec and document chains, including skipped prefixes'
        )

    def test_inspect_json_with_name_chains_returns_both_hierarchies(self) -> None:
        #: Given
        expected = {
            'root': _ROOT_PLACEHOLDER,
            'corpora': [
                {
                    'name': 'code',
                    'directory': 'docs/code',
                    'specs': [
                        {'name': 'code', 'files': ['docs/__meta__/code.spec.json'], 'base': None},
                        {
                            'name': 'code-python',
                            'files': ['docs/__meta__/code-python.spec.json'],
                            'base': 'code',
                        },
                        {
                            'name': 'code-fn-names',
                            'files': ['docs/__meta__/code-fn-names.spec.json'],
                            'base': 'code',
                        },
                        {
                            'name': 'code-python-typing',
                            'files': ['docs/__meta__/code-python-typing.spec.json'],
                            'base': 'code-python',
                        },
                    ],
                    'documents': [
                        {
                            'path': 'docs/code/guide.md',
                            'governed_by': ['docs/__meta__/code.spec.json'],
                            'base_chain': ['docs/code/guide.md'],
                        },
                        {
                            'path': 'docs/code/guide-api.md',
                            'governed_by': ['docs/__meta__/code.spec.json'],
                            'base_chain': ['docs/code/guide.md', 'docs/code/guide-api.md'],
                        },
                        {
                            'path': 'docs/code/guide-api-names.md',
                            'governed_by': ['docs/__meta__/code.spec.json'],
                            'base_chain': [
                                'docs/code/guide.md',
                                'docs/code/guide-api.md',
                                'docs/code/guide-api-names.md',
                            ],
                        },
                        {
                            'path': 'docs/code/guide-fn-names.md',
                            'governed_by': ['docs/__meta__/code.spec.json'],
                            'base_chain': ['docs/code/guide.md', 'docs/code/guide-fn-names.md'],
                        },
                        {
                            'path': 'docs/code/overview.md',
                            'governed_by': ['docs/__meta__/code.spec.json'],
                            'base_chain': ['docs/code/overview.md'],
                        },
                        {
                            'path': 'docs/code/python-typing.md',
                            'governed_by': [
                                'docs/__meta__/code.spec.json',
                                'docs/__meta__/code-python.spec.json',
                                'docs/__meta__/code-python-typing.spec.json',
                            ],
                            'base_chain': ['docs/code/python-typing.md'],
                        },
                    ],
                }
            ],
            'agent_skills_dirs': [],
            'skills': [],
        }
        arguments = ('inspect', str(NAME_CHAINS_FIXTURE), '--format', 'json')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        actual = json.loads(result.stdout.replace(str(NAME_CHAINS_FIXTURE), _ROOT_PLACEHOLDER))
        assert actual == expected, 'the whole JSON document keeps the spec and document chains separate'


@pytest.fixture(scope='function')
def invalid_spec_root(tmp_path: Path, faker: Faker) -> Path:
    """A root holding one document under a specification whose frontmatter schema cannot be used.

    Args:
        tmp_path: Directory the specification and the document are written into, as the repository root.
        faker: The test's seeded generator, which fills what the document leaves unset.
    """
    # The model validates a specification when it loads, but only for a corpus whose directory exists, so the corpus
    # holds a document.
    workspace = Workspace(
        specs=[Spec('code', structure={'frontmatter': {'type': 5}})], documents=[Document('code', 'guide')]
    )
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


@pytest.fixture(scope='function')
def default_deny_lc102_root(tmp_path: Path, faker: Faker) -> Path:
    """A root whose only diagnostic is LC102 on a symlink that leaves the repository.

    Args:
        tmp_path: Directory the repository root is written into.
        faker: The seeded generator, which fills the valid skill's generated fields.
    """
    workspace = Workspace(skills=[Skill('review', links={'shared': '../../../../outside'})])
    return workspace.write(tmp_path, faker)


@pytest.mark.e2e
class TestCheckCommand:
    # Every diagnostic prints root-relative, so the output is the same in every checkout and nothing is redacted.
    # The fixture's documents carry no frontmatter and its `beta` skill is a link to `alpha` named `alpha`, so a run
    # over it reports errors and exits 1.

    def test_check_help_shows_option_descriptions_without_a_duplicate_args_section(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', '--help')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout == expected, 'the check help matches the reviewed snapshot'
        assert 'Args:' not in result.stdout, 'option descriptions are not repeated in an Args section'
        lines = result.stdout.splitlines()
        root_option = next(line for line in lines if '--root' in line)
        format_option = next(line for line in lines if '--format' in line)
        color_option = next(line for line in lines if '--color' in line)
        allow_option = next(line for line in lines if '--allow' in line)
        warn_option = next(line for line in lines if '--warn' in line)
        deny_option = next(line for line in lines if '--deny' in line)
        help_option = next(line for line in lines if '--help' in line)
        assert 'Repository root.' in root_option, 'the root description is beside its option'
        assert 'Output format:' in format_option, 'the format description is beside its option'
        assert 'Control when colored output is used.' in color_option, 'the color description is beside its option'
        assert 'Allow this rule or ALL;' in allow_option, 'the allow description is beside its option'
        assert 'Warn on this rule or ALL;' in warn_option, 'the warn description is beside its option'
        assert 'Deny this rule, ALL, or warnings;' in deny_option, 'the deny description is beside its option'
        assert 'Show this message and exit.' in help_option, 'the help description is beside its option'

    def test_check_with_warn_and_deny_warnings_on_default_deny_lc102_keeps_its_error_level(
        self, snapshot: SnapshotAssertion, default_deny_lc102_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', '--root', str(default_deny_lc102_root), '-W', 'LC102', '-D', 'warnings')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the default-deny diagnostic has no warning-elevation note'
        assert '-D warnings elevated warning to error' not in result.stdout, 'the default error is not elevated again'

    def test_check_with_warn_and_deny_warnings_on_default_deny_lc102_reports_default_json_provenance(
        self, snapshot: SnapshotAssertion, default_deny_lc102_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(JsonTextSnapshotExtension)
        arguments = (
            'check',
            '--root',
            str(default_deny_lc102_root),
            '-W',
            'LC102',
            '-D',
            'warnings',
            '--format',
            'json',
        )

        #: When
        result = run_cli(*arguments)
        document = json.loads(result.stdout)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stderr == '', 'the JSON report is the only output'
        assert result.stdout == expected, 'the JSON report retains default provenance'
        assert document['diagnostics'][0]['level_source'] == 'default', 'the warning override resets to default'

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
        assert result.stderr == (
            '.agents/skills/alpha/SKILL.md: ungoverned for structure, outline\n'
            '.agents/skills/beta/SKILL.md: ungoverned for structure, outline\n'
            '.agents/skills/gamma/SKILL.md: ungoverned for structure, outline\n'
            'docs/__meta__/code-python.md: ungoverned for frontmatter, structure, outline, budget\n'
            'docs/__meta__/code.md: ungoverned for frontmatter, structure, outline, budget\n'
            'LC2xx  3 errors\nLC3xx  5 errors\nLC4xx  1 error\nchecked 7 subject(s): 9 error(s), 0 warning(s)\n'
        ), 'every document and skill of the fixture is checked, and each is governed'

    def test_check_reports_a_refused_structure_file_as_lc002(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(specs=[Spec('code')], documents=[Document('code', 'guide')])
        root = workspace.write(tmp_path, faker)
        if not hasattr(os, 'geteuid') or os.geteuid() == 0:
            pytest.skip('permission bits do not refuse reads when the test process is root')
        (root / 'docs' / '__meta__' / 'code.spec.json').chmod(0)

        #: When
        try:
            result = run_cli('check', '--root', str(root))
        finally:
            (root / 'docs' / '__meta__' / 'code.spec.json').chmod(0o644)

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC002' in result.stdout, 'a refused structure specification remains a load diagnostic'

    def test_check_reports_a_refused_corpus_directory_as_lc002(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(specs=[Spec('code')], documents=[Document('code', 'guide')])
        root = workspace.write(tmp_path, faker)
        if not hasattr(os, 'geteuid') or os.geteuid() == 0:
            pytest.skip('permission bits do not refuse reads when the test process is root')
        (root / 'docs' / 'code').chmod(0)

        #: When
        try:
            result = run_cli('check', '--root', str(root))
        finally:
            (root / 'docs' / 'code').chmod(0o755)

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC002' in result.stdout, 'a refused corpus listing remains a load diagnostic'

    @pytest.mark.parametrize(
        ('kind', 'target'),
        [
            ('document', 'docs/code/guide.md'),
            ('spec', 'docs/__meta__/code.md'),
            ('skill entrypoint', '.agents/skills/review/SKILL.md'),
            ('resource', '.agents/skills/review/references/guide.md'),
        ],
    )
    def test_check_reports_a_refused_item_read_as_skipped_coverage(
        self,
        kind: str,
        target: str,
        snapshot: SnapshotAssertion,
        tmp_path: Path,
        faker: Faker,
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        workspace = Workspace(
            specs=[Spec('code', prose='# Code\n')],
            documents=[Document('code', 'guide')],
            skills=[Skill('review', references={'guide.md': '# Guide\n'})],
        )
        root = workspace.write(tmp_path / 'repository', faker)
        refused_path = root / target
        if not hasattr(os, 'geteuid') or os.geteuid() == 0:
            pytest.skip('permission bits do not refuse reads when the test process is root')
        refused_path.chmod(0)
        arguments = ('check', '--root', str(root))

        #: When
        try:
            result = run_cli(*arguments)
        finally:
            refused_path.chmod(0o644)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout == expected, f'the refused {kind} is represented by skipped coverage alone'
        assert 'error[LC002]: path cannot be read' not in result.stdout
        assert f'{target}: skipped, read refused at: {target}' in result.stderr

    def test_check_reports_a_refused_document_in_short_format(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        root = Workspace(specs=[Spec('code')], documents=[Document('code', 'guide')]).write(tmp_path, faker)
        if not hasattr(os, 'geteuid') or os.geteuid() == 0:
            pytest.skip('permission bits do not refuse reads when the test process is root')
        (root / 'docs' / 'code' / 'guide.md').chmod(0)

        #: When
        try:
            result = run_cli('check', '--root', str(root), '--format', 'short')
        finally:
            (root / 'docs' / 'code' / 'guide.md').chmod(0o644)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout == '', 'a refused document produces coverage instead of a diagnostic in short format'
        assert 'docs/code/guide.md: skipped, read refused at: docs/code/guide.md' in result.stderr

    def test_check_reports_a_refused_document_in_json_coverage(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        root = Workspace(specs=[Spec('code')], documents=[Document('code', 'guide')]).write(tmp_path, faker)
        if not hasattr(os, 'geteuid') or os.geteuid() == 0:
            pytest.skip('permission bits do not refuse reads when the test process is root')
        (root / 'docs' / 'code' / 'guide.md').chmod(0)

        #: When
        try:
            result = run_cli('check', '--root', str(root), '--format', 'json')
            document = json.loads(result.stdout)
        finally:
            (root / 'docs' / 'code' / 'guide.md').chmod(0o644)

        #: Then
        assert result.returncode == 0, result.stderr
        assert document['coverage'] == [
            {
                'path': 'docs/code/guide.md',
                'ungoverned': [],
                'cause': 'refused-path',
                'skipped_by': ['docs/code/guide.md'],
            }
        ], 'JSON records a refused item read as skipped coverage'

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
            '.agents/skills/review/SKILL.md: ungoverned for structure, outline\n'
            'docs/notes/todo.md: ungoverned for outline, budget\n'
            'LC0xx  1 error\nLC1xx  1 error\nLC5xx  1 error\n'
            'checked 5 subject(s): 3 error(s), 0 warning(s)\n'
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
                    'code': 'LC503',
                    'name': 'broken-link',
                    'level_source': 'default',
                    'message': '`references/missing.md` names nothing',
                    'labels': [],
                    'children': [
                        {
                            'kind': 'note',
                            'text': "the Agent Skills specification reads a skill's relative links from the skill root",
                            'path': None,
                            'line': None,
                        },
                        {
                            'kind': 'help',
                            'text': 'link a file or a directory the skill holds, relative to the skill root',
                            'path': None,
                            'line': None,
                        },
                        {
                            'kind': 'note',
                            'text': 'read from the skill root, it names `.agents/skills/review/references/missing.md`',
                            'path': None,
                            'line': None,
                        },
                    ],
                },
                {
                    'path': '.agents/skills/review/shared',
                    'line': None,
                    'severity': 'error',
                    'code': 'LC102',
                    'name': 'escaping-symlink',
                    'level_source': 'default',
                    'message': 'symlink leads outside the repository',
                    'labels': [],
                    'children': [
                        {
                            'kind': 'help',
                            'text': (
                                'a `..` on the chain climbs above the repository root; '
                                'move what it links to into the repository'
                            ),
                            'path': None,
                            'line': None,
                        },
                        {
                            'kind': 'note',
                            'text': 'leaves the repository at .agents/skills/review/shared -> ../../../../shared',
                            'path': None,
                            'line': None,
                        },
                    ],
                },
                {
                    'path': 'docs/code/broken.md',
                    'line': 1,
                    'severity': 'error',
                    'code': 'LC001',
                    'name': 'invalid-utf8',
                    'level_source': 'default',
                    'message': 'file is not valid UTF-8',
                    'labels': [
                        {
                            'path': 'docs/code/broken.md',
                            'line': 1,
                            'text': '0xFF at byte offset 0 cannot start a character',
                        }
                    ],
                    'children': [{'kind': 'help', 'text': 'save the file as UTF-8', 'path': None, 'line': None}],
                },
            ],
            'summary': {'subjects': 5, 'errors': 3, 'warnings': 0},
            'coverage': [
                {
                    'path': '.agents/skills/review/SKILL.md',
                    'ungoverned': ['structure', 'outline'],
                    'cause': None,
                    'skipped_by': [],
                },
                {
                    'path': 'docs/notes/todo.md',
                    'ungoverned': ['outline', 'budget'],
                    'cause': None,
                    'skipped_by': [],
                },
            ],
        }, f'the document holds every diagnostic, the summary and the coverage, got {result.stdout!r}'

    def test_check_with_a_removed_select_option_refuses_with_usage_error(
        self, snapshot: SnapshotAssertion, mixed_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', '--root', str(mixed_root), '--select', 'LINK,LC102')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'a rejected option prints no diagnostics'
        assert usage_error_message(result.stderr) == expected, 'the removed --select option is named in the usage error'

    def test_check_with_a_removed_select_option_and_json_refuses_with_usage_error(
        self, snapshot: SnapshotAssertion, mixed_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', '--root', str(mixed_root), '--select', 'NOPE', '--format', 'json')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'a rejected option prints no document'
        assert usage_error_message(result.stderr) == expected, 'the removed --select option is named in the usage error'

    def test_check_with_a_prefix_level_flag_refuses_before_discovering_the_root(
        self, snapshot: SnapshotAssertion, tmp_path: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        missing_root = tmp_path / 'missing-root'
        arguments = ('check', '--root', str(missing_root), '-W', 'LC3')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'a rejected level selector prints no diagnostics'
        assert usage_error_message(result.stderr) == expected, 'the invalid prefix is named before root discovery'

    def test_check_with_an_unknown_code_refuses_before_discovering_the_root(self, tmp_path: Path) -> None:
        #: Given
        missing_root = tmp_path / 'missing-root'
        arguments = ('check', '--root', str(missing_root), '-W', 'LC999')

        #: When
        result = run_cli(*arguments)

        #: Then
        message = usage_error_message(result.stderr)
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'an unknown code is rejected before checking'
        assert 'LC999' in message, 'the usage error names the unknown value'
        assert '-W' in message, 'the usage error names the flag'
        assert 'No such file or directory' not in message, 'validation happens before root discovery'

    def test_check_with_a_group_refuses_before_discovering_the_root(self, tmp_path: Path) -> None:
        #: Given
        missing_root = tmp_path / 'missing-root'
        arguments = ('check', '--root', str(missing_root), '-W', 'LC')

        #: When
        result = run_cli(*arguments)

        #: Then
        message = usage_error_message(result.stderr)
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'a group is rejected before checking'
        assert 'LC' in message, 'the usage error names the group'
        assert '-W' in message, 'the usage error names the flag'
        assert 'No such file or directory' not in message, 'validation happens before root discovery'

    def test_check_with_a_rule_name_refuses_before_discovering_the_root(self, tmp_path: Path) -> None:
        #: Given
        missing_root = tmp_path / 'missing-root'
        arguments = ('check', '--root', str(missing_root), '-W', 'empty-section')

        #: When
        result = run_cli(*arguments)

        #: Then
        message = usage_error_message(result.stderr)
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'a rule name is rejected before checking'
        assert 'empty-section' in message, 'the usage error names the rule name'
        assert '-W' in message, 'the usage error names the flag'
        assert 'No such file or directory' not in message, 'validation happens before root discovery'

    def test_check_with_an_engine_condition_refuses_before_discovering_the_root(self, tmp_path: Path) -> None:
        #: Given
        missing_root = tmp_path / 'missing-root'
        arguments = ('check', '--root', str(missing_root), '-W', 'LC001')

        #: When
        result = run_cli(*arguments)

        #: Then
        message = usage_error_message(result.stderr)
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'an engine condition is rejected before checking'
        assert 'LC001' in message, 'the usage error names the engine condition code'
        assert '-W' in message, 'the usage error names the flag'
        assert 'No such file or directory' not in message, 'validation happens before root discovery'

    def test_check_with_an_empty_level_value_refuses_before_discovering_the_root(self, tmp_path: Path) -> None:
        #: Given
        missing_root = tmp_path / 'missing-root'
        arguments = ('check', '--root', str(missing_root), '-W', '')

        #: When
        result = run_cli(*arguments)

        #: Then
        message = usage_error_message(result.stderr)
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'an empty value is rejected before checking'
        assert "''" in message, 'the usage error names the empty value'
        assert '-W' in message, 'the usage error names the flag'
        assert 'No such file or directory' not in message, 'validation happens before root discovery'

    def test_check_with_lowercase_all_refuses_before_discovering_the_root(self, tmp_path: Path) -> None:
        #: Given
        missing_root = tmp_path / 'missing-root'
        arguments = ('check', '--root', str(missing_root), '-W', 'all')

        #: When
        result = run_cli(*arguments)

        #: Then
        message = usage_error_message(result.stderr)
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'lowercase all is rejected before checking'
        assert 'all' in message, 'the usage error names lowercase all'
        assert '-W' in message, 'the usage error names the flag'
        assert 'No such file or directory' not in message, 'validation happens before root discovery'

    def test_check_with_warnings_on_allow_flag_rejects_before_discovering_the_root(self, tmp_path: Path) -> None:
        #: Given
        missing_root = tmp_path / 'missing-root'
        arguments = ('check', '--root', str(missing_root), '-A', 'warnings')

        #: When
        result = run_cli(*arguments)

        #: Then
        message = usage_error_message(result.stderr)
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'warnings is not valid for -A'
        assert 'warnings' in message, 'the usage error names the reserved value'
        assert '-A' in message, 'the usage error names the flag'
        assert 'No such file or directory' not in message, 'validation happens before root discovery'

    def test_check_with_warnings_on_warn_flag_rejects_before_discovering_the_root(self, tmp_path: Path) -> None:
        #: Given
        missing_root = tmp_path / 'missing-root'
        arguments = ('check', '--root', str(missing_root), '-W', 'warnings')

        #: When
        result = run_cli(*arguments)

        #: Then
        message = usage_error_message(result.stderr)
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'warnings is not valid for -W'
        assert 'warnings' in message, 'the usage error names the reserved value'
        assert '-W' in message, 'the usage error names the flag'
        assert 'No such file or directory' not in message, 'validation happens before root discovery'

    def test_check_with_a_repeated_level_for_one_code_reaches_root_discovery(self, tmp_path: Path) -> None:
        #: Given
        missing_root = tmp_path / 'missing-root'
        arguments = ('check', '--root', str(missing_root), '-W', 'LC101', '-W', 'LC101')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert 'is not an existing directory' in result.stderr, result.stderr
        assert 'Error: Invalid value' not in result.stderr, 'a repeated matching level is accepted'

    def test_check_with_all_and_a_specific_code_at_different_levels_reaches_root_discovery(
        self, tmp_path: Path
    ) -> None:
        #: Given
        root = tmp_path
        arguments = ('check', '--root', str(root), '-A', 'ALL', '-D', 'LC101')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert 'checked 0 subject(s)' in result.stderr, 'the accepted levels reach the check run'
        assert 'Invalid value' not in result.stderr, 'a specific code may override ALL at another level'

    def test_check_with_denied_warnings_and_all_allowed_reaches_root_discovery(self, tmp_path: Path) -> None:
        #: Given
        root = tmp_path
        arguments = ('check', '--root', str(root), '-D', 'warnings', '-A', 'ALL')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert 'checked 0 subject(s)' in result.stderr, 'the accepted levels reach the check run'
        assert 'Invalid value' not in result.stderr, 'warnings and ALL may be assigned together'

    def test_check_with_allow_for_a_warning_rule_silences_it(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            files=[File('docs/skills/guide.md', '# Guide\n')],
            specs=[Spec('skills', structure={'frontmatter': {'type': 'object'}})],
        )
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root), '-A', 'LC101')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout == '', 'allowing LC101 removes its warning from the report'

    def test_check_with_a_code_denied_after_all_is_allowed_uses_the_code_level(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            files=[File('docs/skills/guide.md', '# Guide\n')],
            specs=[Spec('skills', structure={'frontmatter': {'type': 'object'}})],
        )
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root), '-A', 'ALL', '-D', 'LC101')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'error[LC101]' in result.stdout, 'the specific deny overrides the allow-all setting'
        assert 'error[LC' not in result.stdout.replace('error[LC101]', ''), 'only the specifically denied rule runs'

    def test_check_with_a_code_denied_before_all_is_allowed_uses_the_code_level(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            files=[File('docs/skills/guide.md', '# Guide\n')],
            specs=[Spec('skills', structure={'frontmatter': {'type': 'object'}})],
        )
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root), '-D', 'LC101', '-A', 'ALL')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'error[LC101]' in result.stdout, 'the specific deny overrides allow-all in either order'
        assert 'error[LC' not in result.stdout.replace('error[LC101]', ''), 'only the specifically denied rule runs'

    def test_check_with_denied_warnings_fails_a_run_with_only_warnings(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            files=[File('docs/skills/guide.md', '# Guide\n')],
            specs=[Spec('skills', structure={'frontmatter': {'type': 'object'}})],
        )
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root), '-D', 'warnings')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'error[LC101]' in result.stdout, 'warning elevation makes the warning fail the run'
        assert 'error[LC' not in result.stdout.replace('error[LC101]', ''), 'the run contains only the warning rule'

    def test_check_with_denied_warnings_notes_command_line_provenance_in_text(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            files=[File('docs/skills/guide.md', '# Guide\n')],
            specs=[Spec('skills', structure={'frontmatter': {'type': 'object'}})],
        )
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root), '-D', 'warnings')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert '= note: -D warnings elevated warning to error' in result.stdout, (
            'the text report explains the command-line severity change'
        )

    def test_check_with_denied_warnings_reports_cli_level_source_in_json(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            files=[File('docs/skills/guide.md', '# Guide\n')],
            specs=[Spec('skills', structure={'frontmatter': {'type': 'object'}})],
        )
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root), '-D', 'warnings', '--format', 'json')

        #: When
        result = run_cli(*arguments)
        document = json.loads(result.stdout)

        #: Then
        assert result.returncode == 1, result.stderr
        assert document['diagnostics'][0]['code'] == 'LC101', 'the JSON report contains the warning rule'
        assert document['diagnostics'][0]['level_source'] == 'cli', 'the JSON report marks CLI provenance'

    def test_check_with_conflicting_code_levels_names_the_canonical_code_before_root_discovery(
        self, snapshot: SnapshotAssertion, tmp_path: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        missing_root = tmp_path / 'missing-root'
        arguments = ('check', '--root', str(missing_root), '-A', 'LC304', '-D', 'LC304')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'conflicting levels print no diagnostics'
        assert usage_error_message(result.stderr) == expected, 'the conflict names canonical code LC304'

    def test_check_with_conflicting_all_levels_names_the_level_flags_before_root_discovery(
        self, snapshot: SnapshotAssertion, tmp_path: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        missing_root = tmp_path / 'missing-root'
        arguments = ('check', '--root', str(missing_root), '-A', 'ALL', '-D', 'ALL')

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 2, result.stderr
        assert result.stdout == '', 'conflicting levels print no diagnostics'
        assert usage_error_message(result.stderr) == expected, 'the conflict names the level flags involved'

    def test_check_with_a_key_written_twice_prints_the_duplicate_key_diagnostics(
        self, snapshot: SnapshotAssertion, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        # The frontmatter check governs a document only when its corpus specification states a frontmatter schema; this
        # one accepts any mapping, so the repeated key is all it reports.
        spec = Spec('code', structure={'frontmatter': {'type': 'object'}})
        document = Document('code', 'guide', frontmatter=RawFrontmatter('name: guide\ntype: rule\ntype: pattern\n'))
        skill = Skill(
            'review',
            frontmatter=RawFrontmatter('name: review\ndescription: Review a change\ndescription: Audit a change\n'),
        )
        workspace = Workspace(specs=[spec], documents=[document], skills=[skill])
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, "the document's and the skill's duplicate key match the reviewed snapshot"

    def test_check_with_a_non_string_key_prints_the_diagnostic_on_its_line(
        self, snapshot: SnapshotAssertion, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        # `jsonschema` matches a `patternProperties` pattern against every key, so a key that is not a string would
        # crash the run if the frontmatter decoded with it.
        spec = Spec('code', structure={'frontmatter': {'type': 'object', 'patternProperties': {'^x-': {}}}})
        document = Document('code', 'guide', frontmatter=RawFrontmatter('name: guide\n2026: launch\n'))
        workspace = Workspace(specs=[spec], documents=[document])
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, "the diagnostic on the key's line matches the reviewed snapshot"

    def test_check_with_absolute_links_in_a_skill_and_its_resource_prints_each_in_its_file(
        self, snapshot: SnapshotAssertion, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        skill = Skill(
            'review',
            body='# Review\n\nRead [the steps](/steps.md).\n',
            references={'guide.md': '# Guide\n\nRead [the docs](/docs/guide.md).\n'},
        )
        workspace = Workspace(skills=[skill])
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the absolute link in the SKILL.md and in the resource match the snapshot'

    def test_check_with_a_nested_skill_behind_an_alias_names_its_missing_resource_from_the_deepest_skill(
        self, snapshot: SnapshotAssertion, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        workspace = Workspace(
            files=[
                File('.agents/skills/inner/foo/SKILL.md', '---\nname: foo\ndescription: Nested skill\n---\n'),
                File('.agents/skills/inner/foo/ref.md', '# Reference\n\nRead [the missing file](missing.md).\n'),
            ],
            links=[Link('.claude/skills', '../.agents/skills/inner')],
        )
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the LC503 note resolves the resource from foo on every run'

    def test_check_with_an_invalid_specification_prints_it_as_a_diagnostic_on_stdout(
        self, snapshot: SnapshotAssertion, invalid_spec_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', '--root', str(invalid_spec_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout == expected, 'the specification that cannot be used is a diagnostic at it'

    def test_check_with_an_invalid_specification_lists_what_it_governs_as_ungoverned_on_stderr(
        self, snapshot: SnapshotAssertion, invalid_spec_root: Path
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ('check', '--root', str(invalid_spec_root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stderr == expected, 'the full rule range label is shown in coverage'


@pytest.mark.e2e
class TestGovernanceCoverage:
    def test_check_with_timestamp_specs_governs_valid_documents_and_leaves_invalid_values_unmatched(
        self, tmp_path: Path, faker: Faker, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        workspace = Workspace(
            specs=[
                Spec('adr'),
                Spec('adr-YYYY'),
                Spec('adr-YYYYMM'),
                Spec('adr-YYYYMMDD'),
                Spec('adr-YYYYMMDDHH'),
                Spec('adr-YYYYMMDDHHMM'),
                Spec('adr-YYYYMMDDHHMMSS'),
                Spec('adr-YYYYMMDDHHMMSSZZZ'),
            ],
            documents=[
                Document('adr', '2024-valid'),
                Document('adr', '202402-valid'),
                Document('adr', '20240229-valid'),
                Document('adr', '2024022923-valid'),
                Document('adr', '202402292359-valid'),
                Document('adr', '20240229235959-valid'),
                Document('adr', '20240229235959UTC-valid'),
                Document('adr', '20230229-invalid'),
                Document('adr', '2024022924-invalid'),
                Document('adr', '20240229235960-invalid'),
                Document('adr', '202402292359590-invalid'),
            ],
        )
        root = workspace.write(tmp_path, faker)
        arguments = ('check', '--root', str(root))

        #: When
        result = run_cli(*arguments)

        #: Then
        assert result.returncode == 0, result.stdout
        assert result.stdout == '', 'all timestamp documents are valid under the default specifications'
        assert result.stderr == expected, 'all eleven listed documents are checked without findings'

    def test_check_with_a_gap_in_numbered_documents_reports_no_error(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            specs=[Spec('adr'), Spec('adr-0000-nspace')],
            documents=[Document('adr', '0001-nspace-subject'), Document('adr', '0003-nspace-other')],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 0, result.stdout
        assert 'checked 2 subject(s): 0 error(s), 0 warning(s)' in result.stderr, (
            'the digit-leading documents are checked, and the missing 0002 is not reported'
        )

    def test_check_with_only_a_zero_run_spec_checks_the_documents_of_its_width(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[Spec('adr-0000', structure={'frontmatter': {'type': 'object', 'required': ['owner']}})],
            documents=[Document('adr', '0001-subject'), Document('adr', '001-narrow')],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC206' in result.stdout, 'the zero-run spec rule is checked without a corpus spec'
        assert '0001-subject' in result.stdout, 'the four-digit document is the one reported'
        assert '--> docs/adr/001-narrow.md' not in result.stdout, (
            'the three-digit document is not checked against the rule'
        )

    def test_check_applies_a_numbered_namespace_spec_to_matching_documents_only(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[
                Spec('adr'),
                Spec('adr-0000'),
                Spec('adr-0000-nspace', structure={'frontmatter': {'type': 'object', 'required': ['owner']}}),
            ],
            documents=[Document('adr', '0001-subject'), Document('adr', '0002-nspace')],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC206' in result.stdout, 'the namespace rule is checked on the matching document'
        assert '0002-nspace' in result.stdout, 'the matching document is the one reported'
        assert '0001-subject' not in result.stdout, 'the document outside the namespace is not reported'

    def test_check_applies_skills_namespace_spec_to_matching_skill_namespaces(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[
                Spec('skills', structure={'frontmatter': {'type': 'object'}}),
                Spec('skills-review', structure={'frontmatter': {'type': 'object', 'required': ['owner']}}),
            ],
            skills=[Skill('review-a', frontmatter=RawFrontmatter('name: review-a\ndescription: Review\n'))],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'missing required field `owner`' in result.stdout, 'the matching namespace spec governs the skill'

    def test_check_does_not_apply_a_skills_namespace_spec_to_an_unmatched_name(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[
                Spec('skills', structure={'frontmatter': {'type': 'object'}}),
                Spec('skills-review', structure={'frontmatter': {'type': 'object', 'required': ['owner']}}),
            ],
            skills=[Skill('writing', frontmatter=RawFrontmatter('name: writing\ndescription: Writing\n'))],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 0, result.stdout
        assert 'owner' not in result.stdout, 'the review namespace does not govern unrelated skills'

    def test_check_does_not_govern_skill_resources_with_skill_frontmatter_specs(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[Spec('skills', structure={'frontmatter': {'type': 'object', 'required': ['owner']}})],
            skills=[Skill('review', references={'guide.md': '---\nname: guide\n---\n# Guide\n'})],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert '.agents/skills/review/references/guide.md' not in result.stdout, (
            'resources have no skills frontmatter gate'
        )
        assert 'missing required field `owner`' in result.stdout, 'the entrypoint remains governed'

    def test_check_reports_a_reserved_skills_corpus(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            files=[File('docs/skills/guide.md', '# Guide\n')],
            specs=[Spec('skills', structure={'frontmatter': {'type': 'object'}})],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 0, result.stderr
        assert 'warning[LC101]' in result.stdout, 'docs/skills is reserved for skill entrypoints'
        assert 'docs/skills/guide.md' not in result.stdout, 'reserved-corpus contents are not checked as documents'

    def test_check_reports_links_when_a_document_spec_fails_to_load(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            specs=[Spec('code', structure={'frontmatter': {'type': 5}})],
            documents=[Document('code', 'guide', body='# Guide\n\n[Outside](../../../outside.md)\n')],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC504' in result.stdout, 'Always link rules still run while spec-gated checks are suppressed'
        assert 'LC5xx  1 error' in result.stderr, 'the Always finding is counted with the failed-layer finding'

    def test_check_keeps_link_rules_when_the_skills_floor_is_opted_out(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(skills=[Skill('review', body='# Review\n\n[Outside](../../../../outside.md)\n')])
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('--no-agent-skills-spec', 'check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC504' in result.stdout, 'link rules are independent of the builtin skills layer'

    def test_check_deduplicates_a_missing_field_reported_by_two_skill_layers(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[
                Spec('skills', structure={'frontmatter': {'type': 'object', 'required': ['description']}}),
                Spec('skills-review', structure={'frontmatter': {'type': 'object', 'required': ['description']}}),
            ],
            skills=[Skill('review-a', frontmatter=RawFrontmatter('name: review-a\n'))],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout.count('missing required field `description`') == 1, (
            'the same absent field is reported once across governing layers'
        )

    def test_check_uses_the_frontmatter_name_rule_for_documents(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            specs=[Spec('code')],
            documents=[Document('code', 'guide', frontmatter=RawFrontmatter('name: another\ndescription: Guide\n'))],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC204' in result.stdout, 'a document frontmatter name must match its file name'

    def test_check_uses_the_frontmatter_name_rule_for_specs(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            specs=[
                Spec('meta', structure={'frontmatter': {'type': 'object'}}),
                Spec(
                    'code',
                    prose='---\nname: another\ndescription: Code specification\n---\n\n# Code\n',
                ),
            ],
            documents=[Document('code', 'guide')],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC204' in result.stdout, 'a specification frontmatter name must match the spec file name'

    def test_check_runs_link_rules_without_a_structure_file(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(skills=[Skill('review', body='# Review\n\n[Outside](../../../outside.md)\n')])
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC504' in result.stdout, 'Always link rules do not require a structure file'


@pytest.mark.e2e
class TestRemainingGovernanceRules:
    def test_meta_namespace_spec_matches_its_corpus_and_hyphen_extensions_only(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[
                Spec('meta', structure={'frontmatter': {'type': 'object'}}),
                Spec('meta-code', structure={'frontmatter': {'type': 'object', 'required': ['owner']}}),
                Spec('code', prose='---\nname: code\n---\n\n# Code\n'),
                Spec('code-python', prose='---\nname: code-python\n---\n\n# Python\n'),
                Spec('codez', prose='---\nname: codez\n---\n\n# Code Z\n'),
            ]
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'docs/__meta__/code.md' in result.stdout, 'the corpus-name spec is governed by meta-code'
        assert 'docs/__meta__/code-python.md' in result.stdout, 'the hyphen extension is governed by meta-code'
        assert 'docs/__meta__/codez.md' not in result.stdout, 'a name without the hyphen boundary is excluded'

    def test_failed_meta_layer_suppresses_spec_parts_but_keeps_link_rules(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        links = '[Absolute](/outside.md) [Fragment](#missing) [Missing](missing.md) [Escape](../../../outside.md)'
        workspace = Workspace(
            specs=[
                Spec('meta', structure={'outline': 'bad'}, prose=f'# Meta\n\n{links}\n'),
                Spec('code', prose=f'# Code\n\n{links}\n', include_structure=False),
            ]
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        for code in ('LC501', 'LC502', 'LC503', 'LC504'):
            assert code in result.stdout, f'{code} remains active under a failed meta layer'
        assert 'LC003' in result.stdout, 'the failed meta structure is reported'
        for name in ('meta', 'code'):
            assert f'docs/__meta__/{name}.md: ungoverned for frontmatter, structure, outline, budget' in result.stderr

    def test_failed_meta_namespace_layer_suppresses_spec_parts_but_keeps_link_rules(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        links = '[Absolute](/outside.md) [Missing](missing.md) [Escape](../../../outside.md)'
        workspace = Workspace(
            specs=[
                Spec('meta', prose='# Meta\n'),
                Spec('meta-code', structure={'outline': 'bad'}, prose='# Meta Code\n'),
                Spec('meta-python', prose='# Meta Python\n'),
                Spec('code', prose=f'# Code\n\n{links}\n', include_structure=False),
                Spec('code-python', prose='# Code Python\n'),
            ]
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        for code in ('LC501', 'LC503', 'LC504'):
            assert code in result.stdout, f'{code} remains active under a failed meta-code layer'
        assert 'LC003' in result.stdout, 'the failed meta structure is reported'
        assert 'docs/__meta__/code.md: ungoverned for frontmatter, structure, outline, budget' in result.stderr
        assert 'docs/__meta__/code-python.md: ungoverned for frontmatter, structure, outline, budget' in result.stderr
        for name in ('meta', 'meta-code', 'meta-python'):
            assert f'docs/__meta__/{name}.md: ungoverned for' not in result.stderr

    def test_skills_namespace_extends_its_base_without_repeating_required_fields(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[
                Spec('skills', structure={'frontmatter': {'type': 'object', 'required': ['description']}}),
                Spec(
                    'skills-review',
                    structure={'frontmatter': {'type': 'object', 'properties': {'owner': {'type': 'string'}}}},
                ),
            ],
            skills=[Skill('review-a', frontmatter=RawFrontmatter('name: review-a\n'))],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'missing required field `description`' in result.stdout, 'the namespace keeps its base required field'

    def test_link001_to_link003_run_on_a_document_without_a_structure_file(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        body = '# Guide\n\n[Absolute](/outside.md) [Fragment](#missing) [Missing](missing.md)\n'
        workspace = Workspace(
            specs=[Spec('code', prose='# Code\n', include_structure=False)],
            documents=[
                Document('code', 'guide', body=body + '[Extension](guide-extra.md) [Other](../guide-extra/start.md)\n'),
                Document('code', 'guide-extra', body='# Extra\n'),
                Document('guide', 'start', body='# Start\n\n[Guide](../code/guide.md)\n'),
            ],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        for code in ('LC501', 'LC502', 'LC503'):
            assert code in result.stdout, f'{code} runs on a document without a structure file'
        for code in ('LC505', 'LC506', 'LC507'):
            assert code not in result.stdout, f'{code} stays gated without a structure file'

    def test_link001_to_link003_run_on_a_spec_without_a_structure_file(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        body = '# Code\n\n[Absolute](/outside.md) [Fragment](#missing) [Missing](missing.md)\n'
        workspace = Workspace(specs=[Spec('code', prose=body, include_structure=False)])
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        for code in ('LC501', 'LC502', 'LC503'):
            assert code in result.stdout, f'{code} runs on a spec without a structure file'

    def test_link005_and_link006_run_for_documents_with_structure_files(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            specs=[Spec('code')],
            documents=[
                Document('code', 'guide', body='# Guide\n\n[Extension](guide-extra.md)\n'),
                Document('code', 'guide-extra', body='# Extra\n'),
            ],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root), '-A', 'ALL', '-D', 'LC505', '-D', 'LC506')

        #: Then
        assert result.returncode == 1, 'the selected link rules run as errors'
        assert 'LC505' in result.stdout, 'a base cannot link to its extension when governed by structure'
        assert 'LC506' in result.stdout, 'an extension must link to its base when governed by structure'

    def test_link007_runs_for_mutually_linked_documents_with_structure_files(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[Spec('code'), Spec('guide')],
            documents=[
                Document('code', 'rules', body='# Rules\n\n[Guide](../guide/start.md)\n'),
                Document('guide', 'start', body='# Start\n\n[Rules](../code/rules.md)\n'),
            ],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root), '-A', 'ALL', '-D', 'LC507')

        #: Then
        assert result.returncode == 1, 'the selected link rule runs as an error'
        assert result.stdout.count('error[LC507]') == 2, 'both sides of a cross-corpus cycle are reported'

    def test_link004_runs_on_spec_prose(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            specs=[Spec('code', prose='# Code\n\n[Escape](../../../outside.md)\n', include_structure=False)]
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC504' in result.stdout, 'spec prose uses the same repository link bound'

    def test_link004_runs_on_a_skill_resource(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            skills=[
                Skill('review', references={'guide.md': '# Guide\n\n[Escape](../../outside.md) [Missing](#missing)\n'})
            ]
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC502' in result.stdout, 'fragment checks apply to resources too'
        assert 'LC504' in result.stdout, 'resources use their skill root as the link bound'

    def test_lc004_reports_a_skill_schema_that_excludes_the_required_field_type(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[
                Spec(
                    'skills', structure={'frontmatter': {'type': 'object', 'properties': {'name': {'type': 'integer'}}}}
                )
            ],
            skills=[Skill('review')],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC004' in result.stdout, 'a non-string name schema contradicts the Agent Skills floor'

    def test_lc004_reports_a_skill_schema_that_excludes_the_required_field_length(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[
                Spec(
                    'skills',
                    structure={
                        'frontmatter': {
                            'type': 'object',
                            'properties': {'description': {'type': 'string', 'minLength': 1025}},
                        }
                    },
                )
            ],
            skills=[Skill('review')],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC004' in result.stdout, 'a description length outside the floor range is a contradiction'

    def test_lc004_reports_a_skill_schema_enum_with_no_valid_name(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            specs=[
                Spec(
                    'skills',
                    structure={'frontmatter': {'type': 'object', 'properties': {'name': {'enum': ['INVALID']}}}},
                )
            ],
            skills=[Skill('review')],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC004' in result.stdout, 'an enum with no valid Agent Skills name is a contradiction'

    def test_opt_out_skips_lc004_for_a_contradictory_skills_schema(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            specs=[
                Spec(
                    'skills', structure={'frontmatter': {'type': 'object', 'properties': {'name': {'type': 'integer'}}}}
                )
            ],
            skills=[Skill('review')],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('--no-agent-skills-spec', 'check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC004' not in result.stdout, 'the builtin compatibility preflight is disabled with the floor'
        assert 'LC208' in result.stdout, 'the repository schema still validates skill frontmatter'


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
        assert result.stderr == (
            '.agents/skills/review/SKILL.md: ungoverned for structure, outline\n'
            'checked 1 subject(s): 0 error(s), 0 warning(s)\n'
        ), 'the one skill written is the one checked'

    def test_check_rejects_a_skills_schema_that_contradicts_a_builtin_rule(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            specs=[Spec('skills', structure={'frontmatter': {'type': 'object', 'properties': {'description': False}}})]
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, 'the contradictory skills specification makes check fail'
        assert 'skills.spec.json' in result.stdout
        assert 'description' in result.stdout
        assert 'built-in rule' in result.stdout

    def test_check_can_opt_out_of_the_builtin_skills_schema(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(skills=[Skill('review', frontmatter=RawFrontmatter('name: review\n'))])
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('--no-agent-skills-spec', 'check', '--root', str(root))

        #: Then
        assert result.returncode == 0, result.stdout
        assert 'missing required field `description`' not in result.stdout
        assert result.stderr == (
            '.agents/skills/review/SKILL.md: ungoverned for frontmatter, structure, outline, budget\n'
            'checked 1 subject(s): 0 error(s), 0 warning(s)\n'
        ), 'the opted-out frontmatter facet is reported as ungoverned, as on main'

    def test_builtin_floor_warns_on_top_level_repository_fields_but_not_metadata_fields(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[
                Spec(
                    'skills',
                    structure={
                        'frontmatter': {
                            'type': 'object',
                            'required': ['owner', 'metadata'],
                            'properties': {
                                'owner': {'type': 'string'},
                                'metadata': {
                                    'type': 'object',
                                    'required': ['owner'],
                                    'properties': {'owner': {'type': 'string'}},
                                },
                            },
                        }
                    },
                )
            ],
            skills=[
                Skill(
                    'review',
                    frontmatter=RawFrontmatter(
                        'name: review\ndescription: Review\nowner: team\nmetadata:\n  owner: team\n'
                    ),
                )
            ],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 0, result.stderr
        assert 'warning[LC207]' in result.stdout, 'the builtin floor flags an undeclared top-level owner field'
        assert 'metadata.owner' not in result.stdout, 'repository metadata fields are allowed by the builtin floor'

    @pytest.mark.parametrize(
        ('frontmatter', 'case'),
        [
            (RawFrontmatter('name: review\nname: repeated\n'), 'duplicate key'),
            (RawFrontmatter(': review\nname: review\n'), 'empty key'),
            (RawFrontmatter('name: another-skill\n'), 'valid but wrong name'),
        ],
        ids=lambda value: value if isinstance(value, str) else None,
    )
    def test_check_opt_out_reports_inactive_frontmatter_for_skill_inputs(
        self, tmp_path: Path, faker: Faker, frontmatter: RawFrontmatter, case: str
    ) -> None:
        #: Given
        root = Workspace(skills=[Skill('review', frontmatter=frontmatter)]).write(tmp_path, faker)

        #: When
        result = run_cli('--no-agent-skills-spec', 'check', '--root', str(root))

        #: Then
        assert result.returncode == 0, result.stdout
        assert result.stdout == '', f'{case} frontmatter has no active schema diagnostic'
        assert result.stderr == (
            '.agents/skills/review/SKILL.md: ungoverned for frontmatter, structure, outline, budget\n'
            'checked 1 subject(s): 0 error(s), 0 warning(s)\n'
        ), f'{case} frontmatter keeps main coverage output when the built-in schema is opted out'

    def test_check_opt_out_reports_inactive_frontmatter_when_skill_has_no_frontmatter(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        root = Workspace(files=[File('.agents/skills/review/SKILL.md', '# Review\n')]).write(tmp_path, faker)

        #: When
        result = run_cli('--no-agent-skills-spec', 'check', '--root', str(root))

        #: Then
        assert result.returncode == 0, result.stdout
        assert result.stdout == '', 'missing frontmatter has no active schema diagnostic'
        assert result.stderr == (
            '.agents/skills/review/SKILL.md: ungoverned for frontmatter, structure, outline, budget\n'
            'checked 1 subject(s): 0 error(s), 0 warning(s)\n'
        ), 'missing frontmatter keeps main coverage output when the built-in schema is opted out'

    def test_check_opt_out_does_not_apply_builtin_name_rule_alongside_a_repository_schema(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[Spec('skills', structure={'frontmatter': {'type': 'object', 'required': ['owner']}})],
            skills=[Skill('a', frontmatter=RawFrontmatter('name: wrong-name\n'))],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('--no-agent-skills-spec', 'check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stdout
        assert 'missing required field `owner`' in result.stdout, 'the repository schema remains active'
        assert 'error[LC204]' in result.stdout, 'the repository schema governs the skill name rule'
        assert "a skill's `name` must match its directory name" in result.stdout, (
            'the name guidance identifies the skill directory as the expected name'
        )
        assert "or rename the skill directory to 'wrong-name'" in result.stdout
        assert "or rename the file to 'wrong-name.md'" not in result.stdout

    def test_inspect_json_reports_only_the_builtin_skills_opt_out(
        self, tmp_path: Path, faker: Faker, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(JsonTextSnapshotExtension)
        root = Workspace().write(tmp_path, faker)

        #: When
        result = run_cli('--no-agent-skills-spec', 'inspect', str(root), '--format', 'json')

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout.replace(str(root), _ROOT_PLACEHOLDER) == expected, (
            'the JSON document names the active opt-out and no enabled state'
        )

    def test_inspect_text_reports_the_builtin_schema_opt_out_only_when_disabled(
        self, tmp_path: Path, faker: Faker, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        expected = snapshot.use_extension(TextSnapshotExtension)
        root = Workspace().write(tmp_path, faker)

        #: When
        result = run_cli('--no-agent-skills-spec', 'inspect', str(root))

        #: Then
        assert result.returncode == 0, result.stderr
        assert result.stdout.replace(str(root), _ROOT_PLACEHOLDER) == expected, (
            'the tree identifies the active opt-out and no enabled state'
        )

    def test_check_enforces_the_five_hundred_line_skill_limit(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        body = '# Review\n\n' + 'step\n' * 500
        root = Workspace(skills=[Skill('review', body=body)]).write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'error[LC402]' in result.stdout, 'the built-in 500-line ceiling rejects a 501-line skill'
        assert '500' in result.stdout, 'the diagnostic names the built-in ceiling'

    def test_check_reports_both_skill_budgets_when_repository_limit_is_tighter(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        root = Workspace(
            specs=[Spec('skills', structure={'lines': 300})],
            skills=[Skill('review', body='# Review\n\n' + 'step\n' * 500)],
        ).write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert result.stdout.count('error[LC402]') == 2, 'the repository and built-in budgets are both reported'

    def test_check_does_not_allow_a_skills_spec_to_raise_the_builtin_line_limit(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        root = Workspace(
            specs=[Spec('skills', structure={'lines': 700})],
            skills=[Skill('review', body='# Review\n\n' + 'step\n' * 500)],
        ).write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'error[LC402]' in result.stdout, 'a repository cap cannot raise the built-in ceiling'

    def test_check_skill_floor_rules_are_absent_when_the_builtin_layer_is_disabled(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        body = '# Review\n\n' + 'step\n' * 500
        root = Workspace(skills=[Skill('review', frontmatter=RawFrontmatter('name: review\n'), body=body)]).write(
            tmp_path, faker
        )

        #: When
        result = run_cli('--no-agent-skills-spec', 'check', '--root', str(root))

        #: Then
        assert result.returncode == 0, result.stdout
        assert result.stdout == '', 'the opt-out disables every built-in skill finding'
        assert 'LC402' not in result.stdout, 'the opt-out disables the builtin line-budget finding'
        assert 'ungoverned for frontmatter, structure, outline, budget' in result.stderr

    def test_check_suppresses_the_floor_budget_when_a_repository_skills_layer_fails(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[Spec('skills', structure={'frontmatter': {'type': 5}})],
            skills=[Skill('review', body='# Review\n\n' + 'step\n' * 500)],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC004' in result.stdout, 'the unusable repository layer is reported'
        assert 'LC402' not in result.stdout, 'the failed layer suppresses all WhenSpec budget rules'

    def test_check_opt_out_keeps_a_failed_repository_skills_layer_reported(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        workspace = Workspace(
            specs=[Spec('skills', structure={'frontmatter': {'type': 5}})],
            skills=[
                Skill('review', frontmatter=RawFrontmatter('name: review\n'), body='# Review\n\n' + 'step\n' * 500)
            ],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('--no-agent-skills-spec', 'check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC004' in result.stdout, 'opting out does not hide an unusable repository spec'
        assert 'LC402' not in result.stdout, 'the failed layer suppresses the opted-out floor budget too'

    def test_check_reports_malformed_allowed_tools_on_a_skill(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        root = Workspace(
            skills=[
                Skill(
                    'review',
                    frontmatter=RawFrontmatter('name: review\ndescription: Review\nallowed-tools: Read, Grep\n'),
                )
            ]
        ).write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 0, result.stderr
        assert 'LC211' in result.stdout, 'the builtin floor reports a malformed allowed-tools value'

    def test_check_reports_long_allowed_tools_on_a_skill(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        tools = ' '.join(f'tool-{index}' for index in range(100))
        root = Workspace(
            skills=[
                Skill(
                    'review',
                    frontmatter=RawFrontmatter(f'name: review\ndescription: Review\nallowed-tools: {tools}\n'),
                )
            ]
        ).write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 0, result.stderr
        assert 'LC212' in result.stdout, 'the builtin floor reports an oversized allowed-tools value'

    def test_check_keeps_long_allowed_tools_rule_with_repository_frontmatter_and_floor_opted_out(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        tools = ' '.join(f'tool-{index}' for index in range(100))
        workspace = Workspace(
            specs=[Spec('skills', structure={'frontmatter': {'type': 'object'}})],
            skills=[
                Skill(
                    'review',
                    frontmatter=RawFrontmatter(f'name: review\ndescription: Review\nallowed-tools: {tools}\n'),
                )
            ],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('--no-agent-skills-spec', 'check', '--root', str(root))

        #: Then
        assert result.returncode == 0, result.stderr
        assert 'LC212' in result.stdout, 'the repository frontmatter gate keeps the long-value rule active'

    def test_check_keeps_allowed_tools_rules_with_repository_frontmatter_and_floor_opted_out(
        self, tmp_path: Path, faker: Faker
    ) -> None:
        #: Given
        workspace = Workspace(
            specs=[Spec('skills', structure={'frontmatter': {'type': 'object'}})],
            skills=[
                Skill(
                    'review',
                    frontmatter=RawFrontmatter('name: review\ndescription: Review\nallowed-tools: Read, Grep\n'),
                )
            ],
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('--no-agent-skills-spec', 'check', '--root', str(root))

        #: Then
        assert result.returncode == 0, result.stderr
        assert 'LC211' in result.stdout, 'the repository frontmatter gate keeps the allowed-tools rule active'

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

    def test_check_with_a_spec_missing_a_required_field_fails(self, tmp_path: Path, faker: Faker) -> None:
        #: Given
        meta_structure = {
            'frontmatter': {'type': 'object', 'required': ['required-field']},
            'outline': [{'section': 'Required'}],
            'tokens': 1,
        }
        workspace = Workspace(
            specs=[Spec('meta', structure=meta_structure), Spec('code', prose='---\nname: code\n---\n\n# Code\n')]
        )
        root = workspace.write(tmp_path, faker)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stderr
        assert 'LC206' in result.stdout, 'the missing required frontmatter field is checked on a spec'
        assert 'LC306' in result.stdout, 'the required outline section is checked on a spec'
        assert 'LC401' in result.stdout, 'the token budget is checked on a spec'


@pytest.fixture(scope='function')
def linked_specs_root(tmp_path: Path, faker: Faker) -> Path:
    """A root whose `docs/__meta__` is a symlink to the workspace fixture's specifications.

    Args:
        tmp_path: Directory the link and the document are written into, as the repository root.
        faker: The test's seeded generator, which fills what the document leaves unset.
    """
    workspace = Workspace(links=[Link('docs/__meta__', str(WORKSPACE_FIXTURE / 'docs' / '__meta__'))])
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


@pytest.mark.e2e
class TestUncheckedDocsSymlinks:
    def test_check_ignores_a_top_level_symlink_that_is_not_a_corpus(self, tmp_path: Path) -> None:
        root = tmp_path / 'workspace'
        shutil.copytree(WORKSPACE_FIXTURE, root)
        (root / 'docs' / 'README.md').symlink_to('code.md')

        result = run_cli('check', '--root', str(root))

        assert 'docs/README.md: not checked (symlink)' not in result.stderr

    def test_check_reports_a_linked_corpus_as_coverage(self, tmp_path: Path, snapshot: SnapshotAssertion) -> None:
        root = tmp_path / 'workspace'
        shutil.copytree(WORKSPACE_FIXTURE, root)
        shutil.rmtree(root / 'docs' / 'code')
        (root / 'docs' / 'code').symlink_to(WORKSPACE_FIXTURE / 'docs' / 'code', target_is_directory=True)

        result = run_cli('check', '--root', str(root))
        expected = snapshot.use_extension(TextSnapshotExtension)

        assert result.returncode == 1, result.stdout + result.stderr
        assert result.stderr == expected, 'the linked corpus appears in coverage under full group labels'

    def test_check_reports_a_linked_corpus_as_unchecked_in_json(self, tmp_path: Path) -> None:
        #: Given
        root = tmp_path / 'workspace'
        shutil.copytree(WORKSPACE_FIXTURE, root)
        shutil.rmtree(root / 'docs' / 'code')
        (root / 'docs' / 'code').symlink_to(WORKSPACE_FIXTURE / 'docs' / 'code', target_is_directory=True)

        #: When
        result = run_cli('check', '--root', str(root), '--format', 'json')
        document = json.loads(result.stdout)

        #: Then
        assert result.returncode == 1, result.stderr
        assert {
            'path': 'docs/code',
            'ungoverned': [],
            'cause': None,
            'skipped_by': [],
            'unchecked': True,
        } in document['coverage'], 'JSON identifies the linked corpus as unchecked'

    def test_check_reports_a_dangling_document_link_as_unchecked(self, tmp_path: Path) -> None:
        #: Given
        root = tmp_path / 'workspace'
        shutil.copytree(WORKSPACE_FIXTURE, root)
        (root / 'docs' / 'code' / 'dangling.md').symlink_to('missing.md')

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stdout + result.stderr
        assert 'docs/code/dangling.md: not checked (symlink)' in result.stderr

    def test_check_reports_a_document_link_leaving_the_repository_as_unchecked(self, tmp_path: Path) -> None:
        #: Given
        root = tmp_path / 'workspace'
        shutil.copytree(WORKSPACE_FIXTURE, root)
        outside = tmp_path / 'outside.md'
        outside.write_text('# Outside\n', encoding='utf-8')
        (root / 'docs' / 'code' / 'outside.md').symlink_to(outside)

        #: When
        result = run_cli('check', '--root', str(root))

        #: Then
        assert result.returncode == 1, result.stdout + result.stderr
        assert 'docs/code/outside.md: not checked (symlink)' in result.stderr

    def test_check_reports_a_linked_document_as_coverage(self, tmp_path: Path, snapshot: SnapshotAssertion) -> None:
        root = tmp_path / 'workspace'
        shutil.copytree(WORKSPACE_FIXTURE, root)
        (root / 'docs' / 'code' / 'linked.md').symlink_to(root / 'docs' / 'code' / 'python-typing.md')

        result = run_cli('check', '--root', str(root))
        expected = snapshot.use_extension(TextSnapshotExtension)

        assert result.returncode == 1, result.stdout + result.stderr
        assert result.stderr == expected, 'the linked document appears in coverage under full group labels'
