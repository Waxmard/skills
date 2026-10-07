---
name: resolve-merge-conflicts
description: >
  Walk through unresolved merge conflicts one file at a time during an in-progress
  merge, rebase, or cherry-pick. Detects which side is "ours" vs "theirs" (these
  flip between merge and rebase), classifies each file's conflicts, recommends
  mass-accept (`--ours` / `--theirs`) when all hunks lean one way, and otherwise
  helps craft a manual resolution. Runs project type-checks/linters per-file to
  catch broken resolutions early. Never auto-resolves without confirmation,
  never aborts the operation, never commits. Trigger: "resolve merge conflicts",
  "resolve conflicts", "help with the merge conflicts", "fix conflicts", or
  /resolve-merge-conflicts.
---

Resolve the conflicts of the **current in-progress operation** (merge, rebase, or cherry-pick) one file at a time, checking each resolution with project-local type-checks or linters before moving on.

The user must invoke this **mid-conflict**, with unmerged paths already present. If no conflict is in progress, stop and explain.

## Pre-flight

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

**Special-case detections** that override the table:
- **Lockfiles** (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `uv.lock`, `poetry.lock`, `Cargo.lock`, `go.sum`, `Gemfile.lock`, `composer.lock`): never hand-resolve. Pick one side, then **regenerate**. For this repo's `package-lock.json`, see the macOS regeneration note in `CLAUDE.md` (must regen in a Linux container).
- **Generated files** (`dist/`, `build/`, `*.min.js`, snapshots): regenerate, don't hand-resolve.
- **Binary files**: `git diff` shows "Binary files differ" — must pick a whole side with `--ours` or `--theirs`; markers are not applicable.

Order the work: easy mechanical files first (lockfiles, format-only, all-one-side), judgment files last. Resolving easy files first reduces noise in the final per-file type-check.

## Per-file loop

For each file, run this sequence. Propose the recommendation (mass-accept or manual merge) and stop for user confirmation. Once confirmed, applied, verified, and staged, automatically proceed to the next file's recommendation without an intermediate continue gate.

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

| Class | What it looks like | Default action |
|---|---|---|
| **Pure additions, non-overlapping** | Both sides added different lines at the same location | Keep both, merge inline |
| **Format-only** | Whitespace, import order, trailing comma differences | Take the side with real content changes |
| **Semantic overlap** | Both sides changed the same logic differently | Stop, present diff side-by-side, ask user |
| **Rename + edit** | One side renamed identifier/file, other side edited the old name | Take the rename, reapply edit at new name, then grep for stale refs |
| **Dependency version** | `package.json` / `pyproject.toml` / `Cargo.toml` with different version pins | Ask user — usually take the higher version, then regenerate lockfile |
| **Identical resolution** | Both sides made the same edit (rare; usually auto-resolves) | Take either side |

State the classification per hunk before suggesting an action.

### 3. Mass-accept check

If **all** hunks in the file are classified as "take ours" or **all** as "take theirs", offer mass-accept:

```bash
# Pick one — never both
git checkout --ours <file>     # or --theirs
git add <file>
```

**Warning to surface first**: `git checkout --ours/--theirs` discards the conflict markers entirely and takes the **whole file** from that side. Any non-conflicting changes from the other side in that file are lost. Only safe when the file-level lean is unanimous.

Ask the user to confirm. Do not run the checkout without an explicit yes.

### 4. Manual resolve

When hunks are mixed or include semantic overlap:

1. For each hunk, propose a merged version inline. Show:
   - The `ours` version
   - The `theirs` version
   - Your proposed merge
   - The reasoning (one sentence — why this combination preserves both intents)
2. Wait for user confirmation per hunk, or batch confirmation if hunks are independent.
3. Use `Edit` to apply the resolved content. Remove all conflict markers (`<<<<<<<`, `=======`, `|||||||`, `>>>>>>>`).
4. Re-read the file post-edit and verify zero markers remain:
   ```bash
   grep -nE '^(<{7}|={7}|>{7}|\|{7})' <file> || echo "clean"
   ```
5. Run `git diff --check <file>` to catch whitespace errors and any leftover marker fragments.

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

If verification fails:
- Do **not** `git add` the file.
- Show the error verbatim.
- Loop back to step 4 to refine the resolution.

If verification passes:
```bash
git add <file>
```

### 6. Advance to next file

After staging:
- State that `<file>` was resolved (`<N>` of `<M>` conflicted files).
- If more conflicted files remain, immediately present the next file's conflict and recommendation (Steps 1–4) and stop for user confirmation.
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
- **Never run `git checkout --ours/--theirs` without explicit user confirmation** — it takes the whole file from one side.
- **Never `--no-verify`** anywhere.
- **Never auto-edit without showing the diff and getting confirmation first** — every resolution is proposed, confirmed, then applied.
- **Stop on recommendations, not after staging** — always stop for approval on each file's proposed merge/checkout, but advance immediately to the next recommendation once a file is staged.
- **Stop if the operation context disappears mid-flow** — if `MERGE_HEAD` (or equivalent sentinel) vanishes between files, the user finalized externally. Stop and report.

## Common pitfalls

- **Ours/theirs flipped during rebase**: in `git rebase`, `--ours` is the upstream you're rebasing **onto**, the opposite of `git merge`; restate the mapping with branch names before suggesting either flag.
- **Merge-preserving rebase flips ours/theirs back**: a stop on a `merge` command (`MERGE_HEAD` present, or the last `done` line starts with `merge`) is a real merge with merge semantics, while `pick` stops stay inverted. One rebase can interleave both, so re-derive on every `--continue`.
- **diff3 / zdiff3 conflict markers**: when `merge.conflictstyle = diff3` or `zdiff3`, the conflict block includes a `|||||||` base section showing the common ancestor. The marker grep in step 4 must include `\|{7}`, and the proposal in step 4 should reference the base to detect "both sides changed away from the same value" cases.
- **Rename-vs-edit silent bugs**: `git status` shows `UD` / `DU`. Picking either side feels resolved, but you've either lost the edit or kept a dead reference. The post-resolve grep for the old identifier is essential.
- **Lockfile hand-resolution**: never edit `package-lock.json` / `Cargo.lock` / etc. by hand. Pick one side, then regenerate. For npm specifically in this repo, regenerate in a Linux container (see `ui/CLAUDE.md`).
- **Submodule conflicts** (`git status` shows the submodule path as `UU` with a commit-hash conflict): the resolution is a `git submodule update` to the chosen commit, not a marker edit. Flag and hand to the user.
- **Whitespace-only conflicts caused by line-ending differences**: if both sides "differ" but `git diff --ignore-cr-at-eol --ignore-space-at-eol` shows no diff, the conflict is line-ending churn. Take either side. Investigate `.gitattributes` afterwards — the repo is missing a normalization rule.
- **Conflicts in deleted files** (`AU` / `UA` / `DU` / `UD`): the diff tool shows hunks only for the side that still has the file. Decide explicitly: keep deleted (`git rm <file>`) or keep added (`git add <file>` after taking the surviving side's content). Don't leave in the limbo state.
- **Operation finished externally**: user may run `git merge --continue` in another terminal. The sentinel file (`MERGE_HEAD`) disappears. Detect and stop — don't keep proposing edits to a clean tree.
- **Re-conflict on `--continue` during rebase**: rebases can reconflict on each replayed commit. After the user runs `git rebase --continue`, conflicts may reappear on a different commit. Treat each reappearance as a fresh invocation of this skill — re-run pre-flight to re-derive ours/theirs (still inverted for rebase).

## Retro

After the run, propose an edit to this skill only on real signal: a case these steps didn't cover, a
user correction or repeated instruction, a wrong or stale step, or a manual workaround you repeated.
Name the section, show before/after lines, give one sentence of why, and apply only after a yes, in
the Waxmard/skills source (`skills/resolve-merge-conflicts/SKILL.md`), never the installed copy. If
nothing fired, say nothing. Typical signals here: a `git status` code not in Pitfalls, a
lockfile/generated-file regen step not listed, a tool with non-obvious ours/theirs semantics, or a
marker grep that missed a conflict style.
