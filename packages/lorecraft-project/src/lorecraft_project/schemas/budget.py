"""The decoded, unvalidated JSON of a budget specification file.

The budget check still runs as a vendored script, so nothing in the library gives this JSON a meaning yet,
and nothing here claims it has one. When that check migrates, its budgets are decoded at load into a
``BudgetAspect`` whose construction validates them, the way ``StructureAspect`` validates a structure
specification, and this type stays what the repository returns before that step.
"""

from typing import NewType

# A NewType only keeps budget JSON apart from header and structure JSON; it proves nothing about its content.
BudgetSchema = NewType('BudgetSchema', dict[str, object])
