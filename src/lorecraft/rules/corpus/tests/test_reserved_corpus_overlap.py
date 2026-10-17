"""`COR001`, `reserved-corpus-overlap`, over one directory under `docs/` that takes a reserved corpus's name.

The model decides which directories overlap, so every case here is a fake directory entry; a directory with an
ordinary corpus name is no entry, and the rule cases hold that near miss.
"""

import pytest

from lorecraft.rules.identity import Level
from lorecraft.rules.location import EntryHelp, EntryNote, WholeSubject
from lorecraft.rules.tests.fake_database import FakeCorpusDirectoryDatabase, judged

from ..reserved_corpus_overlap import ReservedCorpusOverlap


@pytest.mark.unit
class TestReservedCorpusOverlap:
    def test_code_and_level_of_reserved_corpus_overlap_are_cor001_and_warn(self) -> None:
        #: Given
        rule = ReservedCorpusOverlap

        #: When
        code, level = str(rule.CODE), rule.LEVEL

        #: Then
        assert (code, level) == ('COR001', Level.WARN), 'the overlap is a rule that defaults to a warning'

    def test_check_with_a_directory_taking_a_reserved_name_reports_it_naming_the_corpus(self) -> None:
        #: Given
        subject = FakeCorpusDirectoryDatabase('skills')

        #: When
        occurrences = judged(ReservedCorpusOverlap, subject)

        #: Then
        assert occurrences == (ReservedCorpusOverlap(corpus='skills'),), 'the directory is one occurrence'

    def test_children_of_an_occurrence_say_how_to_fix_it_and_what_is_ignored(self) -> None:
        #: Given
        occurrence = ReservedCorpusOverlap(corpus='skills')

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            EntryHelp('move its documents to a corpus with another name'),
            EntryNote('`skills` is a reserved corpus, so the documents in this directory are not checked'),
        ), 'the help comes first, then the note naming the reserved corpus'

    def test_primary_of_an_occurrence_is_the_whole_directory(self) -> None:
        #: Given
        occurrence = ReservedCorpusOverlap(corpus='skills')

        #: When
        primary = occurrence.primary()

        #: Then
        assert primary == WholeSubject(), 'the diagnostic points at the directory, not a line'
