---
name: code-integrate
description: Integrate a Code Writer's patch files into a part branch, and run the gates and measure the size. Use when a Writer report arrives with format-patch files, or when a part branch needs its commits applied and checked. Not for choosing commit messages (see /commit), for restacking branches, or for syncing open pull requests.
compatibility: Requires python3, git, and just with the repository's gate recipes, and a remote named origin.
allowed-tools: Bash(python3 .agents/skills/code-integrate/scripts/integrate.py *)
---

# Code Integrate

The mechanical step of integrating a Writer's work, as one command. Every command prints ONE compact JSON
result and writes the raw git and gate output to a log file, named in the result as `log`; read the log only when
the result says something failed. Judgement stays with the caller: the commit message, the split, the review.

## When to Use

- **`apply`**: a Writer's patch files are ready to go onto a part branch, and the gates and size are wanted.

The script never resolves a conflict, and never merges or closes a pull request.

## Commands

Run from the repository root, on a clean working tree.

```bash
python3 .agents/skills/code-integrate/scripts/integrate.py apply --branch lnsd/<slug> --base origin/main <patch>...
```

| Argument | Meaning |
|---|---|
| `--branch` | The part branch, as named on the remote |
| `--base` | The ref the part sits on: `origin/main`, or the branch of the part below |
| `<patch>...` | The `git format-patch` files, in order |

`apply` fetches, switches to the branch (created at the base when it is not on the remote, otherwise at
`origin/<branch>`; a local branch that already descends from that start is continued, so a FIX after a failed
gate lands on top of the commits applied before), applies the patches with `git am --3way`, runs the gates
`fmt-check`, `check`, `typecheck`, `test` and `check-docs` in that order, stopping at the first failure, and
measures the size against the base. A gate that passes but leaves the tree changed is reported as `gates_failed`.

## Result

```json
{"status":"ok","branch":"lnsd/x","base_sha":"…","start_sha":"…","head_sha":"…","commits":2,"size":243,"gates":{"fmt-check":"pass","check":"pass"},"log":"…"}
```

- `apply`: `status` is `ok`, `gates_failed` (the failed gate is `fail` and later gates did not run, or a gate
  left the tree changed, with a `reason`) or `needs_rebase`. `size` is lines added plus deleted against the base,
  lockfiles and binary files excluded.
- `refused` and `error` carry a `reason`.

## Exit codes

| Code | Meaning | What the caller does |
|---|---|---|
| 0 | `ok` | Continue |
| 1 | A gate failed | Read the log, send the failure back as a FIX |
| 2 | The patches do not apply; `git am` was aborted and the branch is untouched | Ask the Writer for a REBASE |
| 3 | Refused (dirty tree, local branch not descending from the remote) or a git command failed | Read `reason`; fix the setup, do not work around it |
