"""A repository root a test declares as the parts it holds, and writes to disk with one call.

A test lists the parts its case needs, sets the fields the case turns on, and leaves the rest unset; each unset
field is filled with a valid value from `lib.generated`, so a part is clean unless the test says otherwise. The
layout, where each part lives under the root, is this module's to know: no test spells a path the layout fixes.

A workspace holds only the parts the test lists. Nothing is written that the test did not ask for.

Each part renders its files, every root-relative path to the whole text written there, without touching the disk;
`Workspace.write` is the one place that creates directories and writes files. Parts render in the order the
workspace lists them, drawing from one generator, so reordering them changes the generated values; nothing a test
asserts on is generated, so no test depends on that order.

A symlink has no text, so a part renders its links apart from its files, every root-relative path to the target
the link holds. `Workspace.write` creates every link after every file: a link may then dangle, or lead to a
directory the same workspace wrote files into, and no file is ever written through a link into what it leads to.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Final, Literal, assert_never

from faker import Faker

from . import generated

# Where an agent reads a repository's skills, relative to its root.
_SKILLS_DIRECTORY: Final[PurePosixPath] = PurePosixPath('.agents') / 'skills'

# Where a repository's documents live, one directory per corpus, relative to its root.
_DOCS_DIRECTORY: Final[PurePosixPath] = PurePosixPath('docs')

# Where a repository's specifications live, relative to its root.
_SPECS_DIRECTORY: Final[PurePosixPath] = _DOCS_DIRECTORY / '__meta__'


@dataclass(frozen=True)
class RawFrontmatter:
    """A frontmatter written exactly as given, in place of the one a part generates from its fields.

    For the case a mapping cannot hold, such as a key written twice. The `---` fences are written around it, so
    its first line is line 2 of the file.

    Attributes:
        text: The lines between the fences, each ending in a newline.
    """

    text: str


@dataclass(frozen=True)
class SkillFrontmatter:
    """The frontmatter a skill generates from its fields: `name`, `description`, then `metadata` when it lists any.

    Attributes:
        description: The `description`, on line 3 of the file. One line; generated when unset.
        metadata: The `metadata` mapping, on line 4 of the file, each subkey to the root-relative paths it lists,
            separated by spaces. Empty by default, in which case no `metadata` key is written. A subkey outside the
            three is a malformed frontmatter, written through `RawFrontmatter`.
    """

    description: str | None = None
    metadata: Mapping[Literal['references', 'scripts', 'assets'], str] = field(default_factory=dict)


@dataclass(frozen=True)
class Skill:
    """A skill an agent reads, at `.agents/skills/<name>/`.

    Its `SKILL.md` is the frontmatter followed by `body`.

    Attributes:
        name: The skill's name, written as its `name` unless the frontmatter is raw, and the name of its directory.
            Always set by the test, since every finding the command prints names the skill's path.
        frontmatter: Generated from its fields by default, which is four lines with no `metadata`, so the body's
            first line is line 5 of the file; or written as given.
        body: The Markdown below the frontmatter, written as given. Generated when unset: a title and a
            paragraph, linking nothing.
        references: The files directly under the skill's `references/` directory, each file name to its whole
            text. Empty by default, in which case no `references/` directory is written.
        links: The symlinks directly in the skill's directory, each entry name to the target the link holds,
            written as a `Link` target is. Empty by default.
    """

    name: str
    frontmatter: SkillFrontmatter | RawFrontmatter = field(default_factory=SkillFrontmatter)
    body: str | None = None
    references: Mapping[str, str] = field(default_factory=dict)
    links: Mapping[str, str] = field(default_factory=dict)

    def _render(self, faker: Faker) -> dict[PurePosixPath, str]:
        """Every file of the skill, each root-relative path to its text.

        Args:
            faker: The test's seeded generator, which fills every field the test left unset.
        """
        match self.frontmatter:
            case RawFrontmatter():
                frontmatter_text = self.frontmatter.text
            case SkillFrontmatter():
                frontmatter_text = _skill_frontmatter_text(self.name, self.frontmatter, faker)
            case _:
                assert_never(self.frontmatter)
        body = self.body
        if body is None:
            body = generated.skill_body(faker)

        skill_directory = _SKILLS_DIRECTORY / self.name
        files = {skill_directory / 'SKILL.md': _fenced(frontmatter_text) + body}
        for file_name, text in self.references.items():
            files[skill_directory / 'references' / file_name] = text
        return files

    def _render_links(self) -> dict[PurePosixPath, str]:
        """Every link in the skill's directory, each root-relative path to its target."""
        skill_directory = _SKILLS_DIRECTORY / self.name
        links: dict[PurePosixPath, str] = {}
        for entry_name, target in self.links.items():
            links[skill_directory / entry_name] = target
        return links


@dataclass(frozen=True)
class Spec:
    """A specification in `docs/__meta__/`, governing the corpus `docs/<name>/`, or a namespace within one.

    Attributes:
        name: The specification name, `<corpus>` or `<corpus>-<namespace>`. Always set by the test, since a
            document names its corpus by it.
        structure: The structure specification, written as JSON to `<name>.structure.json`. Generated when unset:
            a rule from each check, as `lib.generated` states, which a default `Document` follows.
        prose: The prose specification, written as given to `<name>.md`. Unlike every other field, nothing is
            written when it is unset rather than a generated value: no check reads the prose, so a specification
            without one is as clean as one with it. A structure finding still cites `<name>.md`, so a snapshot of
            one pins a file the root does not hold unless the test sets this.
    """

    name: str
    structure: Mapping[str, object] | None = None
    prose: str | None = None

    def _render(self, faker: Faker) -> dict[PurePosixPath, str]:
        """Every file of the specification, each root-relative path to its text.

        Args:
            faker: The test's seeded generator, which fills every field the test left unset.
        """
        structure = self.structure
        if structure is None:
            structure = generated.spec_structure(faker)

        files = {_SPECS_DIRECTORY / f'{self.name}.structure.json': json.dumps(structure, indent=2) + '\n'}
        if self.prose is not None:
            files[_SPECS_DIRECTORY / f'{self.name}.md'] = self.prose
        return files


@dataclass(frozen=True)
class Document:
    """A document at `docs/<corpus>/<name>.md`, clean by default under a default `Spec` named after its corpus.

    A document under a specification the test wrote itself is clean only if the fields the test gives make it so.

    Attributes:
        corpus: The directory under `docs/` the document sits in. Always set by the test, since every finding the
            command prints names the document's path.
        name: The file name, without its `.md`. Always set by the test, for the same reason.
        frontmatter: Written as given when set. Generated when unset: `name` set to the document's name, and a
            generated `description`. Unlike a skill's, it has no form built from fields, since no case yet sets
            one field of a document's frontmatter and leaves the rest generated.
        body: The Markdown below the frontmatter, written as given. Generated when unset: a title, then a
            `Summary` section holding one paragraph.
    """

    corpus: str
    name: str
    frontmatter: RawFrontmatter | None = None
    body: str | None = None

    def _render(self, faker: Faker) -> dict[PurePosixPath, str]:
        """The document's one file, its root-relative path to its text.

        Args:
            faker: The test's seeded generator, which fills every field the test left unset.
        """
        if self.frontmatter is None:
            description = generated.document_description(faker)
            frontmatter_text = f'name: {_yaml_string(self.name)}\ndescription: {_yaml_string(description)}\n'
        else:
            frontmatter_text = self.frontmatter.text
        body = self.body
        if body is None:
            body = generated.document_body(faker)

        return {_DOCS_DIRECTORY / self.corpus / f'{self.name}.md': _fenced(frontmatter_text) + body}


@dataclass(frozen=True)
class File:
    """Any file, written as given and governed by nothing in this model: the part for what no other part covers.

    Attributes:
        path: Where the file goes, relative to the root, with `/` between its parts.
        text: The whole text of the file.
    """

    path: str
    text: str

    def _render(self, faker: Faker) -> dict[PurePosixPath, str]:
        """The one file, its root-relative path to its text.

        Args:
            faker: Unused, since nothing in a file is generated; taken so every part renders alike.
        """
        return {PurePosixPath(self.path): self.text}


@dataclass(frozen=True)
class Link:
    """Any symlink, governed by nothing in this model: the part for a link no other part covers.

    Attributes:
        path: Where the link goes, relative to the root, with `/` between its parts. Never under another link's
            path: it would be created inside whatever that link leads to, which may be a checked-in directory, and
            nothing refuses it.
        target: What the link holds, written as given: relative to the link's own directory, or absolute for a
            directory the test did not write, such as a checked-in fixture. Text rather than a `Path`, since a
            relative target names no location until the link resolves it.
    """

    path: str
    target: str

    def _render_links(self) -> dict[PurePosixPath, str]:
        """The one link, its root-relative path to its target."""
        return {PurePosixPath(self.path): self.target}


@dataclass(frozen=True)
class Workspace:
    """A repository root, holding the parts listed and nothing else.

    A test writes any tree it needs beside a root the same way, such as a directory outside the repository that a
    link in the root leads to.

    Every list is empty by default, in which case that kind of part is not written, nor the directory it lives in.

    Attributes:
        specs: The specifications in `docs/__meta__/`.
        documents: The documents under `docs/`.
        skills: The skills under `.agents/skills/`.
        files: Any other file, at the path it gives.
        links: Any other symlink, at the path it gives.
    """

    specs: Sequence[Spec] = ()
    documents: Sequence[Document] = ()
    skills: Sequence[Skill] = ()
    files: Sequence[File] = ()
    links: Sequence[Link] = ()

    def write(self, root: Path, faker: Faker) -> Path:
        """Write every part into `root`, every file first and then every link, and return `root`.

        Args:
            root: The directory written into as the repository root, created with its parents when absent;
                usually the test's `tmp_path`, or a directory under it.
            faker: The test's seeded generator, which fills every field the test left unset.

        Raises:
            FileExistsError: Two parts render the same path, or `root` already holds a file or a link at one.
        """
        root.mkdir(parents=True, exist_ok=True)

        parts_with_files = [*self.specs, *self.documents, *self.skills, *self.files]
        for part in parts_with_files:
            for relative_path, text in part._render(faker).items():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                # Mode `x` refuses a file that is already there, so two parts rendering one path fail the test
                # instead of the later one silently replacing the earlier.
                with path.open('x', encoding='utf-8') as file:
                    file.write(text)

        parts_with_links = [*self.skills, *self.links]
        for part in parts_with_links:
            for relative_path, target in part._render_links().items():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                # Like mode `x`, creating a link refuses a path already holding a file, a directory or a link.
                path.symlink_to(target)
        return root


def _skill_frontmatter_text(name: str, frontmatter: SkillFrontmatter, faker: Faker) -> str:
    """The lines between the fences of a skill's generated frontmatter.

    Args:
        name: The skill's name, written as its `name`.
        frontmatter: The fields the test set, each unset one generated here.
        faker: The test's seeded generator.
    """
    description = frontmatter.description
    if description is None:
        description = generated.skill_description(faker)

    text = f'name: {_yaml_string(name)}\ndescription: {_yaml_string(description)}\n'
    if frontmatter.metadata:
        text += 'metadata:\n'
    for subkey, paths in frontmatter.metadata.items():
        text += f'  {subkey}: {_yaml_string(paths)}\n'
    return text


def _yaml_string(value: str) -> str:
    """`value` as a one-line YAML scalar.

    Written as a JSON string, which YAML reads as a double-quoted scalar, so any text a test passes, a colon or a
    leading quote included, parses as the one-line value it is.

    Args:
        value: The text the scalar holds.
    """
    return json.dumps(value, ensure_ascii=False)


def _fenced(frontmatter_text: str) -> str:
    """The frontmatter block: `frontmatter_text` between two `---` fences, ready for the body to follow.

    Args:
        frontmatter_text: The lines between the fences, each ending in a newline.
    """
    return f'---\n{frontmatter_text}---\n'
