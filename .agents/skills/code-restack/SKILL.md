---
name: code-restack
description: Rebase a stack of pushed part branches onto a new base, run the gates on each, check that every commit is signed, and push them with a lease. Use when the base of a stack moved (a part below merged, or main advanced) and the branches above must follow. Not for applying a Writer's patch files or squashing a part (see /code-integrate), or for syncing open pull requests.
compatibility: Requires python3, git with commit signing configured, and just with the repository's gate recipes. Imports gitflow.py from the code-integrate skill, so that skill must sit next to this one. Pushing needs a remote named origin.
allowed-tools: Bash(python3 .agents/skills/code-restack/scripts/restack.py *) Bash(python3 */.agents/skills/code-restack/scripts/restack.py *)
---

# Code Restack

One command that moves a stack of part branches onto a new base. It prints ONE compact JSON result and writes the
raw git and gate output to a log file, named in the result as `log`; read the log only when the result says
something failed.

## When to Use

- A part below the stack merged, or the stack's base advanced, and every branch above must be rebased.

The script never resolves a conflict, never pushes an unsigned commit, never uses plain `--force`, and never merges
or closes a pull request.

## Command

Run on a clean working tree. `--repo` names the repository and defaults to the current directory, so the call
needs no `cd`.

```bash
python3 <repo>/.agents/skills/code-restack/scripts/restack.py --repo <repo> --onto origin/main --from <old-base> lnsd/<slug>-1 lnsd/<slug>-2 ...
```

| Argument | Meaning |
|---|---|
| `--repo` | The repository to work in; default the current directory |
| `--onto` | The ref the bottom branch moves onto, such as `origin/main` |
| `--from` | The ref the bottom branch sits on now: its old base, or the tip of the part that merged |
| `<branch>...` | The part branches, bottom to top, as named on the remote |

It fetches, then rebases each branch from its `origin/<branch>` with `git rebase --onto`, bottom to top, each one
onto the rebased tip of the branch below. After each rebase it runs the gates `fmt-check`, `check`, `typecheck`,
`test` and `check-docs`, stopping at the first failure, and checks that every commit is signed (`%G?` is `G`).
Only when every branch passed does it push them all in one atomic `git push`, each with a lease pinned to its
`origin/<branch>` from before the rebase, and then move the local branches. Until then no local branch moves and
nothing is pushed. A local branch that another worktree has checked out is not moved, since git refuses to; the
run is still `ok`, because the remote moved, and the branch is listed in `local_not_moved`.

It refuses when `--repo` is not a git repository, when the tree is not clean, when a ref does not exist, when a
branch does not sit on the one below it, when a local branch holds commits its remote branch lacks, and when the push
is rejected, in which case no remote branch moved.

## Result

```json
{"status":"ok","stack":[{"branch":"lnsd/x-1","old_sha":"…","new_sha":"…","gates":{"fmt-check":"pass"},"push":"lease"}],"local_not_moved":[],"log":"…"}
```

- `status` is `ok`, `needs_rebase` (with the `branch` that conflicted; the rebase was aborted), `gates_failed`
  (with the `branch`; its failed gate is `fail` and later gates did not run), `refused` or `error`.
- `local_not_moved` lists the branches whose local copy stayed at its old tip because another worktree holds it.
- `refused` and `error` carry a `reason`.

## Exit codes

| Code | Meaning | What the caller does |
|---|---|---|
| 0 | `ok` | Continue |
| 1 | A gate failed | Read the log, send the failure back as a FIX |
| 2 | A rebase conflicted and was aborted | Ask the Writer for a `REBASE` of the named branch |
| 3 | Refused or a git command failed | Read `reason`; fix the setup, do not work around it |
