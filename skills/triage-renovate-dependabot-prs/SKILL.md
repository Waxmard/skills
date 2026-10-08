---
name: triage-renovate-dependabot-prs
description: >
  Mass-merge renovate (GitLab) and dependabot (GitHub) dependency-bump branches
  into the current feature branch, one at a time, with diff review, reasoned
  risk assessment (changelog read + call-site cross-reference, not just
  semver), and auto-detected post-merge checks. Auto-advances through
  branches, automatically deferring stale-base conflicts for bot rebase and
  preferring bounded upgrade repairs over skips. Real merge conflicts get a
  proposed resolution gated on user acceptance. MEDIUM/HIGH decisions and
  required merge permissions remain gated.
  Language-agnostic: handles JS/TS, Python, Rust, Go, Ruby, Java/Kotlin, and
  any other ecosystem the bots target. Trigger: "merge renovate prs",
  "merge renovate mrs", "merge dependabot prs", "merge bot prs",
  "drain renovate branches", "triage renovate prs",
  "triage dependabot prs", or /triage-renovate-dependabot-prs.
---

# Triage dependency updates

Merge dep-bump branches into the **current branch** one at a time. The user's pattern: create a feature branch off the target (`dev`/`main`), drain bot branches into it, then merge it into target as one safer review. The feature branch must already exist and be checked out.

Covers **Renovate** (GitLab, `renovate/*`) and **Dependabot** (GitHub, `dependabot/*`). No `gh`/`glab` CLI required — discovery is pure `git`. The risk-read and post-merge-check steps detect the ecosystem from manifest files in the repo root.

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- `git` (discovery is pure git; no `gh` or `glab` needed)
- The package manager and check tools of each ecosystem in the repo (the install and check commands in step 5 of the per-branch loop)
- `npx` / `uvx` (optional), to run a bumped linter or formatter at its new version
- `crane` (optional), to compare container-image bumps

Install missing tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## Pre-flight

Before step 1, check the prerequisites:
```bash
command -v git >/dev/null || echo "missing: git"
```
If it prints, stop and tell the user to install git.

1. Confirm CWD is inside a git repo (`git rev-parse --git-dir`). If not, stop and ask.
2. Read `git rev-parse --abbrev-ref HEAD`. If it is `main`, `master`, `dev`, `develop`, `release/*`, or `staging` → **refuse** and explain: the pattern requires a feature branch as a buffer. Ask the user to switch or override.
3. Note the likely target branch (heuristic: whichever of `dev` / `main` exists locally and is not HEAD). Use it only for context messages, not for actions.
4. `git fetch origin --prune` — refresh remote refs and drop deleted bot branches.
5. Detect the ecosystem(s) present in the repo root. The same repo can mix several (e.g. a Rust binary with a JS frontend in a subdir). Note them for steps 2 and 5 of the per-branch loop. For each detected ecosystem, `command -v` the package manager its install-from-lock command uses (step 5 of the per-branch loop); if one is missing, stop and name it, because post-merge checks can't run without it.

## Discovery

```bash
git ls-remote --heads origin 'renovate/*' 'dependabot/*' | awk '{print $2}' | sed 's|^refs/heads/||'
```

Iterate with `while read -r`, never `for b in $(…)` — bot branch names arrive newline-joined and a `for` loop word-splits them into one mangled arg:

```bash
git ls-remote --heads origin 'renovate/*' 'dependabot/*' | awk '{print $2}' | sed 's|^refs/heads/||' \
| while read -r branch; do
    echo "=== $branch ==="
    git log -1 --format='%s' "origin/$branch"
    git merge-base --is-ancestor "origin/$branch" HEAD && echo "already merged"
  done
```

For each branch, show:

- Branch name
- HEAD commit subject: `git log -1 --format='%s' "origin/${branch}"`
- Whether it is already merged into HEAD: `git merge-base --is-ancestor "origin/${branch}" HEAD && echo "already merged"`

Filter out anything already merged. Present the remaining list to the user (numbered) with each branch's redundant/real verdict — for context, **not** for a decision. Then **proceed automatically**: process branches top-to-bottom, skipping any flagged redundant, without asking which to start from. The user's one decision per branch comes later, at the pre-merge gate (step 3).

**Flag redundant branches (payload already in HEAD).** A branch can be *not* an ancestor of HEAD yet contribute nothing new — its bump already landed via a sibling branch that forked off a newer `main`. This is common when bot branches forked weeks apart: the older one's diff looks huge but is mostly `main`'s later progress it lacks, not changes it would add. Two cheap signals, computed at discovery:

```bash
# Fork age — an old base means a misleading two-dot diff and likely-stale payload
git log -1 --format='%h %s (%cr)' "$(git merge-base HEAD origin/${branch})"
# The branch's OWN contribution (three-dot) — what it actually changes, not main's drift
git diff --stat "HEAD...origin/${branch}"
```

If the three-dot delta is tiny and that exact bump is **already satisfied in HEAD** (check the manifest value), mark the branch **redundant → recommend skip**: merging yields a no-op merge commit and the bot auto-closes the MR/PR on its next run once it sees the dep already current on `main`. Always read the branch's contribution via three-dot (`HEAD...origin/${branch}`), never two-dot (`HEAD origin/${branch}`) — two-dot on an old-base branch shows thousands of lines of `main`'s later work that the merge will **not** revert, and reads as a terrifying diff that isn't real.

**Second redundancy case: the target dep no longer exists in HEAD.** Check the dep is still in the manifest at all (`git show HEAD:package.json`, `git show HEAD:Cargo.toml`, or the ecosystem's equivalent). A branch whose target was *removed* by later work looks identical to a real bump in three-dot (`^16.4.0 → ^17.0.3`) but merging it produces a **modify/delete conflict**, not a bump — the branch modified a line HEAD deleted. Mark it **redundant → recommend skip**, with the reason spelled out as "target dep no longer exists in HEAD" so the user isn't left guessing why a real-looking version change is being skipped. The bot closes these once the removal lands on the target.

**Onboarding branches are config adoption, not bumps.** `renovate/configure` (Renovate's onboarding MR) or a branch whose only payload is a first `.github/dependabot.yml` changes no dependency, so the signal table doesn't apply. Assess who starts receiving bot MRs (downstream forks inherit the file via template sync unless `.gitattributes` marks it `merge=ours`) and whether the config matches the repo's renovate standard (e.g. MR limits, release-age delay). Gate it as MEDIUM with merge + repair (expand to the standard), merge as-is, and skip as options.

**Check for local drift before ranking anything.** Identify the bot branch's actual PR/MR target from its metadata or bot configuration; the pre-flight target is only a hint. Run `git log --oneline origin/<target>..HEAD`, then filter that range to the manifests and lockfiles. Local dependency changes can make a bot branch stale, but they do not prove every branch conflicts. Use each branch's contribution and merge prediction to identify affected branches. Automatically defer stale-branch conflicts for bot rebase under step 3; do not ask the user to choose that path.

## Per-branch loop

Process branches automatically in discovery order, skipping redundant branches and automatically deferring stale-branch conflicts for bot rebase. For each remaining branch, show the change and assess the upgrade with any bounded compatibility repair before the step-3 gate. After checks pass, auto-advance. Actual conflicts get a proposed resolution that waits for acceptance (step 4); check failures hand control back under step 5.

### 1. Show the change

```bash
git log -1 --format='%s%n%n%b' "origin/${branch}"
git diff --stat "HEAD...origin/${branch}"
# Show manifest deltas across all common ecosystems — only those present produce output
git diff "HEAD...origin/${branch}" -- \
  'package.json' 'package-lock.json' 'yarn.lock' 'pnpm-lock.yaml' \
  'pyproject.toml' 'uv.lock' 'poetry.lock' 'requirements*.txt' 'Pipfile*' \
  'Cargo.toml' 'Cargo.lock' \
  'go.mod' 'go.sum' \
  'Gemfile' 'Gemfile.lock' \
  'pom.xml' 'build.gradle*' 'gradle.lockfile' \
  'composer.json' 'composer.lock' \
  'mix.exs' 'mix.lock' \
  'Dockerfile' '.github/workflows/*.yml' '.gitlab-ci.yml'
```

Predict the merge before the gate — `git merge-tree --write-tree HEAD "origin/${branch}"` computes the result **without touching the working tree** (exit 1 plus `CONFLICT` lines names the conflicting files). Report predicted conflicts. When bot rebase can remove stale-base conflicts, automatically defer under step 3 instead of offering a merge/skip choice. Do not attempt a merge to discover conflicts.

If the diff is small (<200 lines), show full diff. Otherwise show stat + manifest deltas.

### 2. Risk read

Don't classify by semver label — a linter could apply that rule, and it isn't what the user sees. Read the release and the repo: every MEDIUM-or-above signal below is a trigger to go read, not a verdict to report. Compute it silently; never present a "nominal: HIGH" line — the user only sees the actual verdict in ## Reasoned verdict.

#### Signal (internal trigger, not shown)

Parse the dep delta from the manifest diff and classify. The categories are stack-agnostic — only the example tools differ per ecosystem. This table decides whether step 2b below runs; it is never itself the output.

| Signal | Triggers deep read? | Notes |
|---|---|---|
| Major version bump (`1.x.y → 2.0.0`) on any direct dep | Yes | Breaking changes per semver — unverified until read. |
| Major bump of linter / formatter / type-checker | Yes | Examples by ecosystem: JS/TS (eslint, prettier, biome, tsc), Python (ruff, mypy, black, pyright), Rust (clippy, rustfmt — rare, tied to toolchain), Go (golangci-lint, staticcheck), Ruby (rubocop). |
| Major bump of build / packaging tooling | Yes | Examples: JS (vite, webpack, rollup, esbuild, turbopack), Python (uv, poetry, hatch, setuptools), Rust (cargo itself rarely bumps via bot; build-rs deps do), Go (rarely bot-bumped), JVM (gradle, maven plugins). |
| Major bump of framework / runtime | Yes | Examples: React, Vue, Angular, Next, Django, FastAPI, Rails, Spring, Actix, Axum, Gin. |
| Touches `.github/workflows/`, `.gitlab-ci.yml`, `Dockerfile`, `docker-compose.*`, `Containerfile` | Yes | Infra/CI change — auto-checks won't catch pipeline breakage, so the deep read below can't fully clear this one either; still needs a human watching the pipeline post-merge. |
| Touches build / lint config files | Yes | Examples: `tsconfig.json`, `vite.config.*`, `webpack.config.*`, `eslint.config.*`, `pyproject.toml` (ruff/mypy sections), `Cargo.toml` (features/edition), `.golangci.yml`. |
| Minor bump (`1.2.x → 1.3.x`) on direct dep | No | Actual defaults to LOW; escalate only if something else about the PR looks off. |
| Patch bump (`1.2.3 → 1.2.4`) | No | Actual defaults to LOW. |
| Lockfile-only delta | No | Actual defaults to LOWEST. Watch for hidden major bumps inside the lockfile (see pitfalls) — if one's found, that dep triggers a deep read same as a manifest-level major. |
| Grouped PR (renovate often bumps 5+ packages at once) | Inherit highest | Score each dep individually before rolling up — don't gate on the title alone. |

#### Reasoned verdict (the only thing shown)

Complete the deep read automatically for every triggering signal, including hidden transitive majors. Do not ask the user to select **inspect** to initiate required research. Prefer the release/changelog URLs in the commit body over search. If research is blocked, finish reachable local inspection and state exactly what remains unverified before asking.

For anything the signal table triggers:

1. **Grep the actual call sites** — the exact API surface this repo touches. Pick the pattern matching the ecosystem's import syntax:

   ```bash
   # JS/TS: imports and requires
   grep -rnE "from ['\"]<pkg>['\"]|require\(['\"]<pkg>['\"]\)" --include='*.ts' --include='*.tsx' --include='*.js' --include='*.jsx' . | head -30

   # Python: imports
   grep -rnE "^(from|import) <pkg>(\.|$| )" --include='*.py' . | head -30

   # Rust: `use` and `<pkg>::`
   grep -rnE "use <pkg>(::|;| as )|<pkg>::" --include='*.rs' . | head -30

   # Go: import paths
   grep -rn "<pkg>" --include='*.go' . | head -30
   ```

2. **Read the real release notes for the exact old→new version range** — not just the bump title. `WebFetch`/`WebSearch` the package's changelog or release/compare page (e.g. `github.com/<org>/<repo>/releases`, a `compare/vX...vY` diff, or the ecosystem's changelog convention). If network access isn't available or the notes are unreadable, say so explicitly and report **actual: MEDIUM, "unverified — could not confirm against changelog"** — an unreadable changelog on a triggering signal can't default to LOW; treat it as the floor for that signal (major/framework/infra-touching signals floor at MEDIUM unverified, since HIGH requires positive confirmation of exposure just as much as LOW does).

   **Execute the tool, don't only read about it — for linter / formatter / type-checker bumps this is the stronger check.** Release notes tell you what *might* change; running the new version against the repo tells you what *does*: `npx <pkg>@<new-version> <the repo's own lint target>` (e.g. `npx @biomejs/biome@2.5.14 check src/`, `npx markdownlint-cli2@0.23.2 '**/*.md'`, `uvx ruff@<new> check .`). It costs seconds and clears or confirms the bump outright — the artifact itself, same rationale as the rolling-tag registry check below. A clean run is positive evidence for LOW only after confirming the executable and its compiler/parser dependencies resolve to the proposed versions. `npm exec` can reuse installed tooling; a run against the old version proves nothing about the bump. A dirty run shows the exact new failures the bump would land in CI. Run it with the repo's config in place (from the repo root, not `/tmp`) and use the same target the repo's own lint script uses.

   **Rolling-tag digest bumps** (`chainguard/*`, `distroless`, `alpine`, `node:N-slim`) are the exception: the tag is rebuilt, not versioned, so no release notes exist and the unverified floor above would gate every one of them forever. Inspect the registry instead — it is stronger evidence than notes, being the artifact itself:

   ```bash
   export DOCKER_CONFIG=$(mktemp -d)   # skip a malformed ~/.docker/config.json, which crane refuses to parse
   crane config <img>@sha256:<old> ; crane config <img>@sha256:<new>          # Env / Labels / entrypoint drift
   crane export <img>@sha256:<new> - | tar -tf - | grep -oE '<runtime-path>'  # e.g. usr/lib/python3\.[0-9]+
   ```

   Identical config plus an unchanged runtime version → **LOW**. Any entrypoint, `Env`, or runtime-version delta → read further before clearing. If the registry is unreachable, then fall back to the MEDIUM-unverified floor.

3. **Cross-reference, explicitly, line by line.** For each breaking/notable change in the notes, check it against the call sites from step 1 and state the match: "removed `X`, repo doesn't call `X` → not exposed" / "changed default of `Y`, repo relies on the old default at line N → exposed."

4. **State the actual verdict** — LOW / MEDIUM / HIGH — with the one or two lines of reasoning that got you there, e.g. `Actual: LOW — none of this release's 3 breaking changes touch this repo's 7 call sites (all stable core API).` This is the only risk framing the user sees; never print the signal-table label. If the delta is large/ambiguous (many packages grouped, sparse or unreadable notes) and no exposure can be confirmed either way, verdict floors at MEDIUM rather than guessing LOW.

#### Prefer adopting repairable updates

Recommend accepting an update when its migration is bounded and verifiable, including major versions. A bot branch that omits a matching coverage provider, newly required peer, or small config migration is an incomplete upgrade, not an automatic reason to skip. Read the required compatibility constraints and propose the smallest complete upgrade, including the paired dependency, lockfile, or config changes and the exact checks needed.

Assess the raw branch and the repaired path separately. Report a confirmed peer mismatch as a blocker in the raw branch; do not treat it as proof the repaired upgrade is unsafe. Recommend **merge + repair** when the repair is understood and scoped. Keep unverified compatibility at least MEDIUM until the proposed versions are installed and the affected checks pass. Do not call the repaired path LOW solely because a repair looks small. Default the gate to the repair recommendation rather than skip; keep skip for obsolete payloads, confirmed unsupported requirements, security regressions, or migrations without a bounded safe path. Never bypass peer constraints, release-age policies, or failing checks to accept an update.

For example, a Vitest 4 → 5 branch that leaves coverage-v8 on 4 needs a matching coverage-v8 5 upgrade. Recommend upgrading the pair, regenerating the lock without old installed-dependency resolver context, installing from the lock, and running the repo's coverage command. A passing run against the installed matching versions is evidence for acceptance; a predicted clean merge alone is not.

### 3. Automatically defer stale branches, otherwise confirm

**Bot rebase takes precedence.** When a regenerated bot branch can remove predicted conflicts caused by stale manifest or lockfile state, automatically choose **defer for bot rebase** before any merge attempt or decision prompt. State the affected branches, count, conflict files, and the target-branch prerequisite. Continue with unaffected branches; if none remain, end the drain with the deferred list. This is a deferral of the current bot payload, not rejection of the updates. Do not manufacture this option for genuine incompatibility or a repair the bot cannot generate.

A bot regenerates against its PR/MR target, not the checked-out feature branch. If the prerequisite dependency changes exist only on the feature branch, the user must push and land those changes on the bot's target before regeneration can incorporate them. Pushing the feature branch alone is insufficient. If the target already contains the changes, defer until the bot refreshes its branch against that target. Do not push, merge to the target, or post remote rebase commands without the required explicit authorization. Report deferral as selected, not rebase as requested or completed unless that action was actually performed.

**Actual LOW (or LOWEST)** → state the verdict, merge, run step 5 checks, log, and auto-advance only when the current user instruction explicitly authorizes that merge. Risk classification and invoking this skill do not substitute for required merge permission; otherwise ask for that permission.

**Actual MEDIUM or HIGH** → stop and wait for the branch-specific decision after completing required research. Present options:

- **merge + repair** — recommended when a bounded repair is required; name the files, dependency changes, and checks before seeking approval.
- **merge** — apply `git merge --no-ff` when no repair is required.
- **skip** — leave the branch unmerged and auto-advance.
- **inspect** — show additional evidence; this never gates research already required by step 2.
- **stop** — exit the loop.

Do not offer bot rebase as a choice: automatically select it when applicable. Keep unrelated compatibility decisions and merge permissions gated. Approved repair edits remain working-tree changes for the user to commit before proceeding.

### 4. Merge

```bash
git merge --no-ff "origin/${branch}" -m "Merge ${branch} into $(git rev-parse --abbrev-ref HEAD)"
```

- If `Already up to date.` → branch was already merged (race with platform UI). Skip silently, log it, move on.
- If conflict → propose a resolution, then STOP for acceptance. Don't ask the user to resolve it themselves. List the conflicted files from `git status --short`, then build the proposal in the working tree, leaving it **unstaged**:
  - **Lockfiles** (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `uv.lock`, `poetry.lock`, `Cargo.lock`, `go.sum`, `Gemfile.lock`, …): never hand-merge the conflict markers. Take HEAD's lock (`git checkout --ours -- <lock>`), resolve the manifest first, then regenerate with the repo's lockfile toolchain from a clean state (see the `node_modules` and resolver-drift pitfalls). The regeneration is part of building the proposal; `git merge --abort` reverts it.
  - **Manifests**: keep both intents. For each conflicting dep, take the version the bot branch targets unless HEAD already pins a higher one. Keep HEAD's unrelated edits verbatim.
  - **Modify/delete** (the bot bumped a dep HEAD removed): propose keeping the deletion and recommend aborting the merge as redundant.
  - **Anything else** (source, config): propose a minimal resolution only when both sides' intent is clear from the diff. Otherwise say so and leave that file conflicted for the user.

  Show the proposal: `git diff` per resolved file, plus a short rationale per hunk that names which side's intent survived and why. Then ask the user (structured question tool if the harness has one): **accept** (`git add` the files, `git diff --check`, `git commit --no-edit`, then step 5; accepting is the explicit authorization for that one commit), **edit** (the user adjusts or redirects, then re-show the diff), or **abort** (`git merge --abort`; choosing it is the confirmation). Never stage or commit a proposed resolution before the user accepts it.
- If clean → proceed to step 5.

### 5. Auto-detected post-merge checks

**First, install the bumped deps — or the checks are hollow.** Right after a merge, the installed deps (`node_modules/`, `.venv/`, `target/`) still hold the *old* versions. Linters/type-checkers/builders run against what's installed, not what the manifest now says — so they pass against the pre-bump tree and give a **false green** (e.g. linting under eslint 9 while the manifest says 10). Sync the install from the bot's lockfile before checking:

| Ecosystem | Install-from-lock command |
|---|---|
| npm | `npm ci` — **never `npm install` on macOS** (prunes Linux-only optional deps the lockfile pins; see the macOS gotcha below) |
| pnpm / yarn | `pnpm install --frozen-lockfile` / `yarn install --immutable` |
| uv | `uv lock --check` first, **then** `uv sync --frozen` — `--frozen` does *not* verify the lock against the manifest, so on a stale lock it silently installs the **old** version and greens every check. `uv lock --check` is the only step that catches it. |
| poetry | `poetry install --sync` |
| Cargo / Go | no separate step — `cargo check` / `go build` resolve from the lockfile/module graph directly |

If that install **fails on a stale lockfile** (manifest bumped, lock not regenerated — see the manifest-only-bump gotcha), you must regenerate the lock (respecting any repo-specific toolchain, e.g. a docker-pinned `npm run lockfile`) and re-run the install before checks mean anything. **That regenerated lockfile — plus any manifest fix you applied to make resolution succeed (e.g. a missing peer) — is not part of the `--no-ff` merge commit.** It must be committed too, or the merged result still fails `npm ci` for the next person. You don't commit (except the merge itself): tell the user to **amend the merge commit or add a follow-up commit** for the lockfile/manifest fixes before moving on.

**A version pin repeated across files needs a post-merge sweep.** After merging, if the bump's pin recurs across files (an action tag in several workflows, a tool version in a `Dockerfile` and CI), run `git grep -n '<old>'` and fix stragglers as a working-tree edit for the user to commit, like a lockfile fix.

**Private-registry 403 on install.** If the install fails with `403 Forbidden` against a private feed (Artifact Registry, CodeArtifact, Azure Artifacts, a self-hosted proxy), the token in `~/.npmrc` / `~/.config/pip` is usually expired. Try refreshing it non-interactively first; if the cloud CLI can't mint a token either, the repo's own docs often document a local-build fallback (e.g. `npm install ../sibling-lib --no-save`, building the private package from a sibling checkout).

That fallback has a trap: **`--no-save` only spares `package.json` — it still rewrites `package-lock.json`.** Merge a second branch without restoring it and you silently commit a locally-resolved lock. So:

```bash
cp package-lock.json /tmp/merged-lock.json   # BEFORE the fallback install
npm install ../sibling-lib --no-save
# …run checks…
cp /tmp/merged-lock.json package-lock.json   # restore
git status --short                           # MUST be clean before the next merge
```

Verify the private package's lockfile entry still shows a registry `resolved` URL, not `file:../…`.

A directory install (`npm install ../lib`) is a **symlink**: anything the linked package imports (e.g. eslint plugins in a shared config) resolves from the *sibling's* `node_modules`, not the consumer's, so a green lint on those deps is fake. Install a packed copy instead: `(cd ../lib && npm pack --pack-destination /tmp)` then `npm install /tmp/<lib>-<ver>.tgz --no-save`. Then confirm the version where the importer actually resolves it — check `node_modules/<lib>/node_modules/<pkg>` for a nested copy, not just top-level `node_modules/<pkg>` — before trusting a green.

Then detect the stack from repo root files and **run** the matching checks (not just offer). Show output. Reason aloud about results. If multiple ecosystems are present in one repo, run the checks for whichever ones the merge touched.

| Detection | Commands |
|---|---|
| `package.json` with `scripts.lint` AND `scripts.type-check` | `npm run lint && npm run type-check` |
| `package.json` with only `scripts.build` | `npm run build` |
| `pyproject.toml` + `uv.lock` | `uv run ruff check .` (+ `uv run mypy .` if mypy configured) |
| `pyproject.toml` + `poetry.lock` | `poetry run ruff check .` (+ `poetry run mypy .` if configured) |
| `pyproject.toml`, plain | `ruff check .` (+ `mypy .` if configured) |
| `Cargo.toml` | `cargo check --all-targets && cargo clippy --all-targets -- -D warnings` |
| `go.mod` | `go build ./... && go vet ./...` |
| `Gemfile` | `bundle exec rubocop` (if configured) and `bundle exec rspec` only if user opts in (tests are slow) |
| `pom.xml` | `mvn -q -DskipTests verify` |
| `build.gradle*` | `./gradlew check -x test` |
| `composer.json` | `composer validate && vendor/bin/phpstan analyse` (if configured) |
| `mix.exs` | `mix compile --warnings-as-errors && mix credo` (if configured) |
| Merge touched only `.github/workflows/`, `.gitlab-ci.yml`, or `Dockerfile` | Parse-check the changed CI files (`uv run --with pyyaml python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]"`, or `docker build --check`). Catches syntax breakage only — real verification is a pipeline run, so remind the user to watch CI after pushing. |
| None of the above | Skip checks, tell the user. |

Respect project-specific overrides — if the repo has an `AGENTS.md` (or the harness's rules file), `Makefile`, or script like `./pre-commit.sh` / `./scripts/check.sh` that bundles the canonical checks, prefer that.

Failure handling:

- **HIGH-risk merge, checks fail** → expected. Ask: (a) fix in place now (skill pauses, user/agent makes the code changes, re-runs checks), (b) revert with `git reset --hard HEAD~1` and skip, (c) accept and continue.
- **LOW-risk merge, checks fail** → unexpected. Show output verbatim. Default suggestion: revert and investigate before continuing the loop.

### 6. Log and auto-advance

After checks pass (or the user explicitly accepts a failure), log one line:

> Merged `<branch>` into `<HEAD>`.

Do **not** push. Then **auto-advance**: move to the next non-redundant branch and run steps 1–2 (show change + risk read), stopping at its step-3 gate. When no branches remain, summarize all merges/skips and remind the user to push and watch CI. Never push at any point — the buffer-branch pattern pushes once at the end, after all merges.

## Hard rules

- **`git merge --no-ff` requires explicit current authorization.** An authorized local merge can create its merge commit; invoking this skill or classifying risk LOW is not authorization. Accepting a proposed conflict resolution authorizes concluding that merge with `git commit --no-edit`, and nothing else. No other `git commit` invocations.
- **Never `git push`**, **never `git push --force`** — user pushes manually.
- **Never `--no-verify`** on the merge — let pre-commit / commit-msg hooks run.
- **Never apply a conflict resolution silently.** Always propose it as a diff and wait for explicit acceptance. Conflicts in a renovate bump often mean two PRs touched the same lockfile, and an unreviewed resolution destroys version intent.
- **Never reset / discard without explicit confirmation** — even on a failed merge, ask before `git reset --hard`.
- **Refuse on protected branches** (`main`, `master`, `dev`, `develop`, `release/*`, `staging`) unless user overrides.
- **Bot rebase is automatic when applicable; acceptance is repair-aware.** Defer stale-branch conflicts without a choice prompt. For other branches, prefer a bounded complete upgrade over skipping an incomplete bot payload. Preserve required merge authorization and per-branch MEDIUM/HIGH gates; never batch those approvals or lower risk without evidence.

## Common pitfalls (ecosystem-agnostic unless noted)

- **Stale remote refs**: skipped the `git fetch --prune`, so `origin/renovate/foo` points at last week's HEAD. Always fetch in pre-flight.
- **"Already up to date"**: branch was merged via the platform UI but the local feature branch wasn't refreshed. Skip and continue.
- **Hidden major bumps in lockfiles**: bot groupings can sneak a major version into a transitive dep. When risk-reading a grouped PR, scan the lockfile diff for `"version": "Y."` (npm), `version = "Y."` (Cargo / uv / poetry), or `vY.0.0` (go.sum) where Y is a new major, not just the top-level manifest deltas.
- **CI-config bumps** (`docker/build-push-action@vN`, `actions/checkout@vN`, `setup-node@vN`, `setup-python@vN`): touch `.github/workflows/` or `.gitlab-ci.yml` and need the same scrutiny as code deps. Auto-checks won't catch CI breakage — flag and let the user decide whether to push and watch the pipeline.
- **npm + macOS lockfile bug** (project-specific gotcha — surfaces in some repos via their `AGENTS.md` or the harness's rules file): if a merged Renovate PR regenerated `package-lock.json` inside a Linux container, do **not** run `npm install` locally on macOS afterward — it can prune Linux-only optional deps and break CI. The lockfile from the PR is authoritative. If unsure, check that file for a note about this.
- **Python lockfile resolver drift**: `uv.lock` / `poetry.lock` are platform- and Python-version-aware. Regenerating locally on a different OS or interpreter can produce a different solution than the bot's. Don't re-resolve unless necessary (a lockfile conflict or a stale lock makes it necessary).
- **Cargo `[patch]` / git deps**: a major bump that resolves through a `[patch.crates-io]` section can silently bypass the version constraint. Read `Cargo.toml` end-to-end on major bumps.
- **Go minimum version module graph**: `go.mod` may bump indirect deps that other modules pin lower. After merging a `go.mod` change, `go mod tidy` may want to make further edits — don't blindly accept; verify with the user.
- **Manifest-only bump, stale lockfile**: the branch changes `package.json` / `pyproject.toml` but the lockfile still pins the old version (giveaway: post-merge `npm ci` / `uv lock --check` fails with "lock out of sync" — note `uv sync --frozen` will *not* fail here, it just installs the stale pin). The bot's runner couldn't run the package manager (missing private-registry auth, blocked egress, or a repo-specific lockfile toolchain it lacks — e.g. a docker-pinned `npm run lockfile` that builds in a Linux container). You must regenerate the lock yourself mid-merge before checks pass, then fold it into the merge commit. The bot config can't be fixed from here — note it to the user (it's a runner-capability gap, not a `packageRules`/`postUpdateOptions` issue). If the repo has a docker-based lockfile script, daemon may be down (e.g. colima) — start it first.
- **Lockfile regen blocked by a release-age policy**: if the repo sets `min-release-age` (`.npmrc`) or `exclude-newer` (uv/cargo `pyproject.toml`), regenerating the lock for a *fresh* major fails with `ETARGET … No matching version found for <pkg>@^N with a date before <date>` — the bump is newer than the age floor, and there may be no older release in that major to pin to. You can't complete the merge: the manifest wants vN but the lock can't move to it. **Don't bypass the guard** (it's a deliberate supply-chain defense). Revert the merge (`git reset --hard HEAD~1` — confirm with the user first), skip the branch, and let it age; the bot re-offers it once the version clears the window. Note the renovate-side fix: `minimumReleaseAge` **plus** `internalChecksFilter: "strict"` are both required to stop these surfacing early — `minimumReleaseAge` alone still creates the pending branch, which is how a too-new bump reaches triage in the first place.
- **`node_modules` poisons in-place lockfile regen**: `npm install --package-lock-only` reads the existing `node_modules/` for resolution context, so the *old* installed version anchors the resolver and emits phantom ERESOLVE conflicts (`Found: <pkg>@<old-version>` for a version nothing in the manifest requests). Regenerate from a clean state — `mv node_modules /tmp/stash` (or a temp dir with only the manifest), regen, restore. If a bump's lockfile won't resolve, test it in a clean dir before believing the conflict is real.
- **Transitive→peer promotion in a major**: a major can move a bundled dep to a peer (e.g. `eslint-plugin-vue` 9→10 moved `vue-eslint-parser` from `dependencies` to `peerDependencies`). The bot bumps the parent but can't add the now-required peer — it was never in the manifest, so nothing to group or bump. Resolves on paper, then strict install fails on the unmet peer. Fix = manually add the peer (peer + dev) *with* the merge. On HIGH-risk majors, skim the changelog for "moved to peerDependencies" before merging. Beware OR-range peers the bot widens (`"^9 || ^10"`): the resolver can seat the *lower* major, dragging its old transitive peers into conflict — tighten to the major you actually adopt.
- **Merging into a feature branch with unpushed commits**: harmless, but warn the user so they don't lose track of which merges are local vs pushed.

## Retro

After the run, propose an edit to this skill only on real signal: a case these steps didn't cover, a
user correction or repeated instruction, a wrong or stale step, or a manual workaround you repeated.
Name the section, show before/after lines, give one sentence of why, and apply only after a yes, in
the Waxmard/skills source (`skills/triage-renovate-dependabot-prs/SKILL.md`), never the installed
copy. If nothing fired, say nothing. Typical signals here: a bot-branch ecosystem or lockfile the
post-merge checks didn't auto-detect, a risk-read pattern that recurred across branches, or a
discovery quirk on this host/platform.
