"""The workspace model drawn as a tree and encoded as JSON, from hand-built models."""

import json
from pathlib import Path

import pytest

from lorecraft.cli.workspace_tree import render_json, render_text
from lorecraft_project.aspect import AspectFilename, AspectName, AspectNamespace
from lorecraft_project.corpus import CorpusName
from lorecraft_project.document import DocumentRef
from lorecraft_project.skill import AgentName, Sighting, Skill, SkillName
from lorecraft_project.workspace import (
    AgentSkillsDir,
    Corpus,
    SkillSet,
    Spec,
    TypeSelector,
    WorkspaceModel,
)
from lorecraft_vfs import RootRelativePath


def _path(raw: str) -> RootRelativePath:
    return RootRelativePath.parse(raw)


def _code_model() -> WorkspaceModel:
    """One corpus with a namespace spec and a type selector, one skill linked from another name.

    ``beta`` is a link to ``alpha`` inside the canonical directory, so it is its own skill whose one entry
    leads to another real directory; ``gamma`` sits in no agent's directory, so no agent sees it.
    """
    code = CorpusName.parse('code')
    corpus_spec = Spec(name=(code,), files=(_path('docs/__meta__/code.md'),), header=None)
    python_spec = Spec(
        name=(code, AspectNamespace.parse('python')),
        files=(_path('docs/__meta__/code-python.md'),),
        header=None,
    )
    selector = TypeSelector(
        corpus=code,
        document_type=AspectName.parse('rule'),
        files=(_path('docs/__meta__/code.rule.structure.json'),),
    )
    corpus = Corpus(
        name=code,
        spec=corpus_spec,
        namespace_specs=(python_spec,),
        type_selectors=(selector,),
        documents=(
            DocumentRef(code, AspectFilename.parse('logging')),
            DocumentRef(code, AspectFilename.parse('python-typing')),
        ),
    )

    codex = AgentName('codex')
    alpha = _path('.agents/skills/alpha')
    beta = _path('.agents/skills/beta')
    gamma = _path('.claude/skills/gamma')
    skills = SkillSet(
        agent_dirs=(AgentSkillsDir(codex, _path('.agents/skills'), _path('.agents/skills')),),
        skills=(
            Skill(SkillName.parse('alpha'), alpha, (codex,), (Sighting(alpha, alpha, (codex,)),)),
            Skill(SkillName.parse('beta'), alpha, (codex,), (Sighting(beta, alpha, (codex,)),)),
            Skill(SkillName.parse('gamma'), gamma, (), (Sighting(gamma, gamma, ()),)),
        ),
    )
    return WorkspaceModel(corpora=(corpus,), skills=skills)


def _empty_model() -> WorkspaceModel:
    return WorkspaceModel(corpora=(), skills=SkillSet(agent_dirs=(), skills=()))


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
                '│       ├── type selectors (1)',
                '│       │   └── rule: code.rule.structure.json',
                '│       └── documents (2)',
                '│           ├── logging.md [code]',
                '│           └── python-typing.md [code, code-python]',
                '├── agent skills directories (1)',
                '│   └── codex: .agents/skills',
                '└── skills (3)',
                '    ├── alpha',
                '    │   └── .agents/skills/alpha [codex]',
                '    ├── beta',
                '    │   └── .agents/skills/beta -> .agents/skills/alpha [codex]',
                '    └── gamma [not linked]',
                '        └── .claude/skills/gamma',
            ]
        )

        #: When
        text = render_text(Path('/work'), model)

        #: Then
        assert text == expected, 'each document names its governing specs, and each link names where it leads'

    def test_render_text_with_an_empty_model_draws_every_section_with_a_zero_count(self) -> None:
        #: Given
        model = _empty_model()
        expected = '\n'.join(
            [
                '/work',
                '├── corpora (0)',
                '├── agent skills directories (0)',
                '└── skills (0)',
            ]
        )

        #: When
        text = render_text(Path('/work'), model)

        #: Then
        assert text == expected, 'an empty section is still drawn, so the reader sees it was looked for'


@pytest.mark.unit
class TestRenderJson:
    def test_render_json_with_a_code_model_carries_governance_and_sightings(self) -> None:
        #: Given
        model = _code_model()

        #: When
        text = render_json(Path('/work'), model)

        #: Then
        document = json.loads(text)
        documents = document['corpora'][0]['documents']
        assert document['root'] == '/work', 'the root is reported as given'
        assert documents[1] == {'path': 'docs/code/python-typing.md', 'governed_by': ['code', 'code-python']}, (
            'a document lists its governing specs broad to narrow'
        )
        assert document['skills'][1]['sightings'] == [
            {'path': '.agents/skills/beta', 'target': '.agents/skills/alpha', 'agents': ['codex']}
        ], 'a sighting keeps both the listed entry and the real directory it leads to'
