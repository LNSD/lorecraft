# Contributing to Lorecraft

Thank you for considering a contribution. This guide covers what a pull request needs before it can be
reviewed. How the code is built, tested and checked is in [`AGENTS.md`](AGENTS.md), which this repository
writes for people and agents alike.

## AI Coding Assistants

AI coding assistants are tools, and you may use them.

**The person who submits a change is responsible for it**, whatever produced it. That person:

- reviews every line, and can explain why the change is shaped the way it is;
- makes sure the change can be contributed under this project's licences;
- signs it off themselves. An AI agent must never add a `Signed-off-by:` trailer: only a person can certify
  the [Developer Certificate of Origin](https://developercertificate.org/);
- answers the review themselves.

**Pull requests opened by autonomous agents are closed without review**, however correct the change. That
covers an agent opening pull requests on its own, and an account run by one: no person stands behind the
change, so there is nobody to take the responsibility above.

**Disclosure is optional.** You need not say which tools helped. If you want to, we suggest an `Assisted-by:`
trailer naming the tool rather than `Co-Authored-By:`, since a tool is not an author, and suggest leaving out
session links, which stop working when the tool changes them. Either way, your sign-off is what states that you
reviewed the change and stand behind it.

## Before You Start

- **Find or open an issue first.** Comment on it to say you are working on it, so two people do not solve the
  same thing. A change nobody asked for may be declined however good it is.
- **Issues labelled `good first issue`** are kept for people making their first contribution here. They are
  small, and their description usually states the approach.

## Making the Change

Follow [`AGENTS.md`](AGENTS.md): it names the code rules a change must follow, and the gates it must pass
before you push — `just fmt`, `just check`, `just typecheck` and the test tiers the change reaches. A pull
request that fails CI is not reviewed until it passes.

## One Commit per Pull Request

A pull request holds exactly one commit, and it lands on `main` as that commit. Pull requests are squash
merged, and the squashed message is built from the pull request's commits, so the message you write is the one
the history keeps.

- **Squash before you ask for review.** A pull request with more than one commit is not reviewed.
- **Fold review fixes into the commit.** Amend it and push with `git push --force-with-lease`, rather than
  adding a fixup commit.
- **Keep one concern per pull request.** A change that needs two commits is two pull requests: a refactor and
  the feature it unblocks are opened separately, the feature once the refactor has merged.
- **Mirror the commit in the pull request.** Its title is the commit title, and its description is the commit
  body without the `Signed-off-by:` trailer, followed by `Closes #N` for the issue it resolves. The commit
  message never carries the issue or pull request number.

## Commits

- **Conventional Commits**: `type(scope): description`, at most 72 characters. The message states what the
  change does for the people and agents using Lorecraft, not which files moved.
- **Signed off**, with `git commit -s`. The `Signed-off-by:` trailer certifies the Developer Certificate of
  Origin: that you wrote the change, or have the right to submit it, under this project's licences.
- **Signed**, with a GPG or SSH key registered on your GitHub account, so the commit shows as Verified.

## License

Unless you explicitly state otherwise, any contribution intentionally submitted for inclusion in this project,
as defined in the Apache-2.0 license, shall be dual-licensed under the
[Apache License, Version 2.0](LICENSE-APACHE) and the [MIT License](LICENSE-MIT), without any additional terms
or conditions.
