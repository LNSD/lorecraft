"""The canonical repository layout Lorecraft reads, and the scope a snapshot of it reads.

The layout is fixed, not configurable. The scope is too, but for the directories a command names to check the
skills in, which join it as a skills directory does.
"""

from typing import Final

from lorecraft.agents import iter_agents
from lorecraft.core.error import Error
from lorecraft.core.path import ROOT, RootRelativePath
from lorecraft.vfs import EntryKind, FileSystem, ScanRoot

DOCS_DIR: Final[RootRelativePath] = RootRelativePath.parse('docs')
SPECS_DIR: Final[RootRelativePath] = DOCS_DIR / '__meta__'
DOCUMENT_SUFFIX: Final[str] = '.md'


# Runs once per process, before mutmut swaps a mutant in, so no test can ever see a mutant of it.
def _skills_scan_roots() -> list[ScanRoot]:  # pragma: no mutate block
    """One scan root per project skills directory the agents read, each once: two agents may read the same one.

    A skills directory is read with no depth limit: the directory itself, each skill directory in it, and every
    file and directory inside a skill, at any depth, since a skill carries references, scripts and assets beside
    its `SKILL.md`. Links are followed, since an agent's skills directory is commonly a link to another one, a
    skill entry a link to where the skill's files live, a `SKILL.md` a link to where its text lives, and an entry
    inside a skill a link to a file or a directory elsewhere in the repository.
    """
    scan_roots: list[ScanRoot] = []
    for agent in iter_agents():
        for skills_dir in agent.project_skills_dirs:
            scan_root = ScanRoot(RootRelativePath(skills_dir), depth=None, follow_links=True)
            if scan_root not in scan_roots:
                scan_roots.append(scan_root)
    return scan_roots


SNAPSHOT_SCOPE: Final[tuple[ScanRoot, ...]] = (ScanRoot(DOCS_DIR, depth=1), *_skills_scan_roots())
"""What a snapshot reads: what the document, schema and skill repositories read at the scan roots.

The document and schema repositories list `docs/` and each corpus and specs directory in it; the skill
repository lists each project skills directory the agents read and each skill directory in it. The scope also
reaches every file and directory below a skill directory, at any depth: a skill's own files, which the model
does not list. Which skills directories those are is the agents' statement, in `lorecraft.agents`;
the workspace model records the ones a repository has, with the agent that reads each.

Under `docs/` a link is recorded, not followed. Under a skills directory, inside a skill included, a link to a
directory or a file in the repository is followed, so a skill linked to where its files live, such as
`.agents/skills/review -> ../../skills/review`, a `SKILL.md` linked to where its text lives, or a directory
of references linked in from elsewhere, is in the snapshot as it is on disk, a linked directory with no depth
limit either. A link leading outside the repository is never followed. A link inside a skill to one of its own
ancestors has the scan read that ancestor's whole subtree once, and ends there.

A command that names directories to check the skills in has the snapshot read them too, through
`scope_with_named_dirs`.
"""


def scope_with_named_dirs(named_dirs: tuple[RootRelativePath, ...]) -> tuple[ScanRoot, ...]:
    """`SNAPSHOT_SCOPE`, with each directory a command names to check the skills in read as a skills directory is.

    A named directory is read with no depth limit and its links followed, like an agent's skills directory, since
    it may be one skill or hold many, each with files at any depth. A link leading outside the repository is
    never followed. A directory the scope already holds as such a root is not added again; one inside another
    root, or covering `docs/`, is, and the scan lists each directory once for the deepest root that asks for it.
    The root itself never joins: read that way, the snapshot would hold the whole repository.

    Args:
        named_dirs: The directories as the command spelled them, root-relative and unresolved; one that is no
            directory, such as a file, reads nothing.
    """
    scope: list[ScanRoot] = list(SNAPSHOT_SCOPE)
    for directory in named_dirs:
        scan_root = ScanRoot(directory, depth=None, follow_links=True)
        if directory != ROOT and scan_root not in scope:
            scope.append(scan_root)
    return tuple(scope)


def named_dirs_of_scope(scope: tuple[ScanRoot, ...]) -> tuple[RootRelativePath, ...]:
    """The directories a command named to check the skills in, as a scope `scope_with_named_dirs` built records them.

    They are the directories of the roots beyond `SNAPSHOT_SCOPE`'s, so a snapshot carries what was named in the
    scope it records, and the model of it lists their skills whoever reads the snapshot. A directory named that
    the scope already read as an agent's skills directory, or the root, was never added, so it is not here either.

    Args:
        scope: The scope a snapshot was taken of, as `Snapshot.scope` records it.
    """
    named_dirs: list[RootRelativePath] = []
    for scan_root in scope:
        if scan_root not in SNAPSHOT_SCOPE:
            named_dirs.append(scan_root.directory)
    return tuple(named_dirs)


class LinkedLayoutError(Error):
    """A directory the layout fixes, ``docs/`` or ``docs/__meta__/``, is a symlink.

    Attributes:
        path: The root-relative directory that is a symlink.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath) -> None:
        self.path = path
        super().__init__(f'{path} is a symlink, which lorecraft does not follow: {path}/ must be a real directory')


def reject_linked_layout(fs: FileSystem) -> None:
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
        if fs.find_entry_kind(directory) is EntryKind.SYMLINK:
            raise LinkedLayoutError(directory)
