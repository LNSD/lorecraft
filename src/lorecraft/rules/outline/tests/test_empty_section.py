"""`LC304`, `empty-section`, over a document's headings.

Every case is a document written as text, read through a fake database that parses it as the real parser does, under
structure files decoded from JSON; no document is read from disk.
"""

from typing import Final

import pytest

from lib.primitives import StructurePrimitives
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import SectionEntry, SectionName
from lorecraft.project.syntax import LineNumber, parse_document
from lorecraft.rules.location import Elsewhere, Help, Note
from lorecraft.rules.tests.fake_database import (
    FakeDocumentDatabase,
    judged,
    namespace_spec,
    structure_spec,
    structure_spec_path,
)

from ..empty_section import EmptySection, EmptyTitle, OtherSection, SectionRole, empty_section_facts

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""The corpus structure file."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-cli')
"""A namespace structure file under the same corpus."""

FORBIDS_EMPTY: Final[str] = '{"empty_sections": "forbidden"}'
"""A structure file that forbids empty sections."""

ALLOWS_EMPTY: Final[str] = '{"forbidden": ["Changelog"]}'
"""A structure file that states another rule, and leaves empty sections allowed."""

EMPTY_INSTALL: Final[str] = '# Setup\n\n## Install\n\n## Run\n\nRun the toolkit once over the repository.\n'
"""A document whose title holds two sections: `Install`, empty, on line 3, and `Run`, holding prose, on line 5."""


@pytest.mark.unit
class TestEmptySection:
    def test_check_with_an_empty_section_reports_it_at_its_heading(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(EMPTY_INSTALL, corpus='guide', structure=FORBIDS_EMPTY)

        #: When
        occurrences = judged(EmptySection, subject)

        #: Then
        assert occurrences == (
            EmptySection(
                spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(3)), section='Install', role=OtherSection()
            ),
        ), 'an empty section is one occurrence, at its heading, naming the specification that forbids it'

    def test_check_with_empty_sections_allowed_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(EMPTY_INSTALL, corpus='guide', structure=ALLOWS_EMPTY)

        #: When
        occurrences = judged(EmptySection, subject)

        #: Then
        assert occurrences == (), 'a specification that does not forbid empty sections allows them'

    def test_check_with_every_section_holding_content_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(
            '# Setup\n\n## Run\n\nRun the toolkit once over the repository.\n', corpus='guide', structure=FORBIDS_EMPTY
        )

        #: When
        occurrences = judged(EmptySection, subject)

        #: Then
        assert occurrences == (), 'a document whose every section holds content has no empty section'

    def test_check_with_an_empty_title_reports_it(self) -> None:
        #: Given
        subject = FakeDocumentDatabase('# Setup\n', corpus='guide', structure=FORBIDS_EMPTY)

        #: When
        occurrences = judged(EmptySection, subject)

        #: Then
        assert occurrences == (
            EmptySection(spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(1)), section='Setup', role=EmptyTitle()),
        ), 'a lone title, which nothing follows, is an empty section like any other'

    def test_check_with_empty_sections_of_different_levels_reports_each_in_order(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(EMPTY_INSTALL + '\n### Linux\n', corpus='guide', structure=FORBIDS_EMPTY)

        #: When
        occurrences = judged(EmptySection, subject)

        #: Then
        assert occurrences == (
            EmptySection(
                spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(3)), section='Install', role=OtherSection()
            ),
            EmptySection(
                spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(9)), section='Linux', role=OtherSection()
            ),
        ), 'every empty heading is reported, whatever its level, in document order'

    def test_check_with_two_specifications_forbidding_empty_sections_reports_each_in_order(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(
            EMPTY_INSTALL,
            corpus='guide',
            structure=FORBIDS_EMPTY,
            namespaces=(namespace_spec('guide', 'cli', FORBIDS_EMPTY),),
        )

        #: When
        occurrences = judged(EmptySection, subject)

        #: Then
        assert occurrences == (
            EmptySection(
                spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(3)), section='Install', role=OtherSection()
            ),
            EmptySection(
                spec=NAMESPACE_SPEC, line=LineNumber(NonZeroUnsignedInt(3)), section='Install', role=OtherSection()
            ),
        ), 'each specification applies on its own, so the section is reported once for each, in order'

    def test_check_with_one_of_two_specifications_forbidding_empty_sections_reports_under_it_alone(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(
            EMPTY_INSTALL,
            corpus='guide',
            structure=ALLOWS_EMPTY,
            namespaces=(namespace_spec('guide', 'cli', FORBIDS_EMPTY),),
        )

        #: When
        occurrences = judged(EmptySection, subject)

        #: Then
        assert occurrences == (
            EmptySection(
                spec=NAMESPACE_SPEC, line=LineNumber(NonZeroUnsignedInt(3)), section='Install', role=OtherSection()
            ),
        ), 'a section is reported only under the specification that forbids empty sections'

    def test_message_names_the_section(self) -> None:
        #: Given
        occurrence = EmptySection(
            spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(3)), section='Install', role=OtherSection()
        )

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'section `Install` is empty', 'the message names the empty section'

    def test_check_with_an_empty_required_section_reports_the_entry_requiring_it(self) -> None:
        #: Given
        structure = (
            '{"empty_sections": "forbidden", "outline": [{"section": "Install", "description": "How to install."}]}'
        )
        subject = FakeDocumentDatabase('# Setup\n\n## Install\n', corpus='guide', structure=structure)
        entry = SectionEntry(name=SectionName.parse('Install'), description='How to install.')

        #: When
        occurrences = judged(EmptySection, subject)

        #: Then
        assert occurrences == (
            EmptySection(spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(3)), section='Install', role=entry),
        ), 'an empty section the outline requires carries the entry, for the help to describe'

    def test_check_with_an_empty_optional_section_carries_no_entry(self) -> None:
        #: Given
        structure = '{"empty_sections": "forbidden", "outline": [{"section": "Install", "optional": true}]}'
        subject = FakeDocumentDatabase('# Setup\n\n## Install\n', corpus='guide', structure=structure)

        #: When
        occurrences = judged(EmptySection, subject)

        #: Then
        assert occurrences == (
            EmptySection(
                spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(3)), section='Install', role=OtherSection()
            ),
        ), 'an optional entry requires nothing, so its section may be omitted like any other'

    def test_check_with_an_empty_subsection_named_like_a_required_section_carries_no_entry(self) -> None:
        #: Given
        structure = '{"empty_sections": "forbidden", "outline": [{"section": "Install"}]}'
        subject = FakeDocumentDatabase('# Setup\n\n## Install\n\n### Install\n', corpus='guide', structure=structure)

        #: When
        occurrences = judged(EmptySection, subject)

        #: Then
        assert occurrences == (
            EmptySection(
                spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(5)), section='Install', role=OtherSection()
            ),
        ), 'only an H2 is a section the outline requires, so an H3 of the same text is no required section'

    def test_check_with_an_extra_empty_title_does_not_mark_it_as_the_title(self) -> None:
        #: Given
        subject = FakeDocumentDatabase('# Setup\n\nText.\n\n# Second\n', corpus='guide', structure=FORBIDS_EMPTY)

        #: When
        occurrences = judged(EmptySection, subject)

        #: Then
        assert occurrences == (
            EmptySection(
                spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(5)), section='Second', role=OtherSection()
            ),
        ), 'only the first H1 is the title'

    def test_check_with_a_section_required_by_another_specification_carries_its_entry(self) -> None:
        #: Given
        required = '{"outline": [{"section": "Install", "description": "How to install."}]}'
        subject = FakeDocumentDatabase(
            '# Setup\n\n## Install\n',
            corpus='guide',
            structure=FORBIDS_EMPTY,
            namespaces=(namespace_spec('guide', 'cli', required),),
        )
        entry = SectionEntry(name=SectionName.parse('Install'), description='How to install.')

        #: When
        occurrences = judged(EmptySection, subject)

        #: Then
        assert occurrences == (
            EmptySection(spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(3)), section='Install', role=entry),
        ), 'the entry is looked up across every specification, not only the one that forbids empty sections'

    def _occurrence(self, role: SectionRole) -> EmptySection:
        return EmptySection(spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(3)), section='Install', role=role)

    def test_children_with_a_section_the_outline_does_not_require_say_to_omit_it(self) -> None:
        #: Given
        role = OtherSection()

        occurrence = self._occurrence(role)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('omit the section rather than leave it empty'),
        ), 'a note points at the specification that forbids empty sections, and a help says to omit the section'

    def test_children_with_an_empty_title_say_to_write_the_document_content(self) -> None:
        #: Given
        role = EmptyTitle()

        occurrence = self._occurrence(role)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),
            Help("write the document's content under its title"),
        ), 'the title is never omitted, so the help asks for its content'

    def test_children_with_a_required_section_give_its_description_and_first_example(self) -> None:
        #: Given
        entry = SectionEntry(
            name=SectionName.parse('Install'),
            description='How to install.',
            examples=('Run `pip install`.', 'Run `uv add`.'),
        )

        occurrence = self._occurrence(entry)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('write what the section holds: How to install.'),
            Note('for example:\n## Install\n\nRun `pip install`.'),
        ), 'one help asks for the content with the description as written, then the first example follows verbatim'

    def test_children_with_a_required_section_stating_nothing_ask_for_its_content_alone(self) -> None:
        #: Given
        entry = SectionEntry(name=SectionName.parse('Install'))

        occurrence = self._occurrence(entry)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the document structure is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('write what the section holds'),
        ), 'an entry stating no description and no example adds neither'


@pytest.mark.unit
class TestEmptySectionFacts:
    def test_empty_section_facts_holds_only_the_specifications_forbidding_them(self) -> None:
        #: Given
        corpus = structure_spec('code', '{"tokens": 100, "title": {"chars": 20}, "empty_sections": "forbidden"}')
        namespace = structure_spec('code-python', '{"tokens": 50, "title": {"words": 3}}')

        #: When
        specs = empty_section_facts(StructurePrimitives((corpus, namespace))).specs

        #: Then
        assert specs == (corpus.path,), 'only the specification that forbids empty sections'

    def test_empty_section_facts_of_no_specification_is_empty(self) -> None:
        #: When
        specs = empty_section_facts(StructurePrimitives(())).specs

        #: Then
        assert specs == (), 'nothing governs'

    def test_empty_section_facts_holds_the_empty_sections_in_document_order(self) -> None:
        #: Given
        headings = parse_document('# Title\n\n## Empty\n\n## Full\n\nText.\n\n## Last\n').headings

        #: When
        empty = empty_section_facts(StructurePrimitives((), headings)).empty

        #: Then
        assert [item.heading.text for item in empty] == ['Empty', 'Last'], 'document order'

    def test_empty_section_facts_gives_the_title_its_own_role(self) -> None:
        #: Given
        headings = parse_document('# Title\n').headings

        #: When
        empty = empty_section_facts(StructurePrimitives((), headings)).empty

        #: Then
        assert [item.role for item in empty] == [EmptyTitle()], 'the title'

    def test_empty_section_facts_gives_an_unrequired_section_the_other_role(self) -> None:
        #: Given
        headings = parse_document('# Title\n\nText.\n\n## Empty\n').headings

        #: When
        empty = empty_section_facts(StructurePrimitives((), headings)).empty

        #: Then
        assert [item.role for item in empty] == [OtherSection()], 'no outline requires it'
