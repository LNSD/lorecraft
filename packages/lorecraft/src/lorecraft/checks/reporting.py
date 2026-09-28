"""Shared findings and output formatting for document checks."""

from dataclasses import dataclass

from lorecraft_project.syntax import LineNumber
from lorecraft_vfs import RootRelativePath


@dataclass(frozen=True, slots=True)
class Finding:
    """One validation finding, located in a repository document; frozen, so findings compare and hash by value.

    Attributes:
        path: The affected document; turned into text only where a finding is printed or serialised.
        line: The line containing the finding.
        rule: Stable identifier for the violated rule.
        message: Human-readable explanation of the finding.
    """

    path: RootRelativePath
    line: LineNumber
    rule: str
    message: str


def format_finding(finding: Finding) -> str:
    """Format one finding for text output: ``<path>:<line>: [<rule>] <message>``."""
    return f'{finding.path}:{finding.line}: [{finding.rule}] {finding.message}'
