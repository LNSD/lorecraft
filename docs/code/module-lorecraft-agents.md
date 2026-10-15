---
name: "module-lorecraft-agents"
description: "The lorecraft.agents package's responsibility, role, boundary and invariants: what Lorecraft states about each coding agent, as data. Load when adding an agent or an aspect of one, adding or moving code in lorecraft.agents, or reading an agent's skills directories or guide files from another package"
type: "pkg"
scope: "pkg:lorecraft.agents"
---

# The `lorecraft.agents` Package

## Responsibility

State what Lorecraft knows about each coding agent. It changes when an agent changes where it reads skills or
its guide files, when an agent is added, or when Lorecraft starts to state a new aspect of every agent.

## Role

**Declaration.** The agents' statements are part of what decides the scan's scope: a skills directory an agent
reads is a directory the scan reads. So they are fixed data, never something learned from the disk. A repository
that lacks an agent's directory does not change what the agent states. It only means the model records no such
directory.

## Belongs Here

- A value an agent states about itself: its name, the directories it reads skills from, the files it loads as its
  guide, in the project scope or the user scope.
- The declaration of an aspect that every agent has, and the record that holds an agent's aspects.
- The closed set of known agents, and the way another layer iterates it. A new agent is one package beside the
  others, holding its values, and one record in that set.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Checks whether an agent's directory exists in a repository, or lists it | `lorecraft.project`, through a view |
| Resolves a project-scope path against a workspace root | `lorecraft.project`, through a view |
| Judges a skill against the Agent Skills specification | `lorecraft.rules` |
| Turns an agent's directories into scan roots | `lorecraft.project.layout` |

## Invariants

- `lorecraft.agents` imports `lorecraft.core` and no other Lorecraft package, and reads no environment variable,
  home directory or disk.
- A path it states is a `lorecraft.core.path.RootRelativePath`, validated when it is declared, and relative to
  the root of its scope: the repository for the project scope, the home directory for the user scope. The two
  scopes have distinct types, `ProjectPath` and `UserPath`, so one cannot stand in for the other.
- Every record is immutable data.
- Another layer reaches an agent only by iterating the closed constant tuple of agents and reading the agent's record. It never names
  one agent or one agent's constant, so adding an agent edits only this package.

## Examples

```python
# ❌ Bad — the agent's statement now depends on the machine it runs on: a directory a developer has not yet
# created drops out of the scope, and a skill placed there later is reported as outside it
def project_skills_dirs(root: Path) -> tuple[PurePosixPath, ...]:
    return tuple(d for d in (PurePosixPath('.codex/skills'),) if (root / d).is_dir())
```

```python
# ✅ Good — the agent states where it reads; the project model records the directories a repository has
CODEX_SKILL_DIRS: Final[ProjectSkillsDirs] = (ProjectPath(RootRelativePath.parse('.codex/skills')),)
```

```python
# ❌ Bad — in lorecraft.project: naming one agent's constant means a third agent silently gets no skills
from lorecraft.agents.codex import CODEX_SKILL_DIRS

skills_dirs = CODEX_SKILL_DIRS
```

```python
# ✅ Good — in lorecraft.project: every agent, through `iter_agents()`, each directory tied to its agent
skills_dirs = [(agent, skills_dir) for agent in iter_agents() for skills_dir in agent.skill_dirs]
```

## Checklist

Before committing code, verify:

- [ ] Nothing added to `lorecraft.agents` imports a Lorecraft package other than `lorecraft.core`, or reads the disk or the environment
- [ ] Every path stated is a `ProjectPath` or a `UserPath` over a `RootRelativePath`, relative to the root of its scope
- [ ] No code outside `lorecraft.agents` names an individual agent or one agent's constant
- [ ] A new agent is one package beside the others and one record in the constant tuple `_AGENTS`

## References

- [adr-001-snapshot-model](../arch/adr-001-snapshot-model.md) - Foundation: The Declaration role
- [adr-003-project-model](../arch/adr-003-project-model.md) - Foundation: Why the scope is declared, never discovered
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One reason to change
