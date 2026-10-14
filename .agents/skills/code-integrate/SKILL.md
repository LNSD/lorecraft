---
name: code-integrate
description: Integrate a Code Writer's patch files into a part branch, run the gates and measure the size, then squash the branch into one signed commit and push it. Use when a Writer report arrives with format-patch files, when a part branch needs its commits applied and checked, or when a checked part is ready to squash and push. Not for choosing commit messages (see /commit), for restacking branches, or for syncing open pull requests.
compatibility: Requires python3, git with commit signing configured, and just with the repository's gate recipes. Pushing needs a remote named origin.
allowed-tools: Bash(python3 .agents/skills/code-integrate/scripts/integrate.py *)
---

# Code Integrate

Two mechanical steps of integrating a Writer's work, as one command each. Every command prints ONE compact JSON
result and writes the raw git and gate output to a log file, named in the result as `log`; read the log only when
the result says something failed. Judgement stays with the caller: the commit message, the split, the review.

## When to Use

- **`apply`**: a Writer's patch files are ready to go onto a part branch, and the gates and size are wanted.
- **`squash`**: the applied branch is accepted and is to become one signed commit on its base, pushed.

The scripts never resolve a conflict, never commit unsigned, never use plain `--force`, and never merge or
close a pull request.

## Commands

Run from the repository root, on a clean working tree.

```bash
python3 .agents/skills/code-integrate/scripts/integrate.py apply --branch lnsd/<slug> --base origin/main <patch>...
python3 .agents/skills/code-integrate/scripts/integrate.py squash --branch lnsd/<slug> --base origin/main --message-file <file>
```

| Argument | Meaning |
|---|---|
| `--branch` | The part branch, as named on the remote |
| `--base` | The ref the part sits on: `origin/main`, or the branch of the part below |
| `<patch>...` | The `git format-patch` files, in order |
| `--message-file` | The commit message, written by the caller with the `commit` skill |

`apply` fetches, switches to the branch (created at the base when it is not on the remote, otherwise at
`origin/<branch>`; a local branch that already descends from that start is continued, so a FIX after a failed
gate lands on top of the commits applied before), applies the patches with `git am --3way`, runs the gates
`fmt-check`, `check`, `typecheck`, `test` and `check-docs` in that order, stopping at the first failure, and
measures the size against the base. A gate that passes but leaves the tree changed is reported as `gates_failed`.

`squash` soft-resets to the base, commits with `-s -S`, checks that `%G?` is `G`, then pushes: `-u` when the
branch is new on the remote, otherwise `--force-with-lease` pinned to the `origin/<branch>` that `apply` fetched.
It refuses when the tree is not clean, when `origin/<branch>` is not in the branch, and when the push is
rejected; each time it puts the branch back and pushes nothing, as it does when the commit is not signed.

## Result

```json
{"status":"ok","branch":"lnsd/x","base_sha":"…","start_sha":"…","head_sha":"…","commits":2,"size":243,"gates":{"fmt-check":"pass","check":"pass"},"log":"…"}
```

- `apply`: `status` is `ok`, `gates_failed` (the failed gate is `fail` and later gates did not run, or a gate
  left the tree changed, with a `reason`) or `needs_rebase`. `size` is lines added plus deleted against the base,
  lockfiles and binary files excluded.
- `squash`: `status` is `ok` with `head_sha`, `signature` (`G`) and `push` (`new` or `lease`).
- `refused` and `error` carry a `reason`.

## Exit codes

| Code | Meaning | What the caller does |
|---|---|---|
| 0 | `ok` | Continue |
| 1 | A gate failed | Read the log, send the failure back as a FIX |
| 2 | The patches do not apply; `git am` was aborted and the branch is untouched | Ask the Writer for a REBASE |
| 3 | Refused (dirty tree, local branch not descending from the remote, unsigned commit, base not an ancestor, remote ahead of the branch) or a git command failed | Read `reason`; fix the setup, do not work around it |
