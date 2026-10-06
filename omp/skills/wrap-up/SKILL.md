---
name: wrap-up
description: >
  End-of-branch pre-flight for omp. Always runs pr-review-toolkit; cheaply
  checks which of tooling-sync, ponytail-review, web-design-guidelines,
  interface-review, and triage-renovate-dependabot-prs are worth running, reports a RUN/SKIP
  verdict, run order, and model tier (slow/smol/grunt) for each, lets
  the user pick, then runs read-only reviews as parallel tier-pinned
  subagents, fixes their findings in-session one report at a time with a commit gate after
  each, runs interactive skills inline with commit gates, and ends with a completion
  summary. Orchestrator: its only logic is ordering, gates (including Gate F's
  fixes), and hand-offs. Trigger: "wrap up this
  branch", "I'm done with this branch", "end of branch", "pre-merge
  checklist", "what should I run before merging", "sync tooling and triage
  renovate", "repo spa day", or /skill:wrap-up. Optional `lean` reply keyword
  (suggested when other maintainers are detected) limits the run to definite
  improvements.
---

Thin orchestrator. Owns only the pre-flight signals, the order, the model tiers, the gates and
the hand-offs. All real logic stays in the underlying skills.

Invocation: `/skill:wrap-up` runs pre-flight → report → pick → run. `/skill:wrap-up run <reply>`
(e.g. `run go`, `run 3 6`, `run 2@smol`) re-runs pre-flight silently, skips the report and the
pick, and goes straight to §3 with `<reply>` parsed as in §2. The trigger is the skill args or the
first user message starting with `run `. Use it to run pre-flight in a cheap mode, then start a
new session in a stronger mode and paste the `run` line.

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
   ```
4. Collect the facts:
   - Changed files: `git diff --name-only "$mb"..."$head0"`.
   - Added lines without lockfiles: sum column 1 of
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
6. Verdict per skill. Row number = run order. Tier = model role.

| # | Skill | RUN when | Tier | Reason text |
|---|---|---|---|---|
| 1 | `tooling-sync` | `tooling-sync`'s Step 1 resolver block (same `MW_KIT` resolution, read-only) has `preflight.ok` true and `state.all_settled` not true | `inline · smol+` | "L live tools" (`in_scope` rows with `state.settled == false`), plus ", O orphaned" if `state.orphaned_tools` is non-empty. SKIP: "nothing new since last sync (`state.last_sync`)". If `preflight.ok` is false: SKIP with `preflight.error` |
| 2 | `pr-review-toolkit` | always (not pickable) | `@smol` | "N files, +A lines vs `<base>`". If the changed-files list is empty: verdict `skip`, reason "no commits ahead of `<base>`" — the only case it doesn't run |
| 3 | `ponytail-review` | added lines ≥ 100 **or** a changed file's basename is one of `package.json pyproject.toml Cargo.toml go.mod Gemfile` or matches `requirements*.txt` | `@smol` | "+A lines" and/or "deps changed: `<files>`". SKIP: "small diff (+A), no manifest changes" |
| 4 | `web-design-guidelines` | changed files matching `\.(tsx\|jsx\|vue\|svelte\|css\|scss\|html)$` non-empty | `@grunt` | "N UI files changed". SKIP: "no UI files in diff" |
| 5 | `interface-review` | changed files matching `\.(tsx\|jsx\|vue\|svelte\|css\|scss\|html)$` non-empty | `@smol` | "N UI files changed". SKIP: "no UI files in diff" |
| 6 | `triage-renovate-dependabot-prs` | unmerged bot branches > 0 (loop below) and branch not protected (step 2) | `inline · smol+` | "N unmerged bot branches". SKIP: "no unmerged renovate/dependabot branches", or "protected branch: triage refuses on `<branch>`" |

If a listed skill is not in `skill://`, its verdict is SKIP with reason "not installed". For `ponytail-review`, append " — `/marketplace add DietrichGebert/ponytail` then `/marketplace install ponytail@ponytail`". `interface-review` is exempt: it is intentionally absent from `skill://` (see its dispatch note below).

Tier rationale: defaults favour speed and cost. `@smol` for every judgment row, `@grunt` for
checklist matching against fetched rules (web-design-guidelines). Nothing defaults to `@slow`:
escalate per run with `2@slow` on a large or risky diff (auth, payments, data migrations). Triage
is safe on smol because its per-merge confirmation gate keeps the user as the backstop.

Bot-branch count. Use `while read`, never `for` word-splitting:

```bash
git ls-remote --heads origin 'renovate/*' 'dependabot/*' | awk '{print $2}' | sed 's|^refs/heads/||' \
| while read -r b; do git merge-base --is-ancestor "origin/$b" HEAD || echo "$b"; done | wc -l
```

The redundancy analysis stays in the triage skill. Don't repeat it here.

## 2. Report and pick

Print the table as `# | Skill | Verdict | Tier | Why`, rows in run order, verdicts `RUN`,
`skip`, or `always` (row 2). Under it print:

- Legend: "`@tier` = runs as a subagent pinned to that role of the active mode. `inline` = runs
  in this session because it prompts you; the tier is the recommended strength for this
  session."
- Parallelism: "Row 1 runs first, inline. Rows 2–5 then run in parallel (read-only, pinned to
  `<base>`..`<head0 short>`; they may start while Gate A's commit is pending). Row 6 runs last,
  inline." Gate F then fixes the review findings before row 6 runs.
- Always: "Pre-flight is cheap. To run the picks on a stronger mode, start a new session there
  and send `/skill:wrap-up run <your reply>`."
- Only when `others ≥ 1`: "Lean suggested: N other authors on `<base>`. Add `lean` to your reply
  to limit changes to definite improvements. Your choice; it's off unless you type it."
  When it prints and row 1 or 6 is RUN, append " (lean: pick by number to include)" to that row's
  Why.

Then ask in plain text: "Reply `go` to run the RUN rows, numbers to choose from 1 and 3–6 (e.g. `3 6`),
or `none` for only the review. Override a tier with `N@slow|smol|grunt` (rows 2–5). Add `lean` to
any reply (e.g. `go lean`) for minimal-change mode."

Parse the reply:
- Row 2 is always included (unless its verdict is `skip`, or this is `run <reply>` mode, `<reply>`
  names only rows 1/6, and a row-2 wave already ran in this session). `none` = row 2 only. `go` =
  row 2 + RUN rows. Numbers = row 2 + those rows. A chosen `skip` row runs anyway.
- `N@tier` on rows 2–5 replaces that row's tier. On rows 1 and 6 it's ignored; say "rows 1 and 6
  run inline; switch the session mode instead".
- Picked rows always run in ascending row number.
- `lean` (any position, any reply, including `run <reply>` mode) turns lean mode on. It's off by
  default, with no auto-enable. In lean mode, `go` = row 2 + RUN rows **excluding rows 1 and 6**.
  Rows 1 and 6 still run when picked by number. `none` is unchanged.

Wait for the reply. In `run <reply>` mode, skip printing and waiting and parse `<reply>` directly.

## 3. Run

**Progress tracking.** Right after the reply is parsed (or immediately in `run <reply>` mode),
call `todo` `init` with one item per phase, in run order:
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

Walk the picked rows in order. The delegated rows (2–5) form one **wave**: spawn them in a single
Task call as parallel subagents, each with `model: "@<tier>"` (default tier from the table, or
the user's override). Inline rows (1, 6) run in this session by reading `skill://<name>` and
following it.

**Lean mode** (only when the reply had `lean`):
- Append to each delegated row's task text: "Lean mode: report only definite improvements (bugs,
  correctness, security, regressions, clear contract violations). Omit style nits, refactors,
  naming, and speculative or optional suggestions. If nothing qualifies, say so."
- Gate F uses the lean bar: definite improvements only. Every fix in this session follows the
  same bar: the smallest change that fixes the finding, with no adjacent cleanup.
- Explicitly picked rows 1 and 6 run unchanged. Lean doesn't filter tooling-sync or triage
  internals; picking them by number means the user wants them.

Subagent task text (fill in literals; subagents don't share this conversation):
> Read `skill://<name>` and follow it as a read-only review in repo `<toplevel>`. Review exactly
> `git diff <mb>...<head0>` (base `<base>`). <web-design-guidelines only: Files: `<UI file
> list>`.> Make no edits and no git writes (no checkout/switch/stash; read via git diff/show
> only). Return the skill's report format verbatim.

- `pr-review-toolkit`: its own "Local Branch" diff source, overridden by the pinned range above.
- `ponytail-review`: bare name `ponytail-review`.
- `web-design-guidelines`: always pass the pre-flight UI file list. It asks the user when no files
  are given, and a subagent can't ask.
- `interface-review`: has `disable-model-invocation: true`, so it isn't in `skill://`. Replace the
  first sentence with "Read `~/.claude/skills/interface-review/SKILL.md` and follow it with
  target `<mb>...<head0>`; resolve its relative file references against that directory." The
  user chose to delegate it; the opt-out only stops the model picking it unprompted.

When the wave finishes, print each report under a `### <skill> (@tier)` heading in row order.
Retrieve each report verbatim with `read agent://<id>:raw` (`/report:raw` returns null for
unstructured reports) — the `wait` snapshot truncates each report to a preview, and a plain
`read agent://<id>` truncates every long line. If
the Task tool or a model role fails to resolve, run that row inline in this session and note
"ran inline: <reason>".

**Gate F — fix findings (always, after the wave; never optional).** Runs after the wave's
reports have printed, whether or not an inline row follows. Do not ask "fix or continue":
stopping to fix is the default for all of wrap-up.

1. Build the fix list from every report in the wave:
   - Include every 🔴 Critical and 🟡 Important item, plus every 🔵 Suggestion that has a
     concrete *Fix* line. In non-pr-review-toolkit reports (ponytail-review,
     web-design-guidelines, interface-review), include every actionable finding.
   - Exclude 🟢 strengths and **pure nits**: items the report labels nit/optional/taste that cite
     no project rule (AGENTS.md/CLAUDE.md convention, lint config). A style item backed by a
     project rule is not a nit, so it gets fixed.
   - Merge overlapping items: the same `file:line`, or the same root cause in the same file or
     symbol even when the lines or wording differ. Keep one item under the first report in row
     order, and note the other reports in its finding text (e.g. `(also: ponytail-review)`).
2. Findings that need a user decision (two valid fixes with different shapes, a behavior change,
   a disputed finding, or two reports asking for opposite changes to the same code) go to the
   user in one batched `ask` before any edit. Never skip them silently.
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

1. `tooling-sync`: read `skill://tooling-sync` and follow it, then Gate A.

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
   commit — just proceed.
2. `triage-renovate-dependabot-prs`: read `skill://triage-renovate-dependabot-prs` and follow
   it. It owns discovery, the per-branch risk read, the per-merge confirmation gate, post-merge
   checks, and the never-push rule. Don't second-guess its prompts — just let it drive. When
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
  write happens only inside tooling-sync.
- **Subagents are read-only.** Only rows 2–5 are ever delegated; tooling-sync and triage always
  run inline because they prompt and write.

## Retro — improve this skill

This skill is **two-way**: after the run, spend one beat on whether the run exposed something the
skill itself should encode. Most clean runs need no change — don't force it.

Scope: this Retro also covers the delegated reviews (rows 2–5). Their subagents can't propose
edits, so a review that ignored the pinned range, broke its report format or missed the scope is
raised here. tooling-sync and triage run their own Retros inline; don't repeat what those raised.

Propose an edit only on real signal:

- A case these instructions didn't cover and you had to improvise (e.g. the gate needed a step
  not listed — stash, submodule sync, a follow-up install tooling-sync flagged that wasn't
  runnable).
- The user corrected the ordering or hand-off, or repeated an instruction.
- A step here was wrong, stale, or contradicted what you found (e.g. triage's protected-branch
  list changed, or a gate precondition no longer holds).
- You repeated a manual workaround that belongs in the flow.
- A pre-flight verdict was wrong (RUN on a skill that found nothing useful, or SKIP on one the
  user ran anyway and it mattered). Propose adjusting that row's threshold.
- A tier was wrong (a `@grunt`/`@smol` review missed something a `@slow` re-run caught). Propose
  moving that row's default tier up.

When a signal fires, **propose** the concrete edit: name the section, show before/after lines,
one sentence of why. Apply only after the user says yes — this file is global and durable, never
edit it silently. If the change really belongs in `pr-review-toolkit`, `ponytail-review`,
`web-design-guidelines`, `interface-review`, `tooling-sync` or `triage-renovate-dependabot-prs`,
point there instead (this is a thin wrapper). If nothing fired, say nothing — no "run went well" noise.
