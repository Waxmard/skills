---
name: wrap-up
description: >
  End-of-branch pre-flight. Always runs pr-review-toolkit; cheaply
  checks which of tooling-sync, ponytail-review, web-design-guidelines,
  interface-review, and triage-renovate-dependabot-prs are worth running, reports a RUN/SKIP
  verdict, run order, and model tier (fast/strong) for each, lets
  the user pick, then runs read-only reviews as parallel tier-pinned
  subagents (pr-review-toolkit reviews only commits since the last wrap-up review on re-runs;
  `full` forces the whole branch), fixes their findings in-session one report at a time with a commit gate after
  each, runs interactive skills inline with commit gates, and ends with a completion
  summary. Orchestrator: its only logic is ordering, gates (including Gate F's
  fixes), and hand-offs. Trigger: "wrap up this
  branch", "I'm done with this branch", "end of branch", "pre-merge
  checklist", "what should I run before merging", "sync tooling and triage
  renovate", "repo spa day", or /wrap-up. Optional `lean` reply keyword
  (suggested when other maintainers are detected) limits the run to definite
  improvements.
---

Orchestrates the end-of-branch reviews and hand-offs. It owns only the pre-flight signals, the
order, the model tiers, the gates and the hand-offs; all real logic stays in the underlying skills.

Invocation: invoking wrap-up runs pre-flight → report → pick → run. Invoking wrap-up with `run <reply>`
(e.g. `run go`, `run 3 6`, `run 2@fast`) re-runs pre-flight silently, skips the report and the
pick, and goes straight to §3 with `<reply>` parsed as in §2. The trigger is the skill args or the
first user message starting with `run `. Use it to run pre-flight on a cheap model, then start a
new session on a stronger model and paste the `run` line.

## Harness notes

Steps below use neutral verbs. Map them to your harness:

| Step says | omp | Claude Code | Other agents |
|---|---|---|---|
| invoke with args | `/skill:wrap-up run go` | `/wrap-up run go` | first message `run go` |
| load skill `<name>` | `read skill://<name>` | Skill tool | read that skill's `SKILL.md` |
| spawn the wave | one Task call, `model: "@smol"` (fast) or `"@slow"` (strong) | Agent tool calls in one message, `model: haiku` (fast) or `opus` (strong) | no subagents: run rows 2–5 inline in order, note "ran inline: no subagents" |
| retrieve a report verbatim | `read agent://<id>:raw` (the `wait` snapshot and plain `read agent://<id>` truncate; `/report:raw` returns null for unstructured reports) | the Agent tool result | n/a |
| progress list | `todo` `init` | TodoWrite | numbered checklist printed in chat |
| ask the user | `ask` tool | AskUserQuestion | plain-text question |

## 1. Pre-flight

Read-only: no edits, no installs. Runs before any skill.

1. `git rev-parse --git-dir`. If it fails, stop: "not a git repo".
2. `branch=$(git rev-parse --abbrev-ref HEAD)`. If it matches
   `main|master|dev|develop|release/*|staging`, put a note at the top of the report: "on
   protected branch `<branch>`: reviewing unpushed commits; gate commits will land here".
   Not a blocker.
3. Resolve the base:
   ```bash
   git fetch origin --prune
   base=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)
   git rev-parse --verify -q "$base" >/dev/null || base=origin/master
   mb=$(git merge-base HEAD "$base")
   head0=$(git rev-parse HEAD)
   memo="$(git rev-parse --git-path wrap-up)/$branch"
   last=$(cat "$memo" 2>/dev/null)
   from=$mb; mode=full
   if [ -n "$last" ] && git merge-base --is-ancestor "$mb" "$last" 2>/dev/null \
      && git merge-base --is-ancestor "$last" "$head0" 2>/dev/null; then
     from=$last; mode=delta
   fi
   ```
   `delta` means the last wrap-up review on this branch is still an ancestor of HEAD, so only
   `<from>..<head0>` is new. A rebase, force-push, reset or missing memo falls back to `full`
   (`from=mb`). Only row 2 uses `from`; rows 3–5 always review `<mb>..<head0>`, because their
   verdicts and coverage need the whole branch. The memo lives under `.git/` (per worktree via
   `--git-path`), so it's never committed and never shows in `git status`.
4. Collect the facts:
   - Changed files: `git diff --name-only "$mb"..."$head0"` (rows 3–5). For row 2 in delta mode,
     also collect them over `"$from"..."$head0"`.
   - Added lines without lockfiles, over the same ranges: sum column 1 of
     `git diff --numstat "$mb"..."$head0" -- . ':!*.lock' ':!package-lock.json' ':!pnpm-lock.yaml' ':!yarn.lock' ':!uv.lock' ':!poetry.lock' ':!Cargo.lock' ':!go.sum' ':!Gemfile.lock'`.
   - Uncommitted files: `baseline=$(git status --short)`. If non-empty, put a note at the top of
     the report: "N uncommitted files: reviews below cover committed work only". Not a blocker.
   - Other maintainers (skip if `git config user.email` is empty; no suggestion then):
     ```bash
     me=$(git config user.email); name=$(git config user.name)
     git log --format=%ae -n 200 "$base" | sort -u | grep -vixF "$me" | grep -viF "+$name@users.noreply" \
     | grep -viE '\[bot\]|renovate|dependabot' | wc -l
     ```
     If the count is ≥ 1, set `others=N`.
5. `MW_KIT` stop (row 1 only). If `$MW_KIT` is empty, stop and ask: "`MW_KIT` isn't set, so
   tooling-sync would clone or pull Waxmard/mw-kit into `~/.cache/mw-kit`. Reply `cache` to use
   that, a path to use your own playbook, or `skip` to drop tooling-sync. Export `MW_KIT` in your
   shell profile to skip this question next time." The answer only decides row 1, and every
   other row is evaluated as normal. `cache`: run the resolver as is. A path: prefix the resolver
   with `MW_KIT=<path>`, and pass the same value to tooling-sync in §3. `skip`: row 1 verdict
   `skip`, reason "MW_KIT not set". In `run <reply>` mode, ask only if `<reply>` is `go` or
   includes row 1.
6. Verdict per skill. Row number = run order. Tier = subagent model class (Harness notes).

| # | Skill | RUN when | Tier | Reason text |
|---|---|---|---|---|
| 1 | `tooling-sync` | `tooling-sync`'s Step 1 resolver block (same `MW_KIT` resolution, read-only) has `preflight.ok` true and `state.all_settled` not true | `inline · fast+` | "L live tools" (`in_scope` rows with `state.settled == false`), plus ", O orphaned" if `state.orphaned_tools` is non-empty. SKIP: "nothing new since last sync (`state.last_sync`)". If `preflight.ok` is false: SKIP with `preflight.error` |
| 2 | `pr-review-toolkit` | always (not pickable) | `fast` | Full: "N files, +A lines vs `<base>`". Delta: "delta: N files, +A lines since last review `<from short>`". If the changed-files list is empty: verdict `skip`, reason "no commits ahead of `<base>`" (full) or "no new commits since last review `<from short>`; reply `full` to re-review" (delta) — the only case it doesn't run |
| 3 | `ponytail-review` | added lines ≥ 100 **or** a changed file's basename is one of `package.json pyproject.toml Cargo.toml go.mod Gemfile` or matches `requirements*.txt` | `fast` | "+A lines" and/or "deps changed: `<files>`". SKIP: "small diff (+A), no manifest changes" |
| 4 | `web-design-guidelines` | changed files matching `\.(tsx\|jsx\|vue\|svelte\|css\|scss\|html)$` non-empty | `fast` | "N UI files changed". SKIP: "no UI files in diff" |
| 5 | `interface-review` | changed files matching `\.(tsx\|jsx\|vue\|svelte\|css\|scss\|html)$` non-empty | `fast` | "N UI files changed". SKIP: "no UI files in diff" |
| 6 | `triage-renovate-dependabot-prs` | unmerged bot branches > 0 (loop below) and branch not protected (step 2) | `inline · fast+` | "N unmerged bot branches". SKIP: "no unmerged renovate/dependabot branches", or "protected branch: triage refuses on `<branch>`" |

If a listed skill is not available to this session, its verdict is SKIP with reason "not installed". For `ponytail-review`, append " — omp: `/marketplace add DietrichGebert/ponytail` then `/marketplace install ponytail@ponytail`; Claude Code: `/plugin marketplace add DietrichGebert/ponytail` then `/plugin install ponytail@ponytail`". `interface-review` is exempt: it is intentionally absent from the model-invocable skills (see its dispatch note below).

Tier rationale: defaults favour speed and cost. `fast` for every review row. Nothing defaults to
`strong`: escalate per run with `2@strong` on a large or risky diff (auth, payments, data
migrations). Triage is safe on `fast` because its per-merge confirmation gate keeps the user as
the backstop.

Bot-branch count. Use `while read`, never `for` word-splitting:

```bash
git ls-remote --heads origin 'renovate/*' 'dependabot/*' | awk '{print $2}' | sed 's|^refs/heads/||' \
| while read -r b; do git merge-base --is-ancestor "origin/$b" HEAD || echo "$b"; done | wc -l
```

The redundancy analysis stays in the triage skill. Don't repeat it here.

## 2. Report and pick

Print the table as `# | Skill | Verdict | Tier | Why`, rows in run order, verdicts `RUN`,
`skip`, or `always` (row 2). Under it print:

- Legend: "`fast`/`strong` = runs as a subagent on that model class (Harness notes). `inline` = runs
  in this session because it prompts you; the tier is the recommended strength for this
  session."
- Parallelism: "Row 1 runs first, inline. Rows 2–5 then run in parallel (read-only, pinned to
  `<head0 short>`: row 2 from `<from short>`, rows 3–5 from `<mb short>`; they may start while
  Gate A's commit is pending). Row 6 runs last, inline." Gate F then fixes the review findings
  before row 6 runs.
- Always: "Pre-flight is cheap. To run the picks on a stronger model, start a new session there
  and invoke wrap-up with `run <your reply>`."
- Only when `others ≥ 1`: "Lean suggested: N other authors on `<base>`. Add `lean` to your reply
  to limit changes to definite improvements. Your choice; it's off unless you type it."
  When it prints and row 1 or 6 is RUN, append " (lean: pick by number to include)" to that row's
  Why.

Then ask in plain text: "Reply `go` to run the RUN rows, numbers to choose from 1 and 3–6 (e.g. `3 6`),
or `none` for only the review. Override a tier with `N@fast|strong` (rows 2–5). Add `lean` to
any reply (e.g. `go lean`) for minimal-change mode." Only when `mode=delta`, append: "Add `full`
to re-review the whole branch instead of the delta."

Parse the reply:
- Row 2 is always included (unless its verdict is `skip`, or this is `run <reply>` mode, `<reply>`
  names only rows 1/6, and a row-2 wave already ran in this session). `none` = row 2 only. `go` =
  row 2 + RUN rows. Numbers = row 2 + those rows. A chosen `skip` row runs anyway.
- `N@tier` on rows 2–5 replaces that row's tier. On rows 1 and 6 it's ignored; say "rows 1 and 6
  run inline; switch the session's model instead".
- Picked rows always run in ascending row number.
- `lean` (any position, any reply, including `run <reply>` mode) turns lean mode on. It's off by
  default, with no auto-enable. In lean mode, `go` = row 2 + RUN rows **excluding rows 1 and 6**.
  Rows 1 and 6 still run when picked by number. `none` is unchanged.
- `full` (any position, any reply, including `run <reply>` mode) sets `from=mb`, `mode=full` for
  row 2. Rows 3–5 already review the whole branch. `full` also makes row 2 run when its delta
  verdict was `skip`.

Wait for the reply. In `run <reply>` mode, skip printing and waiting and parse `<reply>` directly.

## 3. Run

**Progress tracking.** Right after the reply is parsed (or immediately in `run <reply>` mode),
create the progress list (Harness notes) with one item per phase, in run order:
- one item per picked row: `Row <N>: <skill>` (e.g. `Row 1: tooling-sync`);
- right after the last review row, the item `Fix review findings`;
- last item: `Close: completion summary`.

Mark each item done as soon as its phase finishes, including rows that report nothing to do.
Print the completion block (inline step 3) only when every item except
`Close: completion summary` is done.

Why this order: tooling-sync first, so its new hooks and CI gates (lefthook, biome, commitlint)
also check the review-fix commits and every triage merge. Reviews next, pinned to `<head0>`, so
neither tooling commits nor triage merges enter the reviewed diff. Triage last, because it stacks
merges on whatever the earlier rows committed.

Walk the picked rows in order. The delegated rows (2–5) form one **wave**: spawn them in one
batch as parallel subagents, each on its tier's model (Harness notes; default tier from the
table, or the user's override). Inline rows (1, 6) run in this session by loading skill `<name>`
and following it.

**Lean mode** (only when the reply had `lean`):
- Append to each delegated row's task text: "Lean mode: report only definite improvements (bugs,
  correctness, security, regressions, clear contract violations). Omit style nits, refactors,
  naming, and speculative or optional suggestions. If nothing qualifies, say so."
- Gate F uses the lean bar: definite improvements only. Every fix in this session follows the
  same bar: the smallest change that fixes the finding, with no adjacent cleanup.
- Explicitly picked rows 1 and 6 run unchanged. Lean doesn't filter tooling-sync or triage
  internals; picking them by number means the user wants them.

Subagent task text (fill in literals; subagents don't share this conversation):
> Load the `<name>` skill and follow it as a read-only review in repo `<toplevel>`. Review exactly
> `git diff <start>..<head0>` (base `<base>`). <row 2 in delta mode only: These are the commits
> since the last review. For context only, the full branch diff is `git diff <mb>...<head0>`;
> report findings only on lines changed in the first range, unless a change there breaks code
> elsewhere in the full range.> <web-design-guidelines only: Files: `<UI file list>`.> Make no
> edits and no git writes (no checkout/switch/stash; read via git diff/show only). Return the
> skill's report format verbatim.

`<start>` is `<from>` for row 2 and `<mb>` for rows 3–5.

- `pr-review-toolkit`: its own "Local Branch" diff source, overridden by the pinned range above.
- `ponytail-review`: bare name `ponytail-review`.
- `web-design-guidelines`: always pass the UI file list from `<mb>...<head0>`. It asks the user
  when no files are given, and a subagent can't ask.
- `interface-review`: has `disable-model-invocation: true`, so it isn't model-invocable. Replace the
  first sentence with "Read the `interface-review` `SKILL.md` (Claude Code:
  `~/.claude/skills/interface-review/SKILL.md`; otherwise the harness's skills dir) and follow it
  with target `<mb>...<head0>`; resolve its relative file references against that directory." The
  user chose to delegate it; the opt-out only stops the model picking it unprompted.

When the wave finishes, print each report under a `### <skill> (<tier>)` heading in row order.
Retrieve each report verbatim, never a truncated preview (Harness notes). If subagents or the
tier's model are unavailable, run that row inline in this session and note "ran inline: <reason>".

Once row 2 has returned a report (delegated or ran inline), record the reviewed head with
literals filled in, since bash calls may not share a shell:
`memo="$(git rev-parse --git-path wrap-up)/<branch>" && mkdir -p "$(dirname "$memo")" && printf '%s\n' <head0> > "$memo"`.
Write it before Gate F, so Gate F's fix commits land in row 2's next delta and get reviewed
then. Rows 1 and 3–6 never touch the memo.

**Gate F — fix findings (always, after the wave; never optional).** Runs after the wave's
reports have printed, whether or not an inline row follows. Do not ask "fix or continue":
stopping to fix is the default for all of wrap-up.

1. Build the fix list from every report in the wave:
   - Include every Critical and Important item, plus every Suggestion that has a
     concrete *Fix* line. In non-pr-review-toolkit reports (ponytail-review,
     web-design-guidelines, interface-review), include every actionable finding.
   - Exclude **pure nits**: items the report labels nit/optional/taste that cite
     no project rule (AGENTS.md or harness rules-file convention, lint config). A style item
     backed by a project rule is not a nit, so it gets fixed.
   - Merge overlapping items: the same `file:line`, or the same root cause in the same file or
     symbol even when the lines or wording differ. Keep one item under the first report in row
     order, and note the other reports in its finding text (e.g. `(also: ponytail-review)`).
2. Findings that need a user decision (two valid fixes with different shapes, a behavior change,
   a disputed finding, or two reports asking for opposite changes to the same code) go to the
   user in one batched question (Harness notes: ask the user) before any edit. Never skip them silently.
3. Work through the reports in row order, one at a time. For each report with items left:
   1. Re-read each of this report's items against the current tree. If an earlier report's fix
      already resolved the item, or deleted or rewrote the code it targets, don't fix it. Mark it
      `skipped: resolved by <skill> fix` or `skipped: moot after <skill> fix`.
   2. Apply its fixes in this session, using the smallest change that resolves each finding. Then
      run the repo's narrowest check that covers the touched files (from its AGENTS.md/Makefile/
      package.json). If a check fails, fix that too before moving on.
   3. Print a fix table under `### Gate F: <skill>`, as `Finding | File | Status`, where status is
      `fixed`, `skipped: <reason>`, or `user-declined`. The only allowed skip reasons are a
      verified false positive (state the evidence), the user declining, or resolved/moot after
      an earlier report's fix (name that report).
   4. If anything changed, show `git status --short` and suggest a subject (e.g. `fix: address
      <skill> findings`). Then stop and wait for the user to commit. Move to the next report only
      when `git status --short` matches the pre-flight `baseline`. If nothing changed, say so and
      go straight to the next report.
4. If the list is empty after the exclusions, print "Gate F: no findings to fix" and continue
   without stopping.

Inline rows:

1. `tooling-sync`: load skill `tooling-sync` and follow it, then Gate A.

   **Gate A — commit the tooling-sync changes**

   1. **Run any follow-up installs** tooling-sync flagged (e.g. `npm i -D @commitlint/cli
      @commitlint/config-conventional`, `lefthook install`). These you *may* run — they're not
      commits. Surface anything else (CI secrets, GitLab approval toggles) as a reminder. Before
      calling a follow-up blocked on private-registry credentials, check the tokens already in the
      environment (e.g. `UV_INDEX_<NAME>_PASSWORD="$GITLAB_TOKEN" uv lock`; `glab auth status`
      shows where glab's token comes from).
   2. **Stop and wait for the user to commit** the tooling-sync changes. Show `git status --short`
      so they see exactly what to commit — this includes `.tooling-sync.json` (the incremental-sync
      memory tooling-sync writes), a normal committed file *unless the user's global gitignore
      excludes it* — then it stays local-only and won't appear here, which is fine: it still drives
      the next sync on this machine. triage's `git merge --no-ff` needs a clean tree, so an
      uncommitted tooling-sync tree would foul the merges. Once the user says it's committed, run
      `git show --stat HEAD` and confirm every follow-up from step 1 (e.g. a regenerated lockfile)
      is in the commit. If one isn't, add it now and wait for the user to amend or commit it
      before running triage.
   3. **Rows 2–5 don't wait for this commit.** They are read-only and pinned to `head0`, so
      neither the tooling commit nor triage's merges enter the reviewed diff — spawn the wave
      while the user commits, then run Gate F. The user may fold the tooling changes and Gate F's
      fixes into one commit; either way the tree must be clean before triage.
   4. **Offer a compaction beat.** If context is already heavy, tell the user they can `/compact`
      before continuing — the playbook page reads are dead weight from here, and triage reloads its
      own instructions on invocation. Their call, not a gate.

   Only continue once the tree is clean. If tooling-sync produced no changes, there's nothing to
   commit, so proceed.
2. `triage-renovate-dependabot-prs`: load skill `triage-renovate-dependabot-prs` and follow
   it. It owns discovery, the per-branch risk read, the per-merge confirmation gate, post-merge
   checks, and the never-push rule. Don't second-guess its prompts: let it drive. When
   triage offers fix / revert / accept after a failed check, recommend **fix in place**. Revert
   or accept only on the user's explicit choice.
3. Close: print the completion block below, then mark `Close: completion summary` done. Then run
   Retro.

   ```
   ## Wrap-up complete
   - Ran: <row: skill — one-line outcome>, …
   - Skipped: <row: skill — reason>, …   (omit line if none)
   - Fixes: <N fixed, M skipped/declined> (Gate F)
   - Tree: clean | <N uncommitted files — commit before pushing>
   - Next: push is yours (`git push`), then open the MR/PR.
   ```

## Hard rules

- **Never commit, never push** — every commit between skills and the final push are the *user's*.
  This skill triggers none of them.
- **Stop and fix is always the default:** fix any problem a phase surfaces before the next phase.
- **Don't skip Gate A** when tooling-sync runs before triage. Running triage against an
  uncommitted tooling-sync tree fouls the merges.
- **Don't duplicate the underlying skills.** If `pr-review-toolkit`, `ponytail-review`,
  `web-design-guidelines`, `interface-review`, `tooling-sync` or `triage-renovate-dependabot-prs`
  behavior needs changing, edit that skill — not this wrapper.
- **Every skill can still run alone.** This is only the convenience path; it adds no
  review/sync/merge logic the six don't already have. Its own behavior is limited to ordering,
  gates (including Gate F's fixes), and hand-offs.
- **Pre-flight is read-only.** `scope.py` writes nothing. The only write is the `~/.cache/mw-kit`
  clone or pull, after the user replies `cache` at the `MW_KIT` stop. The `.tooling-sync.json`
  write happens only inside tooling-sync. The memo write in §3 (`.git/wrap-up/<branch>`, after
  row 2) is the only other write this skill makes; it is local git metadata, not a commit.
- **Subagents are read-only.** Only rows 2–5 are ever delegated; tooling-sync and triage always
  run inline because they prompt and write.

## Retro

After the run, propose an edit to this skill only on real signal: a case these steps didn't cover,
a user correction or repeated instruction, a wrong or stale step, or a manual workaround you
repeated. Name the section, show before/after lines, give one sentence of why, and apply only after
a yes, in the Waxmard/skills source (`skills/wrap-up/SKILL.md`), never the installed copy. If
nothing fired, say nothing.

This Retro also covers the delegated reviews (rows 2–5), whose subagents can't propose edits: a
review that ignored the pinned range, broke its report format or missed the scope is raised here.
tooling-sync and triage run their own Retros inline; don't repeat what those raised.

A pre-flight verdict that was wrong (RUN on a skill that found nothing useful, or SKIP on one the
user ran anyway and it mattered) is a signal to adjust that row's threshold. A tier that was wrong
(a `fast` review missed something a `strong` re-run caught) is a signal to move that row's default
tier up. If the change belongs in `pr-review-toolkit`, `ponytail-review`, `web-design-guidelines`,
`interface-review`, `tooling-sync` or `triage-renovate-dependabot-prs`, point there instead.
