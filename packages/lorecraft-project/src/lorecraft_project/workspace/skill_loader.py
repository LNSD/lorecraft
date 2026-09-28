"""Project-scope skill discovery: vercel-labs/skills' ``listInstalledSkills`` over the filesystem boundary.

Agent detection is replaced by presence: an agent is present when its project skills directory resolves to
a directory under the root. An entry that is not a skill is left out; a directory that cannot be listed or
resolved propagates. Nothing here reads SKILL.md.

Nothing here logs and nothing here catches broadly: a skill repository error names its path already, so it
propagates unchanged to the command that loads the model, which reports it.
"""

from lorecraft_project.layout import UNIVERSAL_SKILLS_DIR
from lorecraft_project.skill.agent import AGENTS, AgentName
from lorecraft_project.skill.name import SkillName, SkillNameError
from lorecraft_project.skill.ref import Sighting, Skill
from lorecraft_project.skill.repo import Repository as SkillRepository
from lorecraft_vfs import EntryKind, RootRelativePath

from .model import AgentSkillsDir, SkillSet


def load_skills(skills: SkillRepository) -> SkillSet:
    """Scan the canonical directory and every present agent directory; merge sightings by entry name.

    An entry is a skill when it leads to a directory inside the root, its name is a valid skill name, and
    that directory holds a regular SKILL.md; any other entry is left out.

    Raises:
        ListSkillEntriesError: If a skills directory cannot be listed.
        ResolveSkillDirectoryError: If a skills path cannot be resolved.
        ProbeSkillMdError: If a skill directory cannot be listed for its SKILL.md.
    """
    canonical = skills.resolve_directory(UNIVERSAL_SKILLS_DIR)
    agent_dirs: list[AgentSkillsDir] = []
    for agent in AGENTS:
        if agent.is_universal:
            # A universal agent reads the canonical directory itself, so it is present exactly when that is.
            real = canonical
        else:
            real = skills.resolve_directory(agent.skills_dir)
        if real is not None:
            agent_dirs.append(AgentSkillsDir(agent.name, agent.skills_dir, real))

    # Each real directory is listed once, canonical first, with every agent that sees it through it.
    scan: dict[RootRelativePath, list[AgentName]] = {}
    if canonical is not None:
        scan[canonical] = []
    for agent_dir in agent_dirs:
        scan.setdefault(agent_dir.resolves_to, []).append(agent_dir.agent)

    # Keyed by the entry name as listed; dict order is first-sighting order, sightings keep scan order.
    sightings: dict[SkillName, list[Sighting]] = {}
    for directory, viewers in scan.items():
        for entry in skills.list_entries(directory):
            if entry.kind is EntryKind.DIRECTORY:
                target = entry.path
            else:
                target = skills.resolve_directory(entry.path)
            if target is None:
                continue
            try:
                name = SkillName.parse(entry.name)
            except SkillNameError:
                continue
            # Last, because it is the only check that reads the filesystem.
            if not skills.has_skill_md(target):
                continue
            sightings.setdefault(name, []).append(Sighting(entry.path, target, tuple(viewers)))

    found: list[Skill] = []
    for name, seen in sightings.items():
        found.append(_build_skill(name, seen))
    found.sort(key=lambda skill: str(skill.name))
    return SkillSet(tuple(agent_dirs), tuple(found))


def _build_skill(name: SkillName, seen: list[Sighting]) -> Skill:
    """One entity from every sighting of the name; agents in registry order, path from the first sighting."""
    exposed: set[AgentName] = set()
    for sighting in seen:
        exposed.update(sighting.agents)
    agents: list[AgentName] = []
    for agent in AGENTS:
        if agent.name in exposed:
            agents.append(agent.name)
    return Skill(name, seen[0].target, tuple(agents), tuple(seen))
