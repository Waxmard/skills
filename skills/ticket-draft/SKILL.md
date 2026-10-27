---
name: ticket-draft
description: >-
  Use when asked to draft, write, or file a ticket or issue (Jira, GitLab
  issues, GitHub issues, Linear) from a bug, investigation, or feature idea,
  with intake forms and story-point weights. Checks for overlapping open
  tickets and offers to post after confirmation; not for status updates.
  Trigger: "write a ticket", "create a Jira", "file an issue", "open an
  issue", "turn this into a ticket", or /ticket-draft.
---

# Ticket drafting

Tickets are actionable work-planning records. Every ticket must be understandable, assignable, estimable, and verifiable on its own without undocumented chat context.

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- The tracker's CLI, as named in its `references/<tracker>-<project>.md`: `jira` (ankitpokhrel/jira-cli, configured with `jira init`), `glab` or `gh` (logged in), or whatever the reference names for Linear

Install missing tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## Calibrate first

Find out which tracker and project the ticket goes to. If it's unclear, ask. Then pull 10–20 recent tickets the user wrote there, so the voice and weights match. Tracker commands, known scales, title examples, and repo path conventions live in `references/<tracker>-<project>.md`. Those files are local to this machine and never synced; read the matching one. Before pulling them, check the tracker's CLI with `command -v <cli>` (plus `glab auth status` or `gh auth status` for GitLab or GitHub issues). If it fails, stop and tell the user what to install, configure, or log in to.

No reference for the tracker yet? Use its CLI (`glab issue list`, `gh issue list`, etc.) to read recent tickets, then add a `references/<tracker>-<project>.md` with what you learned.

## Merge & readiness first

Always err on the side of merging when existing open work covers the same outcome. Before drafting a new ticket, list the project's open tickets and look for one this scope fits, even if it's assigned to someone else. Merge drafts into each other too, when they share a symptom, a screen, or an owner's in-flight work. Don't merge into tickets that are Blocked (the new work would inherit the block), or into tickets that are In Review or Done. When merging, the output is a comment for the target ticket and a revised weight for it, not a new ticket. Remind the user to give the owner a heads-up.

Enforce the SOP readiness gate before drafting:
- **Self-contained context**: Never rely on undocumented Slack/meeting context (`"as discussed"`, `"fix issue"`, `"work on cloud"`). If critical context is missing to make the ticket understandable, assignable, estimable, and verifiable, ask before drafting. If resolving an open question is the first step of the work itself, write that question explicitly at the top of the ticket description.
- **One independently trackable outcome per ticket**: Split unrelated deliverables into separate tickets. Keep single deliverables together — do not split one feature's schema, UI, and migration into separate top-level tickets; use subtasks when step-level tracking is needed.
- **No secrets**: Never include credentials, tokens, keys, or sensitive data in ticket text.
- **No Priority field**: Never propose or set a `Priority` field unless the user explicitly asks for one.

## Title

- Use **Verb + deliverable + scope** so a reader understands the intended outcome without opening the description.
- Simple phrasing always wins: aim for 3–7 words naming one outcome. Never join two changes with "and"; leave standards names, mechanisms, and second clauses to the description.
- Write from the consumer's point of view: say what users or downstream teams get, not how it is built. When a parent or sibling ticket has an established title pattern, mirror it so related tickets read as a set (`<Theme> for Existing <X>` → `<Theme> for New <Y>`).
- Prefix the app or service name when project conventions call for it (`<App> ...`), or include it in the scope clause. Use concise fragments with no trailing period.
- Good: `Delete saved filters in Uploader`, `Generate default upload names automatically`, `Add entity type config in catalog service`, `Provision CloudSQL databases in us-east4`.
- Bad: vague placeholders (`Fix issue`, `Work on cloud`, `As discussed`), noun-only labels with unclear action, root-cause essays, raw line numbers/config keys, or stacked clauses that list every mechanism (`Enforce <standard> <field> writes and <policy> checks in <service>`).

## Description (compact SOP default)

Write in specific, plain language so an unfamiliar teammate knows what to do and why. Credit the reporter or requester by first name when known (e.g. "Sam asked…", "From Sam:"); never write `"a user"` if the name is known, and ask if unknown.

Use this compact section layout inside the ticket description body:

```markdown
### Background / current state

- **<Label>:** <one fact: what the requester saw or what exists today>

### Desired state / proposed outcome

- **<Label>:** <one fact: target end state or component-level approach>

### Dependencies

- **<Label>:** <include only when prerequisites, blockers, approvals, access, or vendor actions exist>

### Risks / security / change

- **<Label>:** <include only when material: IAM, data sensitivity, exposure, compliance, outage, rollback, change window>

### References

- **<Label>:** <include only for sources not already cited above: design docs, ADRs, runbooks, MRs>

### Acceptance criteria

1. <Observable, testable condition that defines completion>
2. <Observable, testable condition — two engineers can independently agree it is done>
```

Formatting:
- Omit `Dependencies`, `Risks / security / change`, and `References` when none apply. No raw line numbers or speculative option essays.
- Use bullets, never paragraphs. Each bullet holds one idea in about 20 words or fewer.
- Start each bullet with a **bold** label of 1–3 words (`- **Gap:** …`, `- **IAM:** …`).
- Use inline code only for literal identifiers someone will copy (paths, column names, permissions, config values). Write product names as plain text.
- State each fact once. Drop References when everything in it is already cited above.
- Section titles are headings; bold is only for bullet labels. Leave a blank line between a heading and its list, or jira-cli posts the bullets as literal "- " text.
- Write every ticket key as a link (`[KEY-123](<tracker-url>/browse/KEY-123)`). Create a tracker link only for a real dependency, meaning one ticket cannot start or finish until the other is done, using the blocking type (`Blocks` in Jira) in the correct direction. Never link for a mention, a shared parent, siblings, the ticket's own parent or subtasks, a merge, or provenance: the description or merge comment already carries the key.
- Desired state names the outcome; Acceptance criteria hold the specific checks. Don't restate one in the other, and don't repeat a Dependency as a Risk.
- Keep the text above Acceptance criteria to about 60 words: at most 4 Background bullets and one Desired-state bullet. Write at most 5 acceptance criteria, one line each, one per distinct outcome.
- Background states what the requester saw, one bullet per problem. Leave out root-cause guesses, evidence trails, cleanup caveats, and answers to side questions; they go in the chat reply or a Task.

## Sizing, ownership & breakdown

- **Weight (Story Points)**: Use the scale the project already uses (story points, GitLab weight, Linear estimate); the project's reference file has it. Default Fibonacci scale when there's no history:
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
  - `Desired state / proposed outcome` (what will be true when complete, plus high-level approach and subtask breakdown if needed)
  - `Dependencies` (upstream/downstream tickets, external teams, approvals, access, vendor actions, or `N/A — <reason>`)
  - `Risks / security / change` (IAM, data sensitivity, network exposure, compliance, outage, rollback, or `N/A — <reason>`)
  - `References / evidence` (links to design docs, ADRs, diagrams, runbooks, logs, MRs, related tickets, or `N/A — <reason>`)
  - `Acceptance criteria (numbered, testable)` (`1. ... 2. ... 3. ...` — specific, observable conditions that define completion)

## Output

Give each draft as plain blocks ready to review or paste:
1. **Title** (`Verb + deliverable + scope`)
2. **Description** (compact SOP format by default, or the 2-table intake form if requested)
3. **Planned metadata**: `Type`, `Parent / Initiative`, `Primary POC (Assignee)`, `Reporter (Alternate POC)`, `Weight (SP)`, `Labels`, `Sprint`, `Target date` (if any), `Subtasks` (if any), and `Links` (blocking dependencies only, with direction, e.g. `Blocked by KEY-123`; omit when none). Every ticket gets a Reporter: the Alternate POC, or the user when none is known and the user is not the Assignee. The Reporter is never the Assignee. Only when the tracker has no settable reporter, append an "Alternate POC: <name>" line above the Acceptance criteria heading.

Then offer to post. If the user agrees, post one ticket at a time:
1. Re-check the tracker for tickets created since drafting; if one now covers a draft, merge into it or skip the draft.
2. Show the draft with its metadata and ask Post / Skip / Post without links.
3. On Post, create it with every field the CLI can set (including weight, parent, assignee when known, and labels); create any confirmed subtasks; create the blocking links; add it to the sprint; and report the key.

Merges follow the same confirm-first flow: comment on the target, move any blocking links that still apply to the target, then delete the merged-away ticket only if the user agrees. Never create, edit, or delete tickets without that per-ticket confirmation.
