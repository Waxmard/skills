---
name: plain-writing
description: >-
  Use when drafting, rewriting, or simplifying prose a person will read:
  Slack/Jira/email messages, status/sprint updates, customer notes, slides,
  wiki pages, PR/MR comments, and review write-ups. Keeps text plain, short,
  sourced, and ready to send; for repo docs (READMEs, CHANGELOGs, API docs),
  load docs-style. Trigger: "write this up", "draft a message", "for Slack",
  "for the slide", "make this simpler", "too wordy", "reword", or
  /plain-writing.
---

# Plain writing

The goal is text the user can send on the first try. Every rule here comes from a correction the user made more than once.

## Before writing

1. **Know the reader.** Who reads it (customer, lead, teammate, the user in chat), and what they do with it (decide, approve, learn, present). Write for that reader, not for the engineer who did the work.
2. **Know the channel.** Pick the preset below. If the text will be pasted somewhere, ask where unless it's obvious.
3. **Check every fact.** Correctness beats everything else. Verify each claim (counts, dates, names, who did what, what shipped where) against the source: code, tickets, PRs/MRs, logs, or the user's own notes. If you can't verify a claim, cut it or mark it as unverified. Never round up a claim to sound better.

## Rules

**Lead with the point**
1. Put the answer, decision, or outcome in the first sentence. Background comes after, if at all.
2. If something is longer than a screen, open with a 2 to 4 line summary the reader could stop after.

**Plain words**
3. Write for someone outside the project. Swap jargon, internal codenames, and config keys for what they mean ("expired sessions sign out after 30 minutes", not "`idle_ttl_ms=1800000` in the Bifrost middleware"). Keep a technical term only when the reader needs it to act or to check you, and explain it the first time.
4. Zoom out. Say what changed for the reader and why it matters. Leave out mechanisms, evidence trails, and side findings unless asked; they belong in a linked internal doc.
5. Spell out an acronym the first time on each page, unless every reader knows it (API, URL).
6. Use one term per concept. Alternating synonyms reads as a new thing.
7. Don't use `simply`, `just`, `easy`, `obviously`, `of course`, `please`, `e.g.`, `i.e.`, or `etc.` (finish the list, or write "and so on").

**Short**
8. One idea per sentence, about 20 words or fewer. One topic per paragraph or bullet.
9. State each fact once. Don't restate the summary in the body or the body in a closing section.
10. Leave out filler: "This document describes", "It is worth noting", "In summary", welcome lines, and sign-offs.
11. Leave out personality and hype. No exclamation marks, no "exciting", "powerful", "seamless", no emoji.

**Voice**
12. Use active voice and name the actor. "Stripe retries failed charges three times", not "failed charges are retried".
13. Use "we" when speaking for the team or company to an outside reader. Use "I" only in the user's own first-person writing (self-reviews, personal messages).
14. Use people's names, never "a user" or "the team" when you know who. Credit people by name for what they did ("Maya built the CSV importer; Jordan added row-level error reports").
15. When suggesting changes to someone else's work, suggest; don't order. Use "We suggest", "It may help to", "This would make X accurate". Say what is true today, then what would close the gap.
16. Use the present tense for current facts. For anything that can go stale, give the date ("as of April 2026"), not "currently" or "still".

**Formatting**
17. Use bullets for sets of facts and numbered lists for steps or ranked items. Start each bullet with a 1 to 3 word **bold label** followed by a colon when the list has more than three items or will be scanned.
18. Use bold only for labels and for the few numbers or phrases that carry the message. Bold scattered through sentences reads as noise.
19. Use inline code only for literal identifiers someone will copy (paths, commands, config values). Write product names as plain text.
20. Write links as descriptive text, never "here" or "this link". Link every ticket, PR/MR, and file reference when the channel renders links.
21. Use a table only when the reader compares the same fields across rows and the channel renders tables. Otherwise use bullets.

## Channel presets

| Channel | Shape |
|---|---|
| Chat reply to the user | The answer first, in one or two sentences, then only the detail they need to act. No headers for short answers. End with the one decision or next step if there is one. |
| Slack, Teams, Jira or PR/MR comment, email | Paste-ready plain text: short paragraphs or `-` bullets, no headers, no tables, no nested lists, no HTML. Under about 150 words unless asked for more. |
| Slide | One line per bullet (about 110 characters including the label), labels in bold, no full sentences of explanation, no personality, no thanks lines. The speaker elaborates. Put notes that must not appear on the slide on separate `>` lines. |
| Status or sprint update | A TL;DR block first: one bold-labeled bullet per workstream, with the owner's name in parentheses and what shipped or what is next. Detail sections after, if any. Status words from a fixed set (Shipped, In review, In progress, Blocked). |
| Feedback or review doc for an outside reader | A header block (Status, Source, Scope, Last updated), then numbered sections. Each section is a short plain heading, a paragraph of what is true today and what would fix it, and an **Affects:** line. Internal notes go in a clearly marked section or a separate file that is not sent. |
| Technical review or proposal (wiki) | A bold **Bottom line** callout first (2 to 3 sentences: verdict, biggest number, where the fixes are). Each section gets a one-line **Impact:** summary under its heading, then bold-labeled bullets with a link for every file reference, then a **Recommendation:** line. Put long evidence tables in a collapsed appendix. |
| Self-review or accomplishments | Group by project, impact first, with real numbers and dates. Name collaborators and what they built. Never claim sole credit for shared work. |

## Final pass

Before showing the draft:
1. Re-check every number, date, name, and claim of credit against its source.
2. Cut every sentence the reader would not miss. Then cut again; the user usually wants it shorter than the first draft.
3. Read it as the target reader. Rewrite any term they would have to look up.
4. Check that the channel preset holds (no tables in a paste, one line per slide bullet).

Show the result once, without a preamble about what you changed unless the user asked.

## Examples

Too technical: "PgBouncer has `max_client_conn=100` without `statement_timeout`, so unindexed exports exhaust the pool."
Plain: "A slow CSV export can hold every database connection and block new sign-ins."

Too wordy: "Throughout the past two weeks, the team made a number of meaningful improvements to the billing portal to make invoices easier for customers to manage."
Plain: "**Billing portal (Maya):** shipped PDF invoice downloads, tax-ID edits, and failed-payment alerts."

Order, not suggestion: "Set the webhook timeout to 5 seconds in the partner guide."
Suggestion: "We suggest listing the 5-second webhook timeout in the partner guide. Right now the guide says 30 seconds, which no longer matches the gateway."

Generic credit: "Someone on the backend team fixed the search indexing lag."
Named: "Jordan Kim and Elena Rostova cut search indexing lag from 12 minutes to 8 seconds."
