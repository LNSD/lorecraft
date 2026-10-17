"""The `token_facts` query of `LEN001`: the budgets that govern a document and the tokens it holds.

Each case decodes its structure files from JSON by the real decoder and reads the headings by the real parser.
"""

from typing import Final

import pytest

from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.schemas import (
    SpecFileType,
    StructurePrimitives,
    StructureSchema,
    StructureSpec,
    StructureSpecFile,
    parse_spec_name,
    spec_filename,
)
from lorecraft.project.syntax import TokenCount

from ..too_many_tokens import token_facts

SPECS_DIR: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__')


def _structure_spec(spec_name: str, text: str) -> StructureSpec:
    """A structure specification decoded from its JSON.

    Args:
        spec_name: The specification's name, such as `code` or `code-python`.
        text: The structure specification's JSON.
    """
    name = parse_spec_name(spec_name)
    file = StructureSpecFile(path=SPECS_DIR / PathComponent.parse(spec_filename(name, SpecFileType.SPEC)), name=name)
    spec = StructureSpec.parse(file, StructureSchema(text))
    assert isinstance(spec, StructureSpec), f'the test states a usable specification, got {spec!r}'
    return spec


@pytest.mark.unit
class TestTokenBudgets:
    def test_token_facts_keeps_the_order_and_skips_specifications_setting_none(self) -> None:
        #: Given
        corpus = _structure_spec('code', '{"tokens": 100, "title": {"chars": 20}, "empty_sections": "forbidden"}')
        silent = _structure_spec('code-silent', '{"outline": [{"section": "Rule"}]}')
        namespace = _structure_spec('code-python', '{"tokens": 50, "title": {"words": 3}}')

        #: When
        budgets = token_facts(StructurePrimitives((corpus, silent, namespace))).budgets

        #: Then
        assert [(b.spec, b.tokens.value) for b in budgets] == [(corpus.path, 100), (namespace.path, 50)], (
            'one budget per specification that sets one'
        )

    def test_token_facts_of_no_specification_is_empty(self) -> None:
        #: When
        budgets = token_facts(StructurePrimitives(())).budgets

        #: Then
        assert budgets == (), 'nothing governs'


@pytest.mark.unit
class TestTokenCount:
    def test_token_facts_counts_tokens_only_when_a_budget_governs(self) -> None:
        #: Given
        budgeted = _structure_spec('code', '{"tokens": 100}')
        silent = _structure_spec('code-silent', '{"outline": [{"section": "Rule"}]}')
        count = TokenCount(UnsignedInt(7))

        #: When
        governed = token_facts(StructurePrimitives((budgeted,), token_total=count))
        ungoverned = token_facts(StructurePrimitives((silent,), token_total=count))

        #: Then
        assert (governed.count, ungoverned.count) == (count, UnsignedInt(0)), (
            'a document no budget governs is never counted'
        )
