---
name: "feat-cli"
description: "Additional rules for feature documents in the CLI namespace. Load when writing or reviewing CLI feature docs"
type: "meta"
scope: "global"
---

# CLI Feature Document Specification

**Applies to every feature document in `docs/feat/` named `cli.md` or `cli-*.md`.** It narrows [feat.md](feat.md) and does not replace its frontmatter, structure, content or budget rules.

## Namespace

CLI feature names are `cli` for the namespace's own meta document, or begin with `cli-`. The suffix identifies the CLI surface; when the document describes a nested command, each command level follows in order, separated by hyphens. For example, `cli-check-header` describes the `lorecraft check header` subcommand.

Use a `meta` document for a command group and a `feature` document for a command users invoke. Feature documents link up to their parent meta document using a relative link in `References`; meta documents do not link down to their children. Do not list sibling documents as an inventory.

The machine-checkable namespace rule is [feat-cli.header.json](feat-cli.header.json). The general feature format remains governed by [feat.md](feat.md), and each document's `type` continues to select its structure rules.

## CLI Content

Describe the command's observable behavior: what it checks, how users invoke it, accepted paths and options, output formats, and exit codes when applicable. Keep source-level responsibilities in the `Implementation` section by naming files; do not reproduce their internal logic.

Write examples as direct invocations of the installed CLI, such as `lorecraft check header`. Do not prefix them with development-environment setup commands such as `uv run`; feature docs describe the command interface independently of how a contributor launches it from a checkout.

Document only behavior that exists. When a command changes, update its feature document in the same change. A command's documentation should not enumerate sibling commands or planned subcommands.

## Checklist

- [ ] The filename and `name` are `cli` or begin with `cli-`; nested command names follow their command hierarchy in kebab-case.
- [ ] The document's type matches its role: `meta` groups a command family; `feature` documents an invokable command.
- [ ] A feature links to its parent meta document, and a meta document does not link to children.
- [ ] Usage examples invoke the installed CLI directly, without `uv run`.
- [ ] Usage states the implemented arguments, options, output and exit behavior relevant to the command.
- [ ] The document describes shipped behavior and does not inventory sibling or planned commands.
