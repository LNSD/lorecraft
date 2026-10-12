"""`LC014`, `unlistable-corpus-directory`: the engine's diagnostic for this load failure."""

import pytest

from lorecraft.project.corpus import CorpusName
from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import EntryHelp, EntryNote, WholeSubject
from lorecraft.vfs import OsRefusal

from ..unlistable_corpus_directory import UnlistableCorpusDirectory


def _occurrence() -> UnlistableCorpusDirectory:
    """One occurrence of `unlistable-corpus-directory`."""
    return UnlistableCorpusDirectory(corpus=CorpusName.parse('guide'), refusal=OsRefusal.PERMISSION_DENIED)


@pytest.mark.unit
class TestUnlistableCorpusDirectory:
    def test_code_of_unlistable_corpus_directory_prints_lc014(self) -> None:
        #: Given
        condition = UnlistableCorpusDirectory

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC014', 'the condition holds its place in the engine group'

    def test_severity_of_unlistable_corpus_directory_is_error(self) -> None:
        #: Given
        condition = UnlistableCorpusDirectory

        #: When
        severity = condition.SEVERITY

        #: Then
        assert severity is Severity.ERROR, 'a load failure always fails the run'

    def test_message_of_an_occurrence_names_the_condition(self) -> None:
        #: Given
        occurrence = _occurrence()

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'corpus directory cannot be listed', 'the message states the condition, lowercase, no period'

    def test_primary_of_an_occurrence_is_the_whole_subject(self) -> None:
        #: Given
        occurrence = _occurrence()

        #: When
        primary = occurrence.primary()

        #: Then
        assert primary == WholeSubject(), 'the failure is not at a line'

    def test_children_of_an_occurrence_say_what_was_found_and_how_to_fix_it(self) -> None:
        #: Given
        occurrence = _occurrence()

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            EntryNote('the documents of corpus guide cannot be listed: permission denied'),
            EntryHelp('make the directory listable by the process that runs the check'),
        ), 'the facts the occurrence holds are said as notes, and the fix as a help'
