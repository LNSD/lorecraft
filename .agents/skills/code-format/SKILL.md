---
name: code-format
description: Format Python code automatically. Use immediately after editing .py files, when the user mentions formatting or code style, or before checks and commits. Applies the project's ruff format configuration.
compatibility: Requires the just task runner and uv. ruff is invoked through the project environment rather than a system install.
allowed-tools: Bash(just fmt *) Bash(just fmt-check *)
---

# Code Formatting Skill

Formatting operations for this repository, a Python package built with uv.

## When to Use This Skill

Use this skill when you need to:
- Format code after editing Python files
- Check whether code meets the formatting standard without rewriting it
- Ensure formatting compliance before checks or commits

## Available Commands

### Format Python code
```bash
just fmt
```
Formats the repository with `ruff format`. This is the primary formatting command.

### Check formatting without writing
```bash
just fmt-check
```
Reports what would change using `ruff format --check`, and exits non-zero if anything would.

Both recipes accept extra flags, which are passed straight through to ruff. The target is always the
repository, so a flag changes how it formats, not what it formats.

## Notes

### What the configuration decides

Formatting is not a matter of taste here; `pyproject.toml` settles it. Two settings surprise people
most often, and neither is negotiable in a diff:

- **Single quotes.** `quote-style = "single"`, so `ruff format` rewrites double-quoted strings.
  Docstrings keep `"""`.
- **A 120-column line length**, not the ruff default of 88.

`just fmt` covers every Python file in the repository. The one exclusion is Markdown: ruff also
formats Python code blocks inside Markdown, and the documents under `docs/` are written to
illustrate a rule — bad examples included — so `extend-exclude = ["*.md"]` keeps the formatter
off them.

### Format before checks and commits

Format when you finish a coherent chunk of work, and always before running checks or committing.
Formatting after linting wastes a lint pass, because a reformat can move code across line boundaries
that the linter already reported on.

### Example workflows

**Single file edit**
1. Edit one module under `packages/lorecraft/src/lorecraft/`.
2. Run `just fmt`.
3. Move on to `/code-check`.

**Several files across packages**
1. Edit files in more than one package under `packages/lorecraft/src/lorecraft/`.
2. Run `just fmt` once — it covers the repository, so there is no per-package variant to choose.
3. Move on to `/code-check`.

## Common Mistakes to Avoid

### Anti-patterns
- **Never run `ruff format` directly** — use `just fmt`, which applies the project's env handling.
- **Never hand-format to match the style** — the formatter is the authority, and hand-formatting
  produces a diff it will simply undo.
- **Never skip formatting because an edit was small** — a one-line change still lands in the diff.
- **Never reformat files your change does not touch** — an unrelated formatting sweep buries the real
  change. If the repository is already clean, `just fmt` is a no-op, which is the expected result.

### Best practices
- Format before checks, tests, or a commit.
- Use `just fmt-check` when you want to know whether formatting is clean without modifying files —
  in a review, or when deciding whether a diff is yours.
- Re-run `just fmt` after `/code-check` applies `--fix` rewrites, since those can change line
  lengths.

## Next Steps

After formatting:
1. **Lint the code** → use `/code-check`
2. **Run targeted tests when warranted** → use `/code-test`
