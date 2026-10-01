"""The canonical repository layout Lorecraft reads. Fixed, not configurable."""

from typing import Final

from lorecraft.agents import iter_agents
from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.vfs import EntryKind, FileSystem, ScanRoot

DOCS_DIR: Final[RootRelativePath] = RootRelativePath.parse('docs')
SPECS_DIR: Final[RootRelativePath] = DOCS_DIR / '__meta__'
DOCUMENT_SUFFIX: Final[str] = '.md'


# Runs once per process, before mutmut swaps a mutant in, so no test can ever see a mutant of it.
def _skills_scan_roots() -> list[ScanRoot]:  # pragma: no mutate block
    """One scan root per project skills directory the agents read, each once: two agents may read the same one.

    A skills directory is read one level deep: the directory itself, and each skill directory in it. Links are
    followed, since an agent's skills directory is commonly a link to another one, a skill entry a link to
    where the skill's files live, and a ``SKILL.md`` a link to where its text lives.
    """
    scan_roots: list[ScanRoot] = []
    for agent in iter_agents():
        for skills_dir in agent.project_skills_dirs:
            scan_root = ScanRoot(RootRelativePath(skills_dir), depth=1, follow_links=True)
            if scan_root not in scan_roots:
                scan_roots.append(scan_root)
    return scan_roots


SNAPSHOT_SCOPE: Final[tuple[ScanRoot, ...]] = (ScanRoot(DOCS_DIR, depth=1), *_skills_scan_roots())
"""What a snapshot reads: what the document, schema and skill repositories read at the scan roots.

The document and schema repositories list ``docs/`` and each corpus and specs directory in it; the skill
repository lists each project skills directory the agents read and each skill directory in it. Which
directories those are is the agents' statement, in ``lorecraft.agents``; the workspace model records the ones a
repository has, with the agent that reads each.

Under ``docs/`` a link is recorded, not followed. Under a skills directory a link to a directory or a file in
the repository is followed, so a skill linked to where its files live, such as
``.agents/skills/review -> ../../skills/review``, or a ``SKILL.md`` linked to where its text lives, is in the
snapshot as it is on disk. A link leading outside the repository is never followed.
"""


class LinkedLayoutError(Error):
    """A directory the layout fixes, ``docs/`` or ``docs/__meta__/``, is a symlink.

    Attributes:
        path: The root-relative directory that is a symlink.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'{path} is a symlink, which lorecraft does not follow: {path}/ must be a real directory')


def require_real_layout(fs: FileSystem) -> None:
    """Refuse a view in which ``docs/`` or ``docs/__meta__/`` is a symlink.

    Under ``docs/`` a snapshot records a symlink and never reads through it. Behind a linked ``docs/`` or
    ``docs/__meta__/`` it therefore holds no specification, and the model loaded from it has no corpus: a
    command would report a clean run over a repository it never read. A root with neither directory is not
    refused; it declares nothing, which is a model with no corpora.

    Args:
        fs: View of the repository whose `docs/` and `docs/__meta__/` entries are inspected, not followed.

    Raises:
        LinkedLayoutError: If ``docs/`` is a symlink, or else if ``docs/__meta__/`` is one.
        EntryInspectError: If the view cannot inspect either directory; a view over a snapshot never raises it.
    """
    # `docs/` first: a scan stops at a linked `docs/`, so a snapshot never knows what `docs/__meta__/` is.
    for directory in (DOCS_DIR, SPECS_DIR):
        if fs.entry_kind(directory) is EntryKind.SYMLINK:
            raise LinkedLayoutError(directory)
