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

    def test_children_with_an_absolute_target_say_it_resolves_differently_in_every_checkout(self) -> None:
        #: Given
        occurrence = OutsideSymlink(leaves_at=RootExit(RootRelativePath.parse('hop'), PurePosixPath('/home/alex')))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            EntryHelp(
                'an absolute target resolves differently in every checkout; move what it links to into the repository'
            ),
            EntryNote('leaves the repository at hop -> /home/alex'),
        ), 'a help comes first and says why an absolute target breaks, then a note names the link and its target'

    def test_children_with_a_relative_target_say_it_climbs_above_the_root(self) -> None:
        #: Given
        occurrence = OutsideSymlink(leaves_at=RootExit(RootRelativePath.parse('hop'), PurePosixPath('../../x')))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            EntryHelp(
                'a `..` on the chain climbs above the repository root; move what it links to into the repository'
            ),
            EntryNote('leaves the repository at hop -> ../../x'),
        ), 'a relative target gets the help for a climb above the root'

    def test_children_with_a_relative_target_without_a_climb_blame_the_chain_not_the_named_link(self) -> None:
        #: Given
        # `inner -> sub`, and `shared -> inner/../../../x`: the named link is `inner`, whose target climbs nothing
        occurrence = OutsideSymlink(leaves_at=RootExit(RootRelativePath.parse('inner'), PurePosixPath('sub')))

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            EntryHelp(
                'a `..` on the chain climbs above the repository root; move what it links to into the repository'
            ),
            EntryNote('leaves the repository at inner -> sub'),
        ), 'the help blames a `..` on the chain, so it does not send the writer to the named link as the climber'
