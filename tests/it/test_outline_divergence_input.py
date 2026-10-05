"""The outline divergence input, built from a database's queries for one decoded document.

The outlines come from the model's governance and the sections from the `parse` query, so the input is tested over
a database opened on an in-memory snapshot: a document that follows its outline, one for each way it can first
stop following it, one governed by two specifications of which one states an outline, and one no outline governs.
"""

from typing import Final

import pytest

from lorecraft.checks import Database, DocumentText
from lorecraft.checks.inputs import Ungoverned, build_outline_divergence_input
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.schemas import SectionName
from lorecraft.project.syntax import Heading, LineNumber, ParsedDocument, parse_document
from lorecraft.rules.inputs import (
    AbsentSection,
    DocumentEnd,
    MisplacedSection,
    OutlineDivergenceInput,
    OutlineDivergenceSpec,
    UnlistedSection,
)
from lorecraft.vfs import Snapshot

TYPING: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))
"""A document of corpus `code` its `python` namespace governs too."""

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code-python.structure.json')
"""The `python` namespace structure specification."""

RULE_ASIDE_CHECKLIST: Final[str] = (
    '# Typing\n'
    '\n'
    '## Rule\n'
    '\n'
    'Annotate every signature.\n'
    '\n'
    '## Aside\n'
    '\n'
    'Read the rationale once.\n'
    '\n'
    '## Checklist\n'
    '\n'
    '- [ ] Annotated.\n'
)
"""A document of thirteen lines: a title, then the sections `Rule`, `Aside` and `Checklist`."""


class ParsingDatabase(Database):
    """A database that records each document it is asked to parse, then parses it as usual."""

    def __init__(self, snapshot: Snapshot) -> None:
        """Open the database on the snapshot, with nothing parsed yet.

        Args:
            snapshot: The revision the database reads.
        """
        super().__init__(snapshot)
        self.parsed: list[DocumentRef] = []

    def parse(self, source: DocumentText) -> ParsedDocument:
        """Record the document, then parse it.

        Args:
            source: The decoded document that is parsed, recorded by its ref first.
        """
        self.parsed.append(source.ref)
        return super().parse(source)


def _snapshot(corpus_spec: bytes | None, namespace_spec: bytes | None, text: str) -> Snapshot:
    """A snapshot of corpus `code`, with a `python` namespace, holding the one document `TYPING`.

    Args:
        corpus_spec: Bytes of the corpus structure specification, or `None` for a corpus that has none.
        namespace_spec: Bytes of the `python` namespace structure specification, or `None` for none.
        text: The text of `TYPING`.
    """
    meta: dict[str, bytes] = {'code.md': b'# Code\n', 'code-python.md': b'# Code Python\n'}
    if corpus_spec is not None:
        meta['code.structure.json'] = corpus_spec
    if namespace_spec is not None:
        meta['code-python.structure.json'] = namespace_spec
    return Snapshot.from_tree({'docs': {'__meta__': meta, 'code': {'python-typing.md': text.encode()}}})


def _document_text(database: Database, ref: DocumentRef) -> DocumentText:
    """The witness of a document the test wrote as UTF-8, as the database decodes it.

    Args:
        database: The database the document is decoded by.
        ref: A document whose bytes are UTF-8.
    """
    source = database.text(ref)
    assert isinstance(source, DocumentText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


def _section(text: str, name: str) -> Heading:
    """The H2 section with this heading text, as the parser reads it from a document's text.

    Args:
        text: The document's text.
        name: The section's heading text.
    """
    for heading in parse_document(text).headings:
        if heading.level == 2 and heading.text == name:
            return heading
    raise AssertionError(f'the document holds a section `{name}`')


@pytest.mark.it
class TestBuildOutlineDivergenceInput:
    def test_build_outline_divergence_input_with_a_document_following_its_outline_holds_no_divergence(self) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'
        database = Database(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        assert subject == OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=None),)), (
            'a document whose sections match the outline, an unnamed one inside an `any` run, does not diverge'
        )

    def test_build_outline_divergence_input_with_a_section_absent_before_another_holds_it_before_that_section(
        self,
    ) -> None:
        #: Given
        outline = (
            b'{"outline": [{"section": "Rule"}, {"section": "Example", "description": "A worked case.",'
            b' "examples": ["The first.", "The second."]}, {"any": true}, {"section": "Checklist"}]}'
        )
        database = Database(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        absent = AbsentSection(
            name=SectionName.parse('Example'),
            description='A worked case.',
            example='The first.',
            before=_section(RULE_ASIDE_CHECKLIST, 'Aside'),
        )
        assert subject == OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=absent),)), (
            'a required section held nowhere is absent before the section found in its place, with what its entry '
            'states and only its first example'
        )

    def test_build_outline_divergence_input_with_a_section_absent_at_the_end_holds_the_last_line(self) -> None:
        #: Given
        outline = (
            b'{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}, {"section": "See Also"}]}'
        )
        database = Database(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        absent = AbsentSection(
            name=SectionName.parse('See Also'),
            description=None,
            example=None,
            before=DocumentEnd(last_line=LineNumber.from_int(13)),
        )
        assert subject == OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=absent),)), (
            "a required section expected after every section is absent at the end, the document's last line"
        )

    def test_build_outline_divergence_input_with_a_section_absent_from_an_empty_document_holds_line_1(self) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Rule"}]}'
        database = Database(_snapshot(outline, None, ''))
        source = _document_text(database, TYPING)

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        absent = AbsentSection(
            name=SectionName.parse('Rule'),
            description=None,
            example=None,
            before=DocumentEnd(last_line=LineNumber.from_int(1)),
        )
        assert subject == OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=absent),)), (
            'an empty document has no line, so its end is placed on line 1'
        )

    def test_build_outline_divergence_input_with_a_named_section_in_place_of_a_later_one_holds_it_misplaced(
        self,
    ) -> None:
        #: Given
        # `Rule` is written, but after `Checklist`, which the outline names and so is out of order where it stands
        text = '# Typing\n\n## Checklist\n\n- [ ] Annotated.\n\n## Rule\n\nAnnotate every signature.\n'
        outline = b'{"outline": [{"section": "Rule"}, {"section": "Checklist"}]}'
        database = Database(_snapshot(outline, None, text))
        source = _document_text(database, TYPING)

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        misplaced = MisplacedSection(section=_section(text, 'Checklist'), expected=SectionName.parse('Rule'))
        assert subject == OutlineDivergenceInput(
            specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=misplaced),)
        ), 'a named section standing where an expected section held later belongs is out of order'

    def test_build_outline_divergence_input_with_an_unnamed_section_in_place_of_a_later_one_holds_it_unlisted(
        self,
    ) -> None:
        #: Given
        # `Aside` stands between `Rule` and `Checklist`, where no `any` run allows a section the outline does not name
        outline = b'{"outline": [{"section": "Rule"}, {"section": "Checklist"}]}'
        database = Database(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        unlisted = UnlistedSection(
            section=_section(RULE_ASIDE_CHECKLIST, 'Aside'), expected=SectionName.parse('Checklist')
        )
        assert subject == OutlineDivergenceInput(
            specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=unlisted),)
        ), 'an unnamed section standing where an expected section held later belongs is unexpected'

    def test_build_outline_divergence_input_with_a_named_section_left_over_holds_it_misplaced(self) -> None:
        #: Given
        # the optional `Rule` is skipped where `Checklist` stands, so the `Rule` written after it is left over
        text = '# Typing\n\n## Checklist\n\n- [ ] Annotated.\n\n## Rule\n\nAnnotate every signature.\n'
        outline = b'{"outline": [{"section": "Rule", "optional": true}, {"section": "Checklist"}]}'
        database = Database(_snapshot(outline, None, text))
        source = _document_text(database, TYPING)

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        misplaced = MisplacedSection(section=_section(text, 'Rule'), expected=None)
        assert subject == OutlineDivergenceInput(
            specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=misplaced),)
        ), 'a named section left over once the outline is used up is out of order, with no section expected there'

    def test_build_outline_divergence_input_with_an_unnamed_section_left_over_holds_it_unlisted(self) -> None:
        #: Given
        text = '# Typing\n\n## Rule\n\nAnnotate every signature.\n\n## Aside\n\nRead the rationale once.\n'
        outline = b'{"outline": [{"section": "Rule"}]}'
        database = Database(_snapshot(outline, None, text))
        source = _document_text(database, TYPING)

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        unlisted = UnlistedSection(section=_section(text, 'Aside'), expected=None)
        assert subject == OutlineDivergenceInput(
            specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=unlisted),)
        ), 'an unnamed section left over once the outline is used up is unexpected, past the outline end'

    def test_build_outline_divergence_input_with_two_specifications_holds_only_those_stating_an_outline(self) -> None:
        #: Given
        corpus_spec = b'{"empty_sections": "forbidden"}'
        namespace_spec = b'{"outline": [{"section": "Rule"}, {"any": true}]}'
        database = Database(_snapshot(corpus_spec, namespace_spec, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        assert subject == OutlineDivergenceInput(
            specs=(OutlineDivergenceSpec(spec=NAMESPACE_SPEC, divergence=None),)
        ), 'a specification that states no outline has no entry, and the one that does is matched on its own'

    def test_build_outline_divergence_input_with_no_outline_returns_ungoverned(self) -> None:
        #: Given
        database = Database(_snapshot(b'{"empty_sections": "forbidden"}', None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        assert subject == Ungoverned(), 'no structure specification states an outline, so no outline governs it'

    def test_build_outline_divergence_input_with_no_outline_never_parses_the_document(self) -> None:
        #: Given
        database = ParsingDatabase(_snapshot(b'{"empty_sections": "forbidden"}', None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        build_outline_divergence_input(database, source)

        #: Then
        assert database.parsed == [], 'governance is read first, so a document no outline governs is never parsed'

    def test_build_outline_divergence_input_with_a_document_in_no_corpus_returns_ungoverned(self) -> None:
        #: Given
        # the code corpus has an outline, but `docs/blog/` has no corpus spec, so the model holds no `blog` corpus
        snapshot = Snapshot.from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n', 'code.structure.json': b'{"outline": [{"section": "Rule"}]}'},
                    'blog': {'launch.md': b'# Launch\n'},
                }
            }
        )
        database = Database(snapshot)
        source = _document_text(database, DocumentRef(CorpusName.parse('blog'), AspectFilename.parse('launch')))

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        assert subject == Ungoverned(), 'no specification governs a document in no corpus the model holds'
