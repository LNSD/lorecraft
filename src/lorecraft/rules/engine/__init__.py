"""The `LC` group: the conditions the engine reports itself, one module per condition.

`__ruleset__` declares the group. The package exposes `RefusedOperation` because `engine/load_failures.py` needs
the operation enum to classify a refusal.
"""

from .__ruleset__ import RefusedOperation

__all__: list[str] = ['RefusedOperation']
