---
name: ticket-draft
description: Draft a ticket title, description, and suggested weight from a bug, investigation, or feature idea, then offer to post it, for any tracker (Jira, GitLab issues, GitHub issues, Linear). Use when asked to "write a ticket", "file an issue", or for ticket wording; not for status updates or work summaries.
---

# Ticket drafting

Tickets are short planning records. Write like Maxwell writes them: terse, casual, consumer-facing.

## Calibrate first

Find out which tracker and project the ticket goes to. If it's unclear, ask. Then pull 10–20 recent tickets the user wrote there, so the voice and weights match. Tracker commands, known scales, title examples, and repo path conventions live in `references/<tracker>-<project>.md`. Those files are local to this machine and never synced; read the matching one.

No reference for the tracker yet? Use its CLI (`glab issue list`, `gh issue list`, etc.) to read recent tickets, then add a `references/<tracker>-<project>.md` with what you learned.

## Merge first

Always err on the side of merging. Before drafting a new ticket, list the project's open tickets and look for one this scope fits, even if it's assigned to someone else. Merge drafts into each other too, when they share a symptom, a screen, or an owner's in-flight work. Don't merge into tickets that are Blocked (the new work would inherit the block), or into tickets that are In Review or Done. When merging, the output is a comment for the target ticket and a revised weight for it, not a new ticket. Remind the user to give the owner a heads-up.

## Title

- As short as possible. Say what the consumer wants or sees, not the mechanism.
- Leaving room for interpretation is fine, and often better.
- Prefix the app name when it's app-specific (`<App> ...`). Sentence fragments, no trailing period.
- Good: `Ability to delete saved filters`, `Auto-generated upload names`, `In-tab notifications in the uploader`.
- Bad: root-cause statements, file names, config keys, or "X instead of Y because Z".

## Description

Two to five plain sentences. No headings, no Expected/Actual sections, no acceptance criteria unless asked.

Include:
1. What the user hit or wants, in one line. Credit the reporter by first name (e.g. "Sam asked…", "From Sam:"). Never write "a user" if the name is known; ask if unknown.
2. Which repos will need changes, as paths from the monorepo root (the project's reference file lists the layout).
3. A rough summary of what was explored. Name the area, not the line numbers.

Do NOT include:
- How to fix it, proposed changes, or option lists.
- Code paths, config values, line numbers, or log event names.
- Hedging boilerplate. One "unconfirmed" word is enough when it applies.

## Weight

Use the scale the project already uses (story points, GitLab weight, Linear estimate); the project's reference file has it. Default when there's no history, Fibonacci:
- **1**: one small change in one place (a config value, a button, an env var).
- **2**: a small, well-scoped build or a testing pass.
- **3**: a known problem that needs some investigation or touches 2+ repos/layers.
- **5**: a cross-cutting or murky bug, LLM/agent behavior debugging, or a cleanup/migration.
- **8**: large or vague, needs design or stakeholder input.

Never go above 8. If merged scope would push a ticket past 8, use 8.

Suggest one number and cite one or two comparable tickets in a short line. Agent/prompt behavior bugs skew higher, because they need prod iteration to verify.

## Output

Give the title, description, and suggested weight as plain blocks, ready to paste. Also include the planned metadata for each ticket: type, parent, labels, sprint, and links to related existing tickets.

Then offer to post. If the user agrees, post one ticket at a time:
1. Re-check the tracker for tickets created since drafting; if one now covers a draft, merge into it or skip the draft.
2. Show the draft with its metadata and ask Post / Skip / Post without links.
3. On Post, create it with every field the CLI can set, including the weight; link it; add it to the sprint; and report the key.

Merges follow the same confirm-first flow: comment on the target, re-create the links, then delete the merged-away ticket only if the user agrees. Never create, edit, or delete tickets without that per-ticket confirmation.
