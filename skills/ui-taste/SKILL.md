---
name: ui-taste
description: Maxwell's personal UI design preferences, layered on top of frontend-design. Use whenever building, restyling, or reviewing UI in Maxwell's projects, alongside frontend-design. Run with no build task to review a surface against these preferences.
---

# UI Taste

This is a preference layer. `frontend-design` owns the build process: brief → token plan → review against defaults → build → critique. This file says what Maxwell likes, where that differs from frontend-design's defaults, and which other skills to load at each step. The one process it owns is **Review**, below.

Precedence: the brief > the repo's existing tokens or design system > this file > `interface-design` / `emil-design-eng` > frontend-design defaults.

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- `git`, for the review memo (without it, every review is full)

Install missing tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## Workflow

For building or restyling. With no build task, skip to **Review**.

1. If `local.md` exists in this skill's directory, read it first. It holds repo-specific rules and exemplars, and it takes precedence over this file for the repos it names.
2. Load `frontend-design` and follow its two-pass process.
3. Look at the repo before planning:
   - If it depends on an in-house design-system package or ships brand tokens: use that package's tokens, base styles and primitives. Don't invent a palette or font. The brand's look wins, even where frontend-design would call it a generic tell.
   - If it already has a token source (`:root` custom properties, Tailwind `@theme`, a theme object): extend that one. Never start a second token source.
   - Otherwise: create one CSS custom-property token file and derive everything from it.
4. Classify the surface as a **tool** (dashboard, uploader, tracker, admin, companion app) or a **page** (landing, marketing, docs). For tools, also load `interface-design` for craft guidance. Don't create `.interface-design/system.md`; the project's token file is the system.
5. Build the token plan from the Fingerprint below. When reviewing the plan against frontend-design's defaults, apply the Overrides.
6. Build. Apply `emil-design-eng` for interaction craft, and follow the Motion section.
7. Review in this order: `web-design-guidelines` on the changed files, then `better-interface` on the surface you built. If you changed an existing surface, ask Maxwell to run `interface-review` instead; it's user-invoked. Fix every HIGH finding. List the MEDIUM/LOW findings for Maxwell in the **Review output** format below. If one of these skills isn't installed, say which and continue.

## Review

Run this when the skill is invoked with no build or restyle task, or when Maxwell asks for a review or critique. It edits nothing in the working tree until Maxwell picks findings by number; its only write is the memo under `.git` (see **Memo**).

1. Do Workflow steps 1, 3 and 4: read `local.md`, find the repo's token source or brand system, and classify the surface. Load `frontend-design` for its calibration list and its restraint guidance. Then load the memo (see **Memo**) to decide between a full and a delta review.
2. Resolve scope from the request: a screen, a flow, or the whole app. Render it at desktop, 390px and short landscape (667×375) and inspect the rendered result, not only the source. If nothing can be rendered, review from source and say so in **Coverage**.
3. **Taste audit.** Walk every Fingerprint subsection, the Overrides, and the Avoid list against the surface (in a delta review, against the changed files only). Each deviation is a `Taste` finding that cites the rule it breaks, e.g. `Fingerprint › Tokens and color` or `Avoid › stock kit class strings`. In a review, the repo's existing tokens decide what the fix uses, not whether the deviation is reported. A repo already built on a kit (daisyUI etc.) still gets the finding, with the fix written in that repo's tokens. The only exemption is a brand design system named in `local.md`: its canvas, accent and font are never findings.
4. **Design suggestions.** Judge the surface as a designer, not a checklist, using frontend-design's principles:
   - Is the subject's world visible (palette, accent face, vernacular)?
   - Is there one signature element, and is it spent in the right place?
   - Do hierarchy and density fit the surface's main job?
   - Does any of frontend-design's generic-default traits appear?
   - Is there a missing motion moment that would show what changed?

   Propose a `Design` suggestion only when one is worth making, each naming the element, the change, and the token or Fingerprint value it would use. In a delta review, carry over the earlier suggestions and add new ones only for changed files.
5. **Accessibility and usability.** Run `web-design-guidelines` on the surface's source files, then `better-interface` on the rendered surface. Use their checks, severities and cap. Drop their table and verdict formats; restate each finding in the format below. When both report the same issue, keep one finding. If either skill isn't installed, say which in **Coverage** and continue. In a delta review, run `web-design-guidelines` on the changed files only. Run `better-interface` on the whole rendered surface, but report only issues that come from changed files or are visible regressions.
6. Emit **Review output**, write the memo, and stop.
7. On a numbered reply, apply those findings, then run Review again; the memo makes it a delta review.

Taste severity:
- `HIGH`: breaks a Layout and stability rule, or an Avoid entry that runs through a shared component or token.
- `MEDIUM`: a Fingerprint deviation in a shared token, primitive or layout.
- `LOW`: a deviation in one leaf component.

Design suggestions carry `SUGGESTION` instead of a severity.

### Memo

The memo lets a rerun after fixes skip what hasn't changed. It lives at `$(git rev-parse --git-path ui-taste)/<branch>/` (per worktree, never committed): `state` holds `tree`, `scope` and `rules` lines, and `findings.md` holds the last Review output verbatim. Outside a git repo there is no memo: always run a full review and say `no memo: not a git repo` under **Coverage**.

```bash
command -v git >/dev/null || echo "missing: git"
```
If it prints, skip the snapshot and memo, run a full review, and say `no memo: git missing` under **Coverage**.

At the start of a review, take a snapshot of the working tree:

```bash
top=$(git rev-parse --show-toplevel)
idx=$(mktemp)
cp "$(git rev-parse --git-path index)" "$idx" 2>/dev/null
GIT_INDEX_FILE="$idx" git -C "$top" add -A
tree=$(GIT_INDEX_FILE="$idx" git -C "$top" write-tree)
rm -f "$idx"
```

`rules` is `git hash-object` of this skill's `SKILL.md` and of `local.md` if it exists, joined by a space. `scope` is the resolved scope from step 2, written as the routes or components reviewed.

Run a **full** review if any of these is true:
- there is no memo;
- `git cat-file -e <memo tree>` fails;
- `scope` or `rules` differs;
- the reply or request contains `full`;
- the changed files include the repo's token source from Workflow step 3.

Otherwise run a **delta** review over `git diff --name-only <memo tree> <tree>`, limited to files in scope. If that list is empty, re-emit the memo's findings renumbered, write `No changes since last review; reply `full` to re-review.` under **Coverage**, and stop.

In a delta review, read `findings.md` and handle each earlier finding as follows:
- **File unchanged:** carry it over as written, and append ` · carried` to its header line.
- **File changed and the issue is gone:** drop it, and list its old number in a `Resolved since last review: #2, #4` line above **Coverage**.
- **File changed and the issue is still there:** restate it with the current line number.

Numbering restarts at 1 every run; old numbers appear only in the Resolved line. Start the **Coverage** line with `Mode: delta, N files re-reviewed; reply `full` for a full review.`

After emitting the output, write the memo. Fill in the literals, because bash calls may not share a shell:
`d="$(git rev-parse --git-path ui-taste)/<branch>" && mkdir -p "$d" && printf 'tree %s\nscope %s\nrules %s\n' <tree> '<scope>' '<rules>' > "$d/state"`. Then write the Review output verbatim to `$d/findings.md`.

### Review output

Number every finding 1..N in one sequence across both sections. Rank by severity within each section, and put Design suggestions after the Taste findings.

````
## Taste and design

**1. HIGH · Taste** — `src/lib/components/ui/button/button.svelte:14`
**Now:** every button variant is a daisyUI `btn-*` class string.
**Change:** a token-themed button primitive whose variants derive from `--color-primary` with `color-mix()`.
**Why:** Avoid › stock kit class strings.

**2. SUGGESTION · Design** — `src/routes/+page.svelte:250`
**Now:** …
**Change:** …
**Why:** …

## Accessibility and usability

**3. MEDIUM · Accessibility** — `src/routes/+page.svelte:497`
**Now:** …
**Change:** …
**Why:** …
````

- The domain after `·` is `Taste`, `Design`, or the owning domain from `better-interface` (Accessibility, Layout, Writing, Typography, Color, Polish).
- For a finding that spans files, name the file holding the shared fix and list the others in **Now**. Keep each block to the three labelled lines, one sentence each.
- After the findings, add one **Coverage** line: the domains inspected, any `Not reviewed` and why, and anything not verified.
- In a delta review, add ` / carried C / resolved R` to the end of the Summary line.
- End with:
  ```
  ---
  Summary: N findings — HIGH X / MEDIUM Y / LOW Z / suggestions S
  Reply with the numbers to fix.
  ```

## Fingerprint

### Tokens and color
- Every value comes from custom properties. Components never contain hex or rgb literals; derive variants with `color-mix()`.
- Tool canvas: cool near-white (`#f8f9fc`), white surfaces, slightly recessed input fill (`#f1f3f8`).
- Text has three tiers tinted toward the palette, never neutral grey: primary / secondary / muted (e.g. `#1a1d2e / #5a5f7a / #9298b0`).
- Borders are alpha hairlines (`rgba(0,0,0,.08)`, subtle `.04`), not solid greys.
- The palette comes from the subject. If the domain has its own color system (Pokémon types, pipeline stages, data classifications), that system is the palette. Every domain color gets a fill plus a contrast-tuned text/label shade.
- One functional accent (blue family) plus semantic success, warning and danger. Colored glows (`0 0 12–20px`, semantic color at .25–.3) only mark state: selected, success, danger.
- A secondary property of an item (e.g. a sensitive-data flag) gets its own tone and icon. It never recolors the primary verdict.

### Type
- Body text uses a neutral grotesk: the system stack or a Public Sans-class face. Personality comes from one contextual accent face used only for the subject's world (e.g. Baskerville for Pokédex "specimen" text such as types, locations and nicknames). Never use it for UI chrome.
- Headings: weight 700, tracking -0.02 to -0.03em. Hero-scale titles use `clamp()` with line-height around 1.
- Section headers: about 0.8rem, weight 600–700, uppercase, +0.05–0.08em tracking, muted color. Use them at one level only (see Overrides).
- Put `font-variant-numeric: tabular-nums` on every number that changes: counts, bytes, timestamps, scores.
- Use monospace only for codes a person reads or types (session codes, room codes, IDs), uppercase with +0.15em tracking.

### Shape and depth
- Spacing is a 4px scale (4/8/12/16/20/24/32/40). It tightens below ~430px and loosens at 1024px and up.
- Radius follows hierarchy: tags 6 → badges 8 → inputs and small cards 12 → cards and dialogs 16 → hero panels 20–24. Status chips, badges, toggles and mode switches are pills (`999px`).
- Shadows are a four-step neutral scale from `0 1px 3px rgba(0,0,0,.08)` to `0 12px 40px rgba(0,0,0,.15)`. Elevation only increases for real lift: hover, drag, dialog.
- Put boldness into one signature shape taken from the subject, e.g. a hexagon `clip-path` gem for a Tera toggle, rather than scattered decoration.

### Layout and stability (non-negotiable)
- No layout shift. Containers that receive variable content get a fixed or clamped height and scroll internally (e.g. a file picker at `clamp(14rem, 25vh, 17.5rem)`). Sibling columns share one height so switching modes never moves the page.
- When a number changes, stack the old and new values in one grid cell (`display: inline-grid; > * { grid-area: 1 / 1 }`) and cross-fade them with a 3px blur and a 5px vertical slide, so the width never jitters.
- Panels that own background work (uploads, polling) stay mounted when hidden. Stack them in one grid cell and mark the inactive one `inert` plus `visibility: hidden`.
- A tool's main job fits on one screen. For grids, use `repeat(auto-fill, minmax(min(var(--grid-min, 320px), 100%), 1fr))`, not breakpoint ladders.
- Pinned, high-contrast header. Clamp content width with `min(var(--content-max-width), calc(100vw - 3rem))`.
- Keep modal and detail state in URL query params so it can be deep-linked.

### Motion
- One default easing: `cubic-bezier(0.22, 1, 0.36, 1)`. It front-loads the motion, so it reads as an instant response that then settles. Micro-interactions take 150–250ms; panels and reveals take 350–400ms. Nothing longer than 500ms, and 500ms only for a single emphasis moment. If the project already has motion tokens, use them.
- Tactile feedback: `:active` scales to 0.95–0.98, hover lifts 1–4px, selected items scale to about 1.05.
- Segmented controls and mode switches use a sliding pill indicator, positioned from the active item's `offsetLeft`/`offsetWidth` and re-measured with a `ResizeObserver`.
- Keyed lists reorder with FLIP (Vue `TransitionGroup` move class, Svelte `animate:flip`, or the framework's equivalent). Leaving items get `position: absolute` so the remaining ones slide into place.
- Stagger at 40ms × index, and only for rows that appear together as a group.
- Reference, not default: [transitions.dev](https://transitions.dev) is a third-party catalogue of bare-CSS transitions with a token scale that matches the values above. The local `transitions-dev` skill mirrors its snippets, and `transitions-polish` mirrors its timing rules. When a needed animation matches one of its patterns (e.g. tabs sliding, number pop-in, menu dropdown, modal, panel reveal, skeleton reveal), it's fine to adapt that snippet into the project's own tokens. Don't import its `_root.css` or tag snippets unless the project already does.
- Every project includes this reset:
  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
  ```

### Mobile
- 44px minimum touch targets, `touch-action: manipulation`, `-webkit-tap-highlight-color: transparent`, and safe-area padding (`calc(var(--space-4) + env(safe-area-inset-top))`).
- Short landscape phones (`(orientation: landscape) and (max-height: 500px)`) get their own side-by-side layout, not a squashed portrait one.
- Drag interactions work with both touch and mouse: add touch handlers alongside HTML5 drag-and-drop.

### Forms
- A field that appears on several forms sits in the same row grouping and slot on every one of them.
- Pair fields by how wide their values get, not by how they read. A multi-select that grows gets its own `auto-fit` row. Never put three multi-selects in one row.
- Filters in a header are "ghost" inputs: borderless, with an underline that appears only on hover or focus (160ms).
- Use the component library for accessible controls (inputs, selects, buttons, drawers, tooltips), themed through its override API. Never adopt the library's shell, card or layout styling.

### Theming
- Decide theme support on purpose. For two themes, swap tokens on `:root[data-theme="dark"]` and design the dark surfaces; don't just invert. For a single theme, set `color-scheme` and make `theme-color` and the status bar match the canvas.

## Overrides to frontend-design

Where frontend-design calls these generic tells, this file wins:
- **Uppercase section headers:** allowed, as one small, muted, tracked level for real section titles. The ban still applies to decorative eyebrows above every heading.
- **Dot-joined counts:** allowed for live status summaries (`3 clean · 1 scanning`). They're still banned as decorative metadata strings.
- **Monospace:** allowed for codes a person reads or types. It's still not for generic small labels.
- **Cards with a shared shadow scale:** fine in tool UIs, as long as the radius varies with hierarchy and each card holds a real unit (a team slot, a gym, a session). Don't wrap prose in cards.
- **Cream/gold backgrounds:** only when a repo's brand design system requires them. Otherwise frontend-design's warning stands.

## Avoid (seen in Maxwell's less-proud projects)
- Stock kit class strings that need override hacks to pass contrast (e.g. DaisyUI `btn-*`). Prefer primitives themed through tokens.
- Roboto, Arial or the platform default font as the choice for a tool, or rounded "friendly" faces like Nunito.
- Entrance animations of 600–1000ms, or animating every screen load.
- One theme with a mismatched status bar or `theme-color`.
- Tokens written twice (CSS plus a TS mirror). Keep one source and add typed wrappers if needed.
- Hand-written breakpoint ladders that set `repeat(2..6, 1fr)`.

## Exemplars

When a rule needs a concrete reference, read the source:
- Tokens, spacing, safe areas, reduced motion: `https://github.com/Waxmard/pokemon-team-status/blob/main/src/styles/main.css`
- Subject palette with contrast-tuned labels and type gradients: `https://github.com/Waxmard/pokemon-team-status/blob/main/src/data/types.js`, `https://github.com/Waxmard/pokemon-team-status/blob/main/src/utils/colors.js`
- Accent serif and the evolution flash: `https://github.com/Waxmard/pokemon-team-status/blob/main/src/components/PokemonPreview.vue`
- Hexagon gem and wizard grids: `https://github.com/Waxmard/pokemon-team-status/blob/main/src/styles/draftPanel.css`
- Touch plus drag-and-drop pinning and score overlays: `https://github.com/Waxmard/pokemon-team-status/blob/main/src/components/GymRow.vue`
- Sliding pill indicator, stacked counters, FLIP list, fixed-height picker, and form-pairing rules: see `local.md` for exemplar paths, if it exists.
