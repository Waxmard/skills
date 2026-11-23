---
name: ticket-draft
description: >-
  Use when asked to draft, write, or file a ticket or issue (Jira, GitHub
  issues, Linear) from a bug, spike, investigation, or feature
  idea, file follow-up tickets from a spike, or tighten unstarted backlog
  tickets, with intake forms and story-point weights. Checks for overlapping
  open tickets and offers to post after confirmation; not for status updates.
  Trigger: "write a ticket", "create a Jira", "file an issue", "open an
  issue", "turn this into a ticket", "tighten tickets", or /ticket-draft.
---

# Ticket drafting

Tickets are actionable work-planning records. Every ticket must be understandable, assignable, estimable, and verifiable on its own without undocumented chat context: state the problem, goal, and hard constraints, not how to build it, so the assignee has room to shape the solution.

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- The tracker's CLI, as named in its `references/<tracker>-<project>.md`: `jira` (ankitpokhrel/jira-cli, configured with `jira init`), `gh` (logged in), or whatever the reference names for Linear

Install missing tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## Calibrate first

Find out which tracker and project the ticket goes to. If it's unclear, ask. Then pull 10–20 recent tickets the user wrote there, so the voice and weights match. Tracker commands, known scales, title examples, and repo path conventions live in `references/<tracker>-<project>.md`. Those files are local to this machine and never synced; read the matching one. Before pulling them, check the tracker's CLI with `command -v <cli>` (plus `gh auth status` for GitHub issues). If it fails, stop and tell the user what to install, configure, or log in to.

No reference for the tracker yet? Use its CLI (`gh issue list`, etc.) to read recent tickets, then add a `references/<tracker>-<project>.md` with what you learned. Do not inherit native-field duplicates or repeated boilerplate from older tickets (`priority::*` labels, `**Story Points**: N` body lines, bare inline blocker lists, or repo-wide architecture/wiki footers already linked from README).

## Merge & readiness first

Always err on the side of merging when existing open work covers the same outcome. Before drafting a new ticket, list the project's open tickets and look for one this scope fits, even if it's assigned to someone else. Merge drafts into each other too, when they share a symptom, a screen, or an owner's in-flight work. Don't merge into tickets that are Blocked (the new work would inherit the block), or into tickets that are In Review or Done. When merging, the output is a comment for the target ticket and a revised weight for it, not a new ticket. Remind the user to give the owner a heads-up.

Enforce the SOP readiness gate before drafting:
- **Self-contained context**: Never rely on undocumented Slack/meeting context (`"as discussed"`, `"fix issue"`, `"work on cloud"`). Self-contained means clear problem, goal, and constraints, not a prescribed implementation; leave approach open where the assignee should exercise judgment. If critical context is missing to make the ticket understandable, assignable, estimable, and verifiable, ask before drafting. If resolving an open question is the first step of the work itself, write that question explicitly at the top of the ticket description.
- **One independently trackable outcome per ticket**: Split unrelated deliverables into separate tickets. Keep single deliverables together — do not split one feature's schema, UI, and migration into separate top-level tickets; use subtasks when step-level tracking is needed.
- **No secrets**: Never include credentials, tokens, keys, or sensitive data in ticket text.
- **No Priority field**: Never propose or set a `Priority` field unless the user explicitly asks for one.

## Title

- Use **Verb + deliverable + scope** (3–7 words naming one outcome) for targeted fixes and features, or a concise **2–4 word theme title** (e.g., `Uploader form polish`, `Dev environment refresh`) for broad improvement or open-ended tickets where a short topic title leaves room to shape the solution.
- Simple phrasing always wins. Never join two changes with "and"; leave standards names, mechanisms, and second clauses to the description.
- Write from the consumer's point of view: say what users or downstream teams get, not how it is built. When a parent or sibling ticket has an established title pattern, mirror it so related tickets read as a set (`<Theme> for Existing <X>` → `<Theme> for New <Y>`).
- Prefix the app or service name when project conventions call for it (`<App> ...`), or include it in the scope clause. Use concise fragments with no trailing period.
- Good: `Uploader form polish`, `Delete saved filters in Uploader`, `Generate default upload names automatically`, `Add entity type config in catalog service`, `Provision CloudSQL databases in us-east4`.
- Bad: vague placeholders (`Fix issue`, `Work on cloud`, `As discussed`), root-cause essays, raw line numbers/config keys, or stacked clauses that list every mechanism (`Enforce <standard> <field> writes and <policy> checks in <service>`).

## Description (compact SOP default)

Write in plain, concise language so an unfamiliar teammate understands the goal and why it matters, while leaving room to decide how to build it. Credit the reporter or requester by first name when known (e.g. "Sam asked…", "From Sam:"); never write `"a user"` if the name is known, and ask if unknown.

Use this compact section layout inside the ticket description body:

```markdown
### Background / current state

- **<Label>:** <one fact: what the requester saw or what exists today>

### Desired state / proposed outcome

- **<Label>:** <one fact: target end state or user-visible outcome>

### Dependencies

- **<Label>:** <include only when prerequisites, blockers, approvals, access, or vendor actions exist>

### Risks / security / change

- **<Label>:** <include only when material: IAM, data sensitivity, exposure, compliance, outage, rollback, change window>

### References

- **<Label>:** <include only for sources not already cited above: design docs, ADRs, runbooks, PRs>

### Acceptance criteria

1. <Observable, testable condition that defines completion>
2. <Observable, testable condition — two engineers can independently agree it is done>
```

Formatting:
- Omit `Dependencies`, `Risks / security / change`, and `References` when none apply. Omit `### Dependencies` when a native blocking link already carries a ticket-to-ticket prerequisite, and omit `### References` for repo-wide architecture docs already linked in the repo README. No raw line numbers or speculative option essays.
- Use bullets, never paragraphs. Each bullet holds one idea in about 20 words or fewer.
- Start each bullet with a **bold** label of 1–3 words (`- **Gap:** …`, `- **IAM:** …`).
- Use inline code only for literal identifiers someone will copy (paths, column names, permissions, config values). Write product names as plain text.
- Section titles are headings; bold is only for bullet labels. Leave a blank line between a heading and its list, or jira-cli posts the bullets as literal "- " text.
- Write every ticket or epic key as a clickable link (`[KEY-123](<tracker-url>/browse/KEY-123)`, or bare `#123` where the tracker auto-links); never wrap tracker refs in backticks, which disables auto-linking. Only reference timeboxes, boards, or groupings by a link or the exact label visible in the tracker UI; never invent names or numbers from hidden API fields (such as turning an internal sequence ID into "Sprint 3"). Create a tracker link only for a real dependency, meaning one ticket cannot start or finish until the other is done, using the blocking type (`Blocks` in Jira) in the correct direction. Never link for a mention, a shared parent, siblings, the ticket's own parent or subtasks, a merge, or provenance: the description or merge comment already carries the key.
- Desired state names the outcome; Acceptance criteria hold the specific checks. Don't restate one in the other, and don't repeat a Dependency as a Risk.
- **Outcome, not implementation:** Productive ambiguity is good. State the problem, desired outcome, and hard constraints (security, compliance, external contracts), and let the assignee choose the approach, tooling, and internal details. Never paste an implementation plan or PR diff summary into a ticket: omit build recipes, internal schemas or config details, and file-by-file change lists unless a fixed external contract requires them.
- Keep length tight: treat `~60 words` above Acceptance criteria (at most 4 Background bullets and one Desired-state bullet) and `at most 5 acceptance criteria` (one line each, one per distinct outcome) as **ceilings, not targets**; shorter is better. For broad, improvement, or exploratory tickets, use 1–3 high-level outcome checks (or omit `### Acceptance criteria` and any unused headings) when a rigid checklist would over-constrain the assignee.
- Background states what the requester saw, one bullet per problem. Leave out root-cause guesses, evidence trails, cleanup caveats, and answers to side questions; they go in the chat reply or a Task.
- When editing an existing ticket's scope in place, update the existing sections directly instead of appending dated changelog headings (`### Scope (YYYY-MM-DD)`).

## Sizing, ownership & breakdown

- **Weight (Story Points)**: Use the scale the project already uses (story points, Linear estimate); the project's reference file has it. Default Fibonacci scale when there's no history:
  - **0**: overtaken by events (OBE), closed with no work.
  - **1**: one small change in one place (a config value, a button, an env var).
  - **2**: a small, well-scoped build or a testing pass.
  - **3**: a known problem that needs some investigation or touches 2+ repos/layers.
  - **5**: a cross-cutting or murky bug, LLM/agent behavior debugging, or a cleanup/migration.
  - **8**: large or vague, needs design or stakeholder input.
  Never go above 8. If merged scope would push a ticket past 8, use 8. Suggest one number and cite one or two comparable tickets in a short line. Agent/prompt behavior bugs skew higher because they need prod iteration to verify.
- **Primary POC / Alternate POC**: Identify one accountable primary owner (Assignee) and one backup owner (the Alternate POC, set as the ticket's **Reporter**), plus specialist contributors if needed. Every ticket always has a Reporter, Tasks included, and the Reporter must never be the same person as the Assignee. If the Alternate POC is unknown and the user (the person filing) is not the Assignee, set the user as Reporter and show it as `Reporter: <user> (default)` in the draft metadata; if the user is the Assignee, ask for an Alternate POC.
- **Target date / milestone** (when applicable): State the date and whether it is fixed (external commitment/event) or preferred.
- **Subtasks / work breakdown** (when applicable): If a ticket is large (`5`–`8` SP or spans multiple independently verifiable phases), list concrete subtasks with owners/estimates so progress is trackable without an opaque monolith.

## Full intake form (on request)

When the user asks for an intake form, intake doc, or TPM review document, output the SOP two-table form instead of the compact description:
- **Rule**: Use `N/A — <reason>` for any field that does not apply; never leave a field blank. Omit `Requested priority` and `Expected duration` unless explicitly requested (size with `Weight (Story Points)` only).
- **1. Request basics** (markdown table):
  - `Proposed title / summary` (`Verb + deliverable + scope`)
  - `Primary POC / Alternate POC` (primary owner + backup owner + specialist contributors if needed)
  - `Initiative (Aligned with priorities of Sprint)` (parent Initiative / Epic or strategic workstream)
  - `Business / delivery outcome (why is this needed?)` (1–2 sentences on operational, security, reliability, compliance, or user outcome)
  - `Weight (Story Points)` (Fibonacci story points and key sizing assumptions)
  - `Environment / scope` (GCP project, region, environment, service, repo, dataset, network, or application boundary)
  - `Target date / milestone` (date + whether fixed or preferred, or `N/A — <reason>`)
- **2. Thorough description** (markdown table):
  - `Background / current state` (what exists today, what problem is occurring, or what requirement triggered this work)
  - `Desired state / proposed outcome` (what will be true when complete, and subtask breakdown if needed)
  - `Dependencies` (upstream/downstream tickets, external teams, approvals, access, vendor actions, or `N/A — <reason>`)
  - `Risks / security / change` (IAM, data sensitivity, network exposure, compliance, outage, rollback, or `N/A — <reason>`)
  - `References / evidence` (links to design docs, ADRs, diagrams, runbooks, logs, PRs, related tickets, or `N/A — <reason>`)
  - `Acceptance criteria (numbered, testable)` (`1. ... 2. ... 3. ...` — specific, observable conditions that define completion)

## Output

Give each draft as plain blocks ready to review or paste:
1. **Title** (`Verb + deliverable + scope`)
2. **Description** (compact SOP format by default, or the 2-table intake form if requested)
3. **Planned metadata**: `Type`, `Parent / Initiative`, `Primary POC (Assignee)`, `Reporter (Alternate POC)`, `Weight (SP)`, `Labels`, `Sprint / Iteration / Milestone`, `Target date` (if any), `Subtasks` (if any), and `Links` (blocking dependencies only, with direction, e.g. `Blocked by KEY-123`; omit when none). Only when the tracker has no settable reporter, append an "Alternate POC: <name>" line above the Acceptance criteria heading.

Then offer to post. If the user agrees, post one ticket at a time:
1. Re-check the tracker for tickets created since drafting; if one now covers a draft, merge into it or skip the draft.
2. Show the draft with its metadata and ask the user: Post / Skip / Post without links. In the same question, ask whether it goes in the current sprint, iteration, or milestone, naming it; never assume either answer.
3. On Post, create it with every field the CLI can set (including weight, parent, assignee when known, and labels); create any confirmed subtasks; create the blocking links; add it to the sprint, iteration, or milestone only if the user said so; and report the key.

Merges follow the same confirm-first flow: comment on the target, move any blocking links that still apply to the target, then delete the merged-away ticket only if the user agrees. Never create, edit, or delete tickets without that per-ticket confirmation.

Before changing any existing ticket (comment, link, edit, sprint, iteration, or milestone move, delete, close), check the ticket's assignee via the tracker CLI (or its reference). If it's assigned to anyone other than the user, or the check fails, ask a second, separate question after the per-ticket confirmation. Name the ticket, its assignee, and every change planned for it in one question (e.g. "KEY-123 is assigned to Sam Lee. Comment and move 1 link anyway?"). Offer "Don't touch, give me the text" first, as the default, then "<changes> anyway". On "Don't touch", print the comment or change for the user to apply and move to the next ticket. Unassigned tickets and the user's own tickets need only the per-ticket confirmation.

## Harness notes

| Step says | omp | Claude Code | Other agents |
|---|---|---|---|
| invoke with args | `/skill:<skill> <args>` | `/<skill> <args>` | first message |
| ask the user | `ask` tool | AskUserQuestion | plain-text question |
