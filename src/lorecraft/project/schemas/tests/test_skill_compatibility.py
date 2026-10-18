"""Bounded contradiction checks for a skills corpus frontmatter schema."""

import pytest

from lorecraft.core.mapping import Plain

from ..skill_compatibility import SkillSchemaContradiction, skill_schema_contradictions


@pytest.mark.unit
class TestSkillSchemaContradictions:
    def test_false_required_field_is_a_contradiction(self) -> None:
        assert skill_schema_contradictions({'properties': {'description': False}}) == (
            SkillSchemaContradiction(
                'description',
                'skill description must contain non-whitespace text and be at most 1024 characters',
            ),
        )

    @pytest.mark.parametrize(
        'field, constraint',
        [
            ('name', {'type': 'integer'}),
            ('description', {'minLength': 1025}),
            ('name', {'enum': ['BAD', 'bad_name']}),
            ('description', {'const': '   '}),
            ('name', {'minLength': 1.0, 'enum': ['BAD']}),
        ],
    )
    def test_direct_required_field_constraint_with_no_valid_value_is_a_contradiction(
        self, field: str, constraint: dict[str, Plain]
    ) -> None:
        assert skill_schema_contradictions({'properties': {field: constraint}}), (
            'the direct constraint excludes every value accepted by the built-in field rule'
        )

    def test_finite_constraint_with_a_valid_candidate_is_not_a_contradiction(self) -> None:
        assert skill_schema_contradictions({'properties': {'name': {'enum': ['valid-name']}}}) == ()

    def test_non_integer_bound_does_not_hide_a_valid_enum_candidate(self) -> None:
        assert skill_schema_contradictions({'properties': {'name': {'minLength': 1.0, 'enum': ['valid-name']}}}) == ()

    def test_unanalysed_indirect_constraint_is_not_declared_contradictory(self) -> None:
        assert skill_schema_contradictions({'properties': {'name': {'pattern': '^x$'}}}) == ()
