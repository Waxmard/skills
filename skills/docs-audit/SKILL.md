---
name: docs-audit
description: >-
  Use when auditing, trimming, or pruning code comments and markdown docs in a
  branch diff or whole repo (lean, default, or full mode). Cuts restated code,
  change narration, commented-out code, padded prose, and stale references
  while keeping why-comments. Trigger: "audit docs", "audit comments", "too
  many comments", "over-documented", "trim docs", "docs spa day", or
  /docs-audit.
---

Audits code comments and markdown docs to cut what a reader doesn't need, while keeping every comment that explains why. Its best outcome is a shorter diff with the same information.

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- `git`

Install missing tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## 1. Scope resolution (`lean` / default / `full`)

Before step 1, check the prerequisites:
```bash
command -v git >/dev/null || echo "missing: git"
```
Missing `git`: stop.

1. Confirm repo: `git rev-parse --git-dir`. If it fails, stop: "not a git repo".
2. Resolve the mode. Take it from the invocation args or the caller's instructions (`mode: <x>`): `lean`, `default`, or `full`. None given: default. Remove the mode word before reading the other args.
3. Resolve the range: the caller's range (`<mb>...<head0>`) when given; standalone, `$(git merge-base HEAD origin/main 2>/dev/null || echo origin/master)...HEAD` plus uncommitted working-tree changes.
4. Exclude machine-authored paths everywhere: lockfiles, snapshots, `dist/`, `build/`, `coverage/`, `*.min.*`, `*.map`, `*.gen.*`, `*.generated.*`, `vendor/`, `third_party/`, `node_modules/`, and binaries. Doc files are `*.md`, `*.mdx`, `*.rst`, `*.adoc`; every other text file is source.
5. Read the root `AGENTS.md` (or `CLAUDE.md` / `GEMINI.md` when there is no `AGENTS.md`) for a comment or docs convention. A project convention overrides every tag below.
6. Set the scope:
   - **`lean`**: only comment lines and doc lines added in the range (`+` lines of `git diff <range>`). Flag only clear bloat; never flag untouched lines.
   - **Default**: every file changed in the range, read in full, plus repo doc files that mention a changed file's path or a changed CLI flag, config key, or exported name (find them with `git grep -l -F <name> -- '*.md' '*.mdx' '*.rst' '*.adoc'`). Check those extra doc files only for `doc-dup` and `stale`. If invoked standalone on a clean branch with no commits ahead of base and no dirty files, switch to `full` and say so in the report header.
   - **`full`**: every tracked doc file, plus the comment lines of every tracked source file. Don't read whole source files: list comment lines with the next line of code, and open the enclosing block only to confirm a finding:
     ```bash
     git grep -n -A1 -E '^[[:space:]]*(#|//|/\*|\*|--|"""|'"'''"')' -- . ':!*.md' ':!*.mdx' ':!*.rst' ':!*.adoc'
     ```
     Append the step 4 exclusions as `':!<glob>'` pathspecs.

## 2. Audit tags (what to cut)

Classify every finding with one tag and one action:

- **`restates-code` (`delete`)**: a comment or docstring that paraphrases the code next to it (`# increment counter` above `count += 1`), or a docstring that only repeats the parameter names and types the signature already states.
- **`narration` (`delete`)**: comments that narrate the change or the process instead of the code: `# changed to use X`, `# fixed the bug`, `# new:`, `# added for <ticket>`, `# Step 1: ...` walk-throughs, `# Now we ...`. That history belongs in commit messages.
- **`commented-out` (`delete`)**: commented-out code. Git keeps the old version.
- **`banner` (`delete`)**: divider or section-banner comments with no content (`# ---- helpers ----`, `/* ======= */`).
- **`doc-padding` (`shrink`)**: markdown filler: welcome or "this section describes" intros, a sentence that restates its heading, summary or conclusion sections that repeat the body, lists that restate code line by line, and sections longer than their content needs. Rewrite kept prose per the `docs-style` skill.
- **`doc-dup` (`merge`)**: the same instructions or facts in two or more files (README and a docs page both explaining setup, a doc copying a script's `--help`). Keep the one canonical copy and replace the others with a link.
- **`stale` (`fix` or `delete`)**: a comment or doc that names a removed or renamed file, flag, config key, function, or behavior. Fix it if the concept still exists; delete it if it doesn't.

## 3. What to keep (hard guardrails)

Never flag:

- Comments that explain why: a non-obvious constraint, a workaround (with its issue link), a security or business rule, a performance trade-off, or a `ponytail:` marker.
- Tool directives and machine-read comments: shebangs, `# noqa`, `// eslint-disable...`, `// @ts-expect-error`, `# type:`, `//go:` directives, `# shellcheck`, license headers, and codegen markers.
- Doc comments on a public API that ship as reference docs, and comments a project convention requires (for example, a header comment per function in a shell helper library).
- `TODO`/`FIXME` lines that name an issue or owner.
- Historical records: past `CHANGELOG` entries, ADRs, and release notes. `stale` doesn't apply to them.
- Agent-instruction files (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `SKILL.md`) are docs: audit them, but never delete a rule an agent needs; only cut repetition and padding.

## 4. Execution

`lean` and default always run inline, with no subagents.

`full` with more than 30 files in scope: group the files by top-level directory (at most 15 files per group) and spawn one read-only subagent per group (Harness notes), each applying every tag except `doc-dup` to its files only. Then run `doc-dup` across all doc files yourself and merge the reports, dropping duplicates.

## Harness notes

| Step says | omp | Claude Code | Other agents |
|---|---|---|---|
| invoke with args | `/skill:<skill> <args>` | `/<skill> <args>` | first message |
| load skill `<name>` | `read skill://<name>` | Skill tool | read its `SKILL.md` |
| spawn subagents | one `task` call, default agent when tasks run shell commands (`scout` has no `bash`); `task` returns at once, so `wait` until every agent settles before using results or ending the turn (agents still running at a session exit or resume are aborted) | Agent tool calls in one message | no subagent support: run inline and say so |
| ask the user | `ask` tool | AskUserQuestion | plain-text question |

## 5. Output format and fix loop

Print a single `1..N` numbered findings list so the user or caller can reference items by number:

```markdown
# Docs Audit Report (<mode>: <N> files inspected)

1. **`<file>:<line-range>`**: `<tag>` (`delete` | `shrink` | `merge` | `fix`): <what>
   - *Why*: <1 sentence; for `doc-dup` and `stale`, cite the other file or the removed symbol at `file:line`>.
   - *Fix*: <delete lines X-Y | replace with "<shorter text>" | replace with a link to `<file>#<heading>`>.
```

End with: `net: -<L> lines (<C> comment lines, <D> doc lines).` If nothing qualifies: `Docs are lean. Nothing to prune.` Never list suspicions you checked and dropped.

- **Read-only vs standalone**: when invoked as a read-only review, make no edits and return the report verbatim. When invoked standalone, ask the user before applying fixes (they may exclude numbers; load `docs-style` before rewriting any kept prose), apply the chosen ones, then run the project's checks (from its `AGENTS.md`, Makefile, or package.json) for the touched files.
