"""Shared findings and output formatting for document checks.

A check returns violations: where in the document a rule is broken, but not which document, since a check is a
pure function of what it reads and never needs the document's path. The run that checked a document knows which
it was, and ``Finding.at`` joins the two into a finding, the located form the output prints.
"""

from dataclasses import dataclass
from typing import Self

from lorecraft_project.syntax import LineNumber
from lorecraft_vfs import RootRelativePath


@dataclass(frozen=True, slots=True)
class Violation:
    """One broken rule in one document, without the document's path.

    Attributes:
        line: Where the violation is reported; line 1 when it concerns the whole document rather than one line.
        rule: Stable identifier for the violated rule.
        message: Human-readable explanation of the violation.
        spec: The specification file that states the broken rule, or None, the default, for a rule the check
            itself holds, such as a document that is not UTF-8.
    """

    line: LineNumber
    rule: str
    message: str
    spec: RootRelativePath | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    """One validation finding, located in a repository document; frozen, so findings compare and hash by value.

    Attributes:
        path: The affected document; turned into text only where a finding is printed or serialised.
        line: The line containing the finding.
        rule: Stable identifier for the violated rule.
        message: Human-readable explanation of the finding.
        spec: The specification file that states the broken rule, or None for a rule the check itself holds.
    """

    path: RootRelativePath
    line: LineNumber
    rule: str
    message: str
    spec: RootRelativePath | None = None

    @classmethod
    def at(cls, path: RootRelativePath, violation: Violation) -> Self:
        """The finding a violation is, in the document at ``path``."""
        return cls(path=path, line=violation.line, rule=violation.rule, message=violation.message, spec=violation.spec)


def format_finding(finding: Finding) -> str:
    """Format one finding for text output: ``<path>:<line>: [<rule>] <message>``."""
    return f'{finding.path}:{finding.line}: [{finding.rule}] {finding.message}'
