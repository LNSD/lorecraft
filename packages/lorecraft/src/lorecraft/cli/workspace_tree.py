"""Draw the workspace model: the text `lorecraft inspect` prints, and the JSON it prints with `--json`.

Pure: the model arrives as a value, so nothing here reads the disk. The text form is a tree with three
sections — the corpora, the agent skills directories present, and the skills — and the JSON form carries the
same content as nested objects.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from lorecraft_project.layout import DOCS_DIR
from lorecraft_project.schemas import schema_name_stem
from lorecraft_project.skill import Sighting, Skill
from lorecraft_project.workspace import AgentSkillsDir, Corpus, Spec, TypeSelector, WorkspaceModel
from lorecraft_vfs import RootRelativePath

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

    A document is followed by the stems of the specs that govern it, broad to narrow. A skill lists each
    entry it was found at, with the real directory when the entry is a link and the agents that see it.

    Returns:
        The lines, newline-separated, without a trailing newline.
    """
    sections = (
        _corpora_section(model.corpora),
        _agent_dirs_section(model.skills.agent_dirs),
        _skills_section(model.skills.skills),
    )
    lines = [str(root)]
    _draw(sections, '', lines)
    return '\n'.join(lines)


def render_json(root: Path, model: WorkspaceModel) -> str:
    """Encode the model as indented JSON, one key per section: ``{"root", "corpora", ..., "skills"}``."""
    corpora: list[dict[str, object]] = []
    for corpus in model.corpora:
        corpora.append(_json_corpus(corpus))
    agent_dirs: list[dict[str, object]] = []
    for agent_dir in model.skills.agent_dirs:
        agent_dirs.append(
            {'agent': agent_dir.agent, 'path': str(agent_dir.path), 'resolves_to': str(agent_dir.resolves_to)}
        )
    skills: list[dict[str, object]] = []
    for skill in model.skills.skills:
        skills.append(_json_skill(skill))
    document = {
        'root': str(root),
        'corpora': corpora,
        'agent_skills_dirs': agent_dirs,
        'skills': skills,
    }
    return json.dumps(document, indent=2)


def _draw(nodes: tuple[_Line, ...], prefix: str, lines: list[str]) -> None:
    """Append one line per node, and recurse into each node's children with the indent it leaves."""
    for index, node in enumerate(nodes):
        is_last = index == len(nodes) - 1
        branch = _LAST_BRANCH if is_last else _BRANCH
        lines.append(prefix + branch + node.label)
        indent = _LAST_INDENT if is_last else _INDENT
        _draw(node.children, prefix + indent, lines)


def _corpora_section(corpora: tuple[Corpus, ...]) -> _Line:
    """``corpora (N)``, then per corpus its specs, its type selectors when it has any, and its documents."""
    corpus_lines: list[_Line] = []
    for corpus in corpora:
        corpus_lines.append(_corpus_line(corpus))
    return _Line(f'corpora ({len(corpora)})', tuple(corpus_lines))


def _corpus_line(corpus: Corpus) -> _Line:
    """One corpus: the directory it reads, its specs, its type selectors and its governed documents."""
    spec_lines: list[_Line] = []
    for spec in (corpus.spec, *corpus.namespace_specs):
        spec_lines.append(_Line(f'{schema_name_stem(spec.name)}: {_file_names(spec.files)}'))
    parts = [_Line(f'specs ({len(spec_lines)})', tuple(spec_lines))]

    if corpus.type_selectors:
        selector_lines: list[_Line] = []
        for selector in corpus.type_selectors:
            selector_lines.append(_Line(f'{selector.document_type}: {_file_names(selector.files)}'))
        parts.append(_Line(f'type selectors ({len(selector_lines)})', tuple(selector_lines)))

    document_lines: list[_Line] = []
    for ref in corpus.documents:
        stems = _governing_stems(corpus.governance(ref).specs)
        document_lines.append(_Line(f'{ref.path.name} [{", ".join(stems)}]'))
    parts.append(_Line(f'documents ({len(document_lines)})', tuple(document_lines)))

    return _Line(f'{corpus.name} ({DOCS_DIR / str(corpus.name)})', tuple(parts))


def _agent_dirs_section(agent_dirs: tuple[AgentSkillsDir, ...]) -> _Line:
    """``agent skills directories (N)``, one line per agent whose directory is present, registry order."""
    agent_lines: list[_Line] = []
    for agent_dir in agent_dirs:
        agent_lines.append(_Line(f'{agent_dir.agent}: {_path_and_target(agent_dir.path, agent_dir.resolves_to)}'))
    return _Line(f'agent skills directories ({len(agent_dirs)})', tuple(agent_lines))


def _skills_section(skills: tuple[Skill, ...]) -> _Line:
    """``skills (N)``, one line per skill with one nested line per entry it was found at."""
    skill_lines: list[_Line] = []
    for skill in skills:
        label = str(skill.name)
        if not skill.is_linked:
            label += ' [not linked]'
        sighting_lines: list[_Line] = []
        for sighting in skill.sightings:
            sighting_lines.append(_sighting_line(sighting))
        skill_lines.append(_Line(label, tuple(sighting_lines)))
    return _Line(f'skills ({len(skills)})', tuple(skill_lines))


def _sighting_line(sighting: Sighting) -> _Line:
    """One entry a skill was found at, the real directory it leads to when that differs, and who sees it."""
    location = _path_and_target(sighting.path, sighting.target)
    if not sighting.agents:
        return _Line(location)
    return _Line(f'{location} [{", ".join(sighting.agents)}]')


def _json_corpus(corpus: Corpus) -> dict[str, object]:
    """One corpus as a JSON object: its specs, its type selectors and its documents with their governance."""
    specs: list[dict[str, object]] = []
    for spec in (corpus.spec, *corpus.namespace_specs):
        specs.append({'stem': schema_name_stem(spec.name), 'files': _paths(spec.files)})
    selectors: list[dict[str, object]] = []
    for selector in corpus.type_selectors:
        selectors.append(_json_type_selector(selector))
    documents: list[dict[str, object]] = []
    for ref in corpus.documents:
        documents.append(
            {'path': str(ref.path), 'governed_by': _governing_stems(corpus.governance(ref).specs)},
        )
    return {
        'name': str(corpus.name),
        'directory': str(DOCS_DIR / str(corpus.name)),
        'specs': specs,
        'type_selectors': selectors,
        'documents': documents,
    }


def _json_type_selector(selector: TypeSelector) -> dict[str, object]:
    """One type selector as a JSON object."""
    return {'type': str(selector.document_type), 'files': _paths(selector.files)}


def _json_skill(skill: Skill) -> dict[str, object]:
    """One skill as a JSON object, each entry it was found at included."""
    sightings: list[dict[str, object]] = []
    for sighting in skill.sightings:
        sightings.append({'path': str(sighting.path), 'target': str(sighting.target), 'agents': list(sighting.agents)})
    return {'name': str(skill.name), 'path': str(skill.path), 'agents': list(skill.agents), 'sightings': sightings}


def _governing_stems(specs: tuple[Spec, ...]) -> list[str]:
    """The stems of the governing specs, broad to narrow, as the model orders them."""
    stems: list[str] = []
    for spec in specs:
        stems.append(schema_name_stem(spec.name))
    return stems


def _path_and_target(path: RootRelativePath, target: RootRelativePath) -> str:
    """``path``, or ``path -> target`` when the path is a link to another real directory."""
    if target == path:
        return str(path)
    return f'{path} -> {target}'


def _file_names(files: tuple[RootRelativePath, ...]) -> str:
    """The file names, comma-separated: every spec file sits in the one specification directory."""
    names: list[str] = []
    for file in files:
        names.append(file.name)
    return ', '.join(names)


def _paths(files: tuple[RootRelativePath, ...]) -> list[str]:
    """The root-relative paths as strings."""
    paths: list[str] = []
    for file in files:
        paths.append(str(file))
    return paths
