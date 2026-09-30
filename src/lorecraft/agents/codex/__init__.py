"""Codex: everything Lorecraft states about it, one module per aspect ``lorecraft.agents.base`` declares."""

from .agent import CODEX
from .agents_md import CODEX_PROJECT_AGENTS_MD_FILES, CODEX_USER_AGENTS_MD_FILES
from .skills import CODEX_PROJECT_SKILLS_DIRS, CODEX_USER_SKILLS_DIRS

__all__: list[str] = [
    'CODEX',
    'CODEX_PROJECT_SKILLS_DIRS',
    'CODEX_USER_SKILLS_DIRS',
    'CODEX_PROJECT_AGENTS_MD_FILES',
    'CODEX_USER_AGENTS_MD_FILES',
]
