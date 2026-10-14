---
name: code-sync
description: Classify open pull requests as up to date, behind, conflicting or base moved, and bring the ones that are behind main up to date with a signed rebase, the gates and a leased push, marking each PR draft meanwhile. Use when main advanced and open PRs may need a rebase, or before merging one. Not for restacking a stack of parts (see /code-restack), for applying a Writer's patches (see /code-integrate), or for creating or editing PRs.
compatibility: Requires python3, git with commit signing configured, gh authenticated for the repository, and just with the repository's gate recipes. Imports gitflow.py from the code-integrate skill, so that skill must sit next to this one. Pushing needs a remote named origin.
allowed-tools: Bash(python3 .agents/skills/code-sync/scripts/sync.py *) Bash(python3 */.agents/skills/code-sync/scripts/sync.py *)
---

# Code Sync

One command that tells which open pull requests are behind their base, and with `--apply` brings them up to date.
It prints ONE compact JSON result and writes the raw git, `gh` and gate output to a log file, named in the result
as `log`; read the log only when the result says something failed.

## When to Use

- `main` advanced and open pull requests may be behind it.
- A pull request is about to be merged and must sit on the current `main`.

The script never resolves a conflict, never pushes an unsigned commit, never uses plain `--force`, never merges or
closes a pull request and never runs `gh pr update-branch`. Creating and editing pull requests stays with the Lead;
the only change it makes to one is the draft/ready toggle.

## Command

Run on a clean working tree. `--repo` names the repository and defaults to the current directory, so the call
needs no `cd`.

```bash
python3 <repo>/.agents/skills/code-sync/scripts/sync.py --repo <repo> [--apply] <pr> [<pr> ...]
```

| Argument | Meaning |
|---|---|
| `--repo` | The repository to work in; default the current directory |
| `<pr>...` | The pull request numbers |
| `--apply` | Run the fast lane on each pull request that is `behind`; without it the script only classifies |

It fetches, then classifies each pull request from its `origin/<head>` and `origin/<base>`:

| Status | Meaning |
|---|---|
| `up_to_date` | The base is already in the branch |
| `behind` | The base is `main`, moved, and the branch rebases onto it cleanly |
| `conflicting` | The base is `main`, moved, and the rebase would conflict |
| `base_moved` | The base is another branch of a stack; use /code-restack |

The fast lane for a `behind` pull request: mark it draft, `git rebase -S origin/main` on a detached HEAD, run the
gates `fmt-check`, `check`, `typecheck`, `test` and `check-docs` (stopping at the first failure), check that every
commit is signed (`%G?` is `G`), push the rebased commit with a lease pinned to the branch's remote SHA from before
the rebase, move the local branch, and mark the pull request ready. A pull request that was already a draft is not
touched and stays one; only one this run drafted is marked ready again. A failure leaves the remote branch
untouched, and the pull request a draft. A rejected push is such a failure: the entry is `refused` with the
`reason`, and carries `"drafted":true` when this run drafted the pull request and did not mark it ready again. A
local branch that another worktree has checked out is not moved, since git refuses to, and its entry carries
`"local_not_moved":true`; the sync is still `synced`. When `gh pr ready` fails after the push, the entry stays
`synced` and carries `"ready":false`; when `--undo` fails the run refuses before the rebase. The caller's branch is
restored at the end.

It refuses when `--repo` is not a git repository, when the tree is not clean, when a pull request is not open or its
branches do not exist, when a commit is unsigned and when a push is rejected.

## Result

```json
{"status":"ok","prs":[{"pr":7,"branch":"lnsd/x","draft":false,"old_sha":"…","new_sha":"…","gates":{"fmt-check":"pass"},"push":"lease","status":"synced"}],"log":"…"}
```

- The top-level `status` is `ok`, `needs_rebase` (a pull request is `conflicting` or `base_moved`), `gates_failed`
  or `refused`; `refused` carries a `reason`.
- Each entry's `status` is one of the classifications above, or `synced` after `--apply`.

## Exit codes

| Code | Meaning | What the caller does |
|---|---|---|
| 0 | Every pull request is up to date or synced | Continue |
| 1 | A gate failed after the rebase | Read the log, send the failure back as a FIX |
| 2 | A pull request is `conflicting` or `base_moved` | Ask the Writer for a `REBASE`, or run /code-restack |
| 3 | Refused or a command failed | Read `reason`; fix the setup, do not work around it |
