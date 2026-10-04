"""Metadata validation over the frontmatter of a skill that links files in through ``metadata``.

``listed_by_subkey``, ``linked_in_paths`` and ``validate_skill_metadata`` are pure, so every case here is a text
literal parsed in memory, and the listed files with their states are built by hand; no snapshot is taken and no
``SKILL.md`` is read.
"""

from pathlib import PurePosixPath

import pytest

from lorecraft.project.syntax import Frontmatter, LineNumber, parse_frontmatter

from ..reporting import Violation
from ..skill_metadata import (
    ListedFile,
    ListedFiles,
    ListedFileState,
    linked_in_paths,
    listed_by_subkey,
    validate_skill_metadata,
)


def _mapping(text: str) -> Frontmatter:
    """Parse a frontmatter literal that the case writes as a mapping.

    Args:
        text: The document text, `---` delimiters included.
    """
    frontmatter = parse_frontmatter(text)
    assert isinstance(frontmatter, Frontmatter), 'the case writes a frontmatter that decodes to a mapping'
    return frontmatter


def _present(written: str) -> ListedFile:
    """A listed path that leads to a regular file the snapshot holds.

    Args:
        written: The path as the subkey writes it.
    """
    return ListedFile(written=written, state=ListedFileState.PRESENT)


def _missing(written: str) -> ListedFile:
    """A listed path in a directory the scope covers, with no regular file there.

    Args:
        written: The path as the subkey writes it.
    """
    return ListedFile(written=written, state=ListedFileState.MISSING)


def _outside_scope(written: str) -> ListedFile:
    """A listed path the snapshot never read.

    Args:
        written: The path as the subkey writes it.
    """
    return ListedFile(written=written, state=ListedFileState.OUTSIDE_SCOPE)


@pytest.mark.unit
class TestListedBySubkey:
    def test_listed_by_subkey_with_every_subkey_returns_them_in_subkey_order(self) -> None:
        #: Given
        frontmatter = _mapping(
            '---\nname: x\nmetadata:\n'
            '  assets: docs/__meta__/code.md\n'
            '  references: docs/code/a.md docs/code/b.md\n'
            '  scripts: skills/x/run.py\n'
            '---\n'
        )

        #: When
        listed = listed_by_subkey(frontmatter)

        #: Then
        assert listed == (
            ('references', ('docs/code/a.md', 'docs/code/b.md')),
            ('scripts', ('skills/x/run.py',)),
            ('assets', ('docs/__meta__/code.md',)),
        ), 'references, then scripts, then assets, whatever order the mapping writes them in'

    def test_listed_by_subkey_with_a_path_written_twice_returns_it_twice(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  references: docs/code/a.md docs/code/a.md\n---\n')

        #: When
        listed = listed_by_subkey(frontmatter)

        #: Then
        assert listed == (('references', ('docs/code/a.md', 'docs/code/a.md')),), (
            'every path is kept as written, so a repeat is there for the check to report'
        )

    def test_listed_by_subkey_with_a_block_scalar_list_splits_it_on_newlines(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  scripts: |\n    skills/a/run.py\n    skills/b/run.py\n---\n')

        #: When
        listed = listed_by_subkey(frontmatter)

        #: Then
        assert listed == (('scripts', ('skills/a/run.py', 'skills/b/run.py')),), (
            'a block scalar separates the paths by newlines, which split as any whitespace does'
        )

    def test_listed_by_subkey_with_a_tab_separated_list_splits_it_on_the_tab(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  assets: "docs/a/x.json\\tdocs/b/x.json"\n---\n')

        #: When
        listed = listed_by_subkey(frontmatter)

        #: Then
        assert listed == (('assets', ('docs/a/x.json', 'docs/b/x.json')),), 'a tab separates two paths as a space does'

    def test_listed_by_subkey_with_a_non_string_subkey_returns_nothing(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  references: 3\n---\n')

        #: When
        listed = listed_by_subkey(frontmatter)

        #: Then
        assert listed == (), 'a non-string value is the specification schema finding, not a list of paths'

    def test_listed_by_subkey_with_a_list_subkey_returns_nothing(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  references:\n    - docs/code/a.md\n    - docs/feat/a.md\n---\n')

        #: When
        listed = listed_by_subkey(frontmatter)

        #: Then
        assert listed == (), 'a list is the specification schema finding, not a list of paths'

    def test_listed_by_subkey_with_other_metadata_keys_returns_nothing(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  author: a.md\n  version: a.md\n---\n')

        #: When
        listed = listed_by_subkey(frontmatter)

        #: Then
        assert listed == (), 'only references, scripts and assets link files in'

    def test_listed_by_subkey_with_a_non_mapping_metadata_returns_nothing(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  - docs/code/a.md\n  - docs/feat/a.md\n---\n')

        #: When
        listed = listed_by_subkey(frontmatter)

        #: Then
        assert listed == (), 'a metadata that is not a mapping is the specification schema finding'

    def test_listed_by_subkey_with_metadata_written_twice_returns_the_last_value(self) -> None:
        #: Given
        frontmatter = _mapping(
            '---\nmetadata:\n  references: docs/code/a.md\nname: x\n'
            'metadata:\n  references: docs/code/a.md docs/feat/a.md\n---\n'
        )

        #: When
        listed = listed_by_subkey(frontmatter)

        #: Then
        assert listed == (('references', ('docs/code/a.md', 'docs/feat/a.md')),), (
            'the value read is the last one written, as the YAML loader keeps it'
        )

    def test_listed_by_subkey_without_metadata_returns_nothing(self) -> None:
        #: Given
        frontmatter = _mapping('---\nname: x\ndescription: y\n---\n')

        #: When
        listed = listed_by_subkey(frontmatter)

        #: Then
        assert listed == (), 'a skill without metadata lists no files'


@pytest.mark.unit
class TestLinkedInPaths:
    def test_linked_in_paths_with_files_under_each_subkey_returns_each_under_its_subkey_by_name(self) -> None:
        #: Given
        frontmatter = _mapping(
            '---\nmetadata:\n  references: docs/code/logging.md docs/feat/a.md\n'
            '  assets: docs/__meta__/code.md\n  scripts: tools/run.py\n---\n'
        )

        #: When
        paths = linked_in_paths(frontmatter)

        #: Then
        assert paths == frozenset(
            {
                PurePosixPath('references/logging.md'),
                PurePosixPath('references/a.md'),
                PurePosixPath('assets/code.md'),
                PurePosixPath('scripts/run.py'),
            }
        ), 'each listed file lands in the directory its subkey names, under its file name alone'

    def test_linked_in_paths_without_linking_subkeys_returns_no_paths(self) -> None:
        #: Given
        frontmatter = _mapping('---\nname: x\nmetadata:\n  author: someone\n---\n')

        #: When
        paths = linked_in_paths(frontmatter)

        #: Then
        assert paths == frozenset(), 'a metadata with no references, scripts or assets links nothing in'


@pytest.mark.unit
class TestValidateSkillMetadata:
    def test_validate_skill_metadata_with_distinct_file_names_returns_no_violations(self) -> None:
        #: Given
        frontmatter = _mapping('---\nname: x\nmetadata:\n  references: docs/code/a.md docs/code/b.md\n---\n')
        listed = (ListedFiles(subkey='references', files=(_present('docs/code/a.md'), _present('docs/code/b.md'))),)

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter, listed=listed)

        #: Then
        assert result.violations == (), 'distinct names link in at distinct paths, which is what the rule asks for'

    def test_validate_skill_metadata_with_a_missing_file_reports_it_on_the_metadata_line(self) -> None:
        #: Given
        frontmatter = _mapping('---\nname: x\nmetadata:\n  references: docs/code/gone.md\n---\n')
        listed = (ListedFiles(subkey='references', files=(_missing('docs/code/gone.md'),)),)

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter, listed=listed)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber.from_int(3),
                rule='skill.metadata-missing-file',
                message='`metadata.references` lists `docs/code/gone.md`, where lorecraft finds no file',
            ),
        ), 'a path with no regular file in a listed directory is one violation, on the line of the metadata key'

    def test_validate_skill_metadata_with_a_missing_file_written_twice_reports_the_repeat_and_both_paths(
        self,
    ) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  assets: docs/gone.md docs/gone.md\n---\n')
        listed = (ListedFiles(subkey='assets', files=(_missing('docs/gone.md'), _missing('docs/gone.md'))),)

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter, listed=listed)

        #: Then
        assert [violation.rule for violation in result.violations] == [
            'skill.metadata-duplicate-name',
            'skill.metadata-missing-file',
            'skill.metadata-missing-file',
        ], 'the repeated name comes first, then the missing file once for every time it is written'

    def test_validate_skill_metadata_with_missing_and_outside_paths_reports_them_grouped_by_rule(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  references: src/a.md docs/feat/b.md src/c.md docs/feat/a.md\n---\n')
        listed = (
            ListedFiles(
                subkey='references',
                files=(
                    _outside_scope('src/a.md'),
                    _missing('docs/feat/b.md'),
                    _outside_scope('src/c.md'),
                    _missing('docs/feat/a.md'),
                ),
            ),
        )

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter, listed=listed)

        #: Then
        assert [violation.rule for violation in result.violations] == [
            'skill.metadata-duplicate-name',
            'skill.metadata-missing-file',
            'skill.metadata-missing-file',
            'skill.metadata-outside-scope',
            'skill.metadata-outside-scope',
        ], 'within a subkey the repeated names come first, then the missing files, then the paths outside the scope'

    def test_validate_skill_metadata_with_a_path_outside_the_scope_reports_it_on_the_metadata_line(self) -> None:
        #: Given
        frontmatter = _mapping('---\nname: x\nmetadata:\n  scripts: src/tool.py\n---\n')
        listed = (ListedFiles(subkey='scripts', files=(_outside_scope('src/tool.py'),)),)

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter, listed=listed)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber.from_int(3),
                rule='skill.metadata-outside-scope',
                message=(
                    '`metadata.scripts` lists `src/tool.py`, which lorecraft does not read; list a file directly '
                    'in docs/, in a directory directly in docs/, or anywhere in a skill directory'
                ),
            ),
        ), 'a path the snapshot never read is one violation, on the line of the metadata key'

    def test_validate_skill_metadata_with_a_repeated_path_outside_the_scope_reports_the_repeat_and_both_paths(
        self,
    ) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  references: src/a.md src/a.md\n---\n')
        listed = (ListedFiles(subkey='references', files=(_outside_scope('src/a.md'), _outside_scope('src/a.md'))),)

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter, listed=listed)

        #: Then
        assert [violation.rule for violation in result.violations] == [
            'skill.metadata-duplicate-name',
            'skill.metadata-outside-scope',
            'skill.metadata-outside-scope',
        ], 'within a subkey the repeated name comes first, then each path outside the scope, in the order written'

    def test_validate_skill_metadata_with_a_repeated_file_name_reports_the_later_path_against_the_first(
        self,
    ) -> None:
        #: Given
        frontmatter = _mapping('---\nname: x\nmetadata:\n  references: docs/code/a.md docs/feat/a.md\n---\n')
        listed = (ListedFiles(subkey='references', files=(_present('docs/code/a.md'), _present('docs/feat/a.md'))),)

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter, listed=listed)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber.from_int(3),
                rule='skill.metadata-duplicate-name',
                message=(
                    '`metadata.references` lists `docs/code/a.md` and `docs/feat/a.md`, '
                    'which both link in as `references/a.md`'
                ),
            ),
        ), 'two paths with one file name would link in at one path; the second is reported, naming both'

    def test_validate_skill_metadata_with_a_name_repeated_twice_reports_each_repeat_against_the_first(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  assets: docs/a/x.md docs/b/x.md docs/c/x.md\n---\n')
        listed = (
            ListedFiles(
                subkey='assets',
                files=(_present('docs/a/x.md'), _present('docs/b/x.md'), _present('docs/c/x.md')),
            ),
        )

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter, listed=listed)

        #: Then
        assert [violation.message for violation in result.violations] == [
            '`metadata.assets` lists `docs/a/x.md` and `docs/b/x.md`, which both link in as `assets/x.md`',
            '`metadata.assets` lists `docs/a/x.md` and `docs/c/x.md`, which both link in as `assets/x.md`',
        ], 'every later repeat names the first path, the one the name was taken by'

    def test_validate_skill_metadata_with_one_name_under_two_subkeys_returns_no_violations(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  references: docs/code/a.md\n  assets: docs/feat/a.md\n---\n')
        listed = (
            ListedFiles(subkey='references', files=(_present('docs/code/a.md'),)),
            ListedFiles(subkey='assets', files=(_present('docs/feat/a.md'),)),
        )

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter, listed=listed)

        #: Then
        assert result.violations == (), 'references/a.md and assets/a.md are two paths, so the subkeys are independent'

    def test_validate_skill_metadata_with_several_subkeys_reports_them_in_the_order_listed(self) -> None:
        #: Given
        frontmatter = _mapping(
            '---\nmetadata:\n  references: docs/a/y.md docs/b/y.md\n  scripts: skills/a/run.py src/run.py\n---\n'
        )
        listed = (
            ListedFiles(subkey='references', files=(_present('docs/a/y.md'), _present('docs/b/y.md'))),
            ListedFiles(subkey='scripts', files=(_present('skills/a/run.py'), _outside_scope('src/run.py'))),
        )

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter, listed=listed)

        #: Then
        assert [(violation.rule, violation.message.split(' lists ')[0]) for violation in result.violations] == [
            ('skill.metadata-duplicate-name', '`metadata.references`'),
            ('skill.metadata-duplicate-name', '`metadata.scripts`'),
            ('skill.metadata-outside-scope', '`metadata.scripts`'),
        ], 'each subkey is checked whole, in the order listed, before the next'

    def test_validate_skill_metadata_with_metadata_written_twice_reports_on_the_last_occurrence(self) -> None:
        #: Given
        frontmatter = _mapping(
            '---\nmetadata:\n  references: docs/code/a.md\nname: x\n'
            'metadata:\n  references: docs/code/a.md docs/feat/a.md\n---\n'
        )
        listed = (ListedFiles(subkey='references', files=(_present('docs/code/a.md'), _present('docs/feat/a.md'))),)

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter, listed=listed)

        #: Then
        assert [violation.line for violation in result.violations] == [LineNumber.from_int(5)], (
            'the value checked is the last one written, so the finding is on its line'
        )

    def test_validate_skill_metadata_with_nothing_listed_returns_no_violations(self) -> None:
        #: Given
        frontmatter = _mapping('---\nname: x\ndescription: y\n---\n')
        listed: tuple[ListedFiles, ...] = ()

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter, listed=listed)

        #: Then
        assert result.violations == (), 'a skill that lists no files under metadata has none to repeat'
