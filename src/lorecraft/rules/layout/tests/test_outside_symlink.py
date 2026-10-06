"""`LAY001`, `outside-symlink`, over one symlink of the skill layout whose chain leaves the repository.

The rule only words where the chain leaves, which the scan decides, so every case here is a fake layout entry; a
symlink that stays inside the repository is no layout entry, and the runner's integration tests hold that near miss.
"""

from pathlib import PurePosixPath

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.location import EntryHelp, EntryNote, WholeSubject
from lorecraft.rules.tests.fake_context import FakeLayoutContext
from lorecraft.vfs import RootExit

from ..outside_symlink import OutsideSymlink


@pytest.mark.unit
class TestOutsideSymlink:
    def test_check_with_a_symlink_linking_straight_out_reports_it_leaving_through_itself(self) -> None:
        #: Given
        leaves_at = RootExit(RootRelativePath.parse('.agents/skills/review'), PurePosixPath('/home/alex/review'))
        subject = FakeLayoutContext(leaves_at)

        #: When
        occurrences = OutsideSymlink.check(subject)

        #: Then
        assert occurrences == (OutsideSymlink(leaves_at=leaves_at),), (
            'a symlink whose own target is outside the repository is one occurrence, leaving through itself'
        )

    def test_check_with_a_chain_leaving_through_a_later_link_reports_that_link(self) -> None:
        #: Given
        # `.agents/skills/review -> ../../hop/review`, and `hop -> /home/alex`
        leaves_at = RootExit(RootRelativePath.parse('hop'), PurePosixPath('/home/alex'))
        subject = FakeLayoutContext(leaves_at)

        #: When
        occurrences = OutsideSymlink.check(subject)

        #: Then
        assert occurrences == (OutsideSymlink(leaves_at=leaves_at),), (
            'the occurrence names the link the chain leaves through, not the symlink an agent reaches'
        )

    def test_check_with_a_link_climbing_above_the_root_reports_its_relative_target(self) -> None:
        #: Given
        leaves_at = RootExit(RootRelativePath.parse('.agents/skills/review/shared'), PurePosixPath('../../../../x'))
        subject = FakeLayoutContext(leaves_at)

        #: When
        occurrences = OutsideSymlink.check(subject)

        #: Then
        assert occurrences == (OutsideSymlink(leaves_at=leaves_at),), (
            'a `..` climbing above the root leaves the repository as an absolute target does'
        )

    def test_primary_with_an_occurrence_points_at_the_whole_entry(self) -> None:
        #: Given
        occurrence = OutsideSymlink(leaves_at=RootExit(RootRelativePath.parse('hop'), PurePosixPath('/home/alex')))

        #: When
        primary = occurrence.primary()

        #: Then
        assert primary == WholeSubject(), 'a symlink has no lines, so the occurrence points at the entry itself'

    def test_message_with_an_occurrence_names_the_condition(self) -> None:
        #: Given
        occurrence = OutsideSymlink(leaves_at=RootExit(RootRelativePath.parse('hop'), PurePosixPath('/home/alex')))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'symlink leads outside the repository', 'the message names the condition alone'

    def test_children_with_an_occurrence_name_where_the_chain_leaves_and_what_to_keep_inside(self) -> None:
        #: Given
        occurrence = OutsideSymlink(leaves_at=RootExit(RootRelativePath.parse('hop'), PurePosixPath('/home/alex')))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            EntryNote('leaves the repository at hop -> /home/alex'),
            EntryHelp('keep every file a skill loads inside the repository'),
        ), 'a note names the link the chain leaves through and its target, and a help what to keep inside'
