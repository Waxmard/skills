---
name: ui-taste
description: Maxwell's personal UI design preferences, layered on top of frontend-design. Use whenever building, restyling, or reviewing UI in Maxwell's projects, alongside frontend-design.
---

# UI Taste

This is a preference layer, not a process. `frontend-design` owns the process: brief → token plan → review against defaults → build → critique. This file says what Maxwell likes, where that differs from frontend-design's defaults, and which other skills to load at each step.

Precedence: the brief > the repo's existing tokens or design system > this file > `interface-design` / `emil-design-eng` > frontend-design defaults.

## Workflow

1. If `local.md` exists in this skill's directory, read it first. It holds repo-specific rules and exemplars, and it takes precedence over this file for the repos it names.
2. Load `frontend-design` and follow its two-pass process.
3. Look at the repo before planning:
   - If it depends on an in-house design-system package or ships brand tokens: use that package's tokens, base styles and primitives. Don't invent a palette or font. The brand's look wins, even where frontend-design would call it a generic tell.
   - If it already has a token source (`:root` custom properties, Tailwind `@theme`, a theme object): extend that one. Never start a second token source.
   - Otherwise: create one CSS custom-property token file and derive everything from it.
4. Classify the surface as a **tool** (dashboard, uploader, tracker, admin, companion app) or a **page** (landing, marketing, docs). For tools, also load `interface-design` for craft guidance. Don't create `.interface-design/system.md`; the project's token file is the system.
5. Build the token plan from the Fingerprint below. When reviewing the plan against frontend-design's defaults, apply the Overrides.
6. Build. Apply `emil-design-eng` for interaction craft, and follow the Motion section.
7. Review in this order: `web-design-guidelines` on the changed files, then `better-interface` on the surface you built. If you changed an existing surface, ask Maxwell to run `interface-review` instead; it's user-invoked. Fix every HIGH finding and list MEDIUM/LOW findings for Maxwell. If one of these skills isn't installed, say which and continue.

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
- Sliding pill indicator, stacked counters, FLIP list, fixed-height picker, and form-pairing rules: see `local.md` for exemplar paths, if it exists. The patterns themselves are fully described above.
