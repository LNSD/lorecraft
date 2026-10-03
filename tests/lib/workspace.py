"""A repository root a test declares as the parts it holds, and writes to disk with one call.

A test lists the parts its case needs, sets the fields the case turns on, and leaves the rest unset; `write` fills
each unset field with a valid value from `lib.generated`, so a part is clean unless the test says otherwise. The
layout, where each part lives under the root, is this module's to know: no test spells a path the layout fixes.

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
class Skill:
    """A skill an agent reads, at `.agents/skills/<name>/`.

    Its `SKILL.md` is four lines of frontmatter, holding `name` and `description`, followed by `body`, so the
    body's first line is line 5 of the file.

    Attributes:
        name: The skill's name, and the name of its directory. Always set by the test, since every finding the
            command prints names the skill's path.
        description: The `description` in the frontmatter. One line; generated when unset.
        body: The Markdown below the frontmatter, written as given. Generated when unset: a title and a
            paragraph, linking nothing.
        references: The files directly under the skill's `references/` directory, each file name to its whole
            text. Empty by default, in which case no `references/` directory is written.
    """

    name: str
    description: str | None = None
    body: str | None = None
    references: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Workspace:
    """A repository root, holding the parts listed and nothing else.

    Attributes:
        skills: The skills under `.agents/skills/`. Empty by default, in which case no skills directory is written.
    """

    skills: Sequence[Skill] = ()

    def write(self, root: Path, faker: Faker) -> Path:
        """Write every part into `root`, creating the directories each needs, and return `root`.

        Args:
            root: An existing directory, written into as the repository root; usually the test's `tmp_path`.
            faker: The test's seeded generator, which fills every field the test left unset.
        """
        for skill in self.skills:
            _write_skill(root / _SKILLS_DIRECTORY, skill, faker)
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
    frontmatter = (
        '---\n'
        f'name: {json.dumps(skill.name, ensure_ascii=False)}\n'
        f'description: {json.dumps(description, ensure_ascii=False)}\n'
        '---\n'
    )

    skill_directory = skills_directory / skill.name
    skill_directory.mkdir(parents=True)
    (skill_directory / 'SKILL.md').write_text(frontmatter + body, encoding='utf-8')

    if skill.references:
        (skill_directory / 'references').mkdir()
    for file_name, text in skill.references.items():
        (skill_directory / 'references' / file_name).write_text(text, encoding='utf-8')
