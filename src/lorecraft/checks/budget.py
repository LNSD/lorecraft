"""Check one document's whole-file token count against the token budgets that govern it.

The check is pure: it takes the already validated structure specifications that govern a document and the
document's token count, and returns violations. It reads the count and nothing else, so it is handed that number
rather than the text, and not the document's path: the run that called it attaches that. The budget is the global
`tokens` key of a structure specification, but it is a check of its own: the structure check reads a document's
parse tree, and this one reads its raw text, frontmatter, code and tables included, since that is what loading it
costs an agent.

Each structure specification is applied on its own. A namespace specification's budget does not replace the corpus
one, so a document governed by both must fit both, and a namespace can only tighten the corpus budget.
"""

from dataclasses import dataclass
from typing import Final

from lorecraft.project.schemas import StructureSpec
from lorecraft.project.syntax import LineNumber

from .reporting import Violation

_FIRST_LINE: Final[LineNumber] = LineNumber(1)
"""Where a budget violation is reported: it concerns the whole file, not one line of it."""


@dataclass(frozen=True, slots=True)
class BudgetCheckResult:
    """What the budget check found in one document.

    Attributes:
        violations: One per structure specification whose budget the document exceeds, in the order given; empty
            when it fits all.
    """

    violations: tuple[Violation, ...]


def validate_budget(structure_specs: tuple[StructureSpec, ...], *, token_count: int) -> BudgetCheckResult:
    """Check one document's token count against the budget of each structure specification that sets one.

    Every violation's message ends by naming the structure specification file that sets the budget, as every
    frontmatter violation does: the number is in that file, not in the prose.

    Args:
        structure_specs: Applied each on its own; one without a `tokens` budget is skipped. Empty means the
            document is ungoverned, which yields no violations.
        token_count: The `o200k_base` tokens in the document's whole file, as `count_tokens` counts them.
    """
    violations: list[Violation] = []
    for structure_spec in structure_specs:
        if structure_spec.tokens is None or token_count <= structure_spec.tokens.value:
            continue
        message = f'{token_count} tokens; the budget is {structure_spec.tokens} (per {structure_spec.path.name})'
        violations.append(Violation(line=_FIRST_LINE, rule='budget.tokens', message=message, spec=structure_spec.path))
    return BudgetCheckResult(violations=tuple(violations))
