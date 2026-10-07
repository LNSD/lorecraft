"""`FM008`, `wrong-type`, over the problems the frontmatter schemas find in a subject's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake context that holds it to its schemas as
the real analysis does, under structure specifications decoded from JSON; no file is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import FieldGuidance, JsonType, WrongTypeProblem
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_context import (
    FakeDocumentContext,
    FakeSkillContext,
    namespace_spec,
    structure_spec_path,
)

from ..wrong_type import WrongType

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure specification lies."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-setup')
"""Where a namespace structure specification under the same corpus lies."""

STRING_DESCRIPTION: Final[str] = (
    '{"frontmatter": {"type": "object", "properties": {"description": {"type": "string", "minLength": 20}}}}'
)
"""A structure specification whose frontmatter schema holds `description` to a string of at least 20 characters."""

TEXT: Final[str] = '---\nname: setup\ndescription: [Install.]\n---\n# Setup\n'
"""A document whose `description`, on line 3, is a list."""

PROBLEM: Final[WrongTypeProblem] = WrongTypeProblem(
    'description', "['Install.'] is not of type 'string'", (JsonType.STRING,), JsonType.ARRAY
)
"""A value of a type the schema does not accept: the rule's condition."""

LINE: Final[LineNumber] = LineNumber.from_int(3)
"""The line `description` is written on."""


@pytest.mark.unit
class TestWrongType:
    def test_check_with_a_wrong_type_reports_it_on_its_line_naming_the_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='guide', structure=STRING_DESCRIPTION)

        #: When
        occurrences = WrongType.check(subject)

        #: Then
        assert occurrences == (WrongType(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),), (
            "one problem is one occurrence, on the line its field is written on, naming the schema's specification"
        )

    def test_check_with_a_value_breaking_a_length_limit_reports_nothing(self) -> None:
        #: Given
        text = '---\nname: setup\ndescription: Install.\n---\n'
        subject = FakeDocumentContext(text, corpus='guide', structure=STRING_DESCRIPTION)

        #: When
        occurrences = WrongType.check(subject)

        #: Then
        assert occurrences == (), "a value of the right type that breaks another constraint is another rule's condition"

    def test_check_with_two_schemas_reports_each_problem_with_its_own_specification(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT,
            corpus='guide',
            structure=STRING_DESCRIPTION,
            namespaces=(namespace_spec('guide', 'setup', STRING_DESCRIPTION),),
        )

        #: When
        occurrences = WrongType.check(subject)

        #: Then
        assert occurrences == (
            WrongType(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM),
            WrongType(spec=NAMESPACE_SPEC, line=LINE, problem=PROBLEM),
        ), 'each schema is applied on its own, so each reports the problem under its own specification, in order'

    def test_check_with_a_skill_reports_it_with_no_specification_file(self) -> None:
        #: Given
        subject = FakeSkillContext('---\nname: review\ndescription: [Review a change.]\n---\n')

        #: When
        occurrences = WrongType.check(subject)

        #: Then
        problem = WrongTypeProblem(
            'description',
            '`description` must be a string',
            (JsonType.STRING,),
            JsonType.ARRAY,
            guidance=FieldGuidance(
                description=(
                    'What the skill does and when to use it, with the keywords that let an agent match it to a task.'
                ),
                example=(
                    'Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when '
                    'working with PDF documents or when the user mentions PDFs, forms, or document extraction.'
                ),
            ),
        )
        assert occurrences == (WrongType(spec=None, line=LINE, problem=problem),), (
            "the package states the Agent Skills schema, so a skill's occurrence names no specification file"
        )

    def test_check_with_a_block_that_is_not_a_mapping_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext('---\n- description\n---\n', corpus='guide', structure=STRING_DESCRIPTION)

        #: When
        occurrences = WrongType.check(subject)

        #: Then
        assert occurrences == (), (
            'no schema is applied to a block that is not a mapping, so it has no problem to report'
        )

    def test_message_with_an_occurrence_names_the_field(self) -> None:
        #: Given
        occurrence = WrongType(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'field `description` has a type the schema does not accept', (
            'the message names the field, in lowercase, naming no specification'
        )

    def test_labels_with_an_occurrence_say_the_type_expected_and_the_type_found(self) -> None:
        #: Given
        occurrence = WrongType(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LINE), 'expected string, found array'),), 'the label is on the field line'

    def test_labels_with_several_types_expected_join_them(self) -> None:
        #: Given
        problem = WrongTypeProblem('tags', 'wrong', (JsonType.STRING, JsonType.NULL), JsonType.OBJECT)
        occurrence = WrongType(spec=CORPUS_SPEC, line=LINE, problem=problem)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LINE), 'expected string or null, found object'),), (
            'every type the schema accepts is named'
        )

    def test_children_with_a_document_occurrence_point_at_the_specification(self) -> None:
        #: Given
        occurrence = WrongType(spec=CORPUS_SPEC, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),), (
            "the validator's prose is gone: the label says the types, and a list is no scalar to quote"
        )

    def test_children_with_a_skill_occurrence_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = WrongType(spec=None, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note("the Agent Skills specification states a SKILL.md's frontmatter schema"),), (
            'the Agent Skills specification is no file, so its note has no location'
        )

    def test_children_with_an_integer_where_a_string_belongs_say_to_quote_it(self) -> None:
        #: Given
        problem = WrongTypeProblem('version', 'wrong', (JsonType.STRING,), JsonType.INTEGER)
        occurrence = WrongType(spec=CORPUS_SPEC, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('quote the value, so YAML reads it as a string'),
        ), 'an integer written unquoted is a pitfall, as in `version: 1`'

    def test_children_with_a_number_where_a_string_belongs_say_to_quote_it(self) -> None:
        #: Given
        problem = WrongTypeProblem('version', 'wrong', (JsonType.STRING,), JsonType.NUMBER)
        occurrence = WrongType(spec=CORPUS_SPEC, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('quote the value, so YAML reads it as a string'),
        ), 'a fraction written unquoted is the usual pitfall, as in `version: 1.0`'

    def test_children_with_a_boolean_where_a_string_belongs_say_to_quote_it(self) -> None:
        #: Given
        problem = WrongTypeProblem('version', 'wrong', (JsonType.STRING,), JsonType.BOOLEAN)
        occurrence = WrongType(spec=CORPUS_SPEC, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('quote the value, so YAML reads it as a string'),
        ), 'a boolean written unquoted is a pitfall, as in `version: yes`'

    def test_children_with_a_number_where_no_string_is_expected_do_not_say_to_quote_it(self) -> None:
        #: Given
        problem = WrongTypeProblem('count', 'wrong', (JsonType.ARRAY,), JsonType.NUMBER)
        occurrence = WrongType(spec=CORPUS_SPEC, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'quoting makes a string, which is no help when a string is not what the schema expects'
        )

    def test_children_with_a_described_field_give_the_description(self) -> None:
        #: Given
        guidance = FieldGuidance(description='What the field is for.')
        problem = WrongTypeProblem('version', 'wrong', (JsonType.STRING,), JsonType.NUMBER, guidance=guidance)
        occurrence = WrongType(spec=CORPUS_SPEC, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('quote the value, so YAML reads it as a string'),
            Help('What the field is for.'),
        ), "the quoting help comes first, then the property's description as the schema wrote it"
