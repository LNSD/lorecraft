"""A repository root a test declares as the parts it holds, and writes to disk with one call.

A test lists the parts its case needs, sets the fields the case turns on, and leaves the rest unset; `write` fills
each unset field with a valid value from `lib.generated`, so a part is clean unless the test says otherwise. The
layout, where each part lives under the root, is this module's to know: no test spells a path the layout fixes.

A file or a link no part models is written raw, as a `File` or a `Link` at a path the test spells out: a source file
a skill's metadata lists, or a directory linked somewhere the layout does not expect.

A workspace holds only the parts the test lists. Nothing is written that the test did not ask for.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from faker import Faker

from . import generated

# Where an agent reads a repository's skills, relative to its root.
_SKILLS_DIRECTORY: Final[Path] = Path('.agents') / 'skills'


@dataclass(frozen=True)
class File:
    """A file at a path the test spells out, holding text written as given.

    For a file no part models, such as a source file or a document a skill's `metadata` lists.

    Attributes:
        path: Where the file is written, relative to the repository root, such as `src/tool.py`. Its directories
            are created as needed. A file already at that path, such as a part's, is an error, never overwritten.
        text: The file's whole content. Never generated: a file of no known kind has no clean default.
    """

    path: Path
    text: str


@dataclass(frozen=True)
class Link:
    """A symbolic link, pointing at `target` exactly as written and never checked to exist.

    Attributes:
        path: Where the link is created, relative to the directory holding it: the repository root for a link in
            `Workspace.links`, the skill's directory for a link in `Skill.links`. Its directories are created as
            needed.
        target: What the link points at, written into it unchanged: a relative target is read from the link's
            own directory, and an absolute one names the same place on every run.
    """

    path: Path
    # Text, not a `Path`: a `Path` would drop `.` segments and doubled separators, and the link must hold the
    # target exactly as the test wrote it.
    target: str


@dataclass(frozen=True)
class Skill:
    """A skill an agent reads, at `.agents/skills/<name>/`.

    Its `SKILL.md` is frontmatter holding `name`, `description` and, when set, `metadata`, followed by `body`.
    Without metadata the frontmatter is four lines, so the body's first line is line 5 of the file; with it,
    `metadata` is on line 4.

    Attributes:
        name: The skill's name, and the name of its directory. Always set by the test, since every finding the
            command prints names the skill's path.
        description: The `description` in the frontmatter. One line; generated when unset.
        metadata: Each `metadata` subkey, such as `references`, `scripts` or `assets`, to its value as written: a
            whitespace-separated list of root-relative paths. Empty by default, in which case the frontmatter has
            no `metadata`. Never generated, since a listed path names a file the test must also write.
        body: The Markdown below the frontmatter, written as given. Generated when unset: a title and a
            paragraph, linking nothing.
        references: The files directly under the skill's `references/` directory, each file name to its whole
            text. Empty by default, in which case no `references/` directory is written.
        links: Symbolic links inside the skill's directory, each at a path relative to it. Empty by default.
    """

    name: str
    description: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    body: str | None = None
    references: Mapping[str, str] = field(default_factory=dict)
    links: Sequence[Link] = ()


@dataclass(frozen=True)
class Workspace:
    """A repository root, holding the parts listed and nothing else.

    The parts are written in the order of these fields, so a file may sit inside a skill's directory and a link
    may sit inside a directory a file created.

    Attributes:
        skills: The skills under `.agents/skills/`. Empty by default, in which case no skills directory is written.
        files: Files at paths the test spells out, relative to the root. Empty by default.
        links: Symbolic links at paths the test spells out, relative to the root. Empty by default.
    """

    skills: Sequence[Skill] = ()
    files: Sequence[File] = ()
    links: Sequence[Link] = ()

    def write(self, root: Path, faker: Faker) -> Path:
        """Write every part into `root`, creating `root` and the directories each part needs, and return `root`.

        Args:
            root: The directory written into as the repository root; usually the test's `tmp_path`, or a
                directory inside it when the test also writes something outside the repository.
            faker: The test's seeded generator, which fills every field the test left unset.
        """
        root.mkdir(parents=True, exist_ok=True)
        for skill in self.skills:
            _write_skill(root / _SKILLS_DIRECTORY, skill, faker)
        for file in self.files:
            _write_file(root, file)
        for link in self.links:
            _write_link(root, link)
        return root


def _write_skill(skills_directory: Path, skill: Skill, faker: Faker) -> None:
    """Write `skill` into its own directory under `skills_directory`.

    Args:
        skills_directory: The directory an agent reads skills from, created if it does not exist yet.
        skill: The skill to write; each unset field is generated here.
        faker: The test's seeded generator.
    """
    description = skill.description
    if description is None:
        description = generated.skill_description(faker)
    body = skill.body
    if body is None:
        body = generated.skill_body(faker)

    # Each value is written as a JSON string, which YAML reads as a double-quoted scalar, so any text a test
    # passes, a colon or a leading quote included, parses as the one-line value it is.
    frontmatter = '---\n'
    frontmatter += f'name: {json.dumps(skill.name, ensure_ascii=False)}\n'
    frontmatter += f'description: {json.dumps(description, ensure_ascii=False)}\n'
    if skill.metadata:
        frontmatter += 'metadata:\n'
    for subkey, value in skill.metadata.items():
        frontmatter += f'  {subkey}: {json.dumps(value, ensure_ascii=False)}\n'
    frontmatter += '---\n'

    skill_directory = skills_directory / skill.name
    skill_directory.mkdir(parents=True)
    (skill_directory / 'SKILL.md').write_text(frontmatter + body, encoding='utf-8')

    if skill.references:
        (skill_directory / 'references').mkdir()
    for file_name, text in skill.references.items():
        (skill_directory / 'references' / file_name).write_text(text, encoding='utf-8')

    for link in skill.links:
        _write_link(skill_directory, link)


def _write_file(root: Path, file: File) -> None:
    """Write `file` at its path under `root`, creating the directories it sits in.

    Args:
        root: The repository root the file's path is relative to.
        file: The file to write.
    """
    path = root / file.path
    path.parent.mkdir(parents=True, exist_ok=True)
    # Mode `x` refuses a path that already exists, so a file cannot silently replace a part written before it.
    with path.open('x', encoding='utf-8') as stream:
        stream.write(file.text)


def _write_link(directory: Path, link: Link) -> None:
    """Create `link` at its path under `directory`, creating the directories it sits in.

    Args:
        directory: The directory the link's path is relative to: the repository root, or a skill's directory.
        link: The link to create; its target is written unchanged.
    """
    path = directory / link.path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(link.target)
