---
name: split-branch
description: >
  Analyze a scope-crept branch and split it into branches that each sit
  directly on the base and merge in any order without conflicting — grouping
  by hunk-overlap analysis, pairwise merge simulation, and trial cherry-picks
  rather than vibes, and fusing two themes into one branch when that is what
  keeps the merges clean. Two phases with a hard stop: it reports a
  recommended split and waits for approval, then recreates the branches,
  verifies the union is byte-identical to the original and that every pair
  merges cleanly, opens one MR/PR per branch, and leaves a breadcrumb comment
  on the original MR pointing at its replacements. Preserves the original
  branch and never force-pushes. GitLab (`glab`) first, GitHub (`gh`)
  supported. Trigger: "split this branch", "this branch has scope creep",
  "break this into separate MRs", "should this be stacked or off main",
  "descope this branch", "split into smaller PRs", or /split-branch.
allowed-tools: >
  Bash(git log *) Bash(git show *) Bash(git diff *) Bash(git status *)
  Bash(git rev-parse *) Bash(git symbolic-ref *) Bash(git merge-base *)
  Bash(git branch *) Bash(git grep *) Bash(git worktree *) Bash(git fetch *)
  Bash(git switch *) Bash(git checkout *) Bash(git cherry-pick *)
  Bash(git restore *) Bash(git add *) Bash(git commit *)
  Bash(git tag *) Bash(git merge *) Bash(git merge-tree *)
  Bash(git push -u origin *)
  Bash(glab mr view *) Bash(glab mr create *) Bash(glab mr update *)
  Bash(glab mr note *) Bash(glab api *) Bash(gh api *)
  Bash(gh pr view *) Bash(gh pr create *) Bash(gh pr comment *)
  Read Grep Glob
---

The `allowed-tools` grant above covers the whole job, local and remote, so the run is not interrupted by a prompt per cherry-pick or per push. **That is exactly why the publish checkpoint in phase 3 is mandatory** — the grant replaced eleven context-free permission prompts with one confirmation that shows the full outward-facing manifest at once. Removing the prompts does not remove the confirmation; it relocates it somewhere the user can actually see what is about to happen.

Still excluded, and still prompting: `git rebase`, `git reset`, `git branch -D`, and bare `git push` — the grant is `git push -u origin *` only, so an arbitrary refspec, a branch deletion (`git push origin :branch`), or a push to another remote all stop. `--force` after a matching prefix would slip through the pattern, so the guardrail against it is a rule this skill follows, not something the allowlist enforces. The same caveat applies to `glab api` / `gh api`, granted for user lookup: the pattern cannot distinguish a `GET` from a `DELETE`, so the only writes this skill makes through them are the ones named in the checkpoint manifest. `glab mr update` is granted for one purpose — setting reviewers on the MRs this run just created — and is never pointed at a pre-existing MR.

The grant lasts only the turn the skill is invoked on and clears on the user's next message, so the approval gate ends it: when handing off to phase 2, tell the user to re-invoke `/split-branch execute` to re-apply it, or expect a prompt per command.

Take a branch that grew several unrelated changes and turn it into a set of correctly scoped branches, **each with its own MR/PR**.

**The target shape: every branch sits directly on the current base and any two of them merge in either order without a conflict.** That is the property being engineered, and it is the one that makes the result usable — a reviewer merges whichever MR is ready, nobody rebases a chain, and no branch is blocked behind another's review round.

Everything else bends to it. Two themes that cannot be made conflict-free apart get **fused into one branch**, even though that branch then covers more than one topic. One slightly broad MR is cheaper than two MRs where the second needs a rebase and a conflict resolution the moment the first lands. Stacking is the escape hatch, not a co-equal option (see [When fusing is wrong](#when-fusing-is-wrong)).

The hard part is not the git mechanics — it is deciding which themes can stand apart. Do that with evidence (shared hunks, symbol dependencies, pairwise merge simulation, trial cherry-picks), not with a guess from the commit subjects.

Three phases, with a **mandatory stop after phase 1**:

1. **Analyze → recommend.** Read-only. Produce a split plan and stop. No branches created, no commits, nothing written.
2. **Execute.** Only after the user approves the plan. Create branches locally off the fetched base, verify the union reproduces the original tree and that every pair of branches merges cleanly.
3. **Publish.** Push each branch, open its MR/PR, and comment on the original MR listing what it was split into.

Phase 1's approval covers the **scope** of the split, including that MRs will be created — the plan must say so. Phase 3 then confirms the **manifest** at its checkpoint, once, immediately before anything leaves the machine. Two gates, different questions: "is this the right split?" then "here is precisely what is about to be pushed and opened."

Never skip straight to phase 2, even if the user's request sounds like "just split it" — the plan is cheap and the decisions are the deliverable.

## Pre-flight

1. Confirm CWD is in a git repo: `git rev-parse --git-dir`. If not, stop.
2. `git status --porcelain` must be empty. Uncommitted work would be silently stranded by the branch surgery. If dirty, stop and tell the user to commit or stash.
3. Confirm no operation is in progress (`.git/rebase-merge`, `.git/rebase-apply`, `MERGE_HEAD`, `CHERRY_PICK_HEAD`). If one is, stop — the user is mid-something.
4. Read the current branch: `git rev-parse --abbrev-ref HEAD`. This is the branch being split.
5. **Resolve the base branch** in this order, stopping at the first that works:
   - An open MR/PR for this branch — its target is authoritative:
     - `glab mr view --output json` → `.target_branch`
     - `gh pr view --json baseRefName -q .baseRefName`
   - `git symbolic-ref refs/remotes/origin/HEAD` → strip `origin/`
   - `main` if it exists, else `master`
   - Ask, if all of the above fail.
6. **Fetch the base and pin `BASE` to the remote ref**: `git fetch origin <base>`, then use `origin/<base>` everywhere below. Every branch is cut from the current tip, so the split is born rebased and the pairwise merge checks are run against the tree the MRs will actually merge into. A local `main` that is three days stale would verify a split against a past that no longer exists.
7. Note whether an MR/PR is already open on this branch and whether the branch has been pushed (`git rev-parse --verify origin/<branch>`). Both change what phase 2 is allowed to do — record them, do not act yet. If an MR is open, also record its **reviewers and assignees** from the same payload; they are the default for the replacements.
8. Detect the forge for later: `git remote get-url origin`. GitLab host → `glab`; `github.com` → `gh`. For a self-hosted host matching neither substring, probe `glab auth status` and `gh auth status` and pick whichever is authed against that host.

## Phase 1 — Analysis

Everything in this phase is read-only. Run the cheap commands first; only reach for trial cherry-picks on the groups where the answer is genuinely unclear.

### 1. Inventory

```bash
BASE=origin/<base>     # from pre-flight, already fetched
git log --oneline "$BASE..HEAD"
git diff --stat "$BASE...HEAD"
git log "$BASE..HEAD" --format='=== %h %s' --name-only
```

The last command is the workhorse — it gives per-commit file sets, which drives the grouping.

### 2. Group commits into themes

A theme is a **shippable unit of intent**, not one commit. Merge into one theme:
- A fix and its follow-up fixup (`fix: X` followed by `fix: compare Y correctly` touching the same new file).
- A change and its tests.
- A change and the docs/infra artifact that describes it.

Signals that two commits are one theme: they touch the same new module; one's diff modifies a function the other introduced; the later commit's message references the earlier's concept.

Do **not** group by commit-message prefix. Five `fix:` commits can be three themes.

### 3. Find the edges between themes

An **edge** between two themes means they cannot go on separate branches without one of them paying for it later — a conflict, a rebase, or a review that does not make sense alone. Under the any-order goal an edge is resolved by **fusing** the two themes onto one branch, not by stacking them.

For every pair of themes, check four things. Any single hit is an edge.

**a. Hunk overlap in shared files.** File-level overlap alone means nothing — two themes can touch `pipeline.py` a thousand lines apart. Get line ranges:

```bash
for c in <commits>; do
  echo "=== $c"
  git show "$c" --unified=0 -- <shared-file> | grep -E '^@@'
done
```

Read the `@@ -old +new @@` ranges *and* the function context git prints after them. Overlapping or adjacent (within ~20 lines, or same function per the hunk header) → edge. Distant hunks in different functions → no edge, but (d) is what actually decides it.

**b. Symbol dependency.** Does the later theme reference something the earlier one introduced?

```bash
git show <earlier> | grep -E '^\+.*(def |function |class |const |export )' # symbols added
git grep -n '<symbol>' $(git show --name-only --format= <later>)           # used by later?
```

Also count as symbol dependency: a config, migration, dashboard, view, or doc in theme B that only makes sense because theme A shipped (a BigQuery view over an event A emits, a README paragraph about A's flag). This one is an edge even when the merge is clean — B merging first would ship a reference to something that does not exist yet, and "any order" has to mean any order *is correct*, not just conflict-free.

**c. Trial cherry-pick.** Ground truth for "does this theme even stand alone", used when (a) and (b) are ambiguous. Do it in a scratch worktree so the user's checkout is never touched:

```bash
WT=$(mktemp -d)
git worktree add --detach "$WT" "$BASE"
git -C "$WT" cherry-pick -n <commits of theme>   # -n: no commit, no message churn
# clean apply? then optionally run the repo's test command inside $WT
git -C "$WT" cherry-pick --abort 2>/dev/null; git worktree remove --force "$WT"
```

Clean apply **and** green tests in isolation → the theme can stand on its own branch. Conflict or red tests → edge with whatever it needed.

Always clean up the worktree, including on failure.

**d. Pairwise merge simulation.** The check that actually enforces the any-order goal, and the only one that catches conflicts (a) misses — a rename against an edit, two insertions at one anchor, a whitespace reflow. `git merge-tree` runs a real three-way merge with no worktree, no checkout, and no cleanup, and exits non-zero on conflict:

```bash
git merge-tree --write-tree <tip-a> <tip-b> || echo "CONFLICT: a x b"
```

Exit 0 means the pair merges clean in either order. Exit 1 prints the conflicted paths — read them, they name exactly which hunk needs to move or fuse. (No `--merge-base` needed: both tips are cut from `$BASE`, so git finds it. Symmetric, so one direction per pair is enough.)

In phase 1 there are no branch tips yet, so build the candidates as throwaway commits in a scratch worktree (cherry-pick each theme onto `$BASE`, `git commit`, note the SHA) and run the pairwise loop over those SHAs. It is the same work phase 2 will do, done once and thrown away, and it is worth it: a split that conflicts with itself is the failure mode this skill exists to avoid, and finding it now costs a worktree instead of five open MRs.

Every conflicting pair is an edge. Fuse, or move the offending hunk (section 4) until the pair comes back clean.

### 4. Find stray hunks

Scope creep hides *inside* commits, not only between them. A commit titled "rank test files below source" that also carries a Makefile fix is two themes in one commit. Look for files in a commit's `--name-only` list that have nothing to do with its subject, and read those hunks:

```bash
git show <commit> -- <suspect-path>
```

Classify each stray hunk: its own theme, or belongs to a different theme in this branch. Flag both — phase 2 has to relocate them, and that is the part most likely to go wrong.

**Generated churn is never its own branch.** A lockfile reformat (`uv.lock` gaining `upload_time` on every entry, `package-lock.json` reordering), a regenerated snapshot, a vendored bump — huge diffs with nothing to review. They pass the mechanical tests for a standalone theme (no edges, merges clean with everything), and that is exactly the trap: an MR nobody can read and nobody needs to. Pull the churn *out* of the feature commit so it does not bury a real review, then land it on whichever branch is already the small housekeeping one — CI config, ignore files, dependency chores. Name that branch for the group (`repo-housekeeping`), not for any one member.

Only give generated churn its own branch when there is no housekeeping branch to join *and* the churn is semantically load-bearing (a genuine dependency bump, not a format rewrite). Verify which it is before deciding: for a lockfile, diff the package names and versions, not the line count — `git show <c> -- uv.lock | grep -E '^[+-]name = '` empty means pure format.

Docs touched by many commits (`AGENTS.md`, `CLAUDE.md`, `README.md`, changelogs) are where the any-order goal is won or lost. They are usually not a theme — they are per-theme hunks that happen to share a file — and splitting them by hunk is the single most reliable way to manufacture a conflict.

**Default: one shared doc file, one branch.** Give the whole file's diff to the branch with the strongest claim on it and let that branch document its siblings too. The doc says three things happened; the three things are separately reviewable in code regardless. Split a doc by hunk only when the hunks are in genuinely distant sections *and* check (d) says the pair is clean — never on the strength of "these paragraphs are unrelated", which is a statement about prose, not about git's merge granularity.

Two things this rule exists to absorb, both learned the hard way:

- **A wholesale rewrite of a doc section cannot be partitioned.** When one commit rewrites every bullet in a contiguous block while other commits each edit one bullet inside it, git's merge granularity is the *block*, not the bullet — the rewrite conflicts with every sibling no matter how carefully the hunks are assigned. The old answer was a separate docs branch that lands last behind a merge dependency, which blocks code review behind prose. The answer now is to fuse: the rewrite and every hunk inside its block ship on one branch.
- **Two branches inserting at the same anchor conflict even with disjoint content.** Git cannot order two insertions at one point, so two themes each adding a bullet to the same list conflict. Both bullets go on one branch.

### 5. Assign themes to branches

Every branch targets the base. The question is not *where* a theme goes but *which themes share a branch*.

Take the themes and their edges from section 3 as a graph, and **put each connected group of themes on one branch**. A theme with no edges gets its own branch. Two themes joined by an edge — hunk overlap, symbol dependency, or a conflicting pair — go on the same branch, even if their topics are unrelated, and the branch's name and MR title then describe the group rather than one topic ("test-context ranking and the Makefile fix it exposed").

Then apply, in order:
- **Prefer fusing over stacking, always.** A stack trades one merge conflict you would resolve once for a rebase on every review round of the parent, forever. The fused branch is one MR that merges when it is ready.
- **Prefer fusing over an accepted conflict.** "It's only a few lines, whoever merges second resolves it" is a cost paid by a person at merge time, on an MR that had already passed review. Pay it now, at split time, where it costs nothing.
- Fuse a theme into a sibling when it is small *and* semantically part of it. A standalone unrelated one-liner with no edges is still fine as its own branch — small unrelated MRs merge in minutes.
- More than ~4 branches from one split is a smell; so is one branch carrying the entire original diff. If fusing collapsed everything into one group, the branch genuinely was not splittable — say that instead of forcing a split that conflicts.

#### When fusing is wrong

Fusing has one real ceiling: a branch big enough that nobody reviews it properly is worse than a stack. Stack instead of fusing when **both** hold:

- The fused branch would be large enough to defeat review (roughly: more than a few hundred changed lines across unrelated subsystems, or a reviewer would need two different specialists).
- The dependency is one-directional and stable — B builds on A, A never needs to know about B — so the child rebases predictably rather than repeatedly.

Then, and only then, stack B on A, target B's MR at A's branch, and say in the phase 1 report that this pair is the exception and why. Everything else in the split still merges in any order; a stack is a local exception, never the shape of the whole plan.

### 6. Report and STOP

Output, and nothing more:

- **Table**: branch → themes it carries → commits → key files → target (`main`, or a sibling branch for the stacked exception) → one-line why.
- **Fusion decisions**: every branch carrying more than one theme, with the edge that forced it (`pipeline.py` hunks at L580 and L536, same function → fused). Name the file and line ranges; a bare "these are related" is not a finding. A fused branch is the plan's most questionable call, so it is the one the user most needs to see the reason for.
- **Pairwise merge results**: the (d) matrix, stated as a result — "all 6 pairs merge clean" — or the pairs that did not and what was fused to fix them.
- **Stray hunks** to relocate, by path, with their destination branch.
- **Proposed branch names**, matching the repo's existing convention (check `git branch -a --sort=-committerdate | head -20` and merged branch names for `fix/`, `feat/`, bare, or ticket-prefixed style). A fused branch's name describes the group, not its largest member.
- **Risks**: any branch whose split needs same-file hunk surgery, any branch whose tests you could not verify in isolation, and any stacked exception.
- **Merge order**: normally the sentence "none — any order". If a stacked exception exists, name the one pair that has an order.
- **What execution will do**, explicitly: create N branches, commit on them, push them, open N MRs with their targets, assignee, and reviewers named, comment on the original MR, and leave the original branch itself untouched. Naming the MRs here is what makes the approval cover them.

Then ask for approval, offering three answers: **execute** (branches + MRs), **branches only** (stop after phase 2), or **script mode** (emit a reviewed shell script the user runs instead). Or the user adjusts the plan.

## Phase 2 — Execution

Only after explicit approval.

### Safety net, first

```bash
git tag "presplit/$(git rev-parse --abbrev-ref HEAD)" HEAD
```

Tell the user the tag name. It is the single-command undo for everything below. The original branch is also left in place, untouched — never delete or reset it.

### Build the branches

Every branch is cut from `$BASE` — the fetched remote ref, so each one is born rebased on the current tip:

```bash
git switch -c <branch-name> "$BASE"          # or "$PARENT_BRANCH" for a stacked exception
```

Build the stacked exception, if the plan has one, after its parent.

Then bring the branch's content over, cheapest applicable method:

**Whole commits, no strays** — cherry-pick in original order:
```bash
git cherry-pick <c1> <c2>
```

**Commit split by path** — pick without committing, drop the paths that belong elsewhere:
```bash
git cherry-pick -n <commit>
git restore --staged --worktree -- <path-belonging-to-another-theme>
git commit -c <commit>          # reuse the original message, edit the subject to match the narrowed scope
```

**Commit split inside one file** (the AGENTS.md case) — take the file, then remove the foreign hunks by hand:
```bash
git cherry-pick -n <commit>
git checkout HEAD -- <mixed-file>            # reset the file
git show <commit> -- <mixed-file>            # read the hunks
# re-apply only this theme's hunks with Edit, then:
git add <mixed-file> && git commit -c <commit>
```

Rules while building:
- **Rewrite commit messages to the new scope.** A narrowed commit whose body still describes the removed part is a lie in the history. Keep the original body's reasoning for the part that stayed; drop the rest.
- Never `git commit -a`. Stage explicitly.
- On a cherry-pick conflict on a branch the analysis called independent, stop: the analysis was wrong. Abort, report, re-plan. Do not resolve conflicts to force a plan through.

### Verify the split

Four checks, all required. Report each one's result explicitly.

**1. Union equals the original.** The strongest invariant — the split must lose nothing:

```bash
WT=$(mktemp -d); git worktree add --detach "$WT" "$BASE"
for b in <branches>; do
  git -C "$WT" merge --no-edit "$b" || { echo "MERGE FAILED: $b"; git -C "$WT" merge --abort; break; }
done
UNION=$(git -C "$WT" rev-parse 'HEAD^{tree}')
REFERENCE=$(git merge-tree --write-tree "$BASE" "presplit/<original>")   # the original, on the same base
git diff --stat "$REFERENCE" "$UNION"              # MUST be empty
git worktree remove --force "$WT"
```

Abort and stop on the first failed merge — carrying on into a conflicted index makes every later result meaningless.

The reference is the *original branch merged onto the same `$BASE`*, not the `presplit` tag itself. Since the branches are cut from the fetched tip, diffing straight against the tag would report every upstream commit that landed since the original forked as if the split had introduced it. If that `merge-tree` conflicts, the base moved under the original branch — report that as its own finding (the user has a rebase to do either way) and fall back to building the union from the original's fork point, `git merge-base "$BASE" presplit/<original>`.

Non-empty diff = content was dropped or duplicated. Show the diff, do not paper over it.

**2. Every pair merges in any order.** The deliverable, verified on the real branches this time rather than the phase 1 candidates:

```bash
for a in <branches>; do for b in <branches>; do
  [ "$a" \< "$b" ] || continue
  git merge-tree --write-tree "$a" "$b" >/dev/null || echo "CONFLICT: $a x $b"
done; done
```

Silence means the whole set merges in any order. Any output means the plan did not hold — name the pair and the conflicted paths, fuse them, and rebuild. Do not ship a set that fails this and mention it as a caveat; the caveat *is* the thing the split was for. (A branch stacked as the documented exception is excluded from this loop — it conflicts with its parent by construction.)

**3. Each branch stands alone.** On every branch, run the repo's own gates — read them from `CLAUDE.md`/`AGENTS.md`/`Makefile`/`package.json`, do not invent commands. Typically lint + type-check + tests. A branch that only passes when its sibling is present has an edge the analysis missed; report it and fuse rather than quietly stacking.

**4. No branch is empty.** `git log --oneline "$BASE..<branch>"` non-empty for each.

### Script mode

If the user chose script mode, write the whole sequence — tag, branch creation, cherry-picks, path restores, verification — to a file in the scratch directory as a `set -euo pipefail` script with a comment above each theme, and hand back the path. Run nothing. The verification block goes in the script too.

Append the phase 3 push, `mr create`, and breadcrumb-comment commands **commented out** at the bottom, so the user gets them ready to paste but a stray `bash script.sh` cannot reach the remote.

## Phase 3 — Publish

Runs only after phase 2's four verifications pass. A branch that failed its gates does not get an MR; report it and leave it local.

### Publish checkpoint — stop here

**Stop and confirm before the first `git push`.** The permission layer will not stop you: pushing and MR creation are pre-approved in `allowed-tools`, so this checkpoint is the only thing standing between a verified split and a remote that has five new MRs on it. Nothing here is reversible by `git branch -D`.

Resolve reviewers first (below) — they are part of what the manifest has to show. Then print the full manifest and wait for a yes:

- **Push**: every branch, with its commit count and whether the remote ref already exists.
- **Create**: each MR as `<source> → <target>`, with its title, assignee, and reviewers.
- **Merge order**: "none — verified any-order", or the one stacked pair if the plan has the documented exception.
- **Comment on**: the original MR by iid, with the comment body shown verbatim.
- **Not doing**: closing the original MR, force-pushing, touching the original branch.

Re-confirm from scratch if anything changed since the phase 1 plan — a branch dropped for failing verification, a renamed branch, a different target. Do not assume the earlier approval still describes reality.

If the user declines or is silent on any part, publish nothing and hand back the ready-to-paste commands.

### One MR per branch

**GitLab (primary):**
```bash
git push -u origin <branch>
glab mr create --source-branch <branch> --target-branch <base> \
  --title "<title>" --description "<why + what>" \
  --assignee "<current-user>" --remove-source-branch --yes
glab mr update <new-iid> --reviewer "+alice,+bob"
```

**GitHub:**
```bash
git push -u origin <branch>
gh pr create --base <base> --head <branch> --title "<title>" --body "<why + what>" \
  --assignee @me --reviewer "<reviewers>"
```

Rules:
- `--target-branch` is the base for every MR. The one exception is a branch stacked under the [When fusing is wrong](#when-fusing-is-wrong) rule, whose target is its **parent branch** — get that wrong and the MR diff shows the parent's changes too, which is exactly the noise the split existed to remove. State each MR's target back to the user as you create it, and create the parent's MR first so the child's target exists on the remote.
- Each description **opens with a link to the original MR**, not its branch name — `Split out of !141.` on GitLab, `Split out of #141.` on GitHub. The forge renders that as a live reference with the title on hover, so a reviewer landing cold gets one click to the full context; a bare branch name is a string they have to go look up, and it is dead the moment the branch is deleted. The iid is already in hand from pre-flight. Only when there was no original MR does the branch name appear instead.
- Then say what the branch does. A fused branch's description names every topic it carries and says why they ship together, citing the evidence from phase 1 (the shared file and line ranges, the symbol one theme needs from another) — otherwise the next reviewer files it as scope creep, which is what this skill is for.
- **No `## Testing` section.** The split ran the repo's gates on every branch already and reported the results to the user; repeating "635 passed" in the MR body is a claim the pipeline is about to verify for real, on the forge, in public. The commits and the diff are the content. This overrides any repo convention asking for test evidence in an MR description — that convention is for MRs whose author wrote new code, not for a mechanical re-slicing of code that was already tested as a whole.
- Keep it short. These MRs are narrow by construction; a description longer than the diff it explains is its own kind of noise.
- Capture each new MR's iid/number and URL from the create output — the breadcrumb comment needs them.

### Assignee and reviewers

**Assignee**: always the user running the split. They own the original branch, so they own its replacements. Resolve with `glab api user` (`.username`) or `gh api user`, not a hardcoded name. On GitLab, an MR created via `glab` is often already assigned to its creator — check before setting, and don't report setting something that was already true.

**Reviewers**: **ask, once, at the publish checkpoint, and apply the one answer to every new MR.** Never guessed and never carried across silently — a split turns one review request into four or five, and who gets four notifications is the user's call, not an inference.

Ask with the candidates already resolved, so the answer is usually one keystroke:
- Reviewers the user passed when invoking the skill (`/split-branch --reviewer alice,bob`) skip the question entirely — that *is* the answer.
- Otherwise, offer the **original MR's** reviewers as the default. A split's replacements usually want the same eyes, and on a bot-reviewed repo that set includes the review bot, whose username is project-scoped and unguessable (`project_<id>_bot_<hash>`) — read it off the payload, never construct it.
- Offer **none** as a real answer, and accept a free-typed list.

Apply the resolved list with `glab mr update <iid> --reviewer "+alice,+bob"` after each MR is created, not with `create --reviewer`. The `+` prefix adds rather than replaces, so it composes with whatever the project's approval rules already put on a fresh MR.

Two rules on the list itself:
- **Drop the current user from it.** They are the author of every MR this skill opens. GitLab does not document whether it rejects the author as their own reviewer, and if it does, the whole call fails and *nobody* gets set — so filter rather than find out.
- Resolve one MR's reviewers, then reuse that same list; do not re-ask per MR.

Setting a reviewer sends notifications, so the resolved list belongs in the checkpoint's manifest like everything else — name the people, not "the usual reviewers".

### Merge order

There should not be one. The pairwise check in phase 2 is what replaced it: a split whose branches merge in any order needs no coordination, and **wanting a merge dependency is the signal that two branches should have been fused.** Go back and fuse them rather than encoding an order on the forge — a dependency orders merges but does not resolve conflicts, so it buys a blocked MR and still leaves someone a conflict.

The stacked exception is the only order this skill produces. State it in both descriptions, link parent from child, and leave it at that; the forge's dependency feature is paid-tier on GitLab and absent on GitHub, and a two-MR order does not need machinery.

### Breadcrumb comment on the original MR

If the original branch had an open MR, comment on it as soon as the new MRs exist. Without this, the original MR is a silent orphan and reviewers keep reviewing a diff that has been superseded.

```bash
glab mr note create <original-iid> --message "<body>"   # GitLab; bare `mr note` is deprecated
gh pr comment <original-number> --body "<body>"         # GitHub
```

Body: one line saying this MR was split, then one line per replacement — MR reference, target branch, and a short scope description. Close with what happens to this MR (see below). Reference MRs by `!<iid>` on GitLab and `#<number>` on GitHub so the forge auto-links them.

```
Split into scoped MRs — this branch had grown several unrelated changes.

- !126 → main — rebase/force-push reuse detection and its telemetry
- !127 → main — auxiliary token accounting
- !128 → main — test files ranked below source in review context

Superseded by the above; closing once they merge.
```

If there was no original MR, skip this step and say so — do not invent a place to put the comment.

### The original MR's fate

Closing it is the user's call. Offer it, never do it unprompted, and never delete the original branch — it is the fallback if a split branch turns out wrong.

## Wrap-up reminder

End every run with this block. It is the only record the user gets of what the skill changed on their behalf.

- **Commits were made** on the new branches. This skill commits by design; that overrides a standing "never commit" rule for the split itself and nothing else.
- **Branches and MRs created**, one line each: `<branch> → <target>` with its MR link, or "local only, not pushed" if it stopped at phase 2. Flag any branch that carries more than one topic, and why.
- **Merge order**: state plainly that the set was verified to merge in any order — that is the property the user is relying on when they merge one of these at 5pm without checking the others — or name the stacked exception.
- **Undo local work**: `git switch <original>` then `git branch -D <new branches>`. `presplit/<original>` is the tag pinning the pre-split HEAD. Note that this does **not** retract anything already pushed or any MR opened — those need closing on the forge.
- **The original branch and its MR are untouched** — the MR is still open against the un-split diff, now with a breadcrumb comment. Decide whether to close it.
- Any verification that did not pass cleanly, restated here even if reported earlier.

## Guardrails

- Read-only until the plan is approved. No branch, tag, or commit on a real ref in phase 1 — the trial cherry-picks and the pairwise merge candidates live in a scratch worktree that is always removed, and `git merge-tree` writes only loose objects, no refs.
- Every branch targets the base and merges in any order, unless a stacked exception was named in the plan and approved. Do not introduce a stack, or accept a known conflict between siblings, during execution.
- Never delete, reset, or force-push the original branch. Never `git push --force` anything, ever, without a separate explicit request.
- Never `git rebase -i` to do the split — non-interactive in this environment, and cherry-pick onto fresh branches is both safer and reversible.
- Always clean up scratch worktrees, including on the error path.
- If the union check fails, say so plainly with the diff. A split that silently drops a hunk is worse than no split.
- Never open an MR for a branch whose verification failed, and never close the original MR.
- Never push or create an MR without passing the phase 3 checkpoint, even though `allowed-tools` pre-approves those commands. A pre-approved command is not an authorized one.
- If analysis and reality disagree (a pair the plan called clean conflicts in phase 2), stop and re-plan. Do not force the plan, and do not ship the conflict as a caveat.
