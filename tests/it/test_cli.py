"""The CLI assembled: the root application, its global options, and the registry that mounts onto it.

These run the command line in process through Typer's `CliRunner`, so they cross module boundaries —
root application, registry, command module, version strings, the scan and the model load behind `inspect`,
the checks behind `check frontmatter`, `check structure` and `check budget` — without needing the console script
that `tests/e2e/` exercises. `inspect` and the checks read a real tree under `tmp_path`.
"""

import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from textwrap import dedent
from typing import Final

import pytest
import typer
from syrupy.assertion import SnapshotAssertion
from typer.testing import CliRunner

from lib.snapshot import TextSnapshotExtension
from lorecraft import __version__
from lorecraft.cli import build_app
from lorecraft.cli.commands.check import app as check_app
from lorecraft.cli.commands.version import version as version_handler
from lorecraft.cli.registry import DuplicateCommandError, register, register_group

runner = CliRunner()

# A structure specification whose frontmatter schema accepts any frontmatter, and which states no other rule; the
# cases below turn on the tree, not the schema.
ACCEPT_ANY_FRONTMATTER_SPEC: Final[str] = '{"frontmatter": {"type": "object"}}'

# A structure specification requiring a Checklist after the document's own sections, with a token budget every
# document below fits.
CHECKLIST_STRUCTURE_SPEC: Final[str] = dedent(
    """
    {
      "tokens": 1000,
      "outline": [{"any": true}, {"section": "Checklist"}]
    }
    """
)

# The Checklist specification above, with a frontmatter schema that accepts any frontmatter as well.
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

# A structure specification whose token budget a two-section document exceeds.
TIGHT_BUDGET_STRUCTURE_SPEC: Final[str] = '{"tokens": 5}'


@pytest.fixture(scope='function')
def workspace(tmp_path: Path) -> Path:
    """A workspace root with a `code` corpus of one document."""
    (tmp_path / 'docs' / '__meta__').mkdir(parents=True)
    (tmp_path / 'docs' / '__meta__' / 'code.md').write_text('# Code\n')
    (tmp_path / 'docs' / 'code').mkdir()
    (tmp_path / 'docs' / 'code' / 'logging.md').write_text('# Logging\n')
    return tmp_path


@pytest.fixture(scope='function')
def malformed_schema_workspace(workspace: Path) -> Path:
    """The workspace with a `code` frontmatter schema that is valid JSON but not a well-formed JSON Schema."""
    (workspace / 'docs' / '__meta__' / 'code.structure.json').write_text('{"frontmatter": {"type": 5}}\n')
    return workspace


@pytest.fixture(scope='function')
def unreadable_workspace(tmp_path: Path) -> Iterator[Path]:
    """A workspace root whose `docs/` refuses listing, restored afterwards so pytest can clean it up."""
    docs = tmp_path / 'docs'
    docs.mkdir()
    docs.chmod(0o000)
    yield tmp_path
    docs.chmod(0o700)


@pytest.fixture(scope='function')
def directory_under_a_locked_parent(tmp_path: Path) -> Iterator[Path]:
    """A directory whose parent refuses search, so nothing below it can be inspected; unlocked afterwards."""
    locked = tmp_path / 'locked'
    directory = locked / 'sub'
    directory.mkdir(parents=True)
    locked.chmod(0o000)
    yield directory
    locked.chmod(0o700)


@pytest.fixture(scope='function')
def working_directory_under_a_locked_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """The working directory, entered before its parent is made to refuse search; unlocked afterwards."""
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
    """
    _write(tmp_path, 'specs/code.md', '# Code\n')
    _write(tmp_path, 'specs/code.structure.json', TIGHT_BUDGET_STRUCTURE_SPEC)
    _write(tmp_path, 'docs/code/guide.md', '## First\n\none two three\n\n## Second\n\nfour five six\n')
    (tmp_path / 'docs' / '__meta__').symlink_to(Path('..') / 'specs')
    return tmp_path


@pytest.fixture(scope='function')
def linked_docs_workspace(tmp_path: Path) -> Path:
    """A workspace root whose `docs` is a symlink to a real directory holding a whole layout."""
    _write(tmp_path, 'documentation/__meta__/code.md', '# Code\n')
    _write(tmp_path, 'documentation/__meta__/code.structure.json', TIGHT_BUDGET_STRUCTURE_SPEC)
    _write(tmp_path, 'documentation/code/guide.md', '## First\n\none two three\n\n## Second\n\nfour five six\n')
    (tmp_path / 'docs').symlink_to('documentation')
    return tmp_path


def _unused_handler() -> None:
    """Stand-in handler for a registration that must be rejected before it is ever mounted."""


def _write(root: Path, relative: str, text: str = '') -> Path:
    """Write one file under the root, creating its parents, and return its path."""
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


@pytest.mark.it
class TestVersionCommand:
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

    def test_inspect_with_json_prints_the_model_as_one_json_document(self, workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(workspace), '--json']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 0, result.output
        document = json.loads(result.output)
        assert document['root'] == str(workspace.resolve()), 'the root is reported resolved'
        assert [corpus['name'] for corpus in document['corpora']] == ['code'], 'the one spec-backed corpus is found'

    def test_inspect_with_json_over_a_root_with_skills_prints_each_directory_and_each_skill(
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
        arguments = ['inspect', str(tmp_path), '--json']

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

    def test_inspect_with_a_malformed_frontmatter_schema_exits_one_and_names_it(
        self, malformed_schema_workspace: Path
    ) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(malformed_schema_workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 1, result.output
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
    def test_inspect_with_an_unreadable_directory_exits_one_and_names_it(self, unreadable_workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(unreadable_workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 1, result.output
        assert 'error: cannot snapshot directory docs: permission denied' in result.output, (
            'the failure names the step, the path the scan stopped at, and the refusal'
        )

    def test_inspect_with_a_linked_specs_directory_exits_one_and_names_it(self, linked_specs_workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(linked_specs_workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == '', 'no model is drawn for a layout the snapshot could not read'
        assert result.stderr == (
            'error: docs/__meta__ is a symlink, which lorecraft does not follow: '
            'docs/__meta__/ must be a real directory\n'
        ), 'the failure names the linked directory instead of drawing a model with no corpora'

    def test_inspect_with_a_linked_docs_directory_exits_one_and_names_it(self, linked_docs_workspace: Path) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(linked_docs_workspace), '--json']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 1, result.output
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
class TestCheckFrontmatterCommand:
    def test_check_frontmatter_with_a_clean_corpus_exits_zero_and_counts_the_documents(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == '', 'a clean run prints no finding lines'
        assert result.stderr == 'checked 1 file(s), 0 finding(s)\n', 'the summary goes to stderr'

    def test_check_frontmatter_without_a_root_finds_the_nearest_parent_with_docs_meta(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '# No frontmatter\n')
        nested = tmp_path / 'src' / 'nested'
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter'])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == 'docs/code/guide.md:1: [frontmatter.missing] no `---` delimited frontmatter block\n', (
            'the root is discovered upward from the working directory, and findings print root-relative'
        )

    def test_check_frontmatter_with_a_corpus_without_a_frontmatter_schema_reports_it_ungoverned(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/feat.md', '# Feat\n')
        _write(tmp_path, 'docs/feat/overview.md', '# No frontmatter\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == (
            'docs/feat/overview.md:1: [feat.ungoverned] '
            'no frontmatter schema for this corpus; frontmatter unvalidated\n'
        ), 'an ungoverned document is reported as unvalidated, not as a finding'

    def test_check_frontmatter_with_a_named_document_checks_that_document_alone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/broken.md', '# No frontmatter\n')
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n')
        monkeypatch.chdir(tmp_path)
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path), 'docs/code/guide.md'])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == '', 'the broken document beside the named one is not checked'
        assert result.stderr == 'checked 1 file(s), 0 finding(s)\n', 'the named document is the one checked'

    def test_check_frontmatter_with_a_missing_named_document_exits_as_invalid_input(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n')
        argument = tmp_path / 'docs' / 'code' / 'missing.md'
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path), str(argument)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == f'error: {argument}: no such file\n', 'the error quotes the argument as typed'

    def test_check_frontmatter_with_a_named_directory_exits_as_invalid_input(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n')
        argument = tmp_path / 'docs' / 'code'
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path), str(argument)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == f'error: {argument}: expected a readable Markdown file\n', (
            'a directory is refused as no document'
        )

    def test_check_frontmatter_with_a_named_non_markdown_file_exits_as_invalid_input(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        argument = _write(tmp_path, 'docs/code/notes.txt', 'notes\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path), str(argument)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == f'error: {argument}: expected a .md file\n', 'only a .md file is a document'

    def test_check_frontmatter_with_a_named_file_outside_docs_exits_as_invalid_input(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        argument = _write(tmp_path, 'README.md', '# Readme\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path), str(argument)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == f'error: {argument}: file must be inside docs/ and outside docs/__meta__/\n', (
            'a file outside docs/ is refused for where it sits'
        )

    def test_check_frontmatter_with_a_named_file_directly_under_docs_exits_as_invalid_input(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        argument = _write(tmp_path, 'docs/architecture.md', '# Architecture\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path), str(argument)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == f'error: {argument}: file must be inside a corpus directory under docs/\n', (
            'a file in no corpus directory is refused for where it sits'
        )

    def test_check_frontmatter_with_a_named_file_the_model_does_not_list_exits_as_invalid_input(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        argument = _write(tmp_path, 'docs/code/README.md', '# Readme\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path), str(argument)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == f'error: {argument}: not a document the workspace lists\n', (
            'a Markdown file in a corpus that the model leaves out is refused as unlisted'
        )

    def test_check_frontmatter_with_invalid_corpus_name_exits_as_invalid_input(self, tmp_path: Path) -> None:
        #: Given
        document = _write(tmp_path, 'docs/bad-name/guide.md', '---\nname: "guide"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path), str(document)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr == (
            f"error: {document}: invalid corpus name\n  caused by: invalid character '-' in corpus name 'bad-name'\n"
        ), 'the CLI reports the invalid name, then the character the parser refused'

    def test_check_frontmatter_with_a_path_in_a_corpus_subdirectory_exits_as_invalid_input(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.md')
        document = _write(tmp_path, 'docs/code/sub/guide.md', '---\nname: "guide"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path), str(document)])

        #: Then
        assert result.exit_code == 2, result.output
        assert 'corpora are flat' in result.output, 'the CLI reports that a nested file is not a document'

    def test_check_frontmatter_with_a_path_in_a_directory_without_a_spec_exits_as_invalid_input(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.md')
        document = _write(tmp_path, 'docs/blog/post.md', '---\nname: "post"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path), str(document)])

        #: Then
        assert result.exit_code == 2, result.output
        assert 'not a corpus' in result.output, 'the CLI reports that the directory has no specification'

    def test_check_frontmatter_with_a_malformed_frontmatter_schema_exits_as_invalid_input(
        self, malformed_schema_workspace: Path
    ) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(malformed_schema_workspace)])

        #: Then
        assert result.exit_code == 2, result.output
        assert 'invalid structure schema docs/__meta__/code.structure.json' in result.stderr, (
            'the failure names the specification the load rejected'
        )

    def test_check_frontmatter_with_a_non_utf8_governed_document_exits_with_an_undecodable_finding(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        document = tmp_path / 'docs' / 'code' / 'guide.md'
        document.parent.mkdir(parents=True)
        document.write_bytes(b'---\nname: "gu\xffide"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 1, result.output
        assert 'docs/code/guide.md:1: [frontmatter.undecodable]' in result.stdout, (
            'a document that is not UTF-8 is a finding, not an invalid-input failure'
        )

    def test_check_frontmatter_with_a_spec_less_directory_beside_a_corpus_reports_only_the_corpus(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n')
        _write(tmp_path, 'docs/blog/post.md', '---\nname: "post"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 0, result.output
        report = json.loads(result.stdout)
        assert report == {'checked': 1, 'findings': [], 'ungoverned': []}, (
            'only the corpus named in docs/__meta__/ is checked; the spec-less directory is not mentioned'
        )

    def test_check_frontmatter_with_a_finding_and_json_format_reports_the_file_as_text_and_the_line_as_a_number(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '# No frontmatter\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout)['findings'] == [
            {
                'file': 'docs/code/guide.md',
                'line': 1,
                'rule': 'frontmatter.missing',
                'message': 'no `---` delimited frontmatter block',
                'spec': None,
            }
        ], f'a finding serialises as the root-relative path and the line number, got {result.stdout!r}'

    def test_check_frontmatter_with_a_key_written_twice_and_json_format_reports_the_duplicate_key(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: guide\ntype: rule\ntype: pattern\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout) == {
            'checked': 1,
            'findings': [
                {
                    'file': 'docs/code/guide.md',
                    'line': 4,
                    'rule': 'frontmatter.duplicate-key',
                    'message': "'type' is already written on line 3",
                    'spec': None,
                }
            ],
            'ungoverned': [],
        }, 'the repetition is reported on its own line, naming the line of the first occurrence'

    def test_check_frontmatter_from_a_deleted_working_directory_exits_with_a_working_directory_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        deleted = tmp_path / 'deleted'
        deleted.mkdir()
        monkeypatch.chdir(deleted)
        deleted.rmdir()
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'frontmatter'])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr.startswith('error: cannot read the current directory:'), (
            f'an unreadable working directory is the reported failure, got {result.stderr!r}'
        )


@pytest.mark.it
class TestCheckHeaderAlias:
    def test_check_header_with_a_clean_corpus_behaves_as_check_frontmatter(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stderr == 'checked 1 file(s), 0 finding(s)\n', 'the alias runs the frontmatter check'

    def test_check_header_with_a_finding_prints_and_exits_as_check_frontmatter(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '# No frontmatter\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == 'docs/code/guide.md:1: [frontmatter.missing] no `---` delimited frontmatter block\n', (
            'the alias prints the finding the frontmatter check prints'
        )

    def test_check_header_with_a_malformed_frontmatter_schema_exits_as_invalid_input(
        self, malformed_schema_workspace: Path
    ) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header', '--root', str(malformed_schema_workspace)])

        #: Then
        assert result.exit_code == 2, result.output
        assert 'invalid structure schema docs/__meta__/code.structure.json' in result.stderr, (
            'the alias reports a rejected specification as the frontmatter check does'
        )


@pytest.mark.it
class TestCheckStructureCommand:
    def test_check_structure_with_a_clean_corpus_exits_zero_and_counts_the_documents(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_STRUCTURE_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '## Rule\n\ntext\n\n## Checklist\n\n- [ ] item\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'structure', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == '', 'a clean run prints no finding lines'
        assert result.stderr == 'checked 1 file(s), 0 finding(s)\n', 'the summary goes to stderr'

    def test_check_structure_with_a_missing_section_exits_one_and_prints_the_finding(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_STRUCTURE_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '## Rule\n\ntext\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'structure', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == (
            'docs/code/guide.md:1: [structure.outline] missing required section `Checklist` (per code.md)\n'
        ), 'the finding prints root-relative, quoting the prose the specification checks'

    def test_check_structure_with_a_corpus_without_a_structure_spec_reports_it_ungoverned(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/feat.md', '# Feat\n')
        _write(tmp_path, 'docs/feat/overview.md', '## Empty\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'structure', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == (
            'docs/feat/overview.md:1: [feat.ungoverned] no structure spec for this corpus; structure unvalidated\n'
        ), 'an ungoverned document is reported as unvalidated, not as a finding'

    def test_check_structure_with_a_malformed_structure_spec_exits_as_invalid_input(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', '{}')
        _write(tmp_path, 'docs/code/guide.md', '## Rule\n\ntext\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'structure', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 2, result.output
        assert 'invalid structure schema docs/__meta__/code.structure.json' in result.stderr, (
            'the failure names the specification the load rejected'
        )

    def test_check_structure_with_a_finding_and_json_format_reports_the_file_as_text_and_the_line_as_a_number(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_STRUCTURE_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '## Checklist\n\n- [ ] item\n\n## Appendix\n\ntext\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'structure', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout)['findings'] == [
            {
                'file': 'docs/code/guide.md',
                'line': 5,
                'rule': 'structure.outline',
                'message': 'unexpected section `Appendix`; the outline ends before it (per code.md)',
                'spec': 'docs/__meta__/code.structure.json',
            }
        ], f'a finding serialises as the root-relative path and the line number, got {result.stdout!r}'


@pytest.mark.it
class TestCheckBudgetCommand:
    def test_check_budget_with_a_clean_corpus_exits_zero_and_counts_the_documents(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_STRUCTURE_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '## Rule\n\ntext\n\n## Checklist\n\n- [ ] item\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'budget', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == '', 'a clean run prints no finding lines'
        assert result.stderr == 'checked 1 file(s), 0 finding(s)\n', 'the summary goes to stderr'

    def test_check_budget_with_a_file_over_its_budget_exits_one_and_prints_the_finding(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', TIGHT_BUDGET_STRUCTURE_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '## Rule\n\ntext\n\n## Checklist\n\n- [ ] item\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'budget', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == (
            'docs/code/guide.md:1: [budget.tokens] 13 tokens; the budget is 5 (per code.structure.json)\n'
        ), 'the finding prints root-relative, quoting the prose the specification checks'

    def test_check_budget_with_a_finding_and_json_format_names_the_spec_from_the_root(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', TIGHT_BUDGET_STRUCTURE_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '## Rule\n\ntext\n\n## Checklist\n\n- [ ] item\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'budget', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout)['findings'] == [
            {
                'file': 'docs/code/guide.md',
                'line': 1,
                'rule': 'budget.tokens',
                'message': '13 tokens; the budget is 5 (per code.structure.json)',
                'spec': 'docs/__meta__/code.structure.json',
            }
        ], f'the spec that sets the budget serialises root-relative, apart from the message, got {result.stdout!r}'

    def test_check_budget_with_a_structure_spec_without_tokens_reports_it_ungoverned(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', '{"empty_sections": "forbidden"}')
        _write(tmp_path, 'docs/code/guide.md', '## Rule\n\ntext\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'budget', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == (
            'docs/code/guide.md:1: [code.ungoverned] no token budget for this corpus; tokens unvalidated\n'
        ), 'a structure spec that sets no `tokens` leaves the document unvalidated, not failed'

    def test_check_budget_with_a_linked_specs_directory_exits_as_invalid_input(
        self, linked_specs_workspace: Path
    ) -> None:
        #: Given
        app = build_app()
        arguments = ['check', 'budget', '--root', str(linked_specs_workspace), '--format', 'json']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'no report is printed for a run that could not start'
        assert result.stderr == (
            'error: docs/__meta__ is a symlink, which lorecraft does not follow: '
            'docs/__meta__/ must be a real directory\n'
        ), 'a named check refuses the linked directory instead of reporting zero documents checked'


@pytest.mark.it
class TestCheckSkillsCommand:
    def test_check_skills_with_json_format_over_clean_skills_reports_them_checked(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/commit/SKILL.md', '---\nname: commit\ndescription: Write a commit\n---\n')
        _write(tmp_path, '.agents/skills/review/SKILL.md', '---\nname: review\ndescription: Review a change\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {'checked': 2, 'findings': [], 'ungoverned': []}, (
            'every skill is checked, none is ungoverned, and a clean run has no finding'
        )

    def test_check_skills_with_json_format_over_broken_skills_reports_each_finding(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/bare/SKILL.md', '# No frontmatter\n')
        _write(tmp_path, '.agents/skills/review/SKILL.md', '---\ndescription: Review\nname: audit\nmodel: opus\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout) == {
            'checked': 2,
            'findings': [
                {
                    'file': '.agents/skills/bare/SKILL.md',
                    'line': 1,
                    'rule': 'skill.frontmatter-missing',
                    'message': 'no `---` delimited frontmatter block',
                    'spec': None,
                },
                {
                    'file': '.agents/skills/review/SKILL.md',
                    'line': 3,
                    'rule': 'skill.name-matches-directory',
                    'message': "`name` is 'audit'; expected 'review', the name of the skill directory",
                    'spec': None,
                },
                {
                    'file': '.agents/skills/review/SKILL.md',
                    'line': 4,
                    'rule': 'skill.unknown-field',
                    'message': '`model` is not a field of the Agent Skills specification',
                    'spec': None,
                },
            ],
            'ungoverned': [],
        }, 'each finding names its SKILL.md from the root, its line as a number and its rule'

    def test_check_skills_with_json_format_over_a_skill_writing_a_key_twice_reports_the_duplicate_key(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            '---\nname: review\ndescription: Review a change\ndescription: Audit a change\n---\n',
        )
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout) == {
            'checked': 1,
            'findings': [
                {
                    'file': '.agents/skills/review/SKILL.md',
                    'line': 4,
                    'rule': 'skill.duplicate-key',
                    'message': "'description' is already written on line 3",
                    'spec': None,
                }
            ],
            'ungoverned': [],
        }, 'the repetition is reported on its own line, naming the line of the first occurrence'

    def test_check_skills_with_json_format_over_a_skill_with_an_absolute_link_reports_the_link(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            '---\nname: review\ndescription: Review a change\n---\n# Review\n\nRead [the guide](/docs/guide.md).\n',
        )
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout) == {
            'checked': 1,
            'findings': [
                {
                    'file': '.agents/skills/review/SKILL.md',
                    'line': 7,
                    'rule': 'skill.link-absolute',
                    'message': '`/docs/guide.md` is absolute; link relative to the skill root',
                    'spec': None,
                }
            ],
            'ungoverned': [],
        }, 'the absolute link is reported on its own line, naming its destination'

    def test_check_skills_with_json_format_over_a_skill_with_a_link_to_a_missing_heading_reports_the_link(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            '---\nname: review\ndescription: Review a change\n---\n# Review\n\nSee [the checklist](#checklist).\n',
        )
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout) == {
            'checked': 1,
            'findings': [
                {
                    'file': '.agents/skills/review/SKILL.md',
                    'line': 7,
                    'rule': 'skill.link-fragment',
                    'message': '`#checklist` names a heading this file does not have',
                    'spec': None,
                }
            ],
            'ungoverned': [],
        }, 'the link to a missing heading is reported on its own line, naming its fragment'

    def test_check_skills_with_json_format_over_a_skill_linked_outside_the_skills_directories_checks_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'skills/review/SKILL.md', '---\nname: audit\ndescription: Review a change\n---\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout) == {
            'checked': 1,
            'findings': [
                {
                    'file': '.agents/skills/review/SKILL.md',
                    'line': 2,
                    'rule': 'skill.name-matches-directory',
                    'message': "`name` is 'audit'; expected 'review', the name of the skill directory",
                    'spec': None,
                }
            ],
            'ungoverned': [],
        }, 'the skill is read through its link and reported where an agent finds it'

    def test_check_skills_with_json_format_over_a_skill_repeating_a_file_name_reports_it(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/code/guide.md', '# Guide\n')
        _write(tmp_path, 'docs/feat/guide.md', '# Guide\n')
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            '---\nname: review\ndescription: Review a change\nmetadata:\n'
            '  references: docs/code/guide.md docs/feat/guide.md\n---\n',
        )
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout) == {
            'checked': 1,
            'findings': [
                {
                    'file': '.agents/skills/review/SKILL.md',
                    'line': 4,
                    'rule': 'skill.metadata-duplicate-name',
                    'message': (
                        '`metadata.references` lists `docs/code/guide.md` and `docs/feat/guide.md`, '
                        'which both link in as `references/guide.md`'
                    ),
                    'spec': None,
                }
            ],
            'ungoverned': [],
        }, 'the repeated file name is reported on the line of the metadata key'

    def test_check_skills_with_json_format_over_a_skill_listing_a_source_file_reports_it(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'src/tool.py')
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            '---\nname: review\ndescription: Review a change\nmetadata:\n  scripts: src/tool.py\n---\n',
        )
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout) == {
            'checked': 1,
            'findings': [
                {
                    'file': '.agents/skills/review/SKILL.md',
                    'line': 4,
                    'rule': 'skill.metadata-outside-scope',
                    'message': (
                        '`metadata.scripts` lists `src/tool.py`, which lorecraft does not read; list a file directly '
                        'in docs/, in a real directory directly in docs/, or directly in a skill directory'
                    ),
                    'spec': None,
                }
            ],
            'ungoverned': [],
        }, 'the source file is outside what the command reads, and reported on the line of the metadata key'

    def test_check_skills_with_json_format_and_a_named_skill_checks_that_skill_alone(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/bare/SKILL.md', '# No frontmatter\n')
        named = _write(tmp_path, '.agents/skills/review/SKILL.md', '---\nname: review\ndescription: Review\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', str(named), '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {'checked': 1, 'findings': [], 'ungoverned': []}, (
            'only the named skill is checked, so the broken one beside it is not reported'
        )

    def test_check_skills_with_json_format_and_a_linked_skill_file_named_checks_that_skill(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'shared/REVIEW.md', '---\nname: review\ndescription: Review\n---\n')
        (tmp_path / '.agents' / 'skills' / 'review').mkdir(parents=True)
        named = tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md'
        named.symlink_to('../../../shared/REVIEW.md')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', str(named), '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {'checked': 1, 'findings': [], 'ungoverned': []}, (
            'a SKILL.md that is a link to its text names its skill, as the skill directory does'
        )

    def test_check_skills_with_a_non_utf8_skill_exits_with_an_undecodable_finding(self, tmp_path: Path) -> None:
        #: Given
        skill_file = tmp_path / '.agents' / 'skills' / 'latin' / 'SKILL.md'
        skill_file.parent.mkdir(parents=True)
        skill_file.write_bytes(b'---\nname: caf\xe9\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == '.agents/skills/latin/SKILL.md:1: [skill.undecodable] SKILL.md is not valid UTF-8\n', (
            'a skill that is not UTF-8 is a finding that names the file as a skill, not a document'
        )
        assert result.stderr == 'checked 1 skill(s), 1 finding(s)\n', 'the summary counts skills, not files'

    def test_check_skills_without_a_root_finds_the_nearest_parent_with_docs_meta(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        (tmp_path / 'docs' / '__meta__').mkdir(parents=True)
        _write(tmp_path, '.agents/skills/review/SKILL.md', '---\nname: review\n---\n')
        nested = tmp_path / 'src' / 'nested'
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills'])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == '.agents/skills/review/SKILL.md:1: [skill.description] `description` is required\n', (
            'the root is discovered upward from the working directory, and findings print root-relative'
        )

    def test_check_skills_with_one_skill_named_twice_checks_it_once(self, tmp_path: Path) -> None:
        #: Given
        skill_file = _write(tmp_path, '.agents/skills/review/SKILL.md', '---\nname: review\n---\n')
        arguments = ['check', 'skills', str(skill_file.parent), str(skill_file), '--root', str(tmp_path)]
        app = build_app()

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == '.agents/skills/review/SKILL.md:1: [skill.description] `description` is required\n', (
            'the skill named by its directory and by its SKILL.md is reported once'
        )
        assert result.stderr == 'checked 1 skill(s), 1 finding(s)\n', 'the skill named twice is checked once'

    def test_check_skills_with_a_linked_specs_directory_checks_the_skills(self, linked_specs_workspace: Path) -> None:
        #: Given
        _write(
            linked_specs_workspace, '.agents/skills/review/SKILL.md', '---\nname: review\ndescription: Review\n---\n'
        )
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', '--root', str(linked_specs_workspace), '--format', 'json'])

        #: Then
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {'checked': 1, 'findings': [], 'ungoverned': []}, (
            'the skill check reads no document, so a linked docs/__meta__ does not stop it'
        )

    def test_check_skills_with_json_format_over_a_root_without_skills_reports_none_checked(
        self, tmp_path: Path
    ) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {'checked': 0, 'findings': [], 'ungoverned': []}, (
            'a root with no skills directory has no skill to check, which is clean'
        )

    def test_check_skills_with_a_path_that_is_no_skill_exits_as_invalid_input(self, tmp_path: Path) -> None:
        #: Given
        not_a_skill = _write(tmp_path, '.agents/skills/drafts/README.md', '# Drafts\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'skills', str(not_a_skill.parent), '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'after an error nothing is printed but the error'
        assert result.stderr == (
            f'error: {not_a_skill.parent}: not a skill the workspace lists; name a skill directory or its SKILL.md\n'
        ), 'the error quotes the argument as typed and says what a skill argument names'


@pytest.mark.it
class TestCheckAllCommand:
    def test_check_with_a_clean_corpus_exits_zero_and_counts_the_documents_and_checks(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_AND_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n## Checklist\n\n- [ ] item\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == '', 'a clean run prints no finding lines'
        assert result.stderr == 'checked 1 file(s) and 0 skill(s) with 4 check(s), 0 finding(s)\n', (
            'one summary line covers every check the run made'
        )

    def test_check_with_findings_from_two_checks_exits_one_and_prints_them_check_by_check(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_AND_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '# No frontmatter\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == (
            'docs/code/guide.md:1: [frontmatter.missing] no `---` delimited frontmatter block\n'
            'docs/code/guide.md:1: [structure.outline] missing required section `Checklist` (per code.md)\n'
        ), "the bare run prints each check's findings as the check itself would, in check name order"
        assert result.stderr == 'checked 1 file(s) and 0 skill(s) with 4 check(s), 2 finding(s)\n', (
            'the summary counts the findings of every check together'
        )

    def test_check_with_an_ungoverned_document_prints_it_as_unvalidated(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == (
            'docs/code/guide.md:1: [code.ungoverned] no token budget for this corpus; tokens unvalidated\n'
        ), 'the document a check does not govern is printed under that check, not counted as a finding'
        assert result.stderr == 'checked 1 file(s) and 0 skill(s) with 4 check(s), 0 finding(s)\n', (
            'an ungoverned document is not a finding'
        )

    def test_check_with_a_broken_skill_prints_its_finding_after_the_document_checks(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_AND_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n## Checklist\n\n- [ ] item\n')
        _write(tmp_path, '.agents/skills/review/SKILL.md', '---\nname: review\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == '.agents/skills/review/SKILL.md:1: [skill.description] `description` is required\n', (
            'the skill finding prints as the skills check itself would'
        )
        assert result.stderr == 'checked 1 file(s) and 1 skill(s) with 4 check(s), 1 finding(s)\n', (
            'the summary counts the documents and the skills apart, and the skill finding with the rest'
        )

    def test_check_with_json_format_reports_each_check_under_its_name(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {
            'checks': {
                'budget': {'checked': 1, 'findings': [], 'ungoverned': ['docs/code/guide.md']},
                'frontmatter': {'checked': 1, 'findings': [], 'ungoverned': []},
                'skills': {'checked': 0, 'findings': [], 'ungoverned': []},
                'structure': {'checked': 1, 'findings': [], 'ungoverned': []},
            },
        }, f'each check keeps the report its own subcommand prints, got {result.stdout!r}'

    def test_check_with_json_format_over_a_broken_skill_reports_it_under_the_skills_check(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n')
        _write(tmp_path, '.agents/skills/review/SKILL.md', '---\nname: review\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout) == {
            'checks': {
                'budget': {'checked': 1, 'findings': [], 'ungoverned': ['docs/code/guide.md']},
                'frontmatter': {'checked': 1, 'findings': [], 'ungoverned': []},
                'skills': {
                    'checked': 1,
                    'findings': [
                        {
                            'file': '.agents/skills/review/SKILL.md',
                            'line': 1,
                            'rule': 'skill.description',
                            'message': '`description` is required',
                            'spec': None,
                        }
                    ],
                    'ungoverned': [],
                },
                'structure': {'checked': 1, 'findings': [], 'ungoverned': []},
            },
        }, 'a skill finding alone fails the bare run, and sits under the skills check beside the document checks'

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
        assert result.stderr == 'checked 0 file(s) and 0 skill(s) with 4 check(s), 0 finding(s)\n', (
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

    def test_check_with_an_option_before_a_named_check_exits_as_a_usage_error(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.structure.json', ACCEPT_ANY_FRONTMATTER_SPEC)
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path), 'frontmatter'])

        #: Then
        assert result.exit_code == 2, result.output
        assert 'give it after the check name' in result.output, (
            'an option the named check would never see is refused, not silently dropped'
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

    def test_register_with_a_group_name_raises_duplicate_command_error(self) -> None:
        #: Given
        build_app()
        name = 'check'

        #: When
        with pytest.raises(DuplicateCommandError) as exc_info:
            register(name)(_unused_handler)

        #: Then
        assert exc_info.value.name == name, 'a command cannot take the name a command group holds'

    def test_register_group_with_a_command_name_raises_duplicate_command_error(self) -> None:
        #: Given
        build_app()
        group = typer.Typer()

        #: When
        with pytest.raises(DuplicateCommandError) as exc_info:
            register_group('version', group)

        #: Then
        assert exc_info.value.name == 'version', 'a group cannot take the name a plain command holds'

    def test_build_app_when_called_mounts_the_check_group_with_its_frontmatter_command(self) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--help'])

        #: Then
        assert result.exit_code == 0, result.output
        assert 'frontmatter' in result.output, 'the check group lists the frontmatter check discovered beside it'
        assert 'header' not in result.output, 'the header alias of the frontmatter check is hidden from the help'

    def test_build_app_when_called_mounts_the_check_group_with_its_structure_command(self) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--help'])

        #: Then
        assert result.exit_code == 0, result.output
        assert 'structure' in result.output, 'the check group lists the structure check discovered beside it'

    def test_register_with_the_registered_handler_again_returns_it_unchanged(self) -> None:
        #: Given
        name = 'version'

        #: When
        returned = register(name)(version_handler)

        #: Then
        assert returned is version_handler, 'registering the same handler again is a no-op, not a duplicate'

    def test_register_group_with_a_different_group_under_a_taken_name_raises_duplicate_command_error(self) -> None:
        #: Given
        rival = typer.Typer()

        #: When
        with pytest.raises(DuplicateCommandError) as exc_info:
            register_group('check', rival)

        #: Then
        assert exc_info.value.name == 'check', 'a group cannot take the name another group holds'
        assert 'check' in str(exc_info.value), 'the message names the contested subcommand'

    def test_register_group_with_the_registered_group_again_keeps_it_mounted_once(self) -> None:
        #: Given
        name = 'check'

        #: When
        register_group(name, check_app)

        #: Then
        mounted = build_app().registered_groups
        assert len(mounted) == 1, f'registering the same group again is a no-op, got {len(mounted)} groups'
        assert mounted[0].typer_instance is check_app, 'the group mounted is still the one registered'
