"""`LC003`, `malformed-structure-file`: the engine's diagnostic for a structure file that is not in the format."""

import pytest

from lorecraft.rules.identity import Severity
from lorecraft.rules.location import Help, Note, WholeSubject

from ..malformed_structure_file import FormatViolated, MalformedStructureFile, NoRuleStated


@pytest.mark.unit
class TestMalformedStructureFile:
    def test_code_of_malformed_structure_file_prints_lc003(self) -> None:
        #: Given
        condition = MalformedStructureFile

        #: When
        code = str(condition.CODE)

        #: Then
        assert code == 'LC003', 'the condition holds its place in the engine group'

    def test_severity_of_malformed_structure_file_is_error(self) -> None:
        #: Given
        condition = MalformedStructureFile

        #: When
        severity = condition.SEVERITY

        #: Then
        assert severity is Severity.ERROR, 'a load failure always fails the run'

    def test_primary_of_an_occurrence_is_the_whole_subject(self) -> None:
        #: Given
        occurrence = MalformedStructureFile(cause=NoRuleStated())

        #: When
        primary = occurrence.primary()

        #: Then
        assert primary == WholeSubject(), 'the failure is not at a line'

    def test_message_of_a_file_that_violates_the_format_names_the_format(self) -> None:
        #: Given
        occurrence = MalformedStructureFile(cause=FormatViolated(problems=('max_tokens: Extra inputs',)))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'structure file does not follow the structure format', (
            'the message states the condition, lowercase, no period'
        )

    def test_message_of_a_file_that_states_no_rule_says_so(self) -> None:
        #: Given
        occurrence = MalformedStructureFile(cause=NoRuleStated())

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'structure file states no rule', 'the message states the condition, lowercase, no period'

    def test_children_of_a_file_that_violates_the_format_list_each_problem_and_say_to_fix_them(self) -> None:
        #: Given
        occurrence = MalformedStructureFile(
            cause=FormatViolated(problems=('max_tokens: Extra inputs are not permitted', 'tokens: Input should be 1'))
        )

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Help('fix each problem listed'),
            Note('max_tokens: Extra inputs are not permitted'),
            Note('tokens: Input should be 1'),
        ), 'the fix is said as a help, then the facts the occurrence holds as notes'

    def test_children_of_a_file_that_states_no_rule_say_to_state_one_or_delete_it(self) -> None:
        #: Given
        occurrence = MalformedStructureFile(cause=NoRuleStated())

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Help('state a rule, or delete the file'),), 'there is nothing found to list, only a fix'
