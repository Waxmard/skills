---
name: docs-style
description: >
  Apply Google developer documentation style to prose written into files —
  READMEs, CHANGELOGs, docs/ pages, API references, migration guides, ADRs,
  release notes, tutorials, and doc comments that ship as public API surface.
  Governs file content only, never chat responses. Use whenever writing or
  substantially editing user-facing prose in a repo. Trigger: "write a
  README", "update the docs", "write the changelog", "document this API",
  "write a migration guide", "draft release notes", "rewrite these docs",
  "docs style", "/docs-style".
---

# docs-style

Google developer documentation style guide, distilled to the rules that
change output. Full guide: https://developers.google.com/style

## Scope boundary

Applies to **prose written into files**. Does not apply to chat responses,
which keep any session style. Same carve-out as code and commit messages.

Does not apply to: code, code comments (the repo's comment policy wins),
commit subjects, PR descriptions.

## Rules

**Voice and person**

1. Second person. "You configure the client", not "the user configures" or
   "we configure". Imperative for instructions: "Run the migration."
2. Active voice. Name the actor. "The parser rejects malformed input", not
   "malformed input is rejected".
3. Present tense. "The request returns 404", not "the request will return
   404". No future tense for current behavior.

**Word choice**

4. Ban the belittling set: `simply`, `just`, `easy`, `easily`, `obviously`,
   `of course`, `merely`, `trivial`. They only tell readers they should have
   already understood.
5. Ban `please` in instructions. "Run `npm ci`", not "please run `npm ci`".
6. One term per concept, every time. Pick `directory` or `folder`, `argument`
   or `parameter` — then never alternate. Synonym variety reads as a new
   concept.
7. No latin abbreviations in prose: `e.g.` → "for example", `i.e.` → "that
   is", `etc.` → finish the list or write "and so on". Fine inside
   parentheses if space is tight.
8. Spell out an acronym on first use per page, then use the acronym. Skip for
   universally known ones (API, HTTP, JSON, CLI, URL).

**Structure**

9. Sentence case for all headings and titles. "Configure the build cache",
   not "Configure The Build Cache".
10. Headings are descriptive, not clever. Task headings start with a gerund
    or imperative: "Installing dependencies" / "Install dependencies" — pick
    one form and hold it across the document.
11. Front-load. Most important information in the first sentence of a section
    and the first clause of a sentence. Readers scan; they do not read.
12. One idea per sentence, one topic per paragraph. Split any sentence
    carrying two independent clauses joined by "and".
13. Numbered lists for sequences, bullets for unordered sets. Every list item
    in a list uses parallel grammatical structure.
14. Introduce every code block with a sentence saying what it does and what
    the reader should get back.

**Links and references**

15. Descriptive link text that reads standalone. "See the
    [authentication guide]", never "[click here]" or "[this link]".
16. Refer to UI elements by their visible label in bold: click **Save**. Do
    not describe the widget type unless it disambiguates.

**Precision**

17. State prerequisites and platform constraints before steps, not inside
    them.
18. Warn before the destructive step, not after. Lead with the consequence:
    "This deletes all local state."
19. Give real values in examples. `us-east-1`, not `<YOUR_REGION_HERE>`,
    unless the placeholder genuinely varies per reader — then use a
    consistent placeholder format throughout.
20. Never document intent as behavior. If it is not implemented, it does not
    belong in the docs.
21. No present-tense status that goes stale ("still backfilling", "not
    decided yet", "the feed stopped"). Write dated history ("No records
    since 2026-07-30") or the command that checks the current state.

## README shape

For a project README, in this order:

1. One or two sentences: what it is, what it's built with, and what it
   deliberately leaves out. No "Welcome", no badges beyond one CI badge,
   no emoji in headings.
2. A small text diagram of the data or control flow
   (`input ──▶ this repo ──▶ output`). Skip it for a single-file tool.
3. The commands that run it, each with a trailing `# what you get back`
   comment. The comments stand in for rule 14's introducing sentence.
4. A `| Path | What |` table or an indented layout block, once the repo has
   more than about five top-level paths.
5. Pending work as a numbered **Open items** list: a bold one-line
   constraint, then why it's open and what decides it.
6. Past about 400 lines, or once a second audience appears (operators, data
   consumers), split into `docs/` files and link them from a two-column
   table.

## Anti-goals

Do not pad. Google style is terse — these rules cut words, they do not add
ceremony. A README that follows every rule and runs 300 lines when 80 would
do has failed.

Do not restructure documents that already follow a house convention. Match
the surrounding document first; these rules break ties, they do not override
an established pattern in the repo.
