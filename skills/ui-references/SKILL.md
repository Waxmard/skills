---
name: ui-references
description: Use when restyling, redesigning, or building a UI screen by borrowing concrete mechanics from reference UIs (local repo paths, live URLs, named apps). Writes a donor-to-host transfer brief and stops for approval before building. Not for reviewing a finished change; use interface-review for that.
---

# UI references

Good UI changes come from concrete donors, not abstract taste. This skill turns "make X feel like A and B, keep Z" into an inspected, approved brief, then builds it.

## Prerequisites & Required Tools

Harness capabilities this skill depends on:

- A browser driver, recommended for rendering donors and the host.
- An ask-the-user tool.
- File read and search.

No browser: continue source-only and label every visual claim in the brief "source-only".

## Harness notes

Steps below use neutral verbs. Map them to your harness:

| Step says | omp | Claude Code | Other agents |
|---|---|---|---|
| invoke with args | `/skill:ui-references <goal>` | `/ui-references <goal>` | first message `<goal>` |
| ask the user | `ask` tool | AskUserQuestion | plain-text question |
| render and screenshot | `browser` tool | connected browser/Playwright MCP | skip, source-only |
| progress list | `todo` | TodoWrite | numbered checklist in chat |

## Catalog

If `local.md` exists in this skill's directory, read it first. It lists donor entries in this format:

```markdown
## <donor name>
- Path: <absolute path or URL>
- Stack: <framework + styling system>
- Tokens: <file(s) holding colors/spacing/radius/motion>
- Run: <command + port>, or "none: no dev server"
- Look at: `<file>`: <mechanic>   (one line per file, 2–6 lines)
- Borrow for: <comma-separated mechanics this donor is good at>
```

If `local.md` is missing, or an entry's path no longer exists, say so in one line and ask for paths or URLs instead. Never invent catalog entries. Never commit `local.md`; it may hold private paths.

## Workflow

1. **Intake (one batched question).** Gather:
   - the host repo and target screen or flow;
   - the goal in the user's words;
   - 1–3 donors;
   - the **take** for each donor (which mechanics to transfer);
   - what the host **keeps** (palette, fonts, domain vocabulary, platform constraints).

   Prefill whatever the invocation already states and ask only for the gaps. When the user named no donors, propose up to three catalog entries whose `Borrow for` matches the goal, plus "other paths/URLs". Donors may use a different stack from the host; mechanics transfer, code does not.
2. **Inspect donors.** For each donor, read its `Tokens` and `Look at` files and extract concrete values:
   - spacing scale, row and card heights, radius, type sizes and weights;
   - color roles;
   - motion durations and easings;
   - component anatomy (what sits leading, middle, and trailing; what's hidden behind a tap).

   Render the donor only when it is already being served or its `Run` is cheap and safe. Never stop or restart a server you didn't start. Screenshot at the host's target viewports: default 390×844 phone, plus 1280×800 desktop when the host is responsive. For URL or app donors, use the public site or app-store screenshots. Record each finding with its source (`file:line` or screenshot).
3. **Inspect the host.** Read the target screen's components and the host's token and theme files. Render its current state at the same viewports. List what is structurally wrong for the goal: elements to delete or restructure, not only restyle.
4. **Write the transfer brief** in chat, with exactly these sections:
   - **Goal**: one sentence.
   - **Transfers**: a numbered table with columns `# | Donor | Mechanic | Evidence | Lands in (host files/components)`.
   - **Host keeps**: bullets.
   - **Host drops**: host structure or code to delete because a transfer replaces it. Deletion is expected; don't wrap old structure in new styling.
   - **Not taking**: donor traits deliberately excluded, such as donor brand colors and fonts unless the take names them.
   - **Viewports & checks**: what the post-build screenshots must show.
   - **Coverage**: what was rendered versus read source-only.

   End with: "Edit the brief, drop rows by number, or say go. Nothing has been changed."
5. **Stop.** Make no edits until the user approves. Apply their edits to the brief and re-show only the changed rows.
6. **Build on approval.** Implement only the approved rows in the host's stack, reusing its tokens and components. Add no new dependency unless a brief row names it. Then follow the host repo's own verification rules. Render the same viewports and compare after-screenshots against the donor and before screenshots, row by row. Report any row that didn't land.

## Rules

- No generic taste rules or style checklists. The donors and the user's words are the only taste source.
- Don't load other design skills (`frontend-design`, `better-*`, `interface-design`, `emil-design-eng`, transitions) unless the user asks.
- Copy mechanics, not branding or code across stacks.
- Host repo rules (`AGENTS.md`, etc.) always win.
- Accessibility floor only: labeled controls, visible keyboard focus, reachable targets.
- Screenshots may contain secrets or private data; they never leave the machine.
