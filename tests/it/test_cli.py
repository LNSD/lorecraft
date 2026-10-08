"""The CLI assembled: the root application, its global options, and the registry that mounts onto it.

These run the command line in process through Typer's `CliRunner`, so they cross module boundaries —
root application, registry, command module, version strings, the scan and the model load behind `inspect`, the
rules engine behind `check` — without needing the console script that `tests/e2e/` exercises. `inspect` and `check`
read a real tree under `tmp_path`.
"""

import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from textwrap import dedent
from typing import Final

import pytest
from syrupy.assertion import SnapshotAssertion
from typer.testing import CliRunner

from lib.snapshot import TextSnapshotExtension
from lorecraft import __version__, rules
from lorecraft.cli import build_app
from lorecraft.cli.commands.version import version as version_handler
from lorecraft.cli.registry import DuplicateCommandError, register
from lorecraft.cli.rulebook import render_listing, render_page
from lorecraft.rules.outline.empty_section import EmptySection
from lorecraft.rules.registry import Registry

runner = CliRunner()

# A structure specification whose frontmatter schema accepts any frontmatter, and which states no other rule; the
# cases below turn on the tree, not the schema.
ACCEPT_ANY_FRONTMATTER_SPEC: Final[str] = '{"frontmatter": {"type": "object"}}'

# A structure specification requiring a Checklist after the document's own sections, with a frontmatter schema that
# accepts any frontmatter and a token budget every document below fits.
CHECKLIST_AND_FRONTMATTER_SPEC: Final[str] = dedent(
    """
    {
      "tokens": 1000,
      "frontmatter": {"type": "object"},
      "outline": [{"any": true}, {"section": "Checklist"}]
    }
    """
)

# The help is drawn by Rich, which reads the terminal it draws for: under GitHub Actions it emits colour codes, and
# it wraps at the width it finds. A dumb terminal 80 columns wide draws the same plain text on every machine.
PLAIN_TERMINAL: Final[dict[str, str | None]] = {'TERM': 'dumb', 'COLUMNS': '80'}

# A `SKILL.md` holding a field the Agent Skills specification does not define, which is a warning and nothing else.
UNKNOWN_FIELD_SKILL_MD: Final[str] = '---\nname: review\ndescription: Review a change\nversion: 2\n---\n# Review\n'

# A structure specification whose token budget a two-section document exceeds.
TIGHT_BUDGET_STRUCTURE_SPEC: Final[str] = '{"tokens": 5}'


@pytest.fixture(scope='function')
def workspace(tmp_path: Path) -> Path:
    """A workspace root with a `code` corpus of one document.

    Args:
        tmp_path: Directory the corpus is written into, as the workspace root.
    """
    (tmp_path / 'docs' / '__meta__').mkdir(parents=True)
    (tmp_path / 'docs' / '__meta__' / 'code.md').write_text('# Code\n')
    (tmp_path / 'docs' / 'code').mkdir()
    (tmp_path / 'docs' / 'code' / 'logging.md').write_text('# Logging\n')
    return tmp_path


@pytest.fixture(scope='function')
def malformed_schema_workspace(workspace: Path) -> Path:
    """The workspace with a `code` frontmatter schema that is valid JSON but not a well-formed JSON Schema.

    Args:
        workspace: Workspace root the malformed schema file is added to.
    """
    (workspace / 'docs' / '__meta__' / 'code.structure.json').write_text('{"frontmatter": {"type": 5}}\n')
    return workspace


@pytest.fixture(scope='function')
def unreadable_workspace(tmp_path: Path) -> Iterator[Path]:
    """A workspace root whose `docs/` refuses listing, restored afterwards so pytest can clean it up.

    Args:
        tmp_path: Directory returned as the workspace root, holding the locked `docs/`.
    """
    docs = tmp_path / 'docs'
    docs.mkdir()
    docs.chmod(0o000)
    yield tmp_path
    docs.chmod(0o700)


@pytest.fixture(scope='function')
def directory_under_a_locked_parent(tmp_path: Path) -> Iterator[Path]:
    """A directory whose parent refuses search, so nothing below it can be inspected; unlocked afterwards.

    Args:
        tmp_path: Directory the locked parent and the returned directory are created under.
    """
    locked = tmp_path / 'locked'
    directory = locked / 'sub'
    directory.mkdir(parents=True)
    locked.chmod(0o000)
    yield directory
    locked.chmod(0o700)


@pytest.fixture(scope='function')
def working_directory_under_a_locked_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """The working directory, entered before its parent is made to refuse search; unlocked afterwards.

    Args:
        tmp_path: Directory the locked parent and the working directory are created under.
        monkeypatch: Changes the process's working directory to the new directory, undone at teardown.
    """
    locked = tmp_path / 'locked'
    directory = locked / 'sub'
    directory.mkdir(parents=True)
    monkeypatch.chdir(directory)
    locked.chmod(0o000)
    yield directory
    locked.chmod(0o700)


@pytest.fixture(scope='function')
def linked_specs_workspace(tmp_path: Path) -> Path:
    """A workspace root whose `docs/__meta__` is a symlink to a real directory holding a tight token budget.

    Read through the link, the one document would break its budget; the snapshot never reads through it.

    Args:
        tmp_path: Directory the specifications, the document and the link are written into, as the workspace root.
    """
    _write(tmp_path, 'specs/code.md', '# Code\n')
    _write(tmp_path, 'specs/code.structure.json', TIGHT_BUDGET_STRUCTURE_SPEC)
    _write(tmp_path, 'docs/code/guide.md', '## First\n\none two three\n\n## Second\n\nfour five six\n')
    (tmp_path / 'docs' / '__meta__').symlink_to(Path('..') / 'specs')
    return tmp_path


@pytest.fixture(scope='function')
def linked_docs_workspace(tmp_path: Path) -> Path:
    """A workspace root whose `docs` is a symlink to a real directory holding a whole layout.

    Args:
        tmp_path: Directory the real layout and the link are written into, as the workspace root.
    """
    _write(tmp_path, 'documentation/__meta__/code.md', '# Code\n')
    _write(tmp_path, 'documentation/__meta__/code.structure.json', TIGHT_BUDGET_STRUCTURE_SPEC)
    _write(tmp_path, 'documentation/code/guide.md', '## First\n\none two three\n\n## Second\n\nfour five six\n')
    (tmp_path / 'docs').symlink_to('documentation')
    return tmp_path


@pytest.fixture(scope='function')
def two_group_root(tmp_path: Path) -> Path:
    """A workspace root whose one document breaks a frontmatter rule and an outline rule.

    Args:
        tmp_path: Directory the specification and the document are written into, as the workspace root.
    """
    _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_AND_FRONTMATTER_SPEC)
    _write(tmp_path, 'docs/code/guide.md', '# No frontmatter\n')
    return tmp_path


def _unused_handler() -> None:
    """Stand-in handler for a registration that must be rejected before it is ever mounted."""


def _write(root: Path, relative: str, text: str = '') -> Path:
    """Write one file under the root, creating its parents, and return its path.

    Args:
        root: Directory the file is written under.
        relative: Slash-separated path of the file, relative to `root`.
        text: UTF-8 text the file holds. The file is empty when omitted.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


@pytest.mark.it
class TestRootApplication:
    def test_help_option_prints_the_usage_the_options_and_every_command(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        app = build_app()
        expected = snapshot.use_extension(TextSnapshotExtension)

        #: When
        result = runner.invoke(app, ['--help'], env=PLAIN_TERMINAL)

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == expected, 'the root help matches the reviewed snapshot'

    def test_root_without_arguments_prints_the_help_and_exits_two(self) -> None:
        #: Given
        app = build_app()
        arguments: list[str] = []

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, f'a bare invocation is a usage error, got exit {result.exit_code}'
        assert 'Usage:' in result.stdout, 'a bare invocation prints the help rather than nothing'


@pytest.mark.it
class TestVersionOption:
    def test_version_option_long_form_prints_the_short_version(self) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['--version'])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.output.strip() == f'lorecraft {__version__}', 'the option prints the short version'

    def test_version_option_with_short_form_exits_successfully_and_prints_the_version(self) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['-V'])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.output.strip() == f'lorecraft {__version__}', '-V prints the short version'

    def test_version_option_followed_by_a_command_and_its_arguments_prints_only_the_short_version(self) -> None:
        #: Given
        app = build_app()
        # a check over a root that does not exist, which would exit 2 were it run
        arguments = ['--version', 'check', 'frontmatter', '--root', 'missing']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        assert result.output == f'lorecraft {__version__}\n', (
            'the option prints the short version and exits, whatever follows it on the command line'
        )


@pytest.mark.it
class TestVersionCommand:
    def test_version_command_with_help_prints_the_usage_and_the_options(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        app = build_app()
        expected = snapshot.use_extension(TextSnapshotExtension)

        #: When
        result = runner.invoke(app, ['version', '--help'], env=PLAIN_TERMINAL)

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == expected, 'the version help matches the reviewed snapshot, with no docstring section'

    def test_version_command_without_verbose_prints_one_line(self) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['version'])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.output.strip() == f'lorecraft {__version__}', 'the plain command prints one line'


@pytest.mark.it
class TestInspectCommand:
    def test_inspect_with_help_prints_the_description_and_stops_before_raises(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        app = build_app()
        expected = snapshot.use_extension(TextSnapshotExtension)

        #: When
        result = runner.invoke(app, ['inspect', '--help'], env=PLAIN_TERMINAL)

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == expected, 'the inspect help matches the reviewed snapshot, with no docstring section'

    def test_inspect_with_a_workspace_root_draws_its_model(self, workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        lines = result.output.splitlines()
        assert lines[0] == str(workspace.resolve()), 'the tree is headed by the resolved root'
        assert '│           └── logging.md [code]' in lines, 'a rule document sits under its corpus, with its spec'

    def test_inspect_with_json_format_prints_the_model_as_one_json_document(self, workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(workspace), '--format', 'json']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        document = json.loads(result.output)
        assert document['root'] == str(workspace.resolve()), 'the root is reported resolved'
        assert [corpus['name'] for corpus in document['corpora']] == ['code'], 'the one spec-backed corpus is found'

    def test_inspect_with_the_deprecated_json_flag_prints_the_model_as_json(self, workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(workspace), '--json']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)['root'] == str(workspace.resolve()), '`--json` still prints the JSON model'

    def test_inspect_with_both_format_and_json_exits_with_a_usage_error(self, workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(workspace), '--format', 'json', '--json']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'no model is printed when both options are given'

    def test_inspect_with_json_format_over_a_root_with_skills_prints_each_directory_and_each_skill(
        self, tmp_path: Path
    ) -> None:
        #: Given
        (tmp_path / 'skills' / 'review').mkdir(parents=True)
        (tmp_path / 'skills' / 'review' / 'SKILL.md').write_text('')
        (tmp_path / '.agents' / 'skills' / 'commit').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'commit' / 'SKILL.md').write_text('')
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')
        app = build_app()
        arguments = ['inspect', str(tmp_path), '--format', 'json']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == {
            'root': str(tmp_path.resolve()),
            'corpora': [],
            'agent_skills_dirs': [
                {'agent': 'claude-code', 'path': '.claude/skills', 'resolves_to': '.agents/skills'},
                {'agent': 'codex', 'path': '.agents/skills', 'resolves_to': '.agents/skills'},
            ],
            'skills': [
                {'path': '.agents/skills/commit/SKILL.md', 'agents': ['claude-code', 'codex']},
                {'path': '.agents/skills/review/SKILL.md', 'agents': ['claude-code', 'codex']},
            ],
        }, 'the linked agent directory and the skill linked from outside it are both in the document'

    def test_inspect_with_a_malformed_frontmatter_schema_exits_two_and_names_it(
        self, malformed_schema_workspace: Path
    ) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(malformed_schema_workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert 'error: invalid structure schema docs/__meta__/code.structure.json' in result.output, (
            'the failure names the specification the load rejected'
        )

    def test_inspect_without_a_root_scans_the_current_directory(
        self, workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        app = build_app()
        monkeypatch.chdir(workspace)
        arguments = ['inspect']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        assert result.output.splitlines()[0] == str(workspace.resolve()), 'the root defaults to the working directory'

    def test_inspect_with_a_missing_root_exits_with_a_usage_error(self, tmp_path: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(tmp_path / 'missing')]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, 'a root that does not exist is rejected before any scan'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_inspect_with_an_unreadable_directory_exits_two_and_names_it(self, unreadable_workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(unreadable_workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert 'error: cannot snapshot directory docs: permission denied' in result.output, (
            'the failure names the step, the path the scan stopped at, and the refusal'
        )

    def test_inspect_with_a_linked_specs_directory_exits_two_and_names_it(self, linked_specs_workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(linked_specs_workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'no model is drawn for a layout the snapshot could not read'
        assert result.stderr == (
            'error: docs/__meta__ is a symlink, which lorecraft does not follow: '
            'docs/__meta__/ must be a real directory\n'
        ), 'the failure names the linked directory instead of drawing a model with no corpora'

    def test_inspect_with_a_linked_docs_directory_exits_two_and_names_it(self, linked_docs_workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(linked_docs_workspace), '--format', 'json']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'no JSON document is printed for a layout the snapshot could not read'
        assert result.stderr == (
            'error: docs is a symlink, which lorecraft does not follow: docs/ must be a real directory\n'
        ), 'the failure names the linked directory instead of printing a model with no corpora'

    def test_inspect_with_a_root_without_a_specs_directory_draws_a_model_with_no_corpora(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/code/guide.md', '# Guide\n')
        app = build_app()
        arguments = ['inspect', str(tmp_path)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout.splitlines()[1] == '├── corpora (0)', (
            'a root that declares no specification is a model with no corpora, not an error'
        )


@pytest.mark.it
class TestRuleCommand:
    def test_rule_with_help_prints_the_description_and_stops_before_raises(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        app = build_app()
        expected = snapshot.use_extension(TextSnapshotExtension)

        #: When
        result = runner.invoke(app, ['rule', '--help'], env=PLAIN_TERMINAL)

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == expected, 'the rule help matches the reviewed snapshot, with no docstring section'

    def test_rule_without_an_argument_lists_every_rule_in_code_order(self) -> None:
        #: Given
        app = build_app()
        arguments = ['rule']
        expected = render_listing(Registry.load(rules)) + '\n'

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == expected, 'every rule is listed, in code order, one line each'

    def test_rule_with_a_code_prints_the_rules_page(self) -> None:
        #: Given
        app = build_app()
        arguments = ['rule', 'OUT004']
        expected = render_page(EmptySection)

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == expected, 'the page is the one the rendering function returns, with no extra line'

    def test_rule_with_a_name_prints_the_same_page_as_its_code(self) -> None:
        #: Given
        app = build_app()
        arguments = ['rule', 'empty-section']
        expected = render_page(EmptySection)

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == expected, 'the name finds the page the code finds'

    def test_rule_with_an_unknown_key_exits_two_and_names_it(self) -> None:
        #: Given
        app = build_app()
        # No rule will ever have this as a code, a name or an alias code.
        arguments = ['rule', 'NOPE001']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, f'no rule has the key, so the command fails, got exit {result.exit_code}'
        assert result.stdout == '', 'a failure prints nothing on stdout'
        assert "error: no rule has the code, name or alias code 'NOPE001'" in result.stderr, 'the key is named'


@pytest.mark.it
class TestCheckCommand:
    def test_check_with_overlong_allowed_tools_warns_and_exits_zero(
        self, tmp_path: Path, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        value = 'A' * 501
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            f'---\nname: review\ndescription: Review a change.\nallowed-tools: {value}\n---\n',
        )
        app = build_app()
        expected_text = snapshot.use_extension(TextSnapshotExtension)

        #: When
        text_result = runner.invoke(app, ['check', '--root', str(tmp_path)])
        json_result = runner.invoke(app, ['check', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert (text_result.exit_code, json_result.exit_code) == (0, 0), (
            'the recommendation does not fail either format'
        )
        assert text_result.stdout == expected_text, 'the warning text matches the reviewed snapshot'
        assert text_result.stderr == 'checked 1 subject(s): 0 error(s), 1 warning(s)\n', 'the warning is counted'
        assert json.loads(json_result.stdout) == {
            'diagnostics': [
                {
                    'path': '.agents/skills/review/SKILL.md',
                    'line': 4,
                    'severity': 'warning',
                    'code': 'FM012',
                    'name': 'allowed-tools-too-long',
                    'message': '`allowed-tools` value too long (501 > 500)',
                    'labels': [
                        {'path': '.agents/skills/review/SKILL.md', 'line': 4, 'text': '1 character over'},
                    ],
                    'children': [
                        {
                            'kind': 'note',
                            'text': "the Agent Skills specification's experimental `allowed-tools` field: "
                            'https://agentskills.io/specification#allowed-tools-field',
                            'path': None,
                            'line': None,
                        },
                        {
                            'kind': 'help',
                            'text': 'keep only the tools the skill needs, and merge patterns such as '
                            '`Bash(git diff *) Bash(git log *)` into `Bash(git *)`',
                            'path': None,
                            'line': None,
                        },
                        {
                            'kind': 'note',
                            'text': 'Lorecraft recommends at most 500 characters, the `compatibility` limit; '
                            'the Agent Skills specification sets none for `allowed-tools`',
                            'path': None,
                            'line': None,
                        },
                    ],
                }
            ],
            'summary': {'subjects': 1, 'errors': 0, 'warnings': 1},
            'coverage': [],
        }, 'JSON labels the excess, notes where the specification states the field, and where the limit comes from'

    def test_check_with_malformed_allowed_tools_warns_and_exits_zero(
        self, tmp_path: Path, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            '---\nname: review\ndescription: Review a change.\nallowed-tools: Read, Grep\n---\n',
        )
        app = build_app()
        expected_text = snapshot.use_extension(TextSnapshotExtension)

        #: When
        text_result = runner.invoke(app, ['check', '--root', str(tmp_path)])
        json_result = runner.invoke(app, ['check', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert text_result.exit_code == 0, text_result.output
        assert text_result.stdout == expected_text, 'the warning text matches the reviewed snapshot'
        assert text_result.stderr == 'checked 1 subject(s): 0 error(s), 1 warning(s)\n', (
            'the warning is counted and does not fail the run'
        )
        assert json_result.exit_code == 0, json_result.output
        assert json.loads(json_result.stdout) == {
            'diagnostics': [
                {
                    'path': '.agents/skills/review/SKILL.md',
                    'line': 4,
                    'severity': 'warning',
                    'code': 'FM011',
                    'name': 'malformed-allowed-tools',
                    'message': '`allowed-tools` is not a list of tool entries',
                    'labels': [
                        {
                            'path': '.agents/skills/review/SKILL.md',
                            'line': 4,
                            'text': '`Read,` is not `Tool` or `Tool(pattern)`',
                        },
                    ],
                    'children': [
                        {
                            'kind': 'note',
                            'text': "the Agent Skills specification's experimental `allowed-tools` field: "
                            'https://agentskills.io/specification#allowed-tools-field',
                            'path': None,
                            'line': None,
                        },
                        {
                            'kind': 'help',
                            'text': 'write `Read`',
                            'path': None,
                            'line': None,
                        },
                    ],
                }
            ],
            'summary': {'subjects': 1, 'errors': 0, 'warnings': 1},
            'coverage': [],
        }, 'JSON reports the skill path, line, warning, help and specification note'

    def test_check_with_help_prints_the_description_and_stops_before_raises(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        app = build_app()
        expected = snapshot.use_extension(TextSnapshotExtension)

        #: When
        result = runner.invoke(app, ['check', '--help'], env=PLAIN_TERMINAL)

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == expected, 'the check help matches the reviewed snapshot, with no docstring section'

    def test_check_with_a_clean_corpus_exits_zero_and_prints_only_the_summary(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_AND_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n# Guide\n\n## Checklist\n\n- [ ] item\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == '', 'a clean run prints no diagnostic'
        assert result.stderr == 'checked 1 subject(s): 0 error(s), 0 warning(s)\n', 'one summary line counts the run'

    def test_check_with_errors_from_two_groups_exits_one_and_prints_each_diagnostic(
        self, tmp_path: Path, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_AND_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '# No frontmatter\n')
        app = build_app()
        expected = snapshot.use_extension(TextSnapshotExtension)

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == expected, 'the frontmatter and outline diagnostics match the reviewed snapshot'
        assert result.stderr == 'checked 1 subject(s): 2 error(s), 0 warning(s)\n', 'the summary counts both errors'

    def test_check_with_only_a_warning_exits_zero_and_prints_it(
        self, tmp_path: Path, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.md', '# Code\n')
        _write(tmp_path, '.agents/skills/review/SKILL.md', UNKNOWN_FIELD_SKILL_MD)
        app = build_app()
        expected = snapshot.use_extension(TextSnapshotExtension)

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == expected, 'the unknown-field warning matches the reviewed snapshot'
        assert result.stderr == 'checked 1 subject(s): 0 error(s), 1 warning(s)\n', 'a warning is counted apart'

    def test_check_with_an_ungoverned_document_prints_its_coverage_on_stderr(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n# Guide\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == '', 'a facet no specification governs is no diagnostic'
        assert result.stderr == (
            'docs/code/guide.md: ungoverned for outline, budget\nchecked 1 subject(s): 0 error(s), 0 warning(s)\n'
        ), 'the coverage line precedes the summary on stderr'

    def test_check_with_an_undecodable_document_exits_one_and_prints_the_engine_error(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        (tmp_path / 'docs' / 'code').mkdir()
        (tmp_path / 'docs' / 'code' / 'guide.md').write_bytes(b'\xff\xfe\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == (
            'docs/code/guide.md:1: error[LC001]: file is not valid UTF-8\n'
            '  --> docs/code/guide.md:1: 0xFF at byte offset 0 cannot start a character\n'
            '  = help: save the file as UTF-8\n'
        ), 'a file that does not decode is reported at the line of its first invalid byte, with the bytes and the fix'
        assert result.stderr == 'checked 1 subject(s): 1 error(s), 0 warning(s)\n', 'the engine error is counted'

    def test_check_with_json_format_prints_one_document_and_nothing_on_stderr(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n# Guide\n')
        (tmp_path / 'docs' / 'code' / 'broken.md').write_bytes(b'\xff\xfe\n')
        _write(tmp_path, '.agents/skills/review/SKILL.md', UNKNOWN_FIELD_SKILL_MD)
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stderr == '', 'the JSON run writes nothing beside its document'
        assert json.loads(result.stdout) == {
            'diagnostics': [
                {
                    'path': '.agents/skills/review/SKILL.md',
                    'line': 4,
                    'severity': 'warning',
                    'code': 'FM007',
                    'name': 'unknown-field',
                    'message': 'unknown field `version`',
                    'labels': [
                        {'path': '.agents/skills/review/SKILL.md', 'line': 4, 'text': 'not defined by the schema'},
                    ],
                    'children': [
                        {
                            'kind': 'note',
                            'text': "the Agent Skills specification states a SKILL.md's frontmatter schema",
                            'path': None,
                            'line': None,
                        },
                        {
                            'kind': 'help',
                            'text': 'remove `version`, or respell it as a field the schema defines',
                            'path': None,
                            'line': None,
                        },
                        {
                            'kind': 'note',
                            'text': 'the schema defines: `name`, `description`, `license`, `compatibility`, '
                            '`metadata`, `allowed-tools`',
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
            'summary': {'subjects': 3, 'errors': 1, 'warnings': 1},
            'coverage': [{'path': 'docs/code/guide.md', 'ungoverned': ['outline', 'budget']}],
        }, f'the document holds every diagnostic, the summary and the coverage, got {result.stdout!r}'

    def test_check_with_json_format_and_errors_from_two_groups_reports_their_labels_and_notes(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_AND_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '# No frontmatter\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout) == {
            'diagnostics': [
                {
                    'path': 'docs/code/guide.md',
                    'line': 1,
                    'severity': 'error',
                    'code': 'FM001',
                    'name': 'missing-frontmatter',
                    'message': 'no `---` delimited frontmatter block',
                    'labels': [
                        {'path': 'docs/code/guide.md', 'line': 1, 'text': 'a `---` delimited block is expected here'},
                    ],
                    'children': [
                        {
                            'kind': 'note',
                            'text': 'the frontmatter schema is set here',
                            'path': 'docs/__meta__/code.structure.json',
                            'line': None,
                        },
                        {
                            'kind': 'help',
                            'text': 'open the file with a `---` line, the fields, and a closing `---` line',
                            'path': None,
                            'line': None,
                        },
                    ],
                },
                {
                    'path': 'docs/code/guide.md',
                    'line': 1,
                    'severity': 'error',
                    'code': 'OUT006',
                    'name': 'missing-section',
                    'message': 'missing required section `Checklist`',
                    'labels': [
                        {
                            'path': 'docs/code/guide.md',
                            'line': 1,
                            'text': 'expected `Checklist` before the end of the document',
                        }
                    ],
                    'children': [
                        {
                            'kind': 'note',
                            'text': 'the document structure is set here',
                            'path': 'docs/__meta__/code.structure.json',
                            'line': None,
                        }
                    ],
                },
            ],
            'summary': {'subjects': 1, 'errors': 2, 'warnings': 0},
            'coverage': [],
        }, f'each diagnostic carries its label and its note pointing at the specification, got {result.stdout!r}'

    def test_check_with_a_root_option_checks_that_root_from_another_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        root = tmp_path / 'repository'
        _write(root, 'docs/__meta__/code.structure.json', CHECKLIST_AND_FRONTMATTER_SPEC)
        _write(root, 'docs/code/guide.md', '---\nname: "guide"\n---\n# Guide\n\n## Checklist\n\n- [ ] item\n')
        elsewhere = tmp_path / 'elsewhere'
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(root)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stderr == 'checked 1 subject(s): 0 error(s), 0 warning(s)\n', (
            'the root given is checked, not the working directory'
        )

    def test_check_without_a_root_finds_the_nearest_parent_with_docs_meta(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_AND_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '# No frontmatter\n')
        monkeypatch.chdir(tmp_path / 'docs' / 'code')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check'])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stderr == 'checked 1 subject(s): 2 error(s), 0 warning(s)\n', (
            'the root found above the working directory is checked whole'
        )

    def test_check_with_a_path_argument_exits_with_a_usage_error(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path), 'docs'])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'a usage error checks nothing'

    def test_check_with_a_malformed_frontmatter_schema_exits_as_invalid_input(
        self, malformed_schema_workspace: Path
    ) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(malformed_schema_workspace)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'after an error nothing is printed but the error'
        assert result.stderr == (
            'error: invalid structure schema docs/__meta__/code.structure.json: frontmatter is not a valid JSON '
            'Schema: 5 is not valid under any of the given schemas\n'
        ), 'the specification that cannot be used is reported, naming it'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores file permissions')
    def test_check_with_an_unreadable_document_exits_as_invalid_input_and_names_it(self, workspace: Path) -> None:
        #: Given
        (workspace / 'docs' / 'code' / 'logging.md').chmod(0o000)
        app = build_app()
        arguments = ['check', '--root', str(workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'after an error nothing is printed but the error'
        assert result.stderr == 'error: cannot snapshot file docs/code/logging.md: permission denied\n', (
            'a document the run cannot read stops it, naming the document and the refusal'
        )

    def test_check_with_a_linked_specs_directory_exits_as_invalid_input(self, linked_specs_workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['check', '--root', str(linked_specs_workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'after an error nothing is printed but the error'
        assert result.stderr == (
            'error: docs/__meta__ is a symlink, which lorecraft does not follow: '
            'docs/__meta__/ must be a real directory\n'
        ), 'the run is refused instead of reporting zero documents checked'

    def test_check_without_a_root_in_a_workspace_with_a_linked_specs_directory_exits_as_invalid_input(
        self, linked_specs_workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        monkeypatch.chdir(linked_specs_workspace)
        app = build_app()
        arguments = ['check']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == (
            'error: docs/__meta__ is a symlink, which lorecraft does not follow: '
            'docs/__meta__/ must be a real directory\n'
        ), 'discovery follows the link to accept the root, and the run is then refused for it'

    def test_check_with_a_linked_docs_directory_exits_as_invalid_input(self, linked_docs_workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['check', '--root', str(linked_docs_workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'after an error nothing is printed but the error'
        assert (
            result.stderr
            == 'error: docs is a symlink, which lorecraft does not follow: docs/ must be a real directory\n'
        ), 'the run is refused instead of reporting zero documents checked'

    def test_check_with_a_dangling_specs_link_exits_as_invalid_input(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/code/guide.md', '# Guide\n')
        (tmp_path / 'docs' / '__meta__').symlink_to('missing')
        app = build_app()
        arguments = ['check', '--root', str(tmp_path)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == (
            'error: docs/__meta__ is a symlink, which lorecraft does not follow: '
            'docs/__meta__/ must be a real directory\n'
        ), 'a link leading nowhere is refused like one leading to a directory'

    def test_check_with_a_root_without_a_specs_directory_exits_zero_and_checks_nothing(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/code/guide.md', '# Guide\n')
        app = build_app()
        arguments = ['check', '--root', str(tmp_path)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stderr == 'checked 0 subject(s): 0 error(s), 0 warning(s)\n', (
            'an explicit root that declares no specification has nothing to check, which is not an error'
        )

    def test_check_without_a_root_outside_any_workspace_exits_as_invalid_input(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        monkeypatch.chdir(tmp_path)
        app = build_app()
        arguments = ['check']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == 'error: cannot find repository root: no parent contains docs/__meta__/\n', (
            'a working directory under no docs/__meta__/ has no root to discover'
        )

    def test_check_without_a_root_from_a_deleted_working_directory_exits_as_invalid_input(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        deleted = tmp_path / 'deleted'
        deleted.mkdir()
        monkeypatch.chdir(deleted)
        deleted.rmdir()
        app = build_app()

        #: When
        result = runner.invoke(app, ['check'])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == 'error: cannot read the current directory: no such file or directory\n', (
            'a working directory the operating system cannot report has no root to search from'
        )

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="Python 3.14's is_dir answers False for every failure")
    def test_check_without_a_root_under_a_locked_parent_exits_as_invalid_input_and_names_the_directory(
        self, working_directory_under_a_locked_parent: Path
    ) -> None:
        #: Given
        candidate = working_directory_under_a_locked_parent.resolve()
        app = build_app()
        arguments = ['check']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'after an error nothing is printed but the error'
        assert (
            result.stderr == f'error: cannot find repository root: cannot inspect {candidate}: permission denied\n'
        ), 'a directory the search cannot inspect stops discovery, naming the directory and the refusal'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="Python 3.14's is_dir answers False for every failure")
    def test_check_with_a_root_under_a_locked_parent_exits_as_invalid_input_and_names_the_root(
        self, directory_under_a_locked_parent: Path
    ) -> None:
        #: Given
        root = directory_under_a_locked_parent.resolve()
        app = build_app()
        arguments = ['check', '--root', str(root)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'after an error nothing is printed but the error'
        assert result.stderr == f'error: cannot inspect root {root}: permission denied\n', (
            'a root that cannot be inspected is refused, naming the root and the refusal'
        )

    def test_check_with_a_missing_root_exits_as_invalid_input_and_names_the_root(self, tmp_path: Path) -> None:
        #: Given
        root = tmp_path.resolve() / 'missing'
        app = build_app()
        arguments = ['check', '--root', str(root)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'after an error nothing is printed but the error'
        assert result.stderr == f'error: {root} is not an existing directory\n', (
            'a root that does not exist is refused, naming the resolved root'
        )


@pytest.mark.it
class TestCheckSelection:
    # The document carries no frontmatter and no Checklist, so the whole run reports FM001 and OUT006, one of each
    # group; each case selects or ignores some of them.

    def test_check_with_a_prefix_selected_prints_only_that_groups_diagnostics(
        self, two_group_root: Path, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        app = build_app()
        expected = snapshot.use_extension(TextSnapshotExtension)

        #: When
        result = runner.invoke(app, ['check', '--root', str(two_group_root), '--select', 'FM'])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == expected, 'the frontmatter diagnostic alone matches the reviewed snapshot'
        assert result.stderr == 'checked 1 subject(s): 1 error(s), 0 warning(s)\n', 'the outline rule did not run'

    def test_check_with_a_code_selected_prints_only_that_rules_diagnostic(
        self, two_group_root: Path, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        app = build_app()
        expected = snapshot.use_extension(TextSnapshotExtension)

        #: When
        result = runner.invoke(app, ['check', '--root', str(two_group_root), '--select', 'OUT006'])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == expected, 'the outline diagnostic alone matches the reviewed snapshot'
        assert result.stderr == 'checked 1 subject(s): 1 error(s), 0 warning(s)\n', 'no other rule ran'

    def test_check_with_a_prefix_ignored_runs_every_other_rule(
        self, two_group_root: Path, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        app = build_app()
        expected = snapshot.use_extension(TextSnapshotExtension)

        #: When
        result = runner.invoke(app, ['check', '--root', str(two_group_root), '--ignore', 'FM'])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == expected, 'the outline diagnostic alone matches the reviewed snapshot'
        assert result.stderr == 'checked 1 subject(s): 1 error(s), 0 warning(s)\n', 'the outline rule still runs'

    def test_check_with_a_code_selected_and_its_group_ignored_runs_that_rule(
        self, two_group_root: Path, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        app = build_app()
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ['check', '--root', str(two_group_root), '--select', 'OUT006', '--ignore', 'OUT']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == expected, (
            'the code, more specific than its group, runs its rule; it matches the snapshot'
        )
        assert result.stderr == 'checked 1 subject(s): 1 error(s), 0 warning(s)\n', 'no other rule ran'

    def test_check_with_all_selected_and_a_prefix_ignored_runs_every_other_rule(
        self, two_group_root: Path, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        app = build_app()
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ['check', '--root', str(two_group_root), '--select', 'ALL', '--ignore', 'OUT']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == expected, 'the frontmatter diagnostic alone matches the reviewed snapshot'
        assert result.stderr == 'checked 1 subject(s): 1 error(s), 0 warning(s)\n', 'the outline rules did not run'

    def test_check_with_a_prefix_selected_and_ignored_runs_no_rule_of_it(self, two_group_root: Path) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(two_group_root), '--select', 'FM', '--ignore', 'FM'])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == '', 'ignoring wins over selecting when both are as specific'
        assert result.stderr == 'checked 1 subject(s): 0 error(s), 0 warning(s)\n', 'the run still checks the subject'

    def test_check_with_a_code_prefix_selected_and_its_group_ignored_runs_the_rules_it_starts(
        self, two_group_root: Path, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        app = build_app()
        expected = snapshot.use_extension(TextSnapshotExtension)
        arguments = ['check', '--root', str(two_group_root), '--select', 'OUT0', '--ignore', 'OUT']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == expected, (
            'the code prefix, more specific than its group, runs the rules it starts; it matches the snapshot'
        )
        assert result.stderr == 'checked 1 subject(s): 1 error(s), 0 warning(s)\n', 'no other rule ran'

    def test_check_with_a_code_prefix_selected_and_json_format_prints_the_rules_it_starts(
        self, two_group_root: Path
    ) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(two_group_root), '--select', 'OUT0', '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stderr == '', 'a selection with nothing to warn of writes nothing beside the document'
        assert json.loads(result.stdout) == {
            'diagnostics': [
                {
                    'path': 'docs/code/guide.md',
                    'line': 1,
                    'severity': 'error',
                    'code': 'OUT006',
                    'name': 'missing-section',
                    'message': 'missing required section `Checklist`',
                    'labels': [
                        {
                            'path': 'docs/code/guide.md',
                            'line': 1,
                            'text': 'expected `Checklist` before the end of the document',
                        }
                    ],
                    'children': [
                        {
                            'kind': 'note',
                            'text': 'the document structure is set here',
                            'path': 'docs/__meta__/code.structure.json',
                            'line': None,
                        }
                    ],
                },
            ],
            'summary': {'subjects': 1, 'errors': 1, 'warnings': 0},
            'coverage': [],
        }, f'the document holds the diagnostic of the rule the prefix starts alone, got {result.stdout!r}'

    def test_check_with_a_code_prefix_starting_no_rule_exits_two_before_checking(self, two_group_root: Path) -> None:
        #: Given
        app = build_app()
        selection = ['--select', 'OUT9']

        #: When
        result = runner.invoke(app, ['check', '--root', str(two_group_root), *selection])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'no subject is checked'
        assert result.stderr == "error: --select 'OUT9' is no rule code or prefix\n", (
            'a code prefix no rule starts is named'
        )

    def test_check_with_repeated_and_comma_separated_selections_selects_each(self, two_group_root: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['check', '--root', str(two_group_root), '--select', 'LEN, FM001', '--select', 'OUT006']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stderr == 'checked 1 subject(s): 2 error(s), 0 warning(s)\n', (
            'the selectors of every value add up: the frontmatter and the outline rule both run'
        )

    def test_check_with_a_selection_and_json_format_prints_one_document(self, two_group_root: Path) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(two_group_root), '--select', 'FM', '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stderr == '', 'a selection with nothing to warn of writes nothing beside the document'
        assert json.loads(result.stdout) == {
            'diagnostics': [
                {
                    'path': 'docs/code/guide.md',
                    'line': 1,
                    'severity': 'error',
                    'code': 'FM001',
                    'name': 'missing-frontmatter',
                    'message': 'no `---` delimited frontmatter block',
                    'labels': [
                        {'path': 'docs/code/guide.md', 'line': 1, 'text': 'a `---` delimited block is expected here'},
                    ],
                    'children': [
                        {
                            'kind': 'note',
                            'text': 'the frontmatter schema is set here',
                            'path': 'docs/__meta__/code.structure.json',
                            'line': None,
                        },
                        {
                            'kind': 'help',
                            'text': 'open the file with a `---` line, the fields, and a closing `---` line',
                            'path': None,
                            'line': None,
                        },
                    ],
                },
            ],
            'summary': {'subjects': 1, 'errors': 1, 'warnings': 0},
            'coverage': [],
        }, f"the document holds the selected rule's diagnostic alone, got {result.stdout!r}"

    def test_check_with_an_unknown_prefix_exits_two_before_checking(self, two_group_root: Path) -> None:
        #: Given
        app = build_app()
        selection = ['--select', 'XYZ']

        #: When
        result = runner.invoke(app, ['check', '--root', str(two_group_root), *selection])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'no subject is checked'
        assert result.stderr == "error: --select 'XYZ' is no rule code or prefix\n", (
            'a selector no rule or group has is named'
        )

    def test_check_with_an_unknown_code_ignored_exits_two_before_checking(self, two_group_root: Path) -> None:
        #: Given
        app = build_app()
        selection = ['--ignore', 'FM999']

        #: When
        result = runner.invoke(app, ['check', '--root', str(two_group_root), *selection])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'no subject is checked'
        assert result.stderr == "error: --ignore 'FM999' is no rule code or prefix\n", (
            'an ignored code no rule has is named, under its option'
        )

    def test_check_with_a_rule_name_exits_two_before_checking(self, two_group_root: Path) -> None:
        #: Given
        app = build_app()
        selection = ['--select', 'missing-frontmatter']

        #: When
        result = runner.invoke(app, ['check', '--root', str(two_group_root), *selection])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'no subject is checked'
        assert result.stderr == (
            "error: --select 'missing-frontmatter' is a rule name; select the rule by its code, FM001\n"
        ), 'a name is refused, naming the code to write instead'

    def test_check_with_the_engine_condition_code_ignored_exits_two_before_checking(self, two_group_root: Path) -> None:
        #: Given
        app = build_app()
        selection = ['--ignore', 'LC001']

        #: When
        result = runner.invoke(app, ['check', '--root', str(two_group_root), *selection])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'no subject is checked'
        assert result.stderr == (
            "error: --ignore 'LC001' names engine conditions, which are always reported and cannot be selected "
            'or ignored\n'
        ), 'a file that does not decode is always reported, so its code cannot be ignored'

    def test_check_with_the_engine_prefix_exits_two_before_checking(self, two_group_root: Path) -> None:
        #: Given
        app = build_app()
        selection = ['--select', 'LC']

        #: When
        result = runner.invoke(app, ['check', '--root', str(two_group_root), *selection])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'no subject is checked'
        assert result.stderr == (
            "error: --select 'LC' names engine conditions, which are always reported and cannot be selected or "
            'ignored\n'
        ), "the engine group's prefix cannot be selected"

    def test_check_with_a_trailing_comma_exits_two_before_checking(self, two_group_root: Path) -> None:
        #: Given
        app = build_app()
        selection = ['--select', 'FM,']

        #: When
        result = runner.invoke(app, ['check', '--root', str(two_group_root), *selection])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'no subject is checked'
        assert result.stderr == "error: --select 'FM,' holds an empty selector\n", (
            'an empty selector is refused, naming the value typed'
        )


@pytest.mark.it
class TestCommandRouting:
    def test_build_app_when_called_mounts_every_discovered_subcommand(self) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['--help'])

        #: Then
        assert result.exit_code == 0, result.output
        assert 'version' in result.output, 'discovery mounted the one registered subcommand'

    def test_register_with_a_name_already_taken_raises_duplicate_command_error(self) -> None:
        #: Given
        name = 'version'

        #: When
        with pytest.raises(DuplicateCommandError) as exc_info:
            register(name)(_unused_handler)

        #: Then
        assert exc_info.value.name == name, 'the error names the subcommand that was already registered'
        assert name in str(exc_info.value), 'the message names the contested subcommand'

    def test_register_with_the_registered_handler_again_returns_it_unchanged(self) -> None:
        #: Given
        name = 'version'

        #: When
        returned = register(name)(version_handler)

        #: Then
        assert returned is version_handler, 'registering the same handler again is a no-op, not a duplicate'
