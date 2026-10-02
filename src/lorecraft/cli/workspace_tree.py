"""Draw the workspace model: the text `lorecraft inspect` prints, and the JSON it prints with `--json`.

Pure: the model arrives as a value, so nothing here reads the disk. The text form is a tree with one section
per part of the model — the corpora, the agent skills directories the root has, and the skills — and the JSON
form carries the same content as nested objects.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from lorecraft.core.path import RootRelativePath
from lorecraft.project.skill import SkillsDir
from lorecraft.project.workspace import Corpus, Spec, WorkspaceModel

# The box-drawing prefixes `tree` uses: one for an entry with siblings after it, one for the last entry, and
# the matching indent each leaves for the entries nested under it.
_BRANCH: str = '├── '
_LAST_BRANCH: str = '└── '
_INDENT: str = '│   '
_LAST_INDENT: str = '    '


@dataclass(frozen=True, slots=True)
class _Line:
    """One line of the drawn tree and the lines nested under it.

    Attributes:
        label: The text drawn after the branch.
        children: The lines drawn under this one, in order.
    """

    label: str
    children: tuple['_Line', ...] = ()


def render_text(root: Path, model: WorkspaceModel) -> str:
    """Draw the model as a tree headed by the root, one section per part of the model.

    A document is followed by the names of the specs that govern it, broad to narrow. An agent's skills
    directory is followed by the resolved directory it leads to when it is a link, and a skill by the agents
    that read it.

    Args:
        root: The workspace root, drawn as the first line.
        model: Corpora, agent skills directories and skills to draw, each in the order the model lists them.

    Returns:
        The lines, newline-separated, without a trailing newline.
    """
    sections = (
        _corpora_section(model.corpora),
        _skills_dirs_section(model.skills_dirs),
        _skills_section(model),
    )
    lines = [str(root)]
    _draw(sections, '', lines)
    return '\n'.join(lines)


def render_json(root: Path, model: WorkspaceModel) -> str:
    """Encode the model as indented JSON, the root beside one key per section.

    The keys are `root`, `corpora`, `agent_skills_dirs` and `skills`.

    Args:
        root: The workspace root, written under the `root` key.
        model: Corpora, agent skills directories and skills to encode, one key per section.
    """
    corpora: list[dict[str, object]] = []
    for corpus in model.corpora:
        corpora.append(_json_corpus(corpus))
    skills_dirs: list[dict[str, object]] = []
    for skills_dir in model.skills_dirs:
        skills_dirs.append(
            {'agent': skills_dir.agent, 'path': str(skills_dir.path), 'resolves_to': str(skills_dir.resolves_to)}
        )
    skills: list[dict[str, object]] = []
    for ref in model.skills():
        skills.append({'path': str(ref.path), 'agents': list(model.skill_agents(ref))})
    document = {
        'root': str(root),
        'corpora': corpora,
        'agent_skills_dirs': skills_dirs,
        'skills': skills,
    }
    return json.dumps(document, indent=2)


def _draw(nodes: tuple[_Line, ...], prefix: str, lines: list[str]) -> None:
    """Append one line per node, and recurse into each node's children with the indent it leaves.

    Args:
        nodes: The sibling lines to draw at this depth; the last one takes the closing branch.
        prefix: The indent text already accumulated from the ancestors, written before each branch.
        lines: The output, to which the drawn lines are appended in place.
    """
    for index, node in enumerate(nodes):
        is_last = index == len(nodes) - 1
        branch = _LAST_BRANCH if is_last else _BRANCH
        lines.append(prefix + branch + node.label)
        indent = _LAST_INDENT if is_last else _INDENT
        _draw(node.children, prefix + indent, lines)


def _corpora_section(corpora: tuple[Corpus, ...]) -> _Line:
    """`corpora (N)`, then per corpus its specs and its documents.

    Args:
        corpora: The corpora to draw, in the order the model lists them.
    """
    corpus_lines: list[_Line] = []
    for corpus in corpora:
        corpus_lines.append(_corpus_line(corpus))
    return _Line(f'corpora ({len(corpora)})', tuple(corpus_lines))


def _corpus_line(corpus: Corpus) -> _Line:
    """One corpus: the directory it reads, its specs and its governed documents.

    Args:
        corpus: Corpus drawn as one line, with its specs and documents as children.
    """
    spec_lines: list[_Line] = []
    for spec in (corpus.corpus_spec, *corpus.namespace_specs):
        spec_lines.append(_Line(f'{spec.name}: {_file_names(spec.files)}'))
    parts = [_Line(f'specs ({len(spec_lines)})', tuple(spec_lines))]

    document_lines: list[_Line] = []
    for ref in corpus.documents:
        spec_names = _governing_spec_names(corpus.governance(ref).specs())
        document_lines.append(_Line(f'{ref.path.name} [{", ".join(spec_names)}]'))
    parts.append(_Line(f'documents ({len(document_lines)})', tuple(document_lines)))

    return _Line(f'{corpus.name} ({corpus.directory})', tuple(parts))


def _skills_dirs_section(skills_dirs: tuple[SkillsDir, ...]) -> _Line:
    """`agent skills directories (N)`, one line per agent and directory, as the model orders them.

    A directory that is a link is drawn with the resolved directory it leads to: `path -> resolves_to`.

    Args:
        skills_dirs: The agent skills directories to draw.
    """
    lines: list[_Line] = []
    for skills_dir in skills_dirs:
        location = str(skills_dir.path)
        if skills_dir.resolves_to != skills_dir.path:
            location = f'{skills_dir.path} -> {skills_dir.resolves_to}'
        lines.append(_Line(f'{skills_dir.agent}: {location}'))
    return _Line(f'agent skills directories ({len(skills_dirs)})', tuple(lines))


def _skills_section(model: WorkspaceModel) -> _Line:
    """`skills (N)`, one line per skill: its directory, then the agents that read it in brackets.

    Args:
        model: The workspace model, which lists the skills and the agents that read each.
    """
    lines: list[_Line] = []
    for ref in model.skills():
        agents = model.skill_agents(ref)
        lines.append(_Line(f'{ref.directory} [{", ".join(agents)}]'))
    return _Line(f'skills ({len(model.skill_locations)})', tuple(lines))


def _json_corpus(corpus: Corpus) -> dict[str, object]:
    """One corpus as a JSON object: its specs, and its documents with the spec files that govern each.

    Args:
        corpus: Corpus whose specs and documents become the object's keys.
    """
    specs: list[dict[str, object]] = []
    for spec in (corpus.corpus_spec, *corpus.namespace_specs):
        # The key is `stem` for the specification name: the JSON is the command's published output, so it keeps
        # the word the code has since moved away from.
        specs.append({'stem': str(spec.name), 'files': _paths(spec.files)})
    documents: list[dict[str, object]] = []
    for ref in corpus.documents:
        documents.append(
            {'path': str(ref.path), 'governed_by': _governing_files(corpus.governance(ref).specs())},
        )
    return {
        'name': str(corpus.name),
        'directory': str(corpus.directory),
        'specs': specs,
        'documents': documents,
    }


def _governing_spec_names(specs: tuple[Spec, ...]) -> list[str]:
    """The names of the governing specs, broad to narrow, as the model orders them.

    Args:
        specs: A document's governing specs, in the order the model gives them.
    """
    spec_names: list[str] = []
    for spec in specs:
        spec_names.append(str(spec.name))
    return spec_names


def _governing_files(specs: tuple[Spec, ...]) -> list[str]:
    """Every file of the governing specs as a root-relative path, broad to narrow, each spec's files sorted.

    Args:
        specs: A document's governing specs, in the order the model gives them.
    """
    paths: list[str] = []
    for spec in specs:
        paths.extend(_paths(spec.files))
    return paths


def _file_names(files: tuple[RootRelativePath, ...]) -> str:
    """The file names, comma-separated: every spec file sits in the one specification directory.

    Args:
        files: The spec's files; only the final name of each is written, since the directory is shared.
    """
    names: list[str] = []
    for file in files:
        names.append(file.name)
    return ', '.join(names)


def _paths(files: tuple[RootRelativePath, ...]) -> list[str]:
    """The root-relative paths as strings.

    Args:
        files: The paths to convert, kept in order.
    """
    paths: list[str] = []
    for file in files:
        paths.append(str(file))
    return paths
