---
name: docs-style
description: Use when writing or editing prose in repo files, such as READMEs, CHANGELOGs, docs/ pages, API references, migration guides, ADRs, release notes, tutorials, and public doc comments. Adds Google developer-docs rules on top of plain-writing. Trigger on "write a README", "update the docs", "write the changelog", "document this API", "write a migration guide", "draft release notes", "rewrite these docs", "docs style", or "/docs-style".
---

# docs-style

Load the `plain-writing` skill first; its rules apply to every doc. This skill adds the Google developer documentation rules that matter for repo docs. Full guide: https://developers.google.com/style

Doesn't apply to code, code comments (the repo's comment policy wins), commit subjects, or PR descriptions.

## Rules

1. Write instructions in the second person and the imperative. "Run the migration", not "the user runs the migration" or "we run the migration".
2. Use sentence case for headings and titles. "Configure the build cache", not "Configure The Build Cache".
3. Make headings descriptive, not clever. Start task headings with an imperative or a gerund, and use the same form throughout the document.
4. Make list items in the same list grammatically parallel.
5. Introduce every code block with a sentence that says what it does and what the reader gets back.
6. Refer to UI elements by their visible label in bold: click **Save**.
7. State prerequisites and platform constraints before the steps, not inside them.
8. Put the warning before the destructive step, consequence first: "This deletes all local state."
9. Use real values in examples (`us-east-1`). Use a placeholder only when the value differs for each reader, and use the same placeholder format throughout.
10. Document only what is implemented. Intent isn't behavior.

## README shape

For a project README, in this order:

1. One or two sentences: what it is, what it's built with, and what it deliberately leaves out. No welcome line, no badges beyond one CI badge, no emoji in headings.
2. A small text diagram of the data or control flow (`input ──▶ this repo ──▶ output`). Skip it for a single-file tool.
3. The commands that run it, each with a trailing `# what you get back` comment. The comments stand in for rule 5's introducing sentence.
4. A `| Path | What |` table or an indented layout block, once the repo has more than about five top-level paths.
5. Pending work as a numbered **Open items** list: a bold one-line constraint, then why it's open and what decides it.
6. Past about 400 lines, or once a second audience appears (operators, data consumers), split into `docs/` files and link them from a two-column table.

## Anti-goals

Don't pad. A README that follows every rule and runs 300 lines when 80 would do has failed.

Don't restructure documents that already follow a house convention. Match the surrounding document first; these rules break ties.

## Harness notes

| Step says | omp | Claude Code | Other agents |
|---|---|---|---|
| load skill `<name>` | `read skill://<name>` | Skill tool | read its `SKILL.md` |
