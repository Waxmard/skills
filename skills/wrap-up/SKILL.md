---
name: wrap-up
description: >
  Use at the end of a branch, before opening or merging a PR or MR, or for a
  "repo spa day" pre-merge checklist. Runs pr-review-toolkit and selects which
  of tooling-sync, ponytail-review, test-audit, docs-audit, interface-review,
  and triage-renovate-dependabot-prs to run, then fixes findings behind commit
  gates. Trigger: "wrap up this branch", "I'm done with this branch", "end of
  branch", "pre-merge checklist", "ready to merge", "repo spa day", or
  /wrap-up.
---

Orchestrates the end-of-branch reviews and hand-offs. It owns only the pre-flight signals, the
order, the model tiers, the gates and the hand-offs; all real logic stays in the underlying skills.

Invocation: invoking wrap-up with no args runs pre-flight → report → pick → run. Invoking wrap-up with `run <reply>`
or directly with a `<reply>` arg (e.g. `default`, `lean`, `full`, `go`, `run go`, `run go full`, `run go default`, `run 3 6`, `run 4@full`) re-runs pre-flight silently, skips the report and the
pick, and goes straight to §3 with `<reply>` parsed as in §2. The trigger is non-empty skill args or the
first user message starting with `run `. Use it to run pre-flight on a cheap model, then start a
new session on a stronger model and paste the `run` line.

## Harness notes

Steps below use neutral verbs. Map them to your harness:

| Step says | omp | Claude Code | Other agents |
|---|---|---|---|
| invoke with args | `/skill:wrap-up run go` | `/wrap-up run go` | first message `run go` |
| load skill `<name>` | `read skill://<name>` | Skill tool | read that skill's `SKILL.md` |
| spawn the tasks | one `task` call with no `agent` field (tasks run `git diff`; `scout` has no `bash`), `effort: "med"` (fast) or `"hi"` (strong); avoid `effort: "lo"` on Gemini Vertex models (`THINKING_LEVEL_MINIMAL` 400); `task` returns at once, so `wait` until every task settles before ending the turn; if a task's findings file is missing, `history://<id>` shows whether it aborted or parked, and `write agent://<id>` revives it | Agent tool calls in one message, `model: haiku` (fast) or `opus` (strong) | no subagents: run each task's prompt inline in order, note "ran inline: no subagents" |
| run the script | `bash` tool, never `eval` (its env omits custom exports) | the shell | the shell |
| progress list | `todo` `init` (when stopping at a commit or decision gate, call `todo` `block` with `phase` to block all remaining items in one call so open todos don't trigger auto-continue reminders; `unblock` the phase when resuming) | TodoWrite | numbered checklist printed in chat |
| ask the user | `ask` tool | AskUserQuestion | plain-text question |

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- `git`
- `python3`, for the wrap-up script and row 1's tooling-sync resolver

Install missing tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## 1. Pre-flight

Read-only for this repo: no edits, no installs. Runs before any skill. `scripts/wrap_up.py` does
the git work, verdicts and report; replace `<skill-dir>` with the directory this `SKILL.md` was
loaded from.

```bash
for t in git python3; do command -v "$t" >/dev/null || echo "missing: $t"; done
```
Missing git: stop. Missing python3: stop, "python3 is required for scripts/wrap_up.py".

Then run, with the harness's shell tool (Harness notes), adding `--missing ponytail-review` and
`--missing ponytail-audit` for each one not in this session's skill list:
```bash
python3 -B "<skill-dir>/scripts/wrap_up.py" preflight
```
It prints the report. A non-zero exit means stop and relay stderr.

Every review row defaults to `fast`; escalate per run with `N@strong` on risky diffs.

## 2. Report and pick

Print the script's stdout as-is and wait for the reply. In `run <reply>` mode, skip printing and
waiting. Then run:
```bash
python3 -B "<skill-dir>/scripts/wrap_up.py" plan "<reply>"
```
Exit 2: show stderr and ask again. Otherwise relay its `notes`, then create the progress list
(Harness notes) from its `todo`, marking each item done as soon as its phase finishes, including
rows that report nothing to do. Print the completion block (Close) once every item except `Close:
completion summary` is done or blocked on a user action; list blocked rows under a `Blocked:`
line naming the gate that stopped them.

Modes: `lean` (minimal), `default` (branch), `full` (whole repo); `go full` forces rows 1–4 and 6.

## 3. Run

Why this order: tooling-sync first, so its new hooks and CI gates (lefthook, biome, commitlint)
also check the review-fix commits and every triage merge. Reviews next, pinned to `<head0>`, so
neither tooling commits nor triage merges enter the reviewed diff. Triage last, because it stacks
merges on whatever the earlier rows committed.

1. If the `plan` output's `inline_before` is `[1]`, run row 1 (Inline rows, Gate A) first.
2. Spawn every entry of its `tasks` in one batch (Harness notes), each with the prompt from
   `python3 -B "<skill-dir>/scripts/wrap_up.py" prompt <id>` and the entry's `tier`. If subagents or
   the tier's model are unavailable, run that prompt inline and note "ran inline: <reason>".
3. When all tasks settle, run `python3 -B "<skill-dir>/scripts/wrap_up.py" findings`. Exit 1 lists
   tasks whose findings file is missing or unreadable: re-run each listed prompt inline (or revive
   the agent per the Harness notes), then run `findings` again. A partial review is not a
   completed review.
4. Run `python3 -B "<skill-dir>/scripts/wrap_up.py" memo` before Gate F, so Gate F's fix commits
   land in row 2's next delta and get reviewed then. It refuses to write for an incomplete row 2.

**Gate F: fix findings row by row (always, after the tasks; never optional).** Do not ask "fix or
continue": stopping to fix is the default for all of wrap-up. Do not print all findings or all
decisions at once.

1. Findings arrive filtered, deduplicated by file and line, and numbered. Before leaving Gate F,
   every finding must reach a final status: fixed, verified false positive, user-declined, or
   resolved/moot after an earlier fix. Unaccounted findings block completion. Still:
   - Exclude **retired-concept removals**: a `Regression` finding that a removed element was
     left unreplaced only holds while the concept it served still exists. When the same diff
     also deleted the data field, API type or schema that element rendered from, the removal is
     a cutover with nothing to replace: a false positive, not a finding. Cite the deleted
     counterpart as the evidence in step 2's skip status.
   - Merge items with the same root cause in the same symbol across different lines.
   - For `lean` rows, use the lean bar: definite improvements only, using the smallest change that
     fixes the finding with no adjacent cleanup.
2. Walk the picked review rows in row order (2 → 6), **one row at a time**. Never print a later
   row's findings or ask a later row's decisions until the current row is finished and committed:
   1. Print `python3 -B "<skill-dir>/scripts/wrap_up.py" findings --row <N>` for the current row
      only, then re-read each item against the current tree. If an earlier row's fix already
      resolved the item, or deleted or rewrote the code it targets, mark it
      `skipped: resolved by <skill> fix` or `skipped: moot after <skill> fix`. If the row has no
      findings left, mark the row done and advance immediately to the next row in the same turn.
   2. **Ask decisions for this row only.** If any item is marked `DECISION`, present only this
      row's decision items and wait for the user's choice before editing. Ask in plain text at the
      end of the turn that prints this row's findings (or use `ask` only if its `preview` carries
      the full context so the modal doesn't hide unread text).
   3. Apply this row's fixes in this session, using the smallest change that resolves each
      finding. Run the repo's narrowest check that covers the touched files (from its
      AGENTS.md/Makefile/package.json), plus any configured file-size gate. If a check fails,
      fix that too before moving on.
   4. Print a fix table under `### Gate F: <skill>`, as `Finding | File | Status`, where status is
      `fixed`, `skipped: <reason>`, or `user-declined`. The only allowed skip reasons are a
      verified false positive (state the evidence), the user declining, or resolved/moot after
      an earlier row's fix (name that row).
   5. **Stop and wait for the user to commit every time a row changes files.** Whenever
      `git status --short` differs from the pre-flight `baseline` (in `.git/wrap-up/run/plan.json`),
      show `git status --short` and suggest the `commit:` subject from step 1, then **stop and
      wait for the user to commit**. Never carry straight on to the next row while changes are
      uncommitted, even if the next row touches the same files. Advance to the next row only after
      the user commits and `git status --short` matches `baseline`.
3. If no row had findings after exclusions, print "Gate F: no findings to fix" and continue
   without stopping.
4. If `inline_after` is `[7]`, run row 7 now (Inline rows).

Inline rows:

1. `tooling-sync`: load skill `tooling-sync` and follow it in row 1's mode (`lean`, `default`, or `full`), then Gate A.

   **Gate A — commit the tooling-sync changes**

   1. **Run any follow-up installs** tooling-sync flagged (e.g. `npm i -D @commitlint/cli
      @commitlint/config-conventional`, `lefthook install`). These you *may* run — they're not
      commits. Surface anything else (CI secrets, GitLab approval toggles) as a reminder. Before
      calling a follow-up blocked on private-registry credentials, check the tokens already in the
      environment (e.g. `UV_INDEX_<NAME>_PASSWORD="$GITLAB_TOKEN" uv lock`; `glab auth status`
      shows where glab's token comes from).
   2. **Stop and wait for the user to commit** the tooling-sync changes whenever `tooling-sync`
      modified the working tree (`git status --short` differs from `baseline`). Show
      `git status --short` and suggest a commit subject (`chore: sync repo tooling with mw-kit`).
      This includes `.tooling-sync.json` (the incremental-sync memory tooling-sync writes), a
      normal committed file *unless the user's global gitignore excludes it*; then it stays
      local-only and won't appear here, which is fine: it still drives the next sync on this
      machine. Do **not** spawn the rows 2–6 review wave until the user has committed Gate A's
      changes. Once the user says it's committed, run `git status --short` and
      `git show --stat HEAD` to confirm the tree matches `baseline` and every follow-up from
      step 1 (e.g. a regenerated lockfile) is in the commit. If one isn't, add it now and wait for
      the user to amend or commit it before continuing.
   3. **Offer a compaction beat.** If context is already heavy, tell the user they can `/compact`
      before continuing: the playbook page reads are dead weight from here, and the next phases
      load their own instructions on invocation. Their call, not a gate.

   Only continue to the review wave once the tree matches `baseline`. If tooling-sync produced no
   changes, there's nothing to commit, so proceed immediately.
2. `triage-renovate-dependabot-prs`: load skill `triage-renovate-dependabot-prs` and follow
   it in row 7's mode (`lean`, `default`, or `full`). It owns discovery, the per-branch risk read, the per-merge confirmation gate, post-merge
   checks, and the never-push rule. Don't second-guess its prompts: let it drive. When
   triage offers fix / revert / accept after a failed check, recommend **fix in place**. Revert
   or accept only on the user's explicit choice.
3. Close: print the completion block below, then mark `Close: completion summary` done. Then run
   Retro.

   ```
   ## Wrap-up complete
   - Ran: <row: skill — one-line outcome>, …
   - Skipped: <row: skill — reason>, …   (omit line if none)
   - Blocked: <row: skill — the gate that stopped it>, …   (omit line if none)
   - Fixes: <N fixed, M skipped/declined> (Gate F)
   - Tree: clean | <N uncommitted files — commit before pushing>
   - Next: push is yours (`git push`), then open the MR/PR.
   ```

## Hard rules

- **Never push.** The user commits Gate A and Gate F changes. During dependency triage, a
  merge commit is allowed only when the user's current message explicitly authorizes that merge.
- **Stop and fix is always the default:** fix any problem a phase surfaces before the next phase.
- **Stop for a commit after every phase that changes files.** Gate A and every Gate F row that
  modifies the working tree must stop, show `git status --short` + a suggested commit message,
  and wait for the user to commit before the next phase starts.
- **Never dump multiple review reports or cross-phase decisions in one turn.** Present and resolve
  rows 2–6 one report at a time in row order.
- **Don't duplicate the underlying skills.** If `pr-review-toolkit`, `ponytail-review`,
  `test-audit`, `docs-audit`, `interface-review`, `tooling-sync` or `triage-renovate-dependabot-prs`
  behavior needs changing, edit that skill — not this wrapper.
- **Every skill can still run alone.** This is only the convenience path; it adds no
  review/sync/merge logic the seven don't already have. Its own behavior is limited to ordering,
  gates (including Gate F's fixes), and hand-offs.
- **Pre-flight makes no writes outside `.git/`.** The script writes only
  `.git/wrap-up/run/` (pre-flight facts, the plan, findings files) and the memo
  (`.git/wrap-up/<branch>`, after row 2). All of it is local git metadata, not a commit. The only
  `~/.cache/mw-kit` clone or pull happens inside tooling-sync, when row 1 is picked. The
  `.tooling-sync.json` write happens only inside tooling-sync.
- **Subagents are read-only,** except their findings file under `.git/wrap-up/run/`. Only rows 2–6
  are ever delegated; tooling-sync and triage always run inline because they prompt and write.

## Retro

After the run, propose an edit to this skill only on real signal: a case these steps didn't cover,
a user correction or repeated instruction, a wrong or stale step, or a manual workaround you
repeated. Name the section, show before/after lines, give one sentence of why, and apply only after
a yes, in the skills repo source (`skills/wrap-up/SKILL.md`), never the installed copy. If
nothing fired, say nothing.

This Retro also covers the delegated reviews (rows 2–6), whose subagents can't propose edits: a
review that ignored the pinned range, broke its report format or missed the scope is raised here.
tooling-sync and triage run their own Retros inline; don't repeat what those raised.

A pre-flight verdict that was wrong (RUN on a skill that found nothing useful, or SKIP on one the
user ran anyway and it mattered) is a signal to adjust that row's threshold. A tier that was wrong
(a `fast` review missed something a `strong` re-run caught) is a signal to move that row's default
tier up. If the change belongs in `pr-review-toolkit`, `ponytail-review`, `test-audit`,
`docs-audit`, `interface-review`, `tooling-sync` or `triage-renovate-dependabot-prs`, point there instead.
