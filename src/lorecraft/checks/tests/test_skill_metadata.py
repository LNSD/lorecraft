"""Metadata validation over the frontmatter of a skill that links files in through ``metadata``.

``validate_skill_metadata`` is pure, so every case here is a text literal parsed in memory; no snapshot is taken
and no ``SKILL.md`` is read.
"""

import pytest

from lorecraft.project.syntax import Frontmatter, LineNumber, parse_frontmatter

from ..reporting import Violation
from ..skill_metadata import validate_skill_metadata


def _mapping(text: str) -> Frontmatter:
    """Parse a frontmatter literal that the case writes as a mapping."""
    frontmatter = parse_frontmatter(text)
    assert isinstance(frontmatter, Frontmatter), 'the case writes a frontmatter that decodes to a mapping'
    return frontmatter


@pytest.mark.unit
class TestValidateSkillMetadata:
    def test_validate_skill_metadata_with_distinct_file_names_returns_no_violations(self) -> None:
        #: Given
        frontmatter = _mapping('---\nname: x\nmetadata:\n  references: docs/code/a.md docs/code/b.md\n---\n')

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter)

        #: Then
        assert result.violations == (), 'distinct names link in at distinct paths, which is what the rule asks for'

    def test_validate_skill_metadata_with_a_repeated_file_name_reports_the_later_path_against_the_first(
        self,
    ) -> None:
        #: Given
        frontmatter = _mapping('---\nname: x\nmetadata:\n  references: docs/code/a.md docs/feat/a.md\n---\n')

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(3),
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

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter)

        #: Then
        assert [violation.message for violation in result.violations] == [
            '`metadata.assets` lists `docs/a/x.md` and `docs/b/x.md`, which both link in as `assets/x.md`',
            '`metadata.assets` lists `docs/a/x.md` and `docs/c/x.md`, which both link in as `assets/x.md`',
        ], 'every later repeat names the first path, the one the name was taken by'

    def test_validate_skill_metadata_with_one_name_under_two_subkeys_returns_no_violations(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  references: docs/code/a.md\n  assets: docs/feat/a.md\n---\n')

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter)

        #: Then
        assert result.violations == (), 'references/a.md and assets/a.md are two paths, so the subkeys are independent'

    def test_validate_skill_metadata_with_several_subkeys_reports_them_in_subkey_order(self) -> None:
        #: Given
        frontmatter = _mapping(
            '---\nmetadata:\n'
            '  assets: docs/a/x.json docs/b/x.json\n'
            '  scripts: skills/a/run.py skills/b/run.py\n'
            '  references: docs/a/y.md docs/b/y.md\n'
            '---\n'
        )

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter)

        #: Then
        assert [violation.message.split(' lists ')[0] for violation in result.violations] == [
            '`metadata.references`',
            '`metadata.scripts`',
            '`metadata.assets`',
        ], 'references, then scripts, then assets, whatever order the mapping writes them in'

    def test_validate_skill_metadata_with_a_non_string_subkey_returns_no_violations(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  references: 3\n---\n')

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter)

        #: Then
        assert result.violations == (), 'a non-string value is the specification schema finding, not this check'

    def test_validate_skill_metadata_with_a_list_subkey_returns_no_violations(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  references:\n    - docs/code/a.md\n    - docs/feat/a.md\n---\n')

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter)

        #: Then
        assert result.violations == (), 'a list is the specification schema finding, not a list of paths'

    def test_validate_skill_metadata_with_other_metadata_keys_returns_no_violations(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  author: a.md\n  version: a.md\n---\n')

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter)

        #: Then
        assert result.violations == (), 'only references, scripts and assets link files in'

    def test_validate_skill_metadata_with_a_non_mapping_metadata_returns_no_violations(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  - docs/code/a.md\n  - docs/feat/a.md\n---\n')

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter)

        #: Then
        assert result.violations == (), 'a metadata that is not a mapping is the specification schema finding'

    def test_validate_skill_metadata_with_metadata_written_twice_reports_on_the_last_occurrence(self) -> None:
        #: Given
        frontmatter = _mapping(
            '---\nmetadata:\n  references: docs/code/a.md\nname: x\n'
            'metadata:\n  references: docs/code/a.md docs/feat/a.md\n---\n'
        )

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter)

        #: Then
        assert [violation.line for violation in result.violations] == [LineNumber(5)], (
            'the value checked is the last one written, so the finding is on its line'
        )

    def test_validate_skill_metadata_with_a_block_scalar_list_reports_the_repeat(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  scripts: |\n    skills/a/run.py\n    skills/b/run.py\n---\n')

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(2),
                rule='skill.metadata-duplicate-name',
                message=(
                    '`metadata.scripts` lists `skills/a/run.py` and `skills/b/run.py`, '
                    'which both link in as `scripts/run.py`'
                ),
            ),
        ), 'a block scalar separates the paths by newlines, which split as any whitespace does'

    def test_validate_skill_metadata_with_a_tab_separated_list_reports_the_repeat(self) -> None:
        #: Given
        frontmatter = _mapping('---\nmetadata:\n  assets: "docs/a/x.json\\tdocs/b/x.json"\n---\n')

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter)

        #: Then
        assert [violation.message for violation in result.violations] == [
            '`metadata.assets` lists `docs/a/x.json` and `docs/b/x.json`, which both link in as `assets/x.json`',
        ], 'a tab separates two paths as a space does'

    def test_validate_skill_metadata_without_metadata_returns_no_violations(self) -> None:
        #: Given
        frontmatter = _mapping('---\nname: x\ndescription: y\n---\n')

        #: When
        result = validate_skill_metadata(frontmatter=frontmatter)

        #: Then
        assert result.violations == (), 'a skill that lists no files under metadata has none to repeat'
