"""The report of a symlink of the skill layout whose chain leaves the repository.

`validate_outside_symlink` is pure, so every case here is a recorded exit; no symlink is followed.
"""

from pathlib import PurePosixPath

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.vfs import RootExit

from ..reporting import Note, NoteKind, Violation
from ..skill_symlink import validate_outside_symlink


@pytest.mark.unit
class TestValidateOutsideSymlink:
    def test_validate_outside_symlink_with_an_absolute_target_reports_it_on_line_1_with_a_note(self) -> None:
        #: Given
        leaves_at = RootExit(RootRelativePath.parse('.agents/skills/x'), PurePosixPath('/opt/team-skills/x'))

        #: When
        result = validate_outside_symlink(leaves_at=leaves_at)

        #: Then
        assert result.violations == (
            Violation(
                line=LineNumber(1),
                rule='skill.symlink-outside',
                message='symlink leads outside the repository',
                notes=(
                    Note(NoteKind.NOTE, 'leaves the repository at .agents/skills/x -> /opt/team-skills/x'),
                    Note(NoteKind.HELP, 'keep every file a skill loads inside the repository'),
                ),
            ),
        ), 'one violation on line 1, naming the link and its target in a note, then a help note'

    def test_validate_outside_symlink_with_a_climbing_target_names_it_as_recorded(self) -> None:
        #: Given
        leaves_at = RootExit(RootRelativePath.parse('hop'), PurePosixPath('../shared'))

        #: When
        result = validate_outside_symlink(leaves_at=leaves_at)

        #: Then
        notes = [note.text for violation in result.violations for note in violation.notes if note.kind is NoteKind.NOTE]
        assert notes == ['leaves the repository at hop -> ../shared'], 'a relative target is shown as written'
