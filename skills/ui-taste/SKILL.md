---
name: ui-taste
description: Use when reviewing, improving, building, or restyling UI in any project. Preserve-first judgment: for an existing interface, inspect the real experience and give ranked improvements; explore bigger ideas separately and implement only the requested or selected changes.
---

# UI taste

Improve the product’s real task, not its conformity to a style template. Preserve useful character and working interactions. Simpler code does not require a visually minimalist interface. Keeping the current UI is a valid candidate.

Mandatory repository rules remain binding. For design choices, the explicit brief and product task outrank generic taste; reuse the existing design system. Read `local.md` when present and apply its explicit brand requirements only to the projects it names.

## Prerequisites & Required Tools

Use the tools already available in the harness. A browser enables visual and interaction evidence; source-only review remains useful with narrower claims. Git is optional for branch/history evidence, not a review prerequisite. Name missing prerequisites and continue within honest limits. Never install tools automatically.

## Workflow and review

1. **Understand and preserve.** Read product guidance, existing tokens/components, the requested surface, and relevant behavior contracts. Identify the main user task, what already works, distinctive visual character, and interaction/state contracts that any change must preserve. Respect existing consumer contracts, including navigation, query state, selections, and shared controls.
2. **Inspect the baseline.** Before proposing visual changes, inspect the rendered experience on desktop, phone, and other viewports relevant to the surface. Use any per-project viewport set named in local.md. Exercise the primary flow, not only a static screenshot. Record observations, user-reported defects, and hypotheses separately. Source alone does not prove appearance or runtime failures; explicitly limit visual claims when rendering is unavailable.
3. **Reason from friction.** Assess discoverability, task steps, comparison/scanning, information relationships, hierarchy, density, feedback, and interaction reliability. For consequential structural changes, compare the smallest useful adjustment with the bigger change: displaced information, hidden controls, added scrolling, and cross-screen impact. Recommend the smallest change that achieves the benefit, not the fewest visible elements.
4. **Get independent critiques.** For screen/flow-wide reviews, use two independent read-only critiques when subagents are available: a task-flow reviewer for effort, discoverability, and state continuity; a visual reviewer for hierarchy, density, character, and affordance. Give both the same brief and baseline evidence before sharing your proposed fixes. Reconcile their arguments; votes and model confidence are not design evidence. If reviewers cannot see images, label their critique source-only. For a localized tweak or without subagents, make these two passes inline; do not invent unavailable tools.
5. **Rank practical improvements.** Each recommendation names the observed or user-reported problem, specific change, user benefit, what it preserves, tradeoff/blast radius, evidence and uncertainty, and how to check the changed behavior. Preference mismatch alone is not a defect. Usually show the strongest 3–5 improvements; do not pad a quota or suppress additional functional blockers. Separate bigger bets. A bigger bet needs a materially better outcome and a before/after sketch or bounded prototype comparison before you recommend implementation. A sketch is a hypothesis, not proof that interactions work.
6. **Suggest, then stop.** Use the review output below. Explain decisions, not private chain-of-thought. A review makes no project or Git-metadata writes, including indexes, refs, objects, or memos. Do not create, mutate, or delete memo directories. On reruns, reread and reinspect the affected surface; do not carry findings solely because one file is unchanged or add replacement caching.
7. **Implement only selected scope.** On a numbered selection, reread affected code and confirm the recommendation still applies before changing only those selected behaviors. If the baseline has materially changed, refresh affected proposals and ask for a new selection rather than applying stale numbers. Explicit build/restyle requests use this judgment within their requested scope, not as permission for unrelated global restyling. Preserve consumer contracts and pass project-required checks plus actual interaction/visual smoke.

## Impact and safety

Severity describes user impact, not how broadly a stylistic deviation occurs in tokens or shared components. Escalate demonstrated task-blocking regressions. Do not automatically fix findings from a review.

Keep a scoped safety floor: meaningful labels, operable keyboard/focus behavior, readable text and control affordances, reachable targets, and reduced-motion support where motion exists. Less emphasis on accessibility does not excuse an unusable control. Report accessibility or other domains where they affect the actual task; do not foreground unrelated conformance trivia or run broad audits unless requested or required by the repository.

## Review output

Use these sections: **What works**, **Recommended improvements**, optional **Bigger bets**, optional **Functional blockers**, and **Coverage**. Name working features concretely, without flattery. Number actionable items once across sections. For each item use compact lines:

- **Problem:** observed/user-reported friction; identify which.
- **Proposal:** specific change and what it preserves.
- **Payoff and tradeoff:** user benefit, cost, and blast radius.
- **Evidence and check:** artifact/source, uncertainty, and a concrete interaction/visual check.

Coverage names inspected surfaces, states, viewports, tools, missing prerequisites, and what was not verified. Avoid findings-count scoreboards. End a review with: “Choose the items to implement; nothing has been changed.”

## Contextual preferences

These are judgment aids, not a deviation checklist or grounds by themselves to replace an existing UI.

- **Color and identity:** use the subject’s meaningful color system, with readable labels and distinguishable states. Preserve intentional brand palettes, richer surfaces, colored cards, and useful decoration. Do not default every tool to a cool-white canvas or blue accent.
- **Hierarchy and density:** make relationships, scanning, and the next action clear. Purposeful information density can be a strength. Cards and visible control boundaries are valid affordances, not kit defects. Reuse existing tokens/components and extend their source rather than creating a second convention.
- **Type and shape:** retain existing fonts when they serve the product, including rounded and system fonts. Choose spacing, radius, and depth from the existing hierarchy and content, not a universal numeric scale or a required signature shape. Tabular numbers can help changing values when width jitter is a real issue.
- **Responsive craft:** keep important information and controls reachable. Compare page scrolling, drawers, wrapping, and panes against the task before choosing. No tool must fit one screen; fixed heights, nested scrolling, or a prescribed landscape layout are not defaults. Preserve navigation and state contracts; modal URL state is useful only when the task requires it.
- **Controls and forms:** preserve recognizability and useful field grouping. Ghost inputs and pill navigation are options, not requirements. Theme existing primitives rather than replacing a kit for its appearance alone.
- **Motion:** use meaningful feedback that explains a state change without delaying operation. Reuse project motion tokens and respect reduced motion. Sliding indicators, animated counters, FLIP, and entrance sequences are optional responses to a demonstrated need, not missing-motion findings.
- **Themes:** follow the project’s intended themes; keep text, surfaces, and platform chrome coherent. Do not introduce a new theme as incidental polish.

Avoid duplicated token systems, decorative changes that obscure state, unproven structural redesigns, and animations that impede the task. Do not turn these cautions into a list of mandatory findings.

### Companion skills and examples

Load companions selectively, with a concrete question. Use `frontend-design` for genuinely new directions/builds, choosing a direction from the actual brief rather than a fixed template. Use `interface-design` for tool interaction questions and `emil-design-eng` for selected interaction polish. Use targeted `better-*`, `web-design-guidelines`, or motion guidance only for a demonstrated question or repository requirement. Do not load a cascade that silently substitutes its defaults for the existing design. Missing companions narrow coverage, not trigger automatic installation.

Examples illustrate mechanisms, not compulsory aesthetics. Exemplars, brand requirements, and viewport sets named in `local.md` are binding only for the projects they name; their exemplar interactions do not become universal rules. External exemplars and old numeric values are optional examples, never reasons by themselves to change an existing UI.

## Tools for evidence and exploration

Before each tool use, name the unresolved question and the artifact needed to answer it. Use the lowest rung that answers the question; more style judges are not more evidence.

1. **Behavior and appearance:** use the available browser driver, screenshots, and a short interaction recording or [Playwright trace](https://playwright.dev/docs/trace-viewer) for dynamic behavior. Compare identical data, state, and viewports. Inspect actual pointer/keyboard operation, not only bounding boxes. Use browser/DevTools layout measurements to investigate a concrete issue. Automated accessibility and designer anti-pattern output are scoped validators, not taste authorities; a modern-minimal preset does not authorize making the product minimal.
2. **Pattern uncertainty:** inspect task-equivalent real-product flows from more than one product. Prefer Mobbin `search_flows`/`search_screens` when connected; otherwise use public references through search/browser. Explain the transferable mechanism instead of copying branding. [Mobbin MCP](https://mobbin.com/mcp) requires paid-plan/OAuth access; absent access means public-reference research, not invented results.
3. **Consequential visual fork:** compare two bounded concepts—incremental versus ambitious—using current screenshots, content, tokens, and retained interaction contracts. Match content and viewports. Use [Google Stitch image-led variants](https://developers.googleblog.com/en/stitch-a-new-way-to-design-uis/) if authorized and available; otherwise use session-local static sketches with available native tooling. Treat concepts as hypotheses. Do not import generated app code or new design tokens automatically.
4. **Supplied design frame:** use Figma MCP `get_design_context` plus `get_screenshot` for the same frame and compare it with the actual UI. See [Figma MCP tools](https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/). Do not create or edit Figma files to run a review. Without a supplied frame, Figma is not a prerequisite.
5. **Disputed image judgment:** use image-capable reviewer agents/models already exposed by the harness with identical evidence and a concrete decision question. A separate provider can be proposed for a disputed call, but do not introduce an account, model API integration, or secret. Label reviewers without image access source-only.

New external uploads, paid access, integrations, and remote mutations require explicit approval. Sanitize screenshots/traces; never transmit credentials or private team data because external tools are welcome. Optional-tool failure falls back to local evidence and records the limitation. Never fabricate service results. Review-only runs may produce explicitly requested session-local evidence/output artifacts, never project or Git-metadata writes.

## Harness notes

Discover actual tools and capabilities; these mappings are examples, not promises of identical names or access.

| Capability | omp | Claude Code |
|---|---|---|
| Render and exercise | Available `browser` driver; connected DevTools tools when appropriate | Connected browser driver/MCP and existing Playwright tooling |
| Screenshots and dynamic evidence | Browser screenshots/recording; available DevTools traces | Connected screenshot/recording tools or existing Playwright traces |
| Independent critiques | `task` subagents; verify image access | Available subagents; verify image access |
| Product references | Connected Mobbin MCP or public search/browser | Connected Mobbin MCP or public search/browser |
| Bounded concepts | Authorized available Stitch; otherwise local native sketches | Authorized connected Stitch; otherwise local native sketches |
| Supplied frame | Connected Figma MCP context and screenshot | Connected Figma MCP context and screenshot |

Missing tooling narrows claims, not the safety floor or the obligation to respect repository rules.
