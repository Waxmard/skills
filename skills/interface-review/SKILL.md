---
name: interface-review
disable-model-invocation: true
description: >
  Use when asked for a UI, frontend, interface, or design review of a branch,
  PR, MR, or diff (lean, default, full). Expands changed files to affected UI
  surfaces, checks removed lines for regressions, and reviews accessibility,
  layout, writing, typography, color, and UI polish. Not for general code
  review (pr-review-toolkit). Trigger: "review the UI changes", "UI review",
  "interface review", "design review of this PR", or /interface-review.
---

# Change review

This skill reviews a change rather than a screen (or, in `full` mode, a whole repository's UI). It resolves the scope, expands the changed files to the surfaces they affect, reads both sides of the diff, and evaluates Accessibility, Layout, Writing, Typography, Colors, and UI polish to issue one ranked verdict.

Correctness, tests, security and performance belong to the project's general code review. Name the concern once and move on.

## The change, not the codebase

The author is asking "did I make this worse?". Report what the change caused and stay mostly quiet about what it merely touched. Three pre-existing findings is a courtesy; thirty is a different review and one nobody asked for.

Read the change before forming an opinion of it. The stated intent decides what counts as incomplete, and a skimmed diff produces findings about code the next hunk already fixed.

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- `git`
- `gh` (logged in), for `pr <n>` targets, default-branch fallback, and open-PR checks; not needed when reviewing a local branch or range with `origin/HEAD` set

Install missing CLI tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## Core principles

### 1. Resolve the change scope first

Before step 1, check the prerequisites:

```bash
command -v git >/dev/null || echo "missing: git"
```

Missing `git`: stop. For a `pr <n>` target, also check `command -v gh >/dev/null && gh auth status`; if missing or unauthenticated, stop and name what's missing.

The whole invocation is the target, so `/interface-review pr 482` reviews pull request 482. [Scope resolution](scope-resolution.md) holds the accepted targets and how each resolves.

A leading `lean` or `full` in the invocation, or `mode: <x>` from a calling skill, is the scope mode, not a target: remove it before resolving the target. No mode: default.

- **`lean`**: expand one hop only, tokens and primitives included; report only `HIGH` and `MEDIUM` findings statused `Introduced` or `Regression`; omit the `Pre-existing` section.
- **Default**: as written.
- **`full`**: a whole-repository interface audit across all UI surfaces, reporting findings without a change-scope block, diff statuses (`Introduced`/`Regression`), or `Pre-existing` section.

With no target supplied, resolve in this order and stop at the first match:

1. `HEAD` is ahead of `git merge-base origin/<default-branch> HEAD`: that range **plus** any uncommitted changes, with the commit count and the uncommitted file count stated separately.
2. The working tree is dirty: the uncommitted changes.
3. Neither: there is no change to review. Stop and ask, per **With no change, ask rather than invent one**.

Order matters. Check the working tree first and one stray formatting edit shadows a twelve-commit branch, with the report still claiming full coverage.

Exclude lockfiles, snapshots, generated output, vendored code and binaries, and name what you excluded. An empty scope after exclusions reaches the same place by a different route.

### 2. With no change, ask rather than invent one

A clean tree with nothing ahead of the merge base means the user asked to review a change that does not exist. Never fall back to `HEAD~1..HEAD` on your own. The last commit is whatever happened to land, often a merge, often someone else's work, and a report on it is indistinguishable from a report on what the user meant.

State the repository facts you found, then offer the routes and wait. [Nothing to review](scope-resolution.md#nothing-to-review) holds the facts to gather:

- **The last commit**, `HEAD~1..HEAD`, named by short SHA and subject, so the user sees what they would get before choosing it.
- **A target they name**: `pr <n>`, a branch, a ref, or a range, resolved per **Resolve the change scope first**.
- **A whole-repository interface audit** (`full` mode), reviewing all UI surfaces directly without this skill's scope block, statuses, or pre-existing section. With no change, every finding is pre-existing and the classification says nothing.

Check for an open pull request on the current branch before asking, and offer it first. A branch whose commits already landed resolves to no change, while its pull request is still exactly what the user meant.

Where the scope emptied out after exclusions, say which files were excluded and ask the same way. Never report a review of nothing as `Approve`.

### 3. A diff is not a surface

A changed file is evidence, not the review subject. Its **blast radius** is the set of surfaces it renders in; review those.

Expand the blast radius one hop by default: the direct importers and callers. Expand a second hop only for design tokens, theme values and shared primitives, where one line reaches the whole product.

Review at most five consumers, ordered by [the rule in Scope resolution](scope-resolution.md#expanding-to-consumers), then state how many you did not expand. A sweep with no bound cannot support the coverage it claims, and an unstated cutoff reads as completeness.

### 4. Read the removed lines

Regressions are invisible in the post-change state. Read the `-` side of every hunk against [Removed signals](removed-signals.md).

A signal is a lead, not a finding. A removal is only a regression when nothing in the change replaces it, and the removal concretely degrades its domain under **Evaluate domains, rank by impact, and issue the verdict**. Report only confirmed regressions and status them `Regression`. That tells the author they broke something that worked rather than made a new mistake.

### 5. Classify every finding

Give every finding one status:

- `Introduced`: the change created it.
- `Regression`: the change weakened something previously correct.
- `Pre-existing`: present in the touched code but not caused by this change.

Status by what the diff touched, not by which file it sits in: a line the change never touched is `Pre-existing` even three lines from a hunk. Confirm against the base ref when it matters:

```bash
git blame -L <line>,<line> "$BASE" -- path/to/file
```

Apply the cap and verdict rules in **Evaluate domains, rank by impact, and issue the verdict** to `Introduced` and `Regression` findings only.

### 6. Hold the change to its stated intent

Read the pull request title and body, the linked issue and the commit messages, then review whether the interface delivers what they claim.

This is what surfaces the **incomplete** change. A surface review cannot see it, because it inspects the states that are present, and here the point is the ones that are absent:

- A new variant, size, or theme applied to some states but not all: hover, focus, active, disabled, loading, selected.
- A new user-facing string with no entry in the translation catalogue the project maintains.
- A new component with no empty, loading, error, disabled, or narrow-width state.
- A control added to one surface but not to the siblings that already carry its peers.

Do not report scope creep. Whether a change does too much is a process question, not an interface one.

### 7. Evaluate domains, rank by impact, and issue the verdict

Identify the framework, styling system, component library, design tokens, and convention docs (`AGENTS.md`, `CONTRIBUTING.md`, product specs). Write every fix in the project's own idiom and tokens, preferring the cheapest fix: delete redundant code/chrome first, use native platform elements second, reuse existing project tokens/components third, correct the value fourth, and add new markup or tokens last.

Inspect the affected surfaces (including empty, loading, error, and narrow-width states where present) across six domains:

- **Accessibility**: Native interactive elements (`<button>`, `<a href>`) over `<div onclick>`; visible `:focus-visible` indicator (never bare `outline: none` without a replacement unless the project's product spec mandates otherwise); keyboard reachability where supported (`Escape` closes overlays, focus trapped and restored in modals); touch targets (`>= 44x44px` on touch, `>= 24x24px` WCAG AA baseline, no overlapping hit areas); `prefers-reduced-motion` respected.
- **Layout**: Check for collapsed or clipped containers on narrow (`320px`) or short laptop viewports (such as `max-height` + `flex-shrink: 0` siblings crushing a `min-height: 0` scrollable pane); sticky or fixed overlays and toasts covering controls or keyboard focus targets; nested scrolling traps at container boundaries; misaligned sibling controls in a shared row or grid; missing `env(safe-area-inset-*)` where the app uses `viewport-fit=cover`; and missing-image layout stability.
- **Writing**: Match the product's existing voice, terminology, and capitalization policy (sentence case vs. Title Case per element type); verb-first action labels (never vague noun phrases or bare "Yes"/"No" on consequential actions); error messages that state what went wrong and how to recover; confirmation and fallback copy that matches the actual payload or action; accurate pluralization (`1 item` vs. `2 items`).
- **Typography**: Heading sizes descend with semantic level (`<h1>` > `<h2>` > `<h3>`); `font-variant-numeric: tabular-nums` on aligned or updating numbers in rows and tables; mobile inputs `>= 16px` to prevent iOS Safari auto-zoom; truncated text that hides critical data must leave the full value reachable in a detail view, sheet, or disclosure.
- **Colors**: Compute actual WCAG 2 contrast ratios from declared theme tokens in both light and dark modes (`>= 4.5:1` normal text, `>= 3:1` large text and interactive boundaries) rather than guessing; use semantic tokens in their intended role rather than raw literals; keep one primary filled action per view and reserve danger/error hues for destructive actions or errors; never rely on color alone to convey state.
- **UI**: Verify hover, focus, active (`scale(0.96)` or project press feedback), disabled, and selected states match actual interactivity across all peers (no hover border/cursor on non-clickable cards; no stuck `:hover` on touch without `@media (hover: hover)`); concentric border radii on nested containers; specify exact `transition-property` values instead of `transition: all`.

**Exclusions (evidence, not ceremony or taste):**
- Report only demonstrated consequences, not checklist violations by themselves, and never flag behavior mandated by the project's product spec.
- Do not require placeholder examples, ellipses, input `name` attributes, or identical focus styling without a concrete usability issue or an applicable project rule.
- Skip all screen-reader, assistive-technology, `aria-*`, `role`, `alt`-text, `<label for>`, and live-region (`role="status"` / `role="alert"` / `aria-live`) findings unless the user explicitly asked for a screen-reader audit.
- Skip RTL and CSS logical-property findings (`margin-inline-*`, `padding-inline-*`, `inset-inline-*`, `text-start`) unless the repository actively localizes into RTL languages.
- Respect intentional fixed card heights and single-line truncation (`.truncate` / `line-clamp`) in dense card grids when the full value is reachable in an editor, detail view, or sheet; never require dense card grids to wrap into uneven row heights. Supplementary values (counts, progress summaries, totals) may be exposed through those paths; do not require extra visible text solely because the old design showed it. Report information unavailable through any supported path, explicit product requirement violations, and demonstrated task failures.
- Never launch unprompted multi-viewport, 200%-zoom, or RTL browser sweeps.

**Severity, consolidation, and cap:**
- `HIGH`: blocks a task, misleads the user, hides or clips content or controls at supported viewports, fails required text contrast, creates data-loss risk, or uses a destructive/error treatment against its meaning.
- `MEDIUM`: meaningfully harms comprehension, hierarchy, adaptability, state consistency, or recovery.
- `LOW`: isolated polish with limited task impact.
- Consolidate one root cause into a single row listing every confirmed `path/to/file:line` location. Report at most **15** `Introduced` and `Regression` findings, ordered by severity then reach, plus at most **3** `Pre-existing` findings.

### 8. Never mutate the working tree

A change review is read-only, including the checkout. Fetch pull request refs; never check them out. `git fetch` writes only to `.git` and is permitted. `gh pr checkout`, `git checkout`, `git switch` and `git stash` rewrite the files the author has open. They fail against local edits or discard them, so they are never permitted.

Rendered verification is opt-in. Mark visual and runtime claims **Not verified** unless the project exposes a cheap preview or the user asks for a rendered review. When they do, use an isolated worktree (`git worktree add /tmp/review-<n> refs/remotes/pr/<n>`) and remove it when done.

## Before you finish

| Mistake | Fix |
| --- | --- |
| One stray edit reviewed instead of the branch | Check `merge-base` before the working tree, and report both counts |
| The last commit reviewed because there was no change | State the facts and offer the last commit, a named target, or a repository audit |
| Hunks reviewed without their consumers | Expand one hop, two for tokens and primitives, and name what you skipped |
| Only the `+` side of the diff read | Search the `-` side for removed accessibility, focus, motion and text signals |
| An equivalent replacement reported as a regression | Check the removal against its domain in §7; report only confirmed regressions |
| A removal reported as a new mistake | Status it `Regression` so the author knows it used to work |
| A line near a hunk statused `Introduced` | Status by what the diff touched, confirmed with `git blame` against the base ref |
| A pull request checked out to review it | Fetch the ref and review it in place |
| Line numbers cited that do not exist on the reviewed ref | Cite against the head ref named in the scope block |
| One root cause split into per-file rows | Consolidate into one row listing every confirmed `path/to/file:line` |
| Correctness, test, or security findings in the report | Name the concern once, point at the project's code review and drop it |

## Review output format

Open with the scope block:

| Field | Value |
| --- | --- |
| Target | `branch`, `working`, `staged`, `pr 482`, or the range as entered |
| Base ref | `origin/main` at `a1b2c3d` |
| Head ref | `refs/remotes/pr/482` at `e4f5g6h` |
| Commits | 7 committed, 2 files uncommitted |
| Files in scope | 12 after exclusions |
| Excluded | `pnpm-lock.yaml`, `src/__snapshots__/`: lockfile and snapshots |
| Surfaces expanded | `CheckoutPage`, `SettingsPanel`; 3 further `Button` consumers not expanded |

Followed by the domain coverage table across `Accessibility`, `Layout`, `Writing`, `Typography`, `Colors`, and `UI`:

| Domain | Evidence inspected | Result |
| --- | --- | --- |
| Accessibility | Files, components, states, or checks | Findings count, `Clear`, or `Not reviewed: no evidence in the change scope` |

Then the findings, with a `Status` column per **Classify every finding**:

| Severity | Domain | Status | Location | Before | After | Why |
| --- | --- | --- | --- | --- | --- | --- |
| HIGH | Layout | Regression | `src/Dialog.tsx:42` | `min-h-11` removed in this change | Restore `min-h-11` on the close button | The close control shrank below the 44px touch target |

With no `Introduced` or `Regression` findings, omit the table and state "No actionable interface findings in this change."

Then `Pre-existing` findings, at most three, highest severity first, stated plainly as not this change's responsibility. Omit the section when there are none.

| Severity | Domain | Location | Issue |
| --- | --- | --- | --- |
| MEDIUM | Typography | `src/Toolbar.tsx:7` | Numeric badges use proportional figures; predates this change |

Then list **Verification**: the exact commands or checks run and their results, separated from checks marked **Not verified**.

The cap and the verdict cover `Introduced` and `Regression` only. `Pre-existing` findings sit outside the cap, so touching a legacy file cannot turn into a full-file audit. They sit outside the verdict too, so a change whose only findings are pre-existing is an `Approve`.

End with `Block` when any `HIGH` `Introduced` or `Regression` finding remains and `Approve` otherwise, leaving the remaining findings in the table as work to do.
