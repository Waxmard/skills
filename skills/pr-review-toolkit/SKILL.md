---
name: pr-review-toolkit
description: >-
  Use when reviewing a PR, MR, branch diff, or local changes for bugs,
  regressions, silent failures, test gaps, and broken callers (lean, default,
  or full mode). Single-pass code review; not for judging existing review
  comments (address-review-comments) or posting findings (post-mr-review).
  Trigger: "review this PR", "review this MR", "review my branch", "review the
  diff", "code review", "check my changes before opening a PR", or
  /pr-review-toolkit.
---

Review a Merge Request (GitLab), Pull Request (GitHub), or local branch diff in one pass. Read the diff once and open other code only to confirm or rule out a suspected finding.

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- `git`
- `glab` (GitLab MR source) or `gh` (GitHub PR source), logged in; not needed for a local branch review

Install missing tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## 1. Pre-flight, mode, and diff

Before step 1, check the prerequisites:
```bash
command -v git >/dev/null || echo "missing: git"
```
Missing git: stop. For an MR/PR source, step 2 needs `glab` or `gh` installed and logged in (`glab auth status` / `gh auth status`); if it isn't, use the Local Branch diff source and say once that the MR/PR diff was skipped and why.

1. Confirm repo: `git rev-parse --git-dir`
2. Resolve the mode. Take it from the invocation args or the caller's instructions (`mode: <x>`): `lean`, `default`, or `full`. None given: `default`. Remove the mode word before reading the other args.
3. Determine the diff source:
   - **GitLab MR**: if in a GitLab repo or `--mr <iid>` is provided:
     ```bash
     glab mr diff
     # or fetch metadata:
     glab mr view --output json
     ```
   - **GitHub PR**: if in a GitHub repo or `--pr <num>` is provided:
     ```bash
     gh pr diff
     # or fetch metadata:
     gh pr view --json number,title,baseRefName,headRefName
     ```
   - **Local Branch / Working Tree**:
     ```bash
     # Compare against main/default branch:
     git diff $(git merge-base HEAD origin/main 2>/dev/null || echo "origin/master")...HEAD
     # Or unstaged/staged working tree diff if requested:
     git diff HEAD
     ```
   A caller-pinned range (for example `<from>..<to>`) overrides all three.
4. List the changed files before reading any diff: `git diff --numstat <range>`. Exclude machine-authored paths and name them in the report header: lockfiles (`*.lock`, `package-lock.json`, `pnpm-lock.yaml`, `go.sum`), snapshots (`__snapshots__/`, `*.snap`), generated or minified output (`dist/`, `build/`, `coverage/`, `*.min.*`, `*.map`, `*.gen.*`, `*.generated.*`), vendored code (`vendor/`, `third_party/`, `node_modules/`), and binaries. Then read the diff of the remaining files once, passing them as pathspecs.
5. Read project rules: the root `AGENTS.md` (or `CLAUDE.md` / `GEMINI.md` when there is no `AGENTS.md`). In `default` and `full`, also read any of those files in a directory that contains a changed file.
6. **Memo** (`lean` and `default` only). Skip this step entirely, with no snapshot and no memo read or write, when the mode is `full`, when the caller names an exact range to review (for example, a pinned `<from>..<to>` range), or when the current branch isn't the MR/PR head branch (`source_branch` / `headRefName`). Otherwise take a snapshot of the working tree:
   ```bash
   top=$(git rev-parse --show-toplevel)
   idx=$(mktemp)
   cp "$(git rev-parse --git-path index)" "$idx" 2>/dev/null
   GIT_INDEX_FILE="$idx" git -C "$top" add -A
   tree=$(GIT_INDEX_FILE="$idx" git -C "$top" write-tree)
   rm -f "$idx"
   base=origin/<target_branch|baseRefName>   # MR/PR target branch; local branch: origin/main, else origin/master
   mb=$(git merge-base HEAD "$base")
   ```
   The memo is `$(git rev-parse --git-path pr-review-toolkit)/<branch>/`: `state` holds `tree` and `mb` lines, and `findings.md` holds the last report verbatim. Review the whole range if any of these is true:
   - there is no memo;
   - `git cat-file -e <memo tree>` fails;
   - the memo's `mb` differs from `$mb` (rebase, or base merged in).

   Otherwise run a **delta** review: review `git diff <memo tree> <tree>`, using the full diff only as context. Report findings only on lines in the delta, unless a change there breaks code elsewhere in the full diff. If the delta is empty, re-print `findings.md` under the line `No changes since last review; reply `full` to re-review.` and stop.

## 2. Review pass

Walk the diff once, file by file, and apply every check the mode enables at the same time. Never re-read the diff once per check.

| Check | `lean` | default | `full` |
|---|---|---|---|
| Bugs & regressions | yes | yes | yes |
| Silent failures | yes | yes | yes |
| Test gaps | yes | yes | yes |
| Tests to delete, new e2e specs | no | yes | yes |
| Contract breaks | no | 1 hop | up to 3 hops |
| Comment rot | no | yes | yes |
| Type design | no | no | yes |
| Missing rationale | no | no | yes |
| Simplification | no | no | yes |

- **Bugs & regressions** `[Bug]`: logic errors, null/undefined handling, off-by-one, races, leaks, security vulnerabilities, and violations of the project rules read in step 1.5.
- **Silent failures** `[Silent failure]`: swallowed errors (catch that logs and continues, empty catch/except, unhandled promise rejections), broad `Exception`/`Error` catches that hide unrelated bugs, fallbacks that mask a failure with fake data or silent defaults, and error messages without the context needed to act on them.
- **Test gaps** `[Tests]`: a changed branch of domain or boundary logic with no test: parsing an external format, a data rule, an error or edge condition, concurrency, or a bug fix without its regression test. Never report missing tests for wiring, forwarding, rendering, or glue code.
- **Tests to delete** `[Tests]` (Important, *Fix*: delete the test): tests added or modified in the diff whose expected values are copied from or computed with the code under test, that assert static prompt/source-text substrings or hardcoded constant/lookup-table echoes, that assert only mock call arguments or snapshots of current output, or that only check something renders, starts, or does not throw.
- **New e2e specs** `[Tests]` (Important, *Fix*: delete unless the user asked for this spec; confirm with the user): any Playwright, Cypress, or mocked-fixture e2e spec added in the diff.
- Test checks cover only tests and code in the diff, never pre-existing tests outside it (broader pruning belongs to `test-audit`).
- **Contract breaks** `[Contract]`: only when a hunk changes a contract: an exported signature, return or raise behavior, a schema, a wire/JSON field, a config key, a CLI flag, or an env var. Grep its direct consumers and read only the matching lines. In `full`, follow the consumers that change behavior for up to 3 hops. Report breakage that lands outside the diff.
- **Comment rot** `[Comment]`: a comment in or next to a hunk that contradicts the changed code or describes removed behavior. Redundant or excess comments belong to `docs-audit`; never report them here.
- **Type design** `[Types]`: illegal states made representable, constructors that skip invariant checks, leaked mutable internals, runtime checks where the type system could enforce the rule.
- **Missing rationale** `[Rationale]`: a non-obvious algorithm, security constraint, or business rule added with no comment saying why.
- **Simplification** `[Simplify]`: excess nesting, dead branches, needless abstraction, always behavior-preserving. Outside `full`, simplification belongs to `ponytail-review`.

Rules for every check:
- **Confirm before reporting.** Open code outside the diff only to confirm or rule out a suspected finding, and read the enclosing function or block, not the whole file. Drop a suspicion you cannot confirm in live code.
- **Confidence ≥ 80.** Report only issues with a real trigger. Never report pedantic nits.

## 3. Large diffs

`lean` and default always run inline, with no subagents: a subagent re-reads the diff it is given, so fan-out multiplies the input cost.

`full` with more than 30 files or 1500 changed lines after step 1.4's exclusions: group the files by top-level directory (at most 15 files per group) and spawn one subagent per group, each applying every `full` check to its files only. Then run the contract-break check across groups yourself and merge the reports, dropping duplicates.

## 4. Output Format

```markdown
# MR/PR Review Summary

Mode: <lean|default|full> · <full|delta> · <N> files vs <base> · excluded: <paths or "none">

## Critical (must fix before merge)
- **`<file>:<line>`**: [Bug] Description of issue.
  - *Problem*: Mechanism in ≤2 sentences. When the effect lands outside the diffed file, trace the hops with a file:line at each.
  - *Fix*: Concrete code suggestion.

## Important (should fix)
- **`<file>:<line>`**: [Tests] Description of issue.
  - *Problem*: Why this poses a risk or regression.
  - *Fix*: Suggested improvement.

## Suggestions (optional)
- **`<file>:<line>`**: [Comment] Description and suggestion.
  - *Fix*: Concrete change.
```

Suggestions: none in `lean` (omit the section); at most 3 in default, each with a *Fix*; uncapped in `full`. Omit any empty section. Never list suspicions you checked and dropped.

If no issues meet the confidence threshold, print the header line, then `No high-confidence issues found.`

In a delta review, handle each item in the memo's `findings.md` as follows. Drop items whose check the current mode doesn't enable.
- **File unchanged:** carry it into its severity section and append ` · carried` to its bullet.
- **File changed and fixed:** drop it, and list it in a final `Resolved since last review:` line as `file:line` entries.
- **File changed and not fixed:** restate it at the current line.

After printing the report (unless step 1.6 was skipped), write the memo. Fill in the literals:
`d="$(git rev-parse --git-path pr-review-toolkit)/<branch>" && mkdir -p "$d" && printf 'tree %s\nmb %s\n' <tree> <mb> > "$d/state"`. Then write the report verbatim to `$d/findings.md`.

## 5. Hard Rules

- **Read-only**: Never edit working-tree files, commit, push, or approve/merge MR/PRs automatically. The only write is the memo under `.git` (step 1.6).
- **Cite live code**: Reference exact `file:line` locations and symbol names.
- **No false positives**: Confirm each finding against the surrounding code, never the isolated hunk alone.
