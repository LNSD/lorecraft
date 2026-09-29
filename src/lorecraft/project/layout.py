"""The canonical repository layout Lorecraft reads. Fixed, not configurable."""

from typing import Final

from lorecraft.vfs import RootRelativePath, ScanRoot

DOCS_DIR: Final[RootRelativePath] = RootRelativePath.parse('docs')
SPECS_DIR: Final[RootRelativePath] = DOCS_DIR / '__meta__'
DOCUMENT_SUFFIX: Final[str] = '.md'


SNAPSHOT_SCOPE: Final[tuple[ScanRoot, ...]] = (ScanRoot(DOCS_DIR, depth=1),)
"""What a snapshot reads: what the document and schema repositories read at the scan roots.

The repositories list ``docs/`` and each corpus and specs directory in it. A link leading outside the scan
roots is recorded, not followed.
"""
