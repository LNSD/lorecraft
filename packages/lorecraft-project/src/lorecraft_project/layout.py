"""The canonical repository layout Lorecraft reads. Fixed, not configurable."""

from typing import Final

from lorecraft_vfs import RootRelativePath, ScanRoot

DOCS_DIR: Final[RootRelativePath] = RootRelativePath.parse('docs')
SPECS_DIR: Final[RootRelativePath] = DOCS_DIR / '__meta__'
DOCUMENT_SUFFIX: Final[str] = '.md'
UNIVERSAL_SKILLS_DIR: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills')
SKILL_FILENAME: Final[str] = 'SKILL.md'


SNAPSHOT_SCOPE: Final[tuple[ScanRoot, ...]] = (
    ScanRoot(DOCS_DIR, depth=1),
    ScanRoot(UNIVERSAL_SKILLS_DIR, depth=1),
    # The one project skills directory in skill.agent.AGENTS that is not the canonical one.
    ScanRoot(RootRelativePath.parse('.claude/skills'), depth=1),
)
"""What a snapshot reads: the union of what the document and skill repositories read at the scan roots.

The document repositories list ``docs/`` and each corpus and specs directory in it; the skill repository
lists the canonical and the agent skills directories and each skill directory in them.

A link leading outside the scan roots is recorded, not followed. A skills directory or a skill linked to a
directory no scan root covers, such as ``.agents/skills -> ../vendor/skills``, is found on disk but not over
a snapshot, and nothing reports the difference.
"""
