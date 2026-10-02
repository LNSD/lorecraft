"""The workspace model drawn as a tree and encoded as JSON, from hand-built models."""

import json
from pathlib import Path
from typing import Final

import pytest

from lorecraft.agents import AgentName
from lorecraft.cli.workspace_tree import render_json, render_text
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename, AspectNamespace
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import SkillLocation, SkillRef, SkillsDir
from lorecraft.project.workspace import Corpus, Spec, WorkspaceModel


def _path(raw: str) -> RootRelativePath:
    return RootRelativePath.parse(raw)


def _code_model() -> WorkspaceModel:
    """One corpus with a namespace spec of two files, and two documents."""
    code = CorpusName.parse('code')
    corpus_spec = Spec(name=(code,), files=(_path('docs/__meta__/code.md'),), structure=None)
    python_spec = Spec(
        name=(code, AspectNamespace.parse('python')),
        files=(_path('docs/__meta__/code-python.md'), _path('docs/__meta__/code-python.structure.json')),
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
    return WorkspaceModel(corpora=(corpus,), skills_dirs=(), skill_locations=(), named_dirs=(), outside_symlinks=())


# The JSON document `render_json` encodes `_code_model` as, rooted at `/work`.
_CODE_MODEL_DOCUMENT: Final[dict[str, object]] = {
    'root': '/work',
    'corpora': [
        {
            'name': 'code',
            'directory': 'docs/code',
            'specs': [
                {'stem': 'code', 'files': ['docs/__meta__/code.md']},
                {
                    'stem': 'code-python',
                    'files': ['docs/__meta__/code-python.md', 'docs/__meta__/code-python.structure.json'],
                },
            ],
            'documents': [
                {'path': 'docs/code/logging.md', 'governed_by': ['docs/__meta__/code.md']},
                {
                    'path': 'docs/code/python-typing.md',
                    'governed_by': [
                        'docs/__meta__/code.md',
                        'docs/__meta__/code-python.md',
                        'docs/__meta__/code-python.structure.json',
                    ],
                },
            ],
        }
    ],
    'agent_skills_dirs': [],
    'skills': [],
}


def _empty_model() -> WorkspaceModel:
    return WorkspaceModel(corpora=(), skills_dirs=(), skill_locations=(), named_dirs=(), outside_symlinks=())


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
        named_dirs=(),
        outside_symlinks=(),
    )


def _regular_skill(directory: str) -> SkillLocation:
    """The location of a skill whose directory and `SKILL.md` are no links.

    Args:
        directory: The skill's directory, root-relative and slash-separated; its `SKILL.md` sits directly in it.
    """
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
                '│       │   └── code-python: code-python.md, code-python.structure.json',
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
        assert text == expected, (
            'a spec names each of its files, and each document names its governing specs, broad to narrow'
        )

    def test_render_text_with_an_empty_model_draws_every_section_with_a_zero_count(self) -> None:
        #: Given
        model = _empty_model()
        expected = '\n'.join(['/work', '├── corpora (0)', '├── agent skills directories (0)', '└── skills (0)'])

        #: When
        text = render_text(Path('/work'), model)

        #: Then
        assert text == expected, 'an empty section is still drawn, so the reader sees it was looked for'

    def test_render_text_with_a_skills_model_draws_each_directory_with_its_link_and_each_skill_with_its_agents(
        self,
    ) -> None:
        #: Given
        model = _skills_model()
        expected = '\n'.join(
            [
                '/work',
                '├── corpora (0)',
                '├── agent skills directories (2)',
                '│   ├── claude-code: .claude/skills -> .agents/skills',
                '│   └── codex: .agents/skills',
                '└── skills (2)',
                '    ├── .agents/skills/commit [claude-code, codex]',
                '    └── .agents/skills/review [claude-code, codex]',
            ]
        )

        #: When
        text = render_text(Path('/work'), model)

        #: Then
        assert text == expected, (
            'a linked directory is drawn with where it leads, a real one alone, and a skill with the agents reading it'
        )


@pytest.mark.unit
class TestRenderJson:
    def test_render_json_with_a_code_model_carries_each_spec_and_each_document_with_its_governance(self) -> None:
        #: Given
        model = _code_model()

        #: When
        text = render_json(Path('/work'), model)

        #: Then
        assert json.loads(text) == _CODE_MODEL_DOCUMENT, (
            'a corpus carries its specs with their files, and each document the files of its governing specs'
        )

    def test_render_json_with_a_code_model_indents_by_two_spaces(self) -> None:
        #: Given
        model = _code_model()

        #: When
        text = render_json(Path('/work'), model)

        #: Then
        # Parsing the text back would hide its layout, so the text itself is compared.
        assert text == json.dumps(_CODE_MODEL_DOCUMENT, indent=2), 'the document is indented by two spaces'

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
