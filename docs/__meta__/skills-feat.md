---
name: "skills-feat"
description: "Additional writing rules for feature-document skills. Load when creating or editing a feat-* skill entry"
type: "meta"
scope: "global"
---

# Feature Documentation Skill Layer

**Applies to feature-document skills.** This layer extends [skills](skills.md) and sets a budget for finding,
updating and validating feature documentation.

## Feature Documentation Workflows

Keep discovery, status reporting and document validation as distinct tasks with clear triggers. A skill that checks
whether a feature document matches implementation must identify both sources and report their disagreements; a
skill that reports status should query the current source rather than infer maturity from old notes. The feat
meta specs remain the authority for a feature document's required content.

The 3500-token limit leaves room for a complete feature workflow without carrying a feature-document template into
every skill. It applies in addition to the base budget.

## Checklist

- [ ] Discovery, status and validation tasks have clear triggers and outcomes
- [ ] A validation workflow compares the document with the implementation and reports mismatches
- [ ] Feature-document conventions link to their meta spec instead of duplicating it

## References

- [skills](skills.md) - Extends: Base rules for every skill entry
