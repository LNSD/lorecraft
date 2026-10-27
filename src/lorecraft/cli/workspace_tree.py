"""Draw the workspace model: the text `lorecraft inspect` prints, and the JSON it prints with `--format json`.

Pure: the model arrives as a value, so nothing here reads the disk. The text form is a tree with one section
per part of the model — the corpora, the agent skills directories the root has, and the skills — and the JSON
form carries the same content as nested objects.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from lorecraft.core.error import Unreachable
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import SkillsDir
from lorecraft.project.workspace import Corpus, Spec, WorkspaceModel

# The box-drawing prefixes `tree` uses: one for an entry with siblings after it, one for the last entry, and
# the matching indent each leaves for the entries nested under it.
_BRANCH: Final[str] = '├── '
_LAST_BRANCH: Final[str] = '└── '
_INDENT: Final[str] = '│   '
_LAST_INDENT: Final[str] = '    '


@dataclass(frozen=True, slots=True)
class _Line:
    """One line of the drawn tree and the lines nested under it.

    Attributes:
        label: The text drawn after the branch.
        children: The lines drawn under this one, in order.
    """

    label: str
    children: tuple[_Line, ...] = ()


# The JSON `--format json` prints, one `BaseModel` per object, so a misspelt or missing key fails the type
# check. The keys are the command's published output: renaming one is a change to that contract, not a refactor. A
# field is printed in the order it is declared.


class _SpecJson(BaseModel):
    """One specification of a corpus.

    Attributes:
        name: The specification's name.
        files: The specification's files as root-relative paths, sorted.
        base: The nearest broader specification's name, or None for a root specification.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    files: list[str]
    base: str | None


class _DocumentJson(BaseModel):
    """One governed document of a corpus.

    Attributes:
        path: The document, as a root-relative path.
        governed_by: Every file of the governing specifications, broad to narrow, each specification's files
            sorted.
        base_chain: The document paths in its base chain, broadest first, including itself.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    governed_by: list[str]
    base_chain: list[str]


class _CorpusJson(BaseModel):
    """One corpus: the directory it reads, its specifications and its governed documents.

    Attributes:
        name: The corpus's name, the directory under `docs/` it reads.
        directory: The directory the corpus reads, as a root-relative path.
        specs: The corpus spec first, then its namespace specs broad to narrow; at least one entry.
        documents: The Markdown files directly inside `directory`, sorted by filename, each with the spec files that
            govern it.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    directory: str
    specs: list[_SpecJson]
    documents: list[_DocumentJson]


class _AgentSkillsDirJson(BaseModel):
    """One agent's skills directory.

    Attributes:
        agent: The name of the agent that reads the directory, such as `codex`.
        path: The directory where the agent finds it, as a root-relative path.
        resolves_to: The directory it leads to: `path` itself unless `path` is a link.
    """

    model_config = ConfigDict(frozen=True)

    agent: str
    path: str
    resolves_to: str


class _SkillJson(BaseModel):
    """One skill and the agents that read it.

    Attributes:
        path: The skill's `SKILL.md`, as a root-relative path.
        agents: The names of the agents whose skills directory leads to the one holding the skill, each once, sorted
            by name; each is the `agent` of an entry in `agent_skills_dirs`.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    agents: list[str]


class _WorkspaceJson(BaseModel):
    """The whole document: the root beside one key per section of the model.

    Attributes:
        root: The workspace root, as an absolute path; every other path is root-relative.
        corpora: Every corpus, sorted by name.
        agent_skills_dirs: Every project skills directory an agent reads that the repository has, one entry per agent
            and directory, sorted by agent then path; two agents reading one directory share a `resolves_to`.
        skills: Every skill directly inside a directory an entry of `agent_skills_dirs` resolves to, each once, sorted
            by its directory.
        agent_skills_spec: False when the root command opts out; None for the default, omitted from JSON.
    """

    model_config = ConfigDict(frozen=True)

    root: str
    agent_skills_spec: Literal[False] | None
    corpora: list[_CorpusJson]
    agent_skills_dirs: list[_AgentSkillsDirJson]
    skills: list[_SkillJson]


def render_text(root: Path, model: WorkspaceModel) -> str:
    """Draw the model as a tree headed by the root, one section per part of the model.

    A spec names its base, and a document shows its governing specs and base chain under separate labels.
    An agent's skills directory is followed by the resolved directory it leads to when it is a link, and
    a skill by the agents that read it.

    Args:
        root: The workspace root, drawn as the first line.
        model: Corpora, agent skills directories and skills to draw, each in the order the model lists them.

    Returns:
        The lines, newline-separated, without a trailing newline.
    """
    sections = (
        _corpora_section(model, model.sorted_corpora),
        _skills_dirs_section(model.sorted_skills_dirs),
        _skills_section(model),
    )
    lines = [str(root)]
    _draw(sections, '', lines)
    return '\n'.join(lines)


def render_json(root: Path, model: WorkspaceModel) -> str:
    """Encode the model as one compact JSON document, the root beside one key per section.

    The keys are `root`, `corpora`, `agent_skills_dirs` and `skills`; when opted out, it also carries
    `agent_skills_spec: false`.

    Args:
        root: The workspace root, written under the `root` key.
        model: Corpora, agent skills directories and skills to encode, one key per section.
    """
    corpora: list[_CorpusJson] = []
    for corpus in model.sorted_corpora:
        corpora.append(_json_corpus(model, corpus))
    skills_dirs: list[_AgentSkillsDirJson] = []
    for skills_dir in model.sorted_skills_dirs:
        skills_dirs.append(
            _AgentSkillsDirJson(
                agent=skills_dir.agent, path=str(skills_dir.path), resolves_to=str(skills_dir.resolves_to)
            )
        )
    skills: list[_SkillJson] = []
    for ref in model.skills():
        skills.append(_SkillJson(path=str(ref.path), agents=list(model.skill_agents(ref))))
    document = _WorkspaceJson(
        root=str(root),
        agent_skills_spec=False if not model.agent_skills_floor_enabled else None,
        corpora=corpora,
        agent_skills_dirs=skills_dirs,
        skills=skills,
    )
    excluded = {'agent_skills_spec'} if model.agent_skills_floor_enabled else set()
    return document.model_dump_json(exclude=excluded)


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


def _corpora_section(model: WorkspaceModel, corpora: tuple[Corpus, ...]) -> _Line:
    """`corpora (N)`, then per corpus its specs and its documents.

    Args:
        model: Workspace model whose corpora are drawn.
        corpora: The corpora to draw, in the order the model lists them.
    """
    corpus_lines: list[_Line] = []
    for corpus in corpora:
        corpus_lines.append(_corpus_line(model, corpus))
    return _Line(f'corpora ({len(corpora)})', tuple(corpus_lines))


def _corpus_line(model: WorkspaceModel, corpus: Corpus) -> _Line:
    """One corpus: the directory it reads, its specs and its governed documents.

    Args:
        model: Workspace model that resolves specification bases.
        corpus: Corpus drawn as one line, with its specs and documents as children.
    """
    spec_lines: list[_Line] = []
    for spec in (corpus.corpus_spec, *corpus.namespace_specs):
        base = _spec_base_name(model, spec)
        spec_lines.append(_Line(f'{spec.name}: {_file_names(spec.files)} [base: {base or "none"}]'))
    parts = [_Line(f'specs ({len(spec_lines)})', tuple(spec_lines))]

    document_lines: list[_Line] = []
    for ref in corpus.documents:
        spec_names = _governing_spec_names(corpus.governance(ref.filename).specs())
        chain = _document_base_chain_names(corpus, ref.filename)
        document_lines.append(
            _Line(f'{ref.path.name} [governed_by: {", ".join(spec_names)}] [base_chain: {", ".join(chain)}]')
        )
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
    """`skills (N)`, one line per skill.

    Args:
        model: The workspace model, which lists the skills and the agents that read each.
    """
    lines: list[_Line] = []
    for ref in model.skills():
        agents = model.skill_agents(ref)
        lines.append(_Line(f'{ref.directory} [{", ".join(agents)}]'))
    opt_out = '; Agent Skills specification disabled' if not model.agent_skills_floor_enabled else ''
    return _Line(f'skills ({len(model.skill_locations)}{opt_out})', tuple(lines))


def _json_corpus(model: WorkspaceModel, corpus: Corpus) -> _CorpusJson:
    """One corpus as a JSON object: its specs, and its documents with the spec files that govern each.

    Args:
        model: Workspace model that resolves specification bases.
        corpus: Corpus whose specs and documents become the object's keys.
    """
    specs: list[_SpecJson] = []
    for spec in (corpus.corpus_spec, *corpus.namespace_specs):
        specs.append(_SpecJson(name=str(spec.name), files=_paths(spec.files), base=_spec_base_name(model, spec)))
    documents: list[_DocumentJson] = []
    for ref in corpus.documents:
        documents.append(
            _DocumentJson(
                path=str(ref.path),
                governed_by=_governing_files(corpus.governance(ref.filename).specs()),
                base_chain=_document_base_chain_paths(corpus, ref.filename),
            ),
        )
    return _CorpusJson(
        name=str(corpus.name),
        directory=str(corpus.directory),
        specs=specs,
        documents=documents,
    )


def _spec_base_name(model: WorkspaceModel, spec: Spec) -> str | None:
    """The broader specification's name, using the workspace model's spec hierarchy.

    Args:
        model: Workspace model that resolves specification bases.
        spec: Specification whose base is wanted.
    """
    base = model.specification_base(spec.name)
    return None if base is None else str(base)


def _document_base_chain_names(corpus: Corpus, filename: AspectFilename) -> list[str]:
    """The document base chain as names, broadest first, including the document itself."""
    document = DocumentRef(corpus=corpus.name, filename=filename)
    return [str(ref.filename) for ref in (*corpus.document_base_chain(filename), document)]


def _document_base_chain_paths(corpus: Corpus, filename: AspectFilename) -> list[str]:
    """The document base chain as root-relative paths, broadest first, including the document itself."""
    document = DocumentRef(corpus=corpus.name, filename=filename)
    return [str(ref.path) for ref in (*corpus.document_base_chain(filename), document)]


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
        name = file.name
        # SAFETY: every spec file is listed under the specification directory, so no file here is the root.
        if name is None:
            raise Unreachable('a spec file sits in the specification directory, never at the root')
        names.append(str(name))
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
