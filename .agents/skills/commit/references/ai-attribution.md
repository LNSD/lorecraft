# Why this project records no AI attribution

The rule in [SKILL.md](../SKILL.md) is absolute: no AI attribution in a commit message, a pull request
title or body, or a comment. The rule is short. The reasoning is what decides the cases the rule does not
name, so it is written down here.

## An LLM is a tool, and the committer is the author

A model produces text. A person reads it, judges it, corrects it, and decides to keep it. That deciding is
the authorship, and it carries the liability that comes with authorship. Armin Ronacher states the
consequence directly:

> If my coding tool opens a pull request, I opened that pull request, not the machine.

> If a coding assistant generates a security bug, the model is not to blame but the human who accepted and
> committed the code is.

> The agency is not in the model or harness but in the human and in the organization that deployed it.

Source: [Clanker: A Word For The Machine](https://lucumr.pocoo.org/2026/5/26/clankers/), Armin Ronacher.

His objection to describing these systems in human terms is the same objection this rule encodes. Softer
language, he writes, "makes it easier to move responsibility into some undefined void". A `Co-Authored-By`
trailer naming a model does precisely that. It credits a co-author who reviewed nothing, warrants nothing,
and cannot be asked about the change in a year. The trailer looks like scrupulous honesty and functions as
a disclaimer.

## The kernel reached the same conclusion about the trailer

When the Linux kernel formalised its policy on AI coding assistants, the original proposal was to record
AI help with `Co-developed-by:`. That was rejected in favour of a weaker tag, because co-development
implies authorship. On signing, the policy is unambiguous:

> AI agents MUST NOT add Signed-off-by tags. Only humans can legally certify the Developer Certificate of
> Origin (DCO).

The policy makes the human submitter responsible for reviewing all AI-generated code, for licence
compliance, for adding their own sign-off, and for "taking full responsibility for the contribution".

Source: [AI Coding Assistants](https://docs.kernel.org/process/coding-assistants.html), Linux kernel
documentation.

The premise is shared and well supported: the tool is not an author, and the human who signs is on the
line for every line.

## Where this project goes further, and why

Be honest about the divergence rather than claiming more support than the sources give. The kernel does
**not** stay silent about tool use. It requires an `Assisted-by:` trailer naming the assistant. This
project requires no trailer and forbids one. Two reasons, and they are this project's own.

**Tool use is not a property of the change.** A commit message answers what changed for the project and
why. Which tool the author had open while writing it is process, not consequence. A reader debugging this
history in five years needs the intent and the constraint that forced the shape; the tooling tells them
nothing they can act on. The kernel's reason for recording it is provenance across thousands of
contributors who do not know one another, reviewed through mailing lists, under a legal certification
regime. This project has one author, and the author is the committer. The provenance problem the trailer
solves does not exist here.

**Vendor neutrality.** A product name or a session URL welds permanent, immutable history to one company's
product and one company's URL scheme. Session links rot the moment a vendor changes a route or retires a
product, leaving dead references in a log that cannot be rewritten without rewriting history. Naming a
vendor also reads as an endorsement the project never agreed to carry, in the one artefact every
contributor and every downstream reader inherits. Tools change; the log is permanent. Keep the log free of
them.

## What this is not

This is not a claim that the work was done without tools, and it is not an instruction to conceal
anything. Nobody is misled by the absence of a trailer: a commit asserts that its author reviewed the
change and stands behind it, which is exactly what happened. What is refused is crediting a tool as a
party to the work, and binding a permanent record to a vendor.
