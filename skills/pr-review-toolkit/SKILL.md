---
name: pr-review-toolkit
description: >-
  Comprehensive MR/PR code review using specialized audit lenses. Analyzes code
  diffs from GitLab MRs (glab), GitHub PRs (gh), or local branches for bugs,
  silent failures/error handling, test coverage gaps, type design invariants,
  comment rot, and code simplification. Trigger: "review this PR", "review this
  MR", "review MR", "review PR", "review the diff", "code review",
  "/pr-review-toolkit", or /review-pr.
---

Perform comprehensive code reviews on Merge Requests (GitLab), Pull Requests (GitHub), or local branch diffs using structured audit lenses.

## 1. Pre-flight & Diff Resolution

1. Confirm repo: `git rev-parse --git-dir`
2. Determine diff source:
   - **GitLab MR**: If in a GitLab repo or `--mr <iid>` provided:
     ```bash
     glab mr diff
     # or fetch metadata:
     glab mr view --output json
     ```
   - **GitHub PR**: If in a GitHub repo or `--pr <num>` provided:
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
3. Read project rules: Inspect `CLAUDE.md` / `GEMINI.md` / `AGENTS.md` at repo root or relevant directories for project-specific conventions.

## 2. Review Aspects

Analyze the diff across 6 specialized lenses:

### A. Code Quality & Bug Detection (Confidence threshold ≥ 80)
- **Logic errors & regressions**: Null/undefined checks, race conditions, off-by-one errors, memory leaks, security vulnerabilities.
- **Project guidelines**: Strict compliance with repository rules and patterns.
- **Confidence scoring (0-100)**: Filter out pedantic nitpicks and false positives. Report only high-confidence issues (≥80).
- **Cross-boundary effects**: For each changed producer (API handler, writer, job, config), follow the data to its consumers (DB, queue, sidecar, downstream service, UI) and report breakage that lands outside the diff.

### B. Silent Failure & Error Handling Audit
- **Zero tolerance for swallowed errors**: Catch blocks that silently log and continue, empty catch/except blocks, unhandled promise rejections.
- **Specific catches**: Catching broad `Exception`/`Error` hiding unrelated bugs.
- **Actionable errors**: Ensuring user-facing or log messages include context, error codes, and recovery steps.
- **Inappropriate fallbacks**: Masking failure states with fake data or silent defaults in production code.

### C. Test Coverage & Edge Cases
- **Behavioral coverage**: Test behavior and contracts rather than brittle implementation details.
- **Critical gaps**: Untested error handling branches, missing boundary condition tests, absent negative test cases, async/concurrency edge cases.
- **Test quality**: Resilience to refactoring, clear assertions (DAMP principles).

### D. Type Design & Invariant Strength
- **Encapsulation & Invariants**: Are illegal states unrepresentable? Are constructors validating invariants?
- **Mutation points**: Are internal structures leaked or mutably exposed?
- **Compile-time safety**: Preferring compile-time guarantees over runtime checks where feasible.

### E. Comment & Documentation Audit
- **Comment rot**: Flagging comments that contradict code, describe obsolete behavior, or restate the obvious.
- **Missing rationale**: Ensuring non-obvious algorithms, security constraints, and business logic document *why*, not just *what*.

### F. Code Simplification
- **Clarity over cleverness**: Reducing excessive nesting, dead branches, and unnecessary abstractions while strictly preserving behavior.

## 3. Execution & Delegation

- **Inline execution**: For small to medium diffs (< 10 files or < 300 lines changed), evaluate all applicable lenses sequentially.
- **Subagent fan-out**: For large diffs, delegate individual lenses or file groups to parallel subagents (`flash` model):
  - Subagent 1: Bug & logic audit + project rule compliance
  - Subagent 2: Silent failure & error handling inspection
  - Subagent 3: Test coverage & edge case analysis
  - Subagent 4: Type design & invariant review

## 4. Output Format

Present findings in a structured, actionable report:

```markdown
# MR/PR Review Summary

## Critical (must fix before merge)
- **`<file>:<line>`**: [Lens: Bug/Error Handling] Description of issue.
  - *Problem*: Mechanism in ≤2 sentences. When the effect lands outside the diffed file, trace the hops with a file:line at each.
  - *Fix*: Concrete code suggestion.

## Important (should fix)
- **`<file>:<line>`**: [Lens: Tests/Types] Description of issue.
  - *Problem*: Why this poses a risk or regression.
  - *Fix*: Suggested improvement.

## Suggestions (optional)
- **`<file>:<line>`**: [Lens: Simplification/Comments] Description and suggestion.
```

If no issues meet the confidence threshold:
```markdown
# MR/PR Review Summary

No high-confidence issues found.
```

## 5. Hard Rules

- **Read-only**: Never edit files, commit, push, or approve/merge MR/PRs automatically.
- **Cite live code**: Reference exact `file:line` locations and symbol names.
- **No false positives**: Verify assumptions by reading surrounding code context, not just the isolated diff hunk.
