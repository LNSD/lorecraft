"""`FM009`, `invalid-value`, over the problems the frontmatter schemas find in a subject's frontmatter.

Every case is a document or a `SKILL.md` written as text, read through a fake database that holds it to its schemas as
the real analysis does, under structure files decoded from JSON; no file is read from disk.
"""

from textwrap import dedent
from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import (
    AgentSkillsSchema,
    FieldGuidance,
    InvalidValueProblem,
    OneOfValues,
    OtherValueConstraint,
    PatternMismatch,
    StructureSpecSchema,
)
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_database import (
    FakeDocumentDatabase,
    FakeSkillDatabase,
    judged,
    namespace_spec,
    structure_spec_path,
)
from lorecraft.schemas.agent_skills_frontmatter import SKILL_NAME_PATTERN

from ..invalid_value import InvalidValue

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('guide')
"""Where the corpus structure file lies."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('guide-setup')
"""Where a namespace structure file under the same corpus lies."""

CORPUS_SOURCE: Final[StructureSpecSchema] = StructureSpecSchema(spec=CORPUS_SPEC)
"""The schema the corpus meta spec states."""

NAMESPACE_SOURCE: Final[StructureSpecSchema] = StructureSpecSchema(spec=NAMESPACE_SPEC)
"""The schema the namespace meta spec states."""

AGENT_SKILLS_SOURCE: Final[AgentSkillsSchema] = AgentSkillsSchema()
"""The schema the Agent Skills specification states, which governs a skill."""

NAME_PATTERN: Final[str] = (
    '{"frontmatter": {"type": "object", "properties": {"name": {"type": "string", "pattern": "^[a-z-]+$"}}}}'
)
"""A structure file whose frontmatter schema holds `name` to a string of lowercase letters and hyphens."""

TEXT: Final[str] = dedent("""\
    ---
    name: Setup Guide
    ---
    # Setup
    """)
"""A document whose `name`, on line 2, breaks the pattern."""

PROBLEM: Final[InvalidValueProblem] = InvalidValueProblem(
    'name', "'Setup Guide' does not match '^[a-z-]+$'", PatternMismatch('^[a-z-]+$')
)
"""A value breaking a pattern: the rule's condition."""

LINE: Final[LineNumber] = LineNumber(NonZeroUnsignedInt(2))
"""The line `name` is written on."""


@pytest.mark.unit
class TestInvalidValue:
    def test_check_with_a_value_breaking_a_pattern_reports_it_on_its_line_naming_the_specification(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(TEXT, corpus='guide', structure=NAME_PATTERN)

        #: When
        occurrences = judged(InvalidValue, subject)

        #: Then
        assert occurrences == (InvalidValue(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM),), (
            "one problem is one occurrence, on the line its field is written on, naming the schema's specification"
        )

    def test_check_with_a_wrong_type_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: 3
            ---
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=NAME_PATTERN)

        #: When
        occurrences = judged(InvalidValue, subject)

        #: Then
        assert occurrences == (), "a value of the wrong type is another rule's condition"

    def test_check_with_two_schemas_reports_each_problem_with_its_own_specification(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(
            TEXT, corpus='guide', structure=NAME_PATTERN, namespaces=(namespace_spec('guide', 'setup', NAME_PATTERN),)
        )

        #: When
        occurrences = judged(InvalidValue, subject)

        #: Then
        assert occurrences == (
            InvalidValue(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM),
            InvalidValue(source=NAMESPACE_SOURCE, line=LINE, problem=PROBLEM),
        ), 'each schema is applied on its own, so each reports the problem under its own specification, in order'

    def test_check_with_a_skill_reports_it_with_no_specification_file(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: review
            description: Review a change.
            compatibility: ""
            ---
            """)
        subject = FakeSkillDatabase(text)

        #: When
        occurrences = judged(InvalidValue, subject)

        #: Then
        problem = InvalidValueProblem(
            'compatibility',
            'skill compatibility cannot be empty; leave the field out instead',
            OtherValueConstraint(),
            guidance=FieldGuidance(
                description=(
                    'The environment the skill needs: the product it is meant for, the system packages it runs, or '
                    'network access. Most skills need none, and leave it out.'
                ),
                example='Designed for Claude Code (or similar products)',
            ),
        )
        assert occurrences == (
            InvalidValue(source=AGENT_SKILLS_SOURCE, line=LineNumber(NonZeroUnsignedInt(4)), problem=problem),
        ), "the package states the Agent Skills schema, so a skill's occurrence names no specification file"

    def test_labels_with_a_skill_name_outside_the_allowed_format_name_the_pattern(self) -> None:
        #: Given
        text = dedent("""\
            ---
            name: Review
            description: Review a change.
            ---
            """)
        subject = FakeSkillDatabase(text)
        occurrences = judged(InvalidValue, subject)

        #: When
        labels = occurrences[0].labels()

        #: Then
        assert labels == (
            Label(Here(LineNumber(NonZeroUnsignedInt(2))), f'does not match the pattern `{SKILL_NAME_PATTERN}`'),
        ), "a skill's malformed name is labelled as a document's pattern fault is"

    def test_check_with_a_block_that_is_not_a_mapping_reports_nothing(self) -> None:
        #: Given
        text = dedent("""\
            ---
            - Setup Guide
            ---
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=NAME_PATTERN)

        #: When
        occurrences = judged(InvalidValue, subject)

        #: Then
        assert occurrences == (), (
            'no schema is applied to a block that is not a mapping, so it has no problem to report'
        )

    def test_message_names_the_field(self) -> None:
        #: Given
        occurrence = InvalidValue(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'field `name` breaks a constraint of the schema', (
            'the message names the field, in lowercase, naming no specification'
        )

    def test_labels_with_a_pattern_name_it_on_the_field_line(self) -> None:
        #: Given
        occurrence = InvalidValue(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LINE), 'does not match the pattern `^[a-z-]+$`'),), (
            'the label sits on the field line and states the pattern'
        )

    def test_labels_with_values_allowed_say_the_value_is_not_one_of_them(self) -> None:
        #: Given
        problem = InvalidValueProblem('type', 'wrong', OneOfValues(('rule', 'pattern')))
        occurrence = InvalidValue(source=CORPUS_SOURCE, line=LINE, problem=problem)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LINE), 'not one of the allowed values'),), 'the values themselves are a help'

    def test_labels_with_another_keyword_label_nothing(self) -> None:
        #: Given
        problem = InvalidValueProblem('name', 'wrong', OtherValueConstraint())
        occurrence = InvalidValue(source=CORPUS_SOURCE, line=LINE, problem=problem)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (), "a keyword with no typed constraint has nothing to label but the validator's prose"

    def test_children_with_a_pattern_point_at_the_specification_only(self) -> None:
        #: Given
        occurrence = InvalidValue(source=CORPUS_SOURCE, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),), (
            "the pattern is in the label, and the schema states no reason, so the validator's prose is not repeated"
        )

    def test_children_with_a_skill_occurrence_name_the_agent_skills_specification(self) -> None:
        #: Given
        occurrence = InvalidValue(source=AGENT_SKILLS_SOURCE, line=LINE, problem=PROBLEM)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note("the Agent Skills specification states a SKILL.md's frontmatter schema"),), (
            'the Agent Skills specification is no file, so its note has no location'
        )

    def test_children_with_a_reason_and_a_description_prefer_the_reason(self) -> None:
        #: Given
        guidance = FieldGuidance(description='The name.', example='setup-guide')
        problem = InvalidValueProblem(
            'name', 'wrong', PatternMismatch('^x$'), reason='Lowercase words only.', guidance=guidance
        )
        occurrence = InvalidValue(source=CORPUS_SOURCE, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        example = dedent("""\
            for example:
            name: setup-guide""")
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('Lowercase words only.'),
            Note(example),
        ), "the failing subschema's own reason is the help, as written, and the example follows verbatim"

    def test_children_with_a_description_and_no_reason_give_the_description(self) -> None:
        #: Given
        guidance = FieldGuidance(description='The name.')
        problem = InvalidValueProblem('name', 'wrong', PatternMismatch('^x$'), guidance=guidance)
        occurrence = InvalidValue(source=CORPUS_SOURCE, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('The name.'),
        ), "without a reason, the property's description is the help"

    def test_children_with_values_allowed_list_them(self) -> None:
        #: Given
        problem = InvalidValueProblem('type', 'wrong', OneOfValues(('rule', 'pattern')))
        occurrence = InvalidValue(source=CORPUS_SOURCE, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('write one of: rule, pattern'),
        ), 'the label cannot hold the values, so a help lists them'

    def test_children_with_another_keyword_end_with_the_validator_wording(self) -> None:
        #: Given
        problem = InvalidValueProblem(
            'description',
            "'Load when x.' should not be valid under {'pattern': '\\\\.\\\\s*$'}",
            OtherValueConstraint(),
            reason='No trailing period.',
            guidance=FieldGuidance(example='Load when x'),
        )
        occurrence = InvalidValue(source=CORPUS_SOURCE, line=LINE, problem=problem)

        #: When
        children = occurrence.children()

        #: Then
        example = dedent("""\
            for example:
            description: Load when x""")
        assert children == (
            Note('the frontmatter schema is set here', at=Elsewhere(CORPUS_SPEC)),
            Help('No trailing period.'),
            Note(example),
            Note(problem.message),
        ), "the validator's prose is the fallback for a keyword with no typed constraint, and comes last"

    def test_check_with_a_comment_on_the_failing_subschema_gives_it_as_the_help(self) -> None:
        #: Given
        structure = (
            '{"frontmatter": {"type": "object", "properties": {"description": {"type": "string", "allOf": '
            '[{"not": {"pattern": "\\\\.\\\\s*$"}, "$comment": "No trailing period."}]}}}}'
        )
        text = dedent("""\
            ---
            description: Load when x.
            ---
            """)
        subject = FakeDocumentDatabase(text, corpus='guide', structure=structure)

        #: When
        occurrences = judged(InvalidValue, subject)

        #: Then
        message = "'Load when x.' should not be valid under {'pattern': '\\\\.\\\\s*$'}"
        problem = InvalidValueProblem(
            'description', message, OtherValueConstraint(), reason='No trailing period.', guidance=FieldGuidance()
        )
        assert occurrences == (
            InvalidValue(source=CORPUS_SOURCE, line=LineNumber(NonZeroUnsignedInt(2)), problem=problem),
        ), (
            "the schema's `$comment` reaches the occurrence as the reason, so it is the help, ahead of the "
            "validator's prose"
        )
