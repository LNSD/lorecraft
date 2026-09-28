"""The CLI assembled: the root application, its global options, and the registry that mounts onto it.

These run the command line in process through Typer's `CliRunner`, so they cross module boundaries —
root application, registry, command module, version strings, the scan and the model load behind `inspect`,
the checks behind `check header` and `check structure` — without needing the console script that `tests/e2e/`
exercises. `inspect` and the checks read a real tree under `tmp_path`.
"""

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest
import typer
from typer.testing import CliRunner

from lorecraft import __version__
from lorecraft.cli import build_app
from lorecraft.cli.registry import DuplicateCommandError, register, register_group

runner = CliRunner()

# A well-formed Draft 2020-12 schema that accepts any frontmatter; the cases below turn on the tree, not the schema.
ACCEPT_ANY_HEADER_SCHEMA: Final[str] = '{"type": "object"}'

# A structure specification requiring a Checklist after the document's own sections.
CHECKLIST_STRUCTURE_SPEC: Final[str] = '{"spec": "code.md §5", "outline": [{"any": true}, {"section": "Checklist"}]}'


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
    """The workspace with a `code` header schema that is valid JSON but not a well-formed JSON Schema."""
    (workspace / 'docs' / '__meta__' / 'code.header.json').write_text('{"type": 5}\n')
    return workspace


@pytest.fixture(scope='function')
def unreadable_workspace(tmp_path: Path) -> Iterator[Path]:
    """A workspace root whose `docs/` refuses listing, restored afterwards so pytest can clean it up."""
    docs = tmp_path / 'docs'
    docs.mkdir()
    docs.chmod(0o000)
    yield tmp_path
    docs.chmod(0o700)


def _unused_handler() -> None:
    """Stand-in handler for a registration that must be rejected before it is ever mounted."""


def _write(root: Path, relative: str, text: str = '') -> Path:
    """Write one file under the root, creating its parents, and return its path."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


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
        assert '            └── logging.md [code]' in lines, 'a rule document sits under its corpus, with its spec'

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

    def test_inspect_with_a_malformed_header_schema_exits_one_and_names_it(
        self, malformed_schema_workspace: Path
    ) -> None:
        #: Given
        app = build_app()
        arguments = ['inspect', str(malformed_schema_workspace)]

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 1, result.output
        assert 'error: invalid schema docs/__meta__/code.header.json' in result.output, (
            'the failure names the schema the load rejected'
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
        assert 'error: cannot snapshot docs' in result.output, 'the failure names the path the scan stopped at'


@pytest.mark.it
class TestCheckHeaderCommand:
    def test_check_header_with_a_clean_corpus_exits_zero_and_counts_the_documents(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.header.json', ACCEPT_ANY_HEADER_SCHEMA)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == '', 'a clean run prints no finding lines'
        assert result.stderr == 'checked 1 file(s), 0 finding(s)\n', 'the summary goes to stderr'

    def test_check_header_without_a_root_finds_the_nearest_parent_with_docs_meta(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.header.json', ACCEPT_ANY_HEADER_SCHEMA)
        _write(tmp_path, 'docs/code/guide.md', '# No frontmatter\n')
        nested = tmp_path / 'src' / 'nested'
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header'])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == 'docs/code/guide.md:1: [frontmatter.missing] no `---` delimited frontmatter block\n', (
            'the root is discovered upward from the working directory, and findings print root-relative'
        )

    def test_check_header_with_a_corpus_without_a_header_schema_reports_it_ungoverned(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/feat.md', '# Feat\n')
        _write(tmp_path, 'docs/feat/overview.md', '# No frontmatter\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == (
            'docs/feat/overview.md:1: [feat.ungoverned] no header schema for this corpus; frontmatter unvalidated\n'
        ), 'an ungoverned document is reported as unvalidated, not as a finding'

    def test_check_header_with_invalid_corpus_name_exits_as_invalid_input(self, tmp_path: Path) -> None:
        #: Given
        document = _write(tmp_path, 'docs/bad-name/guide.md', '---\nname: "guide"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header', '--root', str(tmp_path), str(document)])

        #: Then
        assert result.exit_code == 2, result.output
        assert "invalid character '-' in corpus name 'bad-name'" in result.output, 'the CLI reports the invalid name'

    def test_check_header_with_a_path_in_a_corpus_subdirectory_exits_as_invalid_input(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.md')
        document = _write(tmp_path, 'docs/code/sub/guide.md', '---\nname: "guide"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header', '--root', str(tmp_path), str(document)])

        #: Then
        assert result.exit_code == 2, result.output
        assert 'corpora are flat' in result.output, 'the CLI reports that a nested file is not a document'

    def test_check_header_with_a_path_in_a_directory_without_a_spec_exits_as_invalid_input(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.md')
        document = _write(tmp_path, 'docs/blog/post.md', '---\nname: "post"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header', '--root', str(tmp_path), str(document)])

        #: Then
        assert result.exit_code == 2, result.output
        assert 'not a corpus' in result.output, 'the CLI reports that the directory has no specification'

    def test_check_header_with_a_malformed_header_schema_exits_as_invalid_input(
        self, malformed_schema_workspace: Path
    ) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header', '--root', str(malformed_schema_workspace)])

        #: Then
        assert result.exit_code == 2, result.output
        assert 'invalid schema docs/__meta__/code.header.json' in result.stderr, (
            'the failure names the schema the load rejected'
        )

    def test_check_header_with_a_non_utf8_governed_document_exits_with_an_undecodable_finding(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.header.json', ACCEPT_ANY_HEADER_SCHEMA)
        document = tmp_path / 'docs' / 'code' / 'guide.md'
        document.parent.mkdir(parents=True)
        document.write_bytes(b'---\nname: "gu\xffide"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 1, result.output
        assert 'docs/code/guide.md:1: [frontmatter.undecodable]' in result.stdout, (
            'a document that is not UTF-8 is a finding, not an invalid-input failure'
        )

    def test_check_header_with_a_spec_less_directory_beside_a_corpus_reports_only_the_corpus(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.header.json', ACCEPT_ANY_HEADER_SCHEMA)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n')
        _write(tmp_path, 'docs/blog/post.md', '---\nname: "post"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 0, result.output
        report = json.loads(result.stdout)
        assert report == {'checked': 1, 'findings': [], 'ungoverned': []}, (
            'only the corpus named in docs/__meta__/ is checked; the spec-less directory is not mentioned'
        )

    def test_check_header_with_a_finding_and_json_format_reports_the_file_as_text_and_the_line_as_a_number(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.header.json', ACCEPT_ANY_HEADER_SCHEMA)
        _write(tmp_path, 'docs/code/guide.md', '# No frontmatter\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 1, result.output
        assert json.loads(result.stdout)['findings'] == [
            {
                'file': 'docs/code/guide.md',
                'line': 1,
                'rule': 'frontmatter.missing',
                'message': 'no `---` delimited frontmatter block',
            }
        ], f'a finding serialises as the root-relative path and the line number, got {result.stdout!r}'

    def test_check_header_from_a_deleted_working_directory_exits_with_a_working_directory_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        deleted = tmp_path / 'deleted'
        deleted.mkdir()
        monkeypatch.chdir(deleted)
        deleted.rmdir()
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', 'header'])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stderr.startswith('cannot read the current directory:'), (
            f'an unreadable working directory is the reported failure, got {result.stderr!r}'
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
            'docs/code/guide.md:1: [structure.outline] missing required section `Checklist` (per code.md §5)\n'
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
        _write(tmp_path, 'docs/__meta__/code.structure.json', '{"spec": "code.md §5"}')
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
                'message': 'unexpected section `Appendix`; the outline ends before it (per code.md §5)',
            }
        ], f'a finding serialises as the root-relative path and the line number, got {result.stdout!r}'


@pytest.mark.it
class TestCheckAllCommand:
    def test_check_with_a_clean_corpus_exits_zero_and_counts_the_documents_and_checks(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.header.json', ACCEPT_ANY_HEADER_SCHEMA)
        _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_STRUCTURE_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n## Checklist\n\n- [ ] item\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 0, result.output
        assert result.stdout == '', 'a clean run prints no finding lines'
        assert result.stderr == 'checked 1 file(s) with 2 check(s), 0 finding(s)\n', (
            'one summary line covers every check the run made'
        )

    def test_check_with_findings_from_two_checks_exits_one_and_prints_them_check_by_check(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.header.json', ACCEPT_ANY_HEADER_SCHEMA)
        _write(tmp_path, 'docs/__meta__/code.structure.json', CHECKLIST_STRUCTURE_SPEC)
        _write(tmp_path, 'docs/code/guide.md', '# No frontmatter\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path)])

        #: Then
        assert result.exit_code == 1, result.output
        assert result.stdout == (
            'docs/code/guide.md:1: [frontmatter.missing] no `---` delimited frontmatter block\n'
            'docs/code/guide.md:1: [structure.outline] missing required section `Checklist` (per code.md §5)\n'
        ), "the bare run prints each check's findings as the check itself would, in check name order"

    def test_check_with_json_format_reports_each_check_under_its_name(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.header.json', ACCEPT_ANY_HEADER_SCHEMA)
        _write(tmp_path, 'docs/code/guide.md', '---\nname: "guide"\n---\n')
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path), '--format', 'json'])

        #: Then
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout) == {
            'checks': {
                'header': {'checked': 1, 'findings': [], 'ungoverned': []},
                'structure': {'checked': 1, 'findings': [], 'ungoverned': ['docs/code/guide.md']},
            },
        }, f'each check keeps the report its own subcommand prints, got {result.stdout!r}'

    def test_check_with_a_malformed_header_schema_exits_as_invalid_input(
        self, malformed_schema_workspace: Path
    ) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(malformed_schema_workspace)])

        #: Then
        assert result.exit_code == 2, result.output
        assert result.stdout == '', 'after an error nothing is printed but the error'

    def test_check_with_an_option_before_a_named_check_exits_as_a_usage_error(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.header.json', ACCEPT_ANY_HEADER_SCHEMA)
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--root', str(tmp_path), 'header'])

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
        assert name in str(exc_info.value), 'the error names the subcommand that was already registered'

    def test_register_with_a_group_name_raises_duplicate_command_error(self) -> None:
        #: Given
        build_app()
        name = 'check'

        #: When
        with pytest.raises(DuplicateCommandError) as exc_info:
            register(name)(_unused_handler)

        #: Then
        assert 'group' in str(exc_info.value), 'the error says the name is held by a command group'

    def test_register_group_with_a_command_name_raises_duplicate_command_error(self) -> None:
        #: Given
        build_app()
        group = typer.Typer()

        #: When
        with pytest.raises(DuplicateCommandError) as exc_info:
            register_group('version', group)

        #: Then
        assert 'command' in str(exc_info.value), 'the error says the name is held by a plain command'

    def test_build_app_when_called_mounts_the_check_group_with_its_header_command(self) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--help'])

        #: Then
        assert result.exit_code == 0, result.output
        assert 'header' in result.output, 'the check group lists the header check discovered beside it'

    def test_build_app_when_called_mounts_the_check_group_with_its_structure_command(self) -> None:
        #: Given
        app = build_app()

        #: When
        result = runner.invoke(app, ['check', '--help'])

        #: Then
        assert result.exit_code == 0, result.output
        assert 'structure' in result.output, 'the check group lists the structure check discovered beside it'
