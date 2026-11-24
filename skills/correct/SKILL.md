---
name: correct
description: >
  Use only when invoked by name or by wrap-up: finds the mistakes agents keep
  repeating in this repo and makes each one impossible, trying architecture
  first, then types, then a lint whose error names the fix, then a test, with
  prose rules last. Not for a single correction made mid-task. Trigger:
  "run correct", "correct pass", "encode repeated corrections", or /correct.
---

Turns repeated corrections into checks. The user keeps correcting agents in this repo for the same mistakes; change the repo so the next agent cannot make them.

Assume every contributor is an agent that sees only the files it opened, copies the nearest example, and takes the shortest path that compiles. A change that looks right from one file should be right for the whole repo.

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- `git`

Install missing tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## Harness notes

| Step says | omp | Claude Code | Other agents |
|---|---|---|---|
| session history | `eval` with `archive.prompts(...)` and `archive.search(...)`, default project scope | this workspace's `~/.claude/projects/<slug>/*.jsonl` | none: skip, and say so |
| ask the user | `ask` tool | AskUserQuestion | plain-text question |

## 1. Find the mistake classes

Check the prerequisite first:
```bash
command -v git >/dev/null || echo "missing: git"
```
Missing `git`: stop. Not a git repo (`git rev-parse --git-dir` fails): continue, skip the commit record, the `.git` findings and the stamp, and say so.

Read these back to the last pass (`cat "$(git rev-parse --git-path correct)/last"`, a date; no file means 90 days):

- **Session history** for this project only (Harness notes): user messages that correct, redo, or reject agent work. Never read another project's history; it may hold private work from elsewhere.
- **Commit record**: `git log --since=<date> --format='%h %s'`, for reverts and for a `fix` that repairs the `feat` before it.
- **Review findings kept under `.git`**: `wrap-up/run/*.json` and `pr-review-toolkit/*/findings.md`, when present.
- **Agent instruction files** (`AGENTS.md`, `CLAUDE.md`): rules that exist but that nothing enforces.

Group what you find into classes. A class counts once it has happened twice; a single slip is not a pattern. Cite each instance with a date or commit.

## 2. Pick a level for each class

Take the highest level that works, and say why each higher one did not:

1. **Architecture.** Give each piece of state one owner and each task one supported way. Hide internals so the wrong import fails. Replace hand-synced lists with one source of truth. Delete old ways and dead code an agent would copy.
2. **Types, then lint.** Make the bad state impossible to write. If bad code still compiles, add a lint or script to the repo's existing check command whose error names the file, type, or function to use instead. If the pattern is already common, fail only when a change adds more.
3. **Test.** Assert the behavior. Fix or delete a test that still passes when that behavior breaks.
4. **Prose rule.** Only for judgment calls, because nothing fails when an agent skips prose.

## 3. Report and pick

Print one table, most frequent class first: `Class | Evidence | Level | Why not higher | Change`. Then ask the user which classes to fix (Harness notes), and wait. No classes: say so and go to step 5.

A fix that belongs in another repo (a shared lint config, a skill, global agent rules) is not applied from here: name the repo and the change in the table.

## 4. Fix and prove, one class at a time

For each picked class, in table order:

1. Make the change at the level picked.
2. Prove the check fails on a real past mistake: restore the offending lines from the cited commit or session, run the repo's check command, confirm it fails with the new error, then undo the restore. A check never seen failing proves nothing.
3. Delete the prose rule this check replaces from the agent instruction file. Rules that nothing enforces stay; rules a check enforces go.
4. Show `git status --short`, suggest a Conventional Commit subject, and stop until the user commits. Never commit or push.

An exception to a new check needs the user's approval and goes in that check's allow-list, not in an inline suppression.

## 5. Stamp and report

Record the pass, even when nothing was picked:
```bash
d="$(git rev-parse --git-path correct)" && mkdir -p "$d" && date +%F > "$d/last"
```

Reply with each class, its evidence, the level picked, why a higher level did not work, and its outcome: `fixed`, `declined`, or `hand-off: <repo>`.
