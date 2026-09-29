"""Budget validation over a document's whole-file token count.

``validate_budget`` is pure, so every case here is a token count and an in-memory structure aspect; no document
and no specification file is read.
"""

import pytest

from lorecraft.project.layout import SPECS_DIR
from lorecraft.project.schemas import StructureAspect
from lorecraft.project.syntax import LineNumber

from ..budget import validate_budget


def _aspect(tokens: int | None, stem: str = 'code') -> StructureAspect:
    """A structure aspect at ``docs/__meta__/<stem>.structure.json`` with the given budget.

    It forbids empty sections as well, so an aspect without a budget still states a rule and can be built.
    """
    return StructureAspect(
        path=SPECS_DIR / f'{stem}.structure.json',
        title=None,
        forbid_empty_sections=True,
        outline=(),
        forbidden=(),
        tokens=tokens,
        frontmatter=None,
    )


@pytest.mark.unit
class TestValidateBudget:
    def test_validate_budget_with_a_file_over_the_budget_reports_it_on_line_1(self) -> None:
        #: Given
        aspects = (_aspect(tokens=6),)

        #: When
        result = validate_budget(aspects, token_count=7)

        #: Then
        assert [(violation.line, violation.rule, violation.message) for violation in result.violations] == [
            (LineNumber(1), 'budget.tokens', '7 tokens; the budget is 6 (per code.structure.json)')
        ], 'a file over the token budget is reported once, on line 1'

    def test_validate_budget_with_a_file_at_the_budget_returns_no_violations(self) -> None:
        #: Given
        aspects = (_aspect(tokens=7),)

        #: When
        result = validate_budget(aspects, token_count=7)

        #: Then
        assert result.violations == (), 'the budget is the most tokens allowed, so a file at the budget is clean'

    def test_validate_budget_with_an_aspect_without_a_budget_returns_no_violations(self) -> None:
        #: Given
        aspects = (_aspect(tokens=None),)

        #: When
        result = validate_budget(aspects, token_count=100_000)

        #: Then
        assert result.violations == (), 'an aspect that sets no budget limits nothing, however large the file'

    def test_validate_budget_with_empty_aspects_returns_no_violations(self) -> None:
        #: Given
        aspects: tuple[StructureAspect, ...] = ()

        #: When
        result = validate_budget(aspects, token_count=100_000)

        #: Then
        assert result.violations == (), 'an ungoverned document is never checked, whatever its size'

    def test_validate_budget_with_two_layers_applies_each_and_names_its_own_file(self) -> None:
        #: Given
        corpus = _aspect(tokens=100)
        namespace = _aspect(tokens=11, stem='code-python')

        #: When
        result = validate_budget((corpus, namespace), token_count=12)

        #: Then
        assert [violation.message for violation in result.violations] == [
            '12 tokens; the budget is 11 (per code-python.structure.json)'
        ], 'the namespace layer tightens the corpus budget, and the violation quotes the layer that set it'
