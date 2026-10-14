"""gitlint rule holding a commit body to the commit skill's template.

A body is absent, for a mechanical change, a one-line summary alone, or a one-line summary, a blank line, and 2
to 5 bullets of one line each. A block of trailers may follow, after a blank line. The summary and each bullet are
one physical line because wrapping is the display's job: a line broken at some width shows up ragged on GitHub and
in a pull request description.
"""

import re

from gitlint.git import GitCommit
from gitlint.rules import CommitRule, RuleViolation

TRAILER: re.Pattern[str] = re.compile(r'^[A-Za-z-]+: ')
BULLET_PREFIX: str = '- '
MIN_BULLETS: int = 2
MAX_BULLETS: int = 5

# A paragraph is its lines, each with its line number in the whole message.
type Paragraph = list[tuple[int, str]]


def split_paragraphs(body: list[str]) -> list[Paragraph]:
    """Split the body into paragraphs at blank lines."""
    paragraphs: list[Paragraph] = []
    current: Paragraph = []
    # Line 1 is the title, so the body's first line is number 2.
    for line_number, line in enumerate(body, start=2):
        if line.strip():
            current.append((line_number, line))
        elif current:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    return paragraphs


def is_trailer_block(paragraph: Paragraph) -> bool:
    """Tell whether every line of the paragraph is a `Key: value` trailer."""
    return all(TRAILER.match(line) for _, line in paragraph)


class BodyStructure(CommitRule):
    """Reject a body that is not a one-line summary, optionally followed by 2 to 5 one-line bullets."""

    name = 'body-structure'
    id = 'UC2'

    def validate(self, commit: GitCommit) -> list[RuleViolation]:
        """Report every way the body departs from the summary-and-bullets template."""
        paragraphs = split_paragraphs(commit.message.body)
        if paragraphs and is_trailer_block(paragraphs[-1]):
            paragraphs = paragraphs[:-1]

        # A title-only commit, trailers aside.
        if not paragraphs:
            return []

        first_number, first_line = paragraphs[0][0]
        if len(paragraphs) > 2:
            message = f'Body must be a summary and a list of bullets, found {len(paragraphs)} paragraphs'
            return [RuleViolation(self.id, message, first_line, first_number)]

        # Bullets before the summary would also read as a wrapped summary and a bulletless list; report the cause.
        if first_line.startswith(BULLET_PREFIX):
            return [RuleViolation(self.id, 'Body must open with a summary, not a bullet', first_line, first_number)]

        summary = paragraphs[0]
        violations: list[RuleViolation] = []
        for line_number, line in summary[1:]:
            violations.append(RuleViolation(self.id, 'Body summary is wrapped onto a second line', line, line_number))

        # A summary-only body is complete.
        if len(paragraphs) == 1:
            return violations

        bullets = paragraphs[1]
        bullet_count = 0
        for line_number, line in bullets:
            if line.startswith(BULLET_PREFIX):
                bullet_count += 1
            else:
                violations.append(
                    RuleViolation(self.id, 'Body bullet is wrapped onto a second line', line, line_number)
                )
        if not MIN_BULLETS <= bullet_count <= MAX_BULLETS:
            bullets_number, bullets_line = bullets[0]
            message = f'Body must have {MIN_BULLETS} to {MAX_BULLETS} bullets, found {bullet_count}'
            violations.append(RuleViolation(self.id, message, bullets_line, bullets_number))

        return violations
