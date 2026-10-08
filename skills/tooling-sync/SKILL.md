---
name: tooling-sync
description: >
  Compare the current repo's tooling/config against the mw-kit playbook
  (the user's source-of-truth for favorite tooling), report what's missing,
  drifted, or could be added, let the user choose which updates to make, then
  apply the chosen ones — merging into existing config, never clobbering.
  Read-only until the user picks; never commits or pushes. Language-agnostic,
  driven by playbook/MANIFEST.md. Trigger: "sync tooling", "compare tooling",
  "check tooling against mw-kit", "tooling diff", "update tooling from the
  playbook", "what's my playbook say vs this repo", or /tooling-sync.
---

Compare the **current repo** (CWD) against the mw-kit playbook, the user's curated source of truth, and apply chosen updates. The flow is **scope → compare → report → decide → apply**, strictly read-only until the user chooses what to apply.

**Source of truth:** the mw-kit playbook at `$MW_KIT` if set; otherwise a clone of `https://github.com/Waxmard/mw-kit` at `~/.cache/mw-kit`, which the Step 1 block auto-clones and pulls. To use your own playbook, fork mw-kit and set `MW_KIT`. The index is `playbook/MANIFEST.md` there; each row points at a page whose `## Config` block is the canonical config to diff against.

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- `git` (also clones and pulls the mw-kit playbook)
- `python3`, to run the playbook's `scope.py` resolver (stdlib only)

Install missing tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## Pre-flight & Step 1 — Scope (run the resolver)

The deterministic half — repo validation, platform + structure detection, glob-based scoping, alternative resolution, and target presence — lives in a script in the playbook. **Run it and parse its JSON; do not re-derive any of it by hand** (no per-page Glob sweeps, no manual platform/monorepo reasoning).

Before step 1, check the prerequisites:
```bash
for t in git python3; do command -v "$t" >/dev/null || echo "missing: $t"; done
```
If anything prints, stop and tell the user what to install or log in to.

```bash
if [ -z "$MW_KIT" ]; then
  MW_KIT="$HOME/.cache/mw-kit"
  if [ -d "$MW_KIT/.git" ]; then git -C "$MW_KIT" pull -q --ff-only || echo "mw-kit: pull failed, using cached playbook" >&2
  else git clone -q https://github.com/Waxmard/mw-kit.git "$MW_KIT"; fi
fi
echo "MW_KIT=$MW_KIT"
python3 "$MW_KIT/scripts/scope.py" "$(git rev-parse --show-toplevel)"
```

Use the printed `MW_KIT` path for every later playbook read.

The plan JSON:

- `preflight` — `{ok, repo, platform, platform_source}`; on failure `{ok:false, error}` (not a git repo / manifest missing).
- `structure` — `{verdict: single_project|multi_component|ambiguous, ambiguous, manifests, root_orchestrator, component_dirs}`. `component_dirs` are the project roots found under the repo root; nested `targets`/`detect` are anchored there.
- `alternatives` — `{dep_updates:{chosen,reason}, releases:{chosen,reason,note?}, dropped:[…]}`. The losing alternatives are already moved to `skipped`; `chosen` is guaranteed in-scope.
- `in_scope` — one row per relevant page: `{tool, page, scope, tier, platform, targets, targets_present, targets_missing, matched_detect, platform_pending?}`. `targets_present` holds **resolved repo-relative paths** (root-first, component-prefixed in a monorepo, e.g. `fastapi/pyproject.toml`) while `targets_missing` holds the page's raw target strings; read the `targets_present` paths directly and never re-derive them from `targets`.
- `skipped` — `{tool, page, reason}` (no detect match / platform / single-project / alternative not chosen).
- `needs_ask` — questions the script refused to guess (unknown platform, ambiguous structure).
- `warnings` — plan-coherence issues; surface any to the user.
- `state` — incremental-sync memory (see below): `{present, playbook_commit_now, playbook_commit_at_last_sync, last_sync, playbook_unchanged, settled_tools, stale_tools, new_tools, orphaned_tools, all_settled}`. Each `in_scope` row also carries a `state` block: `{decision, decided_at_commit, page_changed_since_decision, settled, reason?}`.

### Incremental sync (`.tooling-sync.json`)

The consumer repo carries a committed `.tooling-sync.json` recording each tool's last decision and the mw-kit commit the page was at when it was made. The resolver checks per tool whether that page has changed since, so a settled decision isn't re-litigated every run. **Read it off the plan; don't compute it.**

- A row with `state.settled: true` means the prior decision (`synced` / `declined` / `override`) still holds *and the governing page hasn't changed*. **Skip its compare** (Step 2) and fold it into a collapsed "settled" line.
- A row with `state.settled: false` is **live**: either new (`decision: "new"`), or its page changed since the decision (`page_changed_since_decision: true`). Compare these normally.
- **Fast path:** if `state.all_settled` is true (every in-scope tool settled, nothing new or stale), there is nothing to compare. Report "Nothing new since last sync (`last_sync`, playbook @ `playbook_commit_at_last_sync` short). N tools settled." and stop — unless the user asks for a full re-check, in which case re-run the resolver with `--no-state` and compare everything.
- If `state.present` is false, this is a first sync (or `--no-state`): compare every in-scope tool and write the file at the end.
- **`state.orphaned_tools`** are recorded decisions whose playbook page no longer exists (deleted or renamed upstream). They produce no `in_scope` or `skipped` row, so name them in the report and **drop them from the file in Step 6**. They don't block the fast path; on an otherwise all-settled run, report the fast path *and* the orphan cleanup. Also check whether the repo still carries what the page governed (a workflow, a config file, a script it installed) and propose its removal in the report; dropping the record is not the cleanup. Don't delete it unilaterally; the user decides, then you apply it like any other Step 5 change.

Then:

1. **`preflight.ok` false** → stop and surface `preflight.error`. (Manifest-missing means check the path / `$MW_KIT`.)
2. **`needs_ask` non-empty** → ask each question, then **re-run the script with the answer as an override** so the plan stays deterministic — don't hand-patch it:
   - platform → `--platform github|gitlab`
   - structure → `--structure single_project|multi_component`
   For the ambiguous-structure case, a nested single component is a strong monorepo signal — present it that way. When the answer is monorepo, also consult an existing **sibling component or org reference repo** for the concrete shape (CI include structure, image-tag flow) — the playbook block is canonical, the sibling shows the wired-up reality.
3. **Greenfield repo → scope in the planned stack by hand.** Detection is *presence*-based (`**/*.py`, `package.json`, `go.mod`), so a repo whose stack is **decided but not yet written** scopes as "no language" and every language page lands in `skipped` with `no detect match`. The signal: `structure.manifests` is empty **and** no language-scope page is in `in_scope`. Don't take that at face value on a near-empty repo — ask what stack it's being built in (check a design doc / README / the user's stated plan first), then pull that scope's pages in manually and compare them as ❌ missing. There is no resolver flag for this; the manual scope-in *is* the fix, so say plainly which pages you added and why.

   **Re-check the alternatives too.** Alternative resolution keys off the same absent detection, so it can pick the wrong winner: an empty repo on GitLab resolves `releases` → `releases-gitlab` (node semantic-release), when a repo about to be written in Python wants `releases-python`. Flip it and record the loser as `declined` with the reason (Step 6).

4. **Relay the scoped set** before diffing, from the JSON: in-scope tools, the chosen alternatives (with the dropped ones named), and what was skipped + why. State single-project vs monorepo. When `state.present`, also name what's settled vs live: "Relevant: ruff, mypy, uv, pytest, lefthook, dependabot, releases-github. 5 settled since last sync (skipping); comparing 2 live: ruff (page changed), pytest (new). Skipped: node/* (no JS), renovate (alternative to dependabot). Scoped as single-project."

## Step 2 — Compare

**First, drop the settled rows.** Only compare `in_scope` rows where `state.settled` is false (new tools + ones whose page changed since the last decision). Settled rows are carried straight to the Step 3 "settled" line without a read.

The resolver already told you, per page, which `targets` exist (`targets_present` / `targets_missing`). Use that to avoid needless reads — the `targets_present` paths are openable as-is, so a target listed there is read/edited at that path.

- **No targets present** → classify directly from `tier` without reading the page: ❌ **missing (baseline)** or ➕ **suggest (optional)**. (For `conventional-commits` and other target-less pages, judge by convention/commit history, not a file.)
- **Some/all targets present** → this is the drift question. Read the page's canonical `## Config` block and the present target file(s), then classify match vs drift.
  - **`agent-instructions` is content-checked, not just presence-checked.** This page has no canonical `## Config` snippet, so "`AGENTS.md` present" is *not* automatically ✅. Classify ⚠️ drift when: (a) any `CLAUDE.md` exists, root or nested (`find . -name CLAUDE.md -not -path './node_modules/*'`) — a real one shadows `AGENTS.md` in Claude Code's default mode, a symlink is a leftover to delete; or (b) the `AGENTS.md` body contains **any** specific-agent reference — `Claude`, `Claude Code`, `Gemini`, a `# CLAUDE.md` heading, any product name. The rule is zero named agents in the prose; always "the agent" / "AI agents". A `../CLAUDE.md`-style pointer to a sibling that's genuinely named that gets reworded to drop the name (not left as-is).

For each page needing a config read, compare its `targets` files against the page's canonical `## Config` block. Read the page body only for the in-scope ones.

**Dispatch rule:** the per-page diff is independent and mostly mechanical (does the target exist, does its config match the canonical block). Count only the **live** (non-settled) pages that have at least one `targets_present` entry — those are the only ones needing a config read. Live pages with no targets present are classified from `tier` inline (see above) and never get a subagent, nor do target-less pages like `conventional-commits`:
- **≤ 7 such pages** → compare inline yourself.
- **≥ 8 such pages** → fan out one subagent per page on a fast, low-cost model, in parallel. Each subagent reads its page's canonical `## Config` block from the playbook + the repo's `targets` file(s), and returns a structured classification row (status, target file(s), headline delta, quoted deltas for drift). **When the target file is present but the subagent flags a sub-element as missing (an ecosystem block, a config table, a key), it must quote the lines it searched as proof — a present multi-block file (dependabot's per-ecosystem blocks, a multi-table `pyproject.toml`) is exactly where a fast skim false-flags an element that's actually there.** Escalate a page to a stronger model only when its config needs *semantic* merge reasoning (e.g. reconciling a hand-customized `biome.json` or a multi-section `pyproject.toml`) rather than a flat presence/equality check. You collect the rows and assemble the Step 3 report. **Apply (Step 5) stays inline in the parent** — it touches files and must stay coherent across confirmations.

Each compare subagent is read-only: it reads the playbook page and the repo target, returns its row, writes nothing.

- **Re-verify intra-file "missing" before applying.** If a row marks something absent *inside* a target that `targets_present` lists, the parent re-reads that file to confirm before the report/apply — never act on a sub-element "missing" claim on a present file without seeing it yourself.

| Status | Meaning |
|---|---|
| ✅ **match** | Repo config aligns with the playbook's canonical block (semantically — ignore key ordering / formatting). |
| ⚠️ **drift** | Tool is present but config differs from canonical. Show the specific deltas. |
| ❌ **missing (baseline)** | `tier: baseline` page applies but the repo has no corresponding config. |
| ➕ **suggest (optional)** | `tier: optional` page applies and could be adopted, but absence isn't a problem. |
| 🔧 **local override** | Repo deliberately diverges (documented in its `AGENTS.md`, or an obvious project-specific reason). Flag, don't fight it. |

Comparison notes:
- Configs are often **fragments**, not whole files. `ruff`/`mypy`/`pytest`/`uv` live in sections of `pyproject.toml`; `package-json` scripts are keys inside `package.json`; `biome`/`tsconfig`/`renovate` are whole files. Diff the relevant slice, not the whole file.
- For drift, report the **direction**: which keys the playbook adds, changes, or is stricter on. Quote both sides for changed values.
- Versions matter: pinned tool versions (`mise.toml`, biome `$schema`, `target-version`, action pins) — note when the repo is behind the playbook, but treat newer-in-repo as fine (the playbook may just be stale).
- Do not treat the playbook as a mandate. If the repo's choice looks intentional, classify it 🔧 and surface the tension rather than proposing a revert.

## Step 3 — Report

Present a grouped summary the user can act on. One line per tool: status, target file(s), and the headline delta. Order: ❌ baseline-missing first, then ⚠️ drift, then ➕ suggestions, then ✅ matches (collapsed). Example:

```
❌ security      .github/workflows/security.yml — no scanning workflow (playbook: semgrep + trivy fs/image)
⚠️ ruff          pyproject.toml [tool.ruff] — missing select packs S, SIM, PL; no per-file test ignores
⚠️ mise          mise.toml — python pinned 3.10, playbook 3.11
➕ tach          (optional) no module-boundary enforcement — app/ has 6 layers, could benefit
✅ uv, mypy, lefthook — aligned
💤 pytest, uv, dependabot — settled since last sync (2026-06-01), page unchanged
```

The 💤 line is the settled rows you skipped — list them so the user sees they were considered, not missed. Omit it on a first sync.

## Step 4 — Decide

Ask which to apply. Offer: **all baseline fixes**, **a specific subset** (numbered), **just one**, or **none / report-only**. Default to nothing until told. For ⚠️ drift items, the user may want only part of the delta — let them say so.

## Step 5 — Apply

For each chosen item, one at a time:

1. Re-read the canonical block from the page and the current target file.
2. **Merge, don't clobber.** Bring the playbook's opinionated values into the repo's existing config; preserve repo-specific keys (extra deps, project name, custom scripts, local ignores). Whole-file targets with no existing file → create from the canonical block, adjusted to the repo (paths, project name, roots like `fastapi/` → the repo's actual layout).
3. Show the proposed change as a diff and **confirm before writing**. Then apply with Edit (fragment merge) or Write (new whole file).
   - **`agent-instructions` is filesystem plumbing, not a config merge.** `AGENTS.md` is the only instructions file. A `CLAUDE.md` symlink to it → `rm` it. A real `CLAUDE.md` and no `AGENTS.md` → `mv CLAUDE.md AGENTS.md` (Bash, confirm first; plain `mv`, not `git mv` — staging stays the user's job). A real `CLAUDE.md` beside a real `AGENTS.md` → surface the conflict instead of clobbering; let the user pick which content wins, then delete `CLAUDE.md`. Never Write a second copy, and add a symlink only for an agent the user names that doesn't read `AGENTS.md`. A repo that *generates* both files from a template is ⚠️ drift, not satisfied: propose collapsing it to `AGENTS.md` and deleting whatever existed only to duplicate the guide — the template, the build script, its `make` targets, the CI staleness gate, the pre-commit hook. Scope that carefully before proposing it: a generator that also renders genuinely different documents (a README from partials) stays, minus the agent guides; one whose remaining outputs are 1:1 copies goes entirely.
     - **Scrub the body to agent-agnostic after the move.** The rename alone isn't the fix — the page's contract is neutral content, so once `AGENTS.md` is the file, rewrite Claude-specific phrasing in it (`Claude Code` / "Claude" → "the agent" / "AI agents"; drop Claude-only asides) and show that edit as part of the diff. Keep a named-agent line only where the instruction genuinely applies to just that one. Skipping this leaves every other agent reading "Claude"-flavored guidance.
4. Adjust for repo reality: the playbook examples assume paths like `fastapi/`, `frontend/`, `app/`. Rewrite globs/roots/`source` to the repo's actual structure. Flag anything you couldn't auto-map.
5. After applying, note any **follow-up** the user must do manually (install a dep, add a CI secret, run a formatter once, add a workflow token) — don't run installs or commits yourself.

Pause after each applied change. Don't batch silently.

## Step 6 — Record decisions (`.tooling-sync.json`)

After the user has decided everything (applied, declined, or report-only), write the repo's `.tooling-sync.json` so the next run skips what's settled. This is the only file the skill writes that isn't a tooling config; it's still just a working-tree edit (the user commits it, like everything else). Note: some users globally gitignore `.tooling-sync.json` — then it stays local-only (never committed) and still drives the next sync on that machine; don't tell the user to commit it if it isn't showing in `git status`.

Write the file with the `Write` tool at the repo root. Schema:

```json
{
  "schema": 1,
  "last_sync": "2026-06-22",
  "playbook_commit": "<mw-kit HEAD — from state.playbook_commit_now in the plan>",
  "tools": {
    "ruff":     { "decision": "synced",   "playbook_commit": "<HEAD>" },
    "tach":     { "decision": "declined", "playbook_commit": "<HEAD>", "reason": "app/ not layered enough" },
    "mypy":     { "decision": "override", "playbook_commit": "<HEAD>", "reason": "py39 floor, documented in AGENTS.md" }
  }
}
```

Rules for building it:

- **`decision` per tool, only for tools you evaluated this run** (live rows): `synced` (applied, or already aligned ✅), `declined` (user chose not to adopt a ❌/⚠️/➕), or `override` (🔧 deliberate local divergence). A `reason` is required for `declined`/`override`, optional for `synced`.
- **`playbook_commit` = the current mw-kit HEAD** (`state.playbook_commit_now`) for every tool you touched — that's the page version the decision was made against, and what the next run diffs from.
- **Carry settled rows forward unchanged.** Start from the existing `tools` map (the plan's per-row `state` already gave you each prior record); only overwrite the entries you re-evaluated. Don't drop or re-stamp settled tools — their original `playbook_commit` is what keeps page-change detection honest.
- Set top-level `last_sync` to today and `playbook_commit` to the same HEAD.
- **Don't list out-of-scope or skipped tools.** Only in-scope tools get records.
- **Delete every tool in `state.orphaned_tools`** while carrying the settled rows forward — its page is gone, so keeping the record means it never surfaces again. Say which ones you dropped. Deleting the record does not delete the artifact: if the report surfaced a leftover workflow/config for that orphan and the user approved, that removal is a separate Step 5 edit, not part of this write.
- On a report-only run where the user applied nothing: still write the file — record everything you compared (✅ as `synced`, the rest the user explicitly declined; if they didn't rule on an item, leave it out so it stays live next run).

Show the written file once; don't pause per-key. Mention it's part of what to commit.

## Hard rules

- **Read-only until the user picks.** Steps 1–3 never modify the repo.
- **Never commit, never push, never `git add`** — global rule. Apply edits to the working tree only; the user commits.
- **Never clobber a config wholesale** when the repo already has one — merge. Only Write a fresh file when none exists.
- **Never run installs** (`npm install`, `uv add`, `pip install`) — surface them as follow-ups.
- **Respect local overrides.** A documented or obviously-intentional divergence is flagged, not overwritten. A value the repo's own tests assert against — a viewport size, a port, a magic threshold — is positive evidence the value is intentional: aligning it to the canonical block leaves the test red, so classify the tool 🔧 `override` and record the reason instead of "fixing" it.
- **The resolver owns scope.** Don't re-derive scope by hand-globbing or reading every page — trust `scope.py`'s plan. If a page exists but the resolver never considers it (missing from its output entirely), the manifest/frontmatter may be stale; tell the user to run `python3 scripts/build_manifest.py` in mw-kit. Never run either script *from* the consumer repo.
- **The resolver owns incremental state too.** Don't hand-compute which pages changed or hand-edit `.tooling-sync.json`'s recall logic — read `state` off the plan, and only ever *write* the file in Step 6. To force a full re-compare, re-run the resolver with `--no-state` rather than deleting the file.

## Permissions (pre-approve these)

The read-only scope+compare phase needs, in addition to defaults:

- `Read(~/.cache/mw-kit/**)` (or your `$MW_KIT` path) — read the playbook + page bodies (outside the workspace, so it prompts otherwise). **This is the key one.**
- `Bash(python3 ~/.cache/mw-kit/scripts/scope.py:*)` (or your `$MW_KIT` path) — run the scope resolver (does its own git/glob/presence work). **The other key one.**
- `Bash(git rev-parse:*)` — resolve the consumer repo toplevel to pass to the resolver. (Already allowed globally.)

The apply phase uses `Edit` / `Write` on the consumer repo's own config files. These are intentionally left to prompt (and the skill confirms each change anyway) — don't blanket-allow them. Reading the consumer repo's own files needs no extra permission (it's the workspace).

## Pitfalls

- **Path assumptions:** playbook configs hardcode `fastapi/`, `frontend/`, `app/`, `src/`. Always remap to the repo's real layout before applying — a copied `root: fastapi/` lefthook entry silently no-ops in a repo with no `fastapi/`.
- **Fragment vs whole-file:** editing `[tool.ruff]` into a `pyproject.toml` that already has it = merge the keys, don't append a duplicate table. Whole-file (`biome.json`) with an existing file = reconcile, don't overwrite custom rules.
- **Alternatives double-count:** never propose both dependabot and renovate, or both release tools — pick by platform + what's already present.
- **Stale playbook:** if the repo pins a newer version than the playbook, the playbook is behind — note it, maybe suggest the user update mw-kit, don't downgrade the repo.
- **Rewritten playbook history marks every tool stale.** If most tools show stale and `git -C "$MW_KIT" cat-file -t <recorded commit>` fails, mw-kit history was rewritten and the page diff can't be computed (the resolver assumes "changed"). Compare the current page against the repo, use each tool's prior decision reason to skip deltas it already covers, and re-stamp the touched tools with the new HEAD.
- **Optional noise:** don't push `tier: optional` pages hard. Mention once, only when the repo plausibly benefits (e.g. tach only for a layered app, docker-bake only if it ships images).
- **Platform mismatch:** a github-only page (security workflow, dependabot, release-please) on a gitlab repo is out of scope — its gitlab counterpart applies instead.
- **A global gitignore can hide a target you just created.** The `.tooling-sync.json` case is called out in Step 6, but it generalizes: users commonly ignore `*plan.md`, `CLAUDE.md` and similar globally, so an applied file can be correct on disk and invisible to `git status`. After applying, `git status --short` and — for anything missing — `git check-ignore -v <path>`. It's usually not a bug to fix, but say which applied files will and won't be committed rather than implying all of them are staged-ready.
- **Trust a reference repo's config, not its prose.** When mirroring a sibling/reference repo (the monorepo-shape case in Step 1, or "match what project X does"), read the actual config file — `pyproject.toml`, `package.json`, `mise.toml`. A reference repo's own `AGENTS.md`/`README` version claims drift from its config and are a real source of wrong pins; the playbook block plus the sibling's *config* are canonical, its docs are not.
- **Copied-from-upstream repos: match the upstream's formatter, not the playbook's.** When the repo's files are copies of another repo's (templates, vendored skills) and are periodically `diff -r`'d against it, adopting the playbook's `line-length`/`target-version` reformats every file and buries real upstream changes in noise. Probe first (`ruff check --config <tmp> . && ruff format --check --config <tmp> .`); if the canonical values churn files, take the upstream project's values and record the tool as `override`.
- **`COPY .` images ship new root configs.** Before creating a whole-file config at the root (`ruff.toml`, `renovate.json`, `lefthook.yml`), check the Dockerfile. If it copies the build context wholesale, add the new files to `.dockerignore` in the same apply, or they land in the image.

## Retro

After the run, propose an edit to this skill only on real signal: a case these steps didn't cover, a
user correction or repeated instruction, a wrong or stale step, or a manual workaround you repeated.
Name the section, show before/after lines, give one sentence of why, and apply only after a yes, in
the Waxmard/skills source (`skills/tooling-sync/SKILL.md`), never the installed copy. If nothing
fired, say nothing.

A missing or stale tool choice or `## Config` snippet is playbook drift: note "update mw-kit" instead
of editing here, and fix the skill only when the process (scope, compare, merge, apply) was wrong.
