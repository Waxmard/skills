---
name: resolve-merge-conflicts
description: >
  Walk through unresolved merge conflicts one file at a time during an in-progress
  merge, rebase, or cherry-pick. Detects which side is "ours" vs "theirs" (these
  flip between merge and rebase), classifies each file's conflicts, and
  automatically applies, verifies, and stages confident resolutions (format-only,
  identical, non-overlapping additions, rename+edit, compatible dependency
  bumps, lockfile/generated regeneration, and unambiguous one-sided or
  composable logic). Stops for user confirmation only on genuine ambiguity or
  check failures; never aborts the operation, never commits. Trigger: "resolve
  merge conflicts", "resolve conflicts", "help with the merge conflicts", "fix
  conflicts", or /resolve-merge-conflicts.
---

Resolve the conflicts of the **current in-progress operation** (merge, rebase, or cherry-pick) one file at a time, checking each resolution with project-local type-checks or linters before moving on.

The user must invoke this **mid-conflict**, with unmerged paths already present. If no conflict is in progress, stop and explain.

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- `git`
- For per-file verification, the repo's own check tools (step 5 table); a missing one is reported, never installed

Install missing tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## Pre-flight

Before step 1, check the prerequisites:
```bash
command -v git >/dev/null || echo "missing: git"
```
If it prints, stop and tell the user to install git.

1. Confirm CWD is inside a git repo (`git rev-parse --git-dir`). If not, stop.
2. Detect the in-progress operation by checking which sentinel file exists in `.git/`. **Check for a rebase directory first** — a merge-preserving rebase (`--rebase-merges`) has *both* a `rebase-merge` dir and `MERGE_HEAD` while replaying a `merge` command, so testing `MERGE_HEAD` first misclassifies it as an ordinary merge.
   - directory `rebase-merge` / `rebase-apply` (or `REBASE_HEAD`) → **rebase**. Then determine the stopped command type — it decides ours/theirs in the next step:
     - `MERGE_HEAD` also present, **or** the last non-empty line of `.git/rebase-merge/done` starts with `merge` → stopped on a **`merge` command** (merge-preserving rebase) → merge semantics
     - otherwise → stopped on a **`pick`/`edit`/`reword`/`squash`/`fixup`** command → inverted rebase semantics
   - `MERGE_HEAD` only, no rebase dir → ordinary merge
   - `CHERRY_PICK_HEAD` → cherry-pick
   - `REVERT_HEAD` → revert
   - None → no operation in progress. Stop and tell the user.
3. **Establish ours/theirs semantics** — this is the most common source of mistakes:
   - **Merge**: `ours` = current branch (HEAD before merge), `theirs` = the branch being merged in (MERGE_HEAD).
   - **Rebase — `pick`/`edit`/`reword`/`squash`/`fixup` (the common case)**: `ours` = the upstream branch you're rebasing **onto**, `theirs` = your own commits being replayed. **This is the opposite of what most people expect.**
   - **Rebase — `merge` command (`--rebase-merges`)**: semantics flip **back** to merge semantics — `ours` = the branch rebuilt so far (HEAD / first parent), `theirs` = the side branch named in the `merge` command. A real merge is running (`MERGE_HEAD` present), so it is *not* inverted. Do **not** apply the pick-rebase inversion here. Re-derive per stop — one rebase can mix both kinds.
   - **Cherry-pick / revert**: `ours` = HEAD, `theirs` = the commit being picked/reverted.
   - State the mapping out loud to the user before any `--ours` / `--theirs` suggestion. Reference the actual branch names, not the abstract terms.
4. Show what's being merged so context is grounded:
   ```bash
   git log --oneline -5 HEAD
   git log --oneline -5 MERGE_HEAD   # or REBASE_HEAD / CHERRY_PICK_HEAD
   ```
5. Check `git config merge.conflictstyle` — if `diff3` or `zdiff3`, conflict markers include a `|||||||` base section. The parsing in step 4 of the per-file loop must handle both styles.

## Discovery

List unresolved files and classify upfront:

```bash
git status --short | grep -E '^(UU|AA|DD|AU|UA|DU|UD)'
```

Status codes:
- `UU` — both modified (the common case)
- `AA` — both added (file created on both sides with different content)
- `DD` — both deleted (rare, usually auto-resolves)
- `AU` / `UA` — added by one, modified by the other
- `DU` / `UD` — deleted by one, modified by the other (high-risk: usually means a rename was missed)

For each file, run a quick **file-level lean check** to see if mass-accept is viable:

```bash
# How many hunks lean each way? Approximate via marker line counts.
git diff --diff-filter=U -- <file>
```

For each conflicted file, present a row:

| File | Status | Hunks | Lean | Suggestion |
|---|---|---|---|---|
| `src/foo.ts` | UU | 3 | all theirs | `git checkout --theirs` |
| `package-lock.json` | UU | 12 | mixed | regenerate (lockfile) |
| `src/bar.ts` | UU | 2 | mixed | manual |
| `src/OLD.ts` | UD | — | renamed-vs-edited | manual w/ reapply |

Present the table for context, not as a confirmation gate, and proceed automatically through the ordered list.

**Special-case detections** that override the table:
- **Lockfiles** (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `uv.lock`, `poetry.lock`, `Cargo.lock`, `go.sum`, `Gemfile.lock`, `composer.lock`): never hand-resolve. Pick one side, then **regenerate** against the merged manifest (e.g. `npm install --package-lock-only`, `uv lock`, `cargo update -w`). If the repo documents how to regenerate a lockfile (e.g. inside a Linux container), follow that.
- **Generated files** (`dist/`, `build/`, `*.min.js`, snapshots): regenerate, don't hand-resolve.
- **Binary files**: `git diff` shows "Binary files differ" — must pick a whole side with `--ours` or `--theirs`; markers are not applicable.

Order the work: confident files first (dependency manifests before their lockfiles so lockfile regeneration runs against the merged manifest, then format-only, identical, non-overlapping additions, generated files, and clear one-sided or composable merges), and ambiguous judgment files last so all confident work is applied, verified, and staged before the first user prompt.

## Per-file loop

For each file, run this sequence. When a file's resolution is **confident** (every hunk's merged intent is unambiguous from the diff, `diff3` base, and commit history), apply it, run per-file verification (step 5), `git add <file>`, log a one-line summary of the applied resolution, and auto-advance to the next file without stopping. Stop for user confirmation only when a file has genuine ambiguity or its verification check fails.

### 1. Show the conflict

Read the full file (not just hunks) so surrounding context is loaded. Then show only the conflicted hunks with a few lines of context:

```bash
git diff --diff-filter=U -- <file>
```

For `UD` / `DU` (rename-vs-edit), also show:

```bash
# Did one side rename the file? Find the rename target.
git log --diff-filter=R --follow --name-status -1 MERGE_HEAD -- <file>
git log --diff-filter=R --follow --name-status -1 HEAD -- <file>
```

### 2. Classify each hunk

For every conflict marker block, classify into one of:

| Class | What it looks like | Action |
|---|---|---|
| **Identical resolution** | Both sides made the same edit (rare; usually auto-resolves) | **Auto-apply**: take either side |
| **Format-only** | Whitespace, import order, trailing comma, or line-ending differences | **Auto-apply**: take the side with real content changes (or either side if purely formatting) |
| **Pure additions, non-overlapping** | Both sides added different lines at the same location | **Auto-apply**: keep both, merge inline |
| **Rename + edit** | One side renamed identifier/file, other side edited the old name | **Auto-apply** when the edit maps cleanly to the new name: take the rename, reapply the edit at the new name, and grep for stale refs. **Stop** if the edit contradicts the rename |
| **Dependency version** | `package.json` / `pyproject.toml` / `Cargo.toml` with different version pins | **Auto-apply** when compatible (same-major bump or one side untouched): take the higher compatible version, then regenerate the lockfile. **Stop** on competing majors, conflicting peer constraints, or modify-vs-remove |
| **Composable or superseded logic** | Both sides touched the same block, and the `diff3` base plus commit history show the changes compose cleanly or one side strictly supersedes the other | **Auto-apply**: merge both intents (or take the superseding side) and verify in step 5 |
| **Ambiguous semantic overlap** | Both sides changed the same logic, behavior, or configuration value in mutually exclusive ways | **Stop**: present diff side-by-side with options and ask the user |
| **Ambiguous delete/modify or binary/submodule** | `DU` / `UD` / `AU` / `UA` without a clear rename or supersession, or binary/submodule conflict with no clear winner from commit history | **Stop**: present both sides and ask the user |

State the classification and one-line rationale per hunk before applying or prompting.

### 3. Mass-accept check

If **all** hunks in the file lean the same way ("take ours" or "take theirs"), check whether the other side has any non-conflicting changes outside the conflict markers (`git diff :1:<file> :3:<file>` when taking `ours`, or `git diff :1:<file> :2:<file>` when taking `theirs`):

- **Other side has changes outside the conflict markers**: do **not** run `git checkout --ours/--theirs` (it overwrites the whole file and silently drops auto-merged hunks). Resolve the conflict markers in place via step 4 instead.
- **Other side has no changes outside the conflict markers** (or the file is a binary or lockfile/generated file being regenerated):
  - If every hunk is **confident** (step 2), run `git checkout --ours <file>` (or `--theirs`), log which side was taken and why, and proceed to step 5 verification and `git add <file>` without prompting.
  - If the choice of winning side is **ambiguous**, warn the user that `git checkout --ours/--theirs` takes the whole file from that side and wait for confirmation before running it.

### 4. Manual resolve

When hunks are mixed or require inline editing:

1. **All hunks in the file are confident (step 2)**:
   - Use `Edit` to apply the merged resolution and remove all conflict markers (`<<<<<<<`, `=======`, `|||||||`, `>>>>>>>`).
   - Log a one-sentence rationale per hunk naming how both intents were preserved (or why one side superseded the other).
2. **One or more hunks in the file are ambiguous**:
   - Apply any confident hunks in the file first, or prepare the full proposed resolution.
   - For each ambiguous hunk, show the `ours` version, the `theirs` version, the proposed merge, and a one-sentence rationale.
   - Ask the user to confirm or adjust (batching independent ambiguous hunks in the same file into one prompt) before finalizing the file.
3. Re-read the file post-edit and verify zero markers remain:
   ```bash
   grep -nE '^(<{7}|={7}|>{7}|\|{7})' <file> || echo "clean"
   ```
4. Run `git diff --check <file>` to catch whitespace errors and any leftover marker fragments.

For **rename-vs-edit** specifically: after taking the rename, `grep` the resolved file (and the rest of the touched area) for the **old** identifier name. The most common silent bug here is a dead reference that compiles in isolation but errors on use.

### 5. Per-file verification

Run the **narrowest** project check that covers the touched file. Don't run the whole suite per file — too slow.

| File type | Check |
|---|---|
| `*.ts` / `*.tsx` | the project's typecheck script — check `npm run` for the name (`type-check` vs `typecheck`) and run it from the package dir |
| `*.py` | `uv run mypy <file>` or `uv run ruff check <file>` |
| `*.rs` | `cargo check -p <crate>` |
| `*.go` | `go vet ./<pkg>/...` |
| `*.json` | `python -m json.tool <file> > /dev/null` |
| `*.yaml` / `*.yml` | `yamllint <file>` (or `yq . <file>`); Kustomize dir: also `kustomize build <dir>` |
| Lockfiles | Regenerate (see lockfile section), then run the project's normal install/check |

If a check's tool isn't installed, don't install it. Report `unverified: <tool> not installed`. For purely mechanical resolutions (identical, format-only, non-overlapping additions) that pass the marker grep and `git diff --check`, `git add <file>` and note `unverified: <tool> not installed` in the log; for semantic, rename+edit, or dependency resolutions that depend on type-check/lint verification for confidence, stop and ask the user whether to stage the file anyway.

If the stop changed a dependency manifest or lockfile, sync installed deps first (`npm ci`, `uv sync`, …) — otherwise the check runs against stale `node_modules`/venv and can pass or fail for reasons unrelated to the resolution. During a rebase, errors that a later commit fixes (e.g. code needing a dependency bumped further down the todo) are expected at intermediate stops; confirm against the todo before treating them as a broken resolution.

If verification fails:
- Do **not** `git add` the file.
- If the failure is caused by an obvious omission in the conflict resolution (such as a missing import or renamed symbol from the other side), refine the resolution once in step 4 and re-run the check; if it still fails, show the error verbatim and stop for user direction.

If verification passes:
```bash
git add <file>
```

### 6. Advance to next file

After staging:
- State that `<file>` was resolved (`<N>` of `<M>` conflicted files) with a one-line summary of the resolution.
- If more conflicted files remain, proceed immediately to the next file (auto-applying confident files and stopping only when a file hits an ambiguity gate in steps 2–4 or an unresolved check failure in step 5).
- If all files are resolved, proceed directly to ## Closing.

## Closing

When all conflicted files are resolved (or skipped), summarize:

```bash
git status --short
```

State:
- How many files were resolved, how many skipped
- Whether the working tree is clean of conflict markers (re-run the grep across all touched files)
- The next manual step for the user (e.g., `git commit` for a merge, `git rebase --continue` for a rebase, `git cherry-pick --continue` for a cherry-pick)

**Do not run** `git commit`, `git rebase --continue`, `git cherry-pick --continue`, or any of the `--abort` variants. The user finalizes.

## Hard rules

- **Never run `git commit`** — even when the merge appears complete. The user commits manually (matches the global "user handles all commits" rule). The one allowed write is `git add <file>` after a successful per-file resolution.
- **Never run `git merge --abort` / `git rebase --abort` / `git cherry-pick --abort`** — destructive, and often invoked accidentally. Only the user invokes these.
- **Never run `git reset --hard`** — discards uncommitted work.
- **Never run `git checkout --ours/--theirs` when the other side has non-conflicting changes in that file** — whole-file checkout discards auto-merged lines outside conflict markers. Verify the other side has no changes outside the conflicted hunks (or that the file is a lockfile/generated file being regenerated), and ask for confirmation whenever the winning side is ambiguous.
- **Never `--no-verify`** anywhere.
- **Auto-apply confident resolutions; gate only on genuine ambiguity or check failure** — when every hunk in a file has an unambiguous resolution and per-file verification passes, apply the edit, log the one-line rationale per hunk, `git add <file>`, and advance without prompting. Stop and ask the user only when hunks have competing semantic choices, incompatible dependency constraints, unclear delete-vs-modify intent, an unverified semantic merge (missing check tool), or a verification failure that doesn't self-correct.
- **Stop if the operation context disappears mid-flow** — if `MERGE_HEAD` (or equivalent sentinel) vanishes between files, the user finalized externally. Stop and report.

## Common pitfalls

- **Ours/theirs flipped during rebase**: in `git rebase`, `--ours` is the upstream you're rebasing **onto**, the opposite of `git merge`; restate the mapping with branch names before suggesting either flag.
- **Merge-preserving rebase flips ours/theirs back**: a stop on a `merge` command (`MERGE_HEAD` present, or the last `done` line starts with `merge`) is a real merge with merge semantics, while `pick` stops stay inverted. One rebase can interleave both, so re-derive on every `--continue`.
- **diff3 / zdiff3 conflict markers**: when `merge.conflictstyle = diff3` or `zdiff3`, the conflict block includes a `|||||||` base section showing the common ancestor. The marker grep in step 4 must include `\|{7}`, and the proposal in step 4 should reference the base to detect "both sides changed away from the same value" cases.
- **Rename-vs-edit silent bugs**: `git status` shows `UD` / `DU`. Picking either side feels resolved, but you've either lost the edit or kept a dead reference. The post-resolve grep for the old identifier is essential.
- **Lockfile hand-resolution**: never edit `package-lock.json` / `Cargo.lock` / etc. by hand. Pick one side, then regenerate. Follow the repo's own regeneration notes if it has any.
- **Submodule conflicts** (`git status` shows the submodule path as `UU` with a commit-hash conflict): the resolution is a `git submodule update` to the chosen commit, not a marker edit. Flag and hand to the user.
- **Whitespace-only conflicts caused by line-ending differences**: if both sides "differ" but `git diff --ignore-cr-at-eol --ignore-space-at-eol` shows no diff, the conflict is line-ending churn. Take either side. Investigate `.gitattributes` afterwards — the repo is missing a normalization rule.
- **Conflicts in deleted files** (`AU` / `UA` / `DU` / `UD`): the diff tool shows hunks only for the side that still has the file. Decide explicitly: keep deleted (`git rm <file>`) or keep added (`git add <file>` after taking the surviving side's content). Don't leave in the limbo state.
- **Operation finished externally**: user may run `git merge --continue` in another terminal. The sentinel file (`MERGE_HEAD`) disappears. Detect and stop — don't keep proposing edits to a clean tree.
- **Re-conflict on `--continue` during rebase**: rebases can reconflict on each replayed commit. After the user runs `git rebase --continue`, conflicts may reappear on a different commit. Treat each reappearance as a fresh invocation of this skill — re-run pre-flight to re-derive ours/theirs (still inverted for rebase).

## Retro

After the run, propose an edit to this skill only on real signal: a case these steps didn't cover, a
user correction or repeated instruction, a wrong or stale step, or a manual workaround you repeated.
Name the section, show before/after lines, give one sentence of why, and apply only after a yes, in
the skills repo source (`skills/resolve-merge-conflicts/SKILL.md`), never the installed copy. If
nothing fired, say nothing. Typical signals here: a `git status` code not in Pitfalls, a
lockfile/generated-file regen step not listed, a tool with non-obvious ours/theirs semantics, or a
marker grep that missed a conflict style.
