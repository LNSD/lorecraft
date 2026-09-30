"""The workspace model drawn as a tree and encoded as JSON, from hand-built models."""

import json
from pathlib import Path

import pytest

from lorecraft.agents import AgentName
from lorecraft.cli.workspace_tree import render_json, render_text
from lorecraft.project.aspect import AspectFilename, AspectNamespace
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import SkillLocation, SkillRef, SkillsDir
from lorecraft.project.workspace import Corpus, Spec, WorkspaceModel
from lorecraft.vfs import RootRelativePath


def _path(raw: str) -> RootRelativePath:
    return RootRelativePath.parse(raw)


def _code_model() -> WorkspaceModel:
    """One corpus with a namespace spec and two documents."""
    code = CorpusName.parse('code')
    corpus_spec = Spec(name=(code,), files=(_path('docs/__meta__/code.md'),), structure=None)
    python_spec = Spec(
        name=(code, AspectNamespace.parse('python')),
        files=(_path('docs/__meta__/code-python.md'),),
        structure=None,
    )
    corpus = Corpus(
        name=code,
        spec=corpus_spec,
        namespace_specs=(python_spec,),
        documents=(
            DocumentRef(code, AspectFilename.parse('logging')),
            DocumentRef(code, AspectFilename.parse('python-typing')),
        ),
    )
    return WorkspaceModel(corpora=(corpus,), skills_dirs=(), skill_locations=())


def _empty_model() -> WorkspaceModel:
    return WorkspaceModel(corpora=(), skills_dirs=(), skill_locations=())


def _skills_model() -> WorkspaceModel:
    """No corpus; two agents reading one real skills directory, one of them through a link, and two skills."""
    universal = _path('.agents/skills')
    return WorkspaceModel(
        corpora=(),
        skills_dirs=(
            SkillsDir(agent=AgentName('claude-code'), path=_path('.claude/skills'), resolves_to=universal),
            SkillsDir(agent=AgentName('codex'), path=universal, resolves_to=universal),
        ),
        skill_locations=(_regular_skill('.agents/skills/commit'), _regular_skill('.agents/skills/review')),
    )


def _regular_skill(directory: str) -> SkillLocation:
    """The location of a skill whose directory and ``SKILL.md`` are no links."""
    path = _path(directory)
    return SkillLocation(SkillRef(path), resolves_to=path, file_resolves_to=path / 'SKILL.md')


@pytest.mark.unit
class TestRenderText:
    def test_render_text_with_a_code_model_draws_each_section_under_the_root(self) -> None:
        #: Given
        model = _code_model()
        expected = '\n'.join(
            [
                '/work',
                '├── corpora (1)',
                '│   └── code (docs/code)',
                '│       ├── specs (2)',
                '│       │   ├── code: code.md',
                '│       │   └── code-python: code-python.md',
                '│       └── documents (2)',
                '│           ├── logging.md [code]',
                '│           └── python-typing.md [code, code-python]',
                '├── agent skills directories (0)',
                '└── skills (0)',
            ]
        )

        #: When
        text = render_text(Path('/work'), model)

        #: Then
        assert text == expected, 'each document names its governing specs, broad to narrow'

    def test_render_text_with_an_empty_model_draws_every_section_with_a_zero_count(self) -> None:
        #: Given
        model = _empty_model()
        expected = '\n'.join(['/work', '├── corpora (0)', '├── agent skills directories (0)', '└── skills (0)'])

        #: When
        text = render_text(Path('/work'), model)

        #: Then
        assert text == expected, 'an empty section is still drawn, so the reader sees it was looked for'


@pytest.mark.unit
class TestRenderJson:
    def test_render_json_with_a_code_model_carries_governance(self) -> None:
        #: Given
        model = _code_model()

        #: When
        text = render_json(Path('/work'), model)

        #: Then
        document = json.loads(text)
        documents = document['corpora'][0]['documents']
        assert document['root'] == '/work', 'the root is reported as given'
        assert documents[1] == {
            'path': 'docs/code/python-typing.md',
            'governed_by': ['docs/__meta__/code.md', 'docs/__meta__/code-python.md'],
        }, 'a document lists the files of its governing specs as root-relative paths, broad to narrow'

    def test_render_json_with_a_skills_model_carries_each_directory_and_each_skill_with_its_agents(self) -> None:
        #: Given
        model = _skills_model()

        #: When
        text = render_json(Path('/work'), model)

        #: Then
        assert json.loads(text) == {
            'root': '/work',
            'corpora': [],
            'agent_skills_dirs': [
                {'agent': 'claude-code', 'path': '.claude/skills', 'resolves_to': '.agents/skills'},
                {'agent': 'codex', 'path': '.agents/skills', 'resolves_to': '.agents/skills'},
            ],
            'skills': [
                {'path': '.agents/skills/commit/SKILL.md', 'agents': ['claude-code', 'codex']},
                {'path': '.agents/skills/review/SKILL.md', 'agents': ['claude-code', 'codex']},
            ],
        }, 'a skills directory names its agent and where it leads, and a skill its SKILL.md and who reads it'
