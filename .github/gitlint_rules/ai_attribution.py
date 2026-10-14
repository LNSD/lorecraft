"""gitlint rule rejecting AI attribution in a commit body.

CONTRIBUTING.md lets a contributor disclose a tool with an `Assisted-by:` trailer, so that trailer passes. What
fails is crediting a tool as an author or signer, a "generated with" footer, and a session link.
"""

import re

from gitlint.git import GitCommit
from gitlint.rules import CommitRule, RuleViolation

AI_TOOLS: str = r'(claude|anthropic|codex|openai|chatgpt|copilot|gemini|cursor|multica)'

FORBIDDEN_LINES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(rf'^(co-authored-by|co-developed-by|signed-off-by):.*{AI_TOOLS}', re.IGNORECASE),
        'Body credits an AI tool as an author or signer',
    ),
    (
        re.compile(rf'generated (with|by).*{AI_TOOLS}', re.IGNORECASE),
        "Body carries a 'generated with' line",
    ),
    (
        re.compile(r'https?://\S*/session_', re.IGNORECASE),
        'Body carries a session link',
    ),
]


class NoAiAttribution(CommitRule):
    """Reject a body line that credits an AI tool as an author, signer or generator."""

    name = 'no-ai-attribution'
    id = 'UC1'

    def validate(self, commit: GitCommit) -> list[RuleViolation]:
        """Report every body line matching a forbidden pattern."""
        violations: list[RuleViolation] = []
        # Line 1 is the title, so the body's first line is number 2.
        for line_number, line in enumerate(commit.message.body, start=2):
            for pattern, message in FORBIDDEN_LINES:
                if pattern.search(line):
                    violations.append(RuleViolation(self.id, message, line, line_number))
        return violations
