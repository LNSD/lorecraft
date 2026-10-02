"""Budget validation over a document's whole-file token count.

`validate_budget` is pure, so every case here is a token count and an in-memory structure specification; no
document and no specification file is read.
"""

import pytest

from lorecraft.project.layout import SPECS_DIR
from lorecraft.project.schemas import SpecFileType, StructureSpec, StructureSpecFile, parse_spec_name, spec_filename
from lorecraft.project.syntax import LineNumber

from ..budget import validate_budget


def _structure_spec(tokens: int | None, spec_name: str = 'code') -> StructureSpec:
    """A structure specification at `docs/__meta__/<spec_name>.structure.json` with the given budget.

    It forbids empty sections as well, so a structure specification without a budget still states a rule and can be
    built.

    Args:
        tokens: The whole-file token budget; `None` sets no budget.
        spec_name: Specification name the file sits at, such as `code` or `code-python`.
    """
    name = parse_spec_name(spec_name)
    return StructureSpec(
        file=StructureSpecFile(path=SPECS_DIR / spec_filename(name, SpecFileType.STRUCTURE), name=name),
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
        structure_specs = (_structure_spec(tokens=6),)

        #: When
        result = validate_budget(structure_specs, token_count=7)

        #: Then
        assert len(result.violations) == 1, f'a file over the token budget is reported once, got {result.violations}'
        assert result.violations[0].line == LineNumber(1), (
            'a budget violation has no line of its own, so it is on line 1'
        )
        assert result.violations[0].rule == 'budget.tokens', 'going over the budget breaks the token budget rule'
        assert result.violations[0].message == '7 tokens; the budget is 6 (per code.structure.json)', (
            'the message states the tokens found, the budget and the specification it comes from'
        )

    def test_validate_budget_with_a_file_at_the_budget_returns_no_violations(self) -> None:
        #: Given
        structure_specs = (_structure_spec(tokens=7),)

        #: When
        result = validate_budget(structure_specs, token_count=7)

        #: Then
        assert result.violations == (), 'the budget is the most tokens allowed, so a file at the budget is clean'

    def test_validate_budget_with_a_structure_spec_without_a_budget_returns_no_violations(self) -> None:
        #: Given
        structure_specs = (_structure_spec(tokens=None),)

        #: When
        result = validate_budget(structure_specs, token_count=100_000)

        #: Then
        assert result.violations == (), (
            'a structure specification that sets no budget limits nothing, however large the file'
        )

    def test_validate_budget_with_empty_structure_specs_returns_no_violations(self) -> None:
        #: Given
        structure_specs: tuple[StructureSpec, ...] = ()

        #: When
        result = validate_budget(structure_specs, token_count=100_000)

        #: Then
        assert result.violations == (), 'an ungoverned document is never checked, whatever its size'

    def test_validate_budget_with_two_layers_applies_each_and_names_its_own_file(self) -> None:
        #: Given
        corpus = _structure_spec(tokens=100)
        namespace = _structure_spec(tokens=11, spec_name='code-python')

        #: When
        result = validate_budget((corpus, namespace), token_count=12)

        #: Then
        assert [violation.message for violation in result.violations] == [
            '12 tokens; the budget is 11 (per code-python.structure.json)'
        ], 'the namespace layer tightens the corpus budget, and the violation quotes the layer that set it'
