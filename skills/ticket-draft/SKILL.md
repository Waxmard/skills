---
name: ticket-draft
description: Draft a ticket title, description, and suggested weight from a bug, investigation, or feature idea, then offer to post it, for any tracker (Jira, GitLab issues, GitHub issues, Linear). Use when asked to "write a ticket", "file an issue", or for ticket wording; not for status updates or work summaries.
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
- **One independently trackable outcome per ticket**: Split unrelated deliverables into separate linked tickets. Keep single deliverables together — do not split one feature's schema, UI, and migration into separate top-level tickets; use subtasks when step-level tracking is needed.
- **No secrets**: Never include credentials, tokens, keys, or sensitive data in ticket text.
- **No Priority field**: Never propose or set a `Priority` field unless the user explicitly asks for one.

## Title

- Use **Verb + deliverable + scope** so a reader understands the intended outcome without opening the description.
- Prefix the app or service name when project conventions call for it (`<App> ...`), or include it in the scope clause. Use concise fragments with no trailing period.
- Good: `Delete saved filters in Uploader`, `Generate default upload names automatically`, `Add entity type config in catalog service`, `Create and sync CloudSQL databases in us-east4`.
- Bad: vague placeholders (`Fix issue`, `Work on cloud`, `As discussed`), noun-only labels with unclear action, root-cause essays, or raw line numbers/config keys.

## Description (compact SOP default)

Write in specific, plain language so an unfamiliar teammate knows what to do and why. Credit the reporter or requester by first name when known (e.g. "Sam asked…", "From Sam:"); never write `"a user"` if the name is known, and ask if unknown.

Use this compact section layout inside the ticket description body:

```markdown
**Background / current state:**
<1–3 sentences: what the user hit or what exists today, why it matters (business/delivery outcome), and the environment/scope (repo paths from monorepo root, GCP project/region/service/dataset as applicable).>

**Desired state / proposed outcome:**
<1–3 sentences: target end state and high-level approach/notes at the service or component level.>

**Dependencies:**
<Include only when dependencies/blockers exist: prerequisite tickets, external teams, approvals, access, or vendor actions.>

**Risks / security / change:**
<Include only when material: IAM, data sensitivity, network exposure, compliance, outage, rollback, or change-window concerns.>

**References:**
<Include only when applicable: links to design docs, ADRs, diagrams, runbooks, logs, MRs, or related tickets.>

**Acceptance criteria:**
1. <Observable, testable condition that defines completion>
2. <Observable, testable condition — two engineers can independently agree it is done>
```

Omit `Dependencies`, `Risks / security / change`, and `References` in the compact CLI description when none apply. Do not include raw line numbers or speculative option essays.

## Sizing, ownership & breakdown

- **Weight (Story Points)**: Use the scale the project already uses (story points, GitLab weight, Linear estimate); the project's reference file has it. Default Fibonacci scale when there's no history:
  - **0**: overtaken by events (OBE), closed with no work.
  - **1**: one small change in one place (a config value, a button, an env var).
  - **2**: a small, well-scoped build or a testing pass.
  - **3**: a known problem that needs some investigation or touches 2+ repos/layers.
  - **5**: a cross-cutting or murky bug, LLM/agent behavior debugging, or a cleanup/migration.
  - **8**: large or vague, needs design or stakeholder input.
  Never go above 8. If merged scope would push a ticket past 8, use 8. Suggest one number and cite one or two comparable tickets in a short line. Agent/prompt behavior bugs skew higher because they need prod iteration to verify.
- **Expected duration**: State effort estimate and expected elapsed duration separately where possible (e.g., `~1d effort / 2d elapsed`), noting key assumptions or confidence when uncertain.
- **Primary POC / Alternate POC**: Identify one accountable primary owner (Assignee) and one backup owner (`Alternate POC`), plus specialist contributors if needed. If the alternate POC is unknown, ask or mark `TBD` in the draft metadata for confirmation.
- **Target date / milestone** (when applicable): State the date and whether it is fixed (external commitment/event) or preferred.
- **Subtasks / work breakdown** (when applicable): If a ticket is large (`5`–`8` SP or spans multiple independently verifiable phases), list concrete subtasks with owners/estimates so progress is trackable without an opaque monolith.

## Full intake form (on request)

When the user asks for an intake form, intake doc, or TPM review document, output the SOP two-table form instead of the compact description:
- **Rule**: Use `N/A — <reason>` for any field that does not apply; never leave a field blank. Omit `Requested priority` unless explicitly requested.
- **1. Request basics** (markdown table):
  - `Proposed title / summary` (`Verb + deliverable + scope`)
  - `Primary POC / Alternate POC` (primary owner + backup owner + specialist contributors if needed)
  - `Initiative (Aligned with priorities of Sprint)` (parent Initiative / Epic or strategic workstream)
  - `Business / delivery outcome (why is this needed?)` (1–2 sentences on operational, security, reliability, compliance, or user outcome)
  - `Expected duration` (effort estimate, expected elapsed duration, story points, and key assumptions/confidence)
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
3. **Planned metadata**: `Type`, `Parent / Initiative`, `Primary POC (Assignee)`, `Alternate POC`, `Weight (SP)`, `Expected duration`, `Labels`, `Sprint`, `Target date` (if any), `Subtasks` (if any), and `Links` (dependencies/related existing tickets). When posting to a tracker CLI that lacks dedicated fields for `Alternate POC` or `Expected duration`, append `**Alternate POC:** <name> · **Expected duration:** <effort / elapsed>` as a trailing metadata line in the posted description before `**Acceptance criteria:**`.

Then offer to post. If the user agrees, post one ticket at a time:
1. Re-check the tracker for tickets created since drafting; if one now covers a draft, merge into it or skip the draft.
2. Show the draft with its metadata and ask Post / Skip / Post without links.
3. On Post, create it with every field the CLI can set (including weight, parent, assignee when known, and labels); create any confirmed subtasks; link related/dependency tickets; add it to the sprint; and report the key.

Merges follow the same confirm-first flow: comment on the target, re-create the links, then delete the merged-away ticket only if the user agrees. Never create, edit, or delete tickets without that per-ticket confirmation.
