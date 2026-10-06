---
name: post-mr-review
description: >
  Turn code-review findings already in the conversation into GitLab MR comments
  (inline where possible), iterate with the user on what to post, and post ONLY
  after the user confirms each comment. Reuses existing threads, dedupes against
  comments already on the MR, consolidates, pins file links to the MR head SHA,
  and adds suggestion blocks for mechanical fixes. Use after a review has run.
  Trigger: "post these on the mr", "put the findings as comments", "post the
  review", "/post-mr-review". Not for judging existing comments (use
  review-pr-comments).
---

Turn review findings that are already in the conversation (from reviewer subagents or the user's own review) into posted GitLab MR discussions. The user and you iterate on what to post: trim, reword, consolidate, drop. **Nothing is posted, edited, or reopened without an explicit per-post confirmation from `ask` in the current turn.** Never approve, merge, resolve, assign, commit, or push.

GitLab only (`glab`); the user's repos live on self-hosted GitLab.

## Pre-flight

1. If the conversation has no review findings, stop and tell the user to run a review first. Do not run one yourself.
2. Detect the MR. Use `--mr <iid>` if given. Otherwise run `glab mr list --source-branch <branch> -F json` for the branch that was reviewed (not necessarily HEAD) and take `.iid`. If there's no MR, stop.
3. Fetch the MR with `glab api projects/:id/merge_requests/<iid>` and read `.sha`, `.diff_refs.base_sha`, `.diff_refs.start_sha`, `.diff_refs.head_sha`, `.source_branch`, `.web_url`. Run the fetch from Python/eval (`subprocess` + `json`), not piped to `jq` in bash (see pitfalls).
4. Run `git fetch origin <source_branch>` and compare the reviewed commit with the MR `head_sha`. If they differ, tell the user the MR moved since the review and offer to re-check the findings against the new head before drafting. Line anchors and "still present" claims must be true at `head_sha`.

## Fetch existing discussions

Page manually from Python/eval until an empty page comes back. Do not use `glab api --paginate | jq`; it emits concatenated arrays that break `jq`.

```python
import json, subprocess

def gl(path):
    return json.loads(subprocess.run(["glab", "api", path], check=True, capture_output=True, text=True).stdout)

discussions, page = [], 1
while batch := gl(f"projects/:id/merge_requests/{iid}/discussions?per_page=100&page={page}"):
    discussions += batch
    page += 1
assert all(d["notes"][0]["noteable_iid"] == iid for d in discussions), "stale/cross-MR data"
me = gl("user")["username"]
```

Normalize each discussion to:

| Field | Source |
|---|---|
| `id` | `id` |
| `author` | `notes[0].author.username` |
| `path` / `line` | `(notes[0].position or {}).get("new_path")` / `.get("new_line")` (null-safe, always) |
| `resolved` | `notes[0].resolved` (`true` / `false` / `None` = non-resolvable) |
| `body` | full `notes[0].body` |
| `after_me` | notes after the user's last note in the thread |

Tag each thread as the current user's (`me`), a reviewer bot's, or a human's.

## Build the posting plan

- **Dedupe.** For each finding, check whether an existing thread by anyone already raises the same issue. Same file or line is not enough; it must be the same problem. By default, drop already-raised findings and tell the user which thread covers each. If a thread raised it and the author "fixed" it wrongly, it is not a duplicate: reply in that thread.
- **Follow-up rounds.** When the user's own earlier threads have author replies ("Fixed", "Acknowledged", "By design"), verify each claim against the code at `head_sha` before drafting. Mark each VERIFIED, PARTIAL, NOT FIXED, or WRONG-CLAIM. Only NOT FIXED and PARTIAL become posts. A reply that restates an earlier round's fix without addressing the new point counts as NOT FIXED. A thread resolved with no change and no reply counts as NOT FIXED.
- **Human-resolved threads.** Before planning to reopen a thread that a human resolved (any author other than `me` or a reviewer bot), read the full thread: `resolved_by`, the resolving note, any "changed this line in version N" system note, and the code at `head_sha`. In the plan, under the table, give one line per such thread: who resolved it, why they most likely did (e.g. "applied the bot's suggestion verbatim", "replied By design", "resolved with no reply after a push"), and why that doesn't close our point (their fix answered a different question, it's incomplete, or the premise was wrong). If their resolution fully covers our point, drop the finding instead of reopening. Prefer replying in an unresolved thread on the same issue over reopening a resolved one.
- **Green pipeline.** If the MR pipeline passed, name for each finding the CI job that should catch it and why it didn't (e.g. the Docker build deletes the lockfile, `lint:typecheck` only runs pyright). If no job could catch it, say so in the Evidence block. Expect the user to ask "how is this a finding if CI passed?" and answer it before they do.
- **Targets, in order:** (a) reply in an existing thread about the same code or issue, ours or a bot's; (b) a new inline diff comment; (c) the general MR comment. Fold related items into one post per thread or file to keep new MR interactions low. Items that can't anchor to the diff (unchanged files, docs outside the MR) go into a single general comment.
- **Present the plan as one table:**

  | # | Target | Labels | Effect line(s) |
  |---|---|---|---|
  | 1 | thread `a1b2c3` `path:line` / new inline `path:line` / general | must-fix, nit | what the post leads with |

  Below it, list what was dropped and why: already raised (name the thread) or verified fixed.

## Iterate with the user

- Loop: apply the user's edits (drop, merge, relabel, reword, trim to what "truly matters") and re-show the updated table. Continue until the user says to post or to show the drafts.
- When asked to trim to essentials, keep only defects that would ship broken behavior or security holes. Drop test quality, docs, style, and architecture preferences, one line each saying so. Hold unverified or low-confidence findings rather than posting them, and offer to verify.
- If the user offers to reproduce findings in a running environment, give exact repro steps per finding (URL, nav path, prompt, what proves it). Put the observed results in each Evidence block, and reframe or drop claims that didn't reproduce, keeping only the part verified in code.
- Draft full bodies only once the plan table is agreed.

## Comment format

- Labels are exactly `blocker`, `must-fix`, `should-fix`, `nit`. Never `P0`/`P1`. They live only in the plan table for triage and ordering; never write them into posted bodies.
- **Per-finding template** (exact shape; one blank line between every block):

  ````
  **OKF discovery always returns an empty catalog.**

  `_build_okf_handlers` passes `okf_provider.list_sources` ([`main.py:468`](…)), which is hard-coded to `return []` ([`catalog_provider.py:46-47`](…)).

  **Fix:** pass `catalog_registry.list_all_sources`.

  <details><summary>Evidence</summary>

  …repro table, command output, long detail…

  </details>
  ````

- **Effect line (line 1):** bold, one sentence of at most ~15 words stating the **practical consequence**, not the code mechanism: what breaks, for whom, or what an attacker or user can now do ("Any private-network caller can list and call MCP tools without auth." not "The `/mcp/admin/` prefix check is too broad."). If the effect is conditional, append the condition in the same sentence ("…when `auth.mode` is on.").
- **Cause block:** at most 2 sentences, with linked `file:line` references. Don't restate the effect.
- **Fix line:** `**Fix:**` plus one line of prose or inline code, or a suggestion block in its place when one applies. Omit only when the fix is genuinely "decide X", and then state the decision needed.
- **Evidence block:** only for a repro table, test output, or detail longer than 2 sentences. Always collapsed in `<details><summary>Evidence</summary>` with blank lines inside the tags so GitLab renders the markdown. Never put long evidence in the visible body.
- **Budget:** the visible body of each finding (excluding `<details>` and suggestion blocks) stays at or under ~60 words. Over budget → cut the cause block first.
- **Several findings in one post:** separate with a line containing only `---`, blank lines around it, ordered by label severity.
- **Several nits in one post:** one bold effect line `**<n> small cleanups.**`, then one bullet per nit: `<what> ([`file:line`](…)): <fix>`. No cause blocks for nits.
- **Follow-up replies** in an existing thread start with a one-line status before the template: `Still present at `<short_sha>`.`, `Half fixed: <done part> is in; <open part> is not.`, or `Resolved without a change.` The template for the remaining finding follows. Never re-explain what the thread already says; "see above" at most.
- **File links** pin to `head_sha`: `[`<file>:<a>-<b>`](https://<host>/<project_path>/-/blob/<head_sha>/<path>#L<a>-<b>)`. Deleted files or removed code pin to `base_sha`. Link every `file:line` reference and every referenced symbol definition you can locate. Before posting, verify each linked line with `git show <sha>:<path>` and check the content matches the claim.
- **Suggestion blocks** (```` ```suggestion:-0+N ````) only for mechanical replacements on new inline comments anchored at `head_sha`: delete a line, swap an import, change a literal. Match source indentation exactly and stay within the repo line length (`line-length` in `pyproject.toml`). When one suggestion depends on another (e.g. an import), say so in both comments. Never put suggestions in replies to existing threads; they apply to the thread's original, possibly shifted, line.
- **Tone:** concrete, practical effect first. No hedging filler, no praise, no "as discussed", no restating the reviewer's or author's words back to them.

## Confirm

- Make one `ask` call with one question per post, using the top-level `ask` tool directly, never `tool.ask` inside `eval` (the eval cell timeout kills the prompt and the kernel state holding the drafts). The question text names the target thread or line and repeats the effect line. Options: `Post` (with `preview` set to the full body, markdown links collapsed to plain `` `file:line` ``, `<details>` shown expanded) and `Skip`.
- If any target thread is resolved, add one question "Reopen threads I reply in?" with options `Reopen` and `Leave resolved`. For threads a human resolved, repeat in the question text who resolved it and why (from the plan line), so the reopen decision is made with that context.
- Post only items answered `Post`. If the user answers with edits ("Other"), revise and re-ask for just that item.

## Post

Run from Python/eval. Write each JSON payload to a temp file and pass `glab api -X <METHOD> <path> --input <file> -H 'Content-Type: application/json'`.

- **New inline comment:** `POST projects/:id/merge_requests/<iid>/discussions`

  ```json
  {"body": "...", "position": {"position_type": "text", "base_sha": "...", "start_sha": "...", "head_sha": "...",
   "old_path": "...", "new_path": "...", "new_line": 42, "old_line": 40}}
  ```

  Build a line map from `git diff --unified=3 <start_sha> <head_sha>`. Added lines need only `new_line`. Unchanged context lines need both `old_line` and `new_line`. A line not in any hunk cannot be inline: move it to the general comment or a nearby changed line.
- **Reply:** `POST .../discussions/<discussion_id>/notes` with `{"body"}`.
- **General comment:** `POST .../discussions` with `{"body"}` only.
- **Reopen** (only if confirmed): `PUT .../discussions/<discussion_id>?resolved=false`.
- **Edit an already-posted note** (only when the user asks): `PUT .../discussions/<discussion_id>/notes/<note_id>` with `{"body"}`. Find the note by matching its current body text.
- After posting, re-fetch discussions and verify: the count of new notes by `me` matches, and every intended inline note has a non-null `position`. Report any failure verbatim.

## Report

A table of what was posted (# / target / labels / gist), the threads reopened, and one line noting anything skipped. No other prose.

## Hard rules

- **Never post, edit, reopen, or delete** without a same-turn `ask` confirmation for that specific post.
- **Never resolve threads, approve, merge, set auto-merge, or assign** reviewers or assignees.
- **Never commit or push. Never edit repo files.**
- **Never post a claim you have not verified at `head_sha`.** Flag lower-confidence items to the user before drafting.
- **Never re-post an issue someone already raised;** reply in their thread instead.

## Common pitfalls

- **Null `position`**: general notes and bot Questions have `position: null`; read it null-safely.
- **`glab api --paginate`** output doesn't parse as one JSON document; page manually.
- **Harness block**: bash commands matching `*merge_requests/*/merge*` are blocked, so a `jq` filter such as `.detailed_merge_status` after `merge_requests/<iid>` fails. Run MR API reads from Python/eval.
- **Silent downgrade**: inline positions silently become general notes if the line isn't in the diff. Check the line map first, then verify `position` after posting.
- **Stale author replies**: replies often answer the previous round ("handlers now called at 3 sites") instead of the new point. Verify against code, not the reply.
- **Remote CI components** (`component: $CI_SERVER_FQDN/<group>/<project>/<name>@<ref>`) can be read without cloning: `glab api "projects/<url-encoded group/project>/repository/files/templates%2F<name>.yml/raw?ref=<ref>"` (list with `repository/tree?ref=<ref>&recursive=true`). Read the component's rules before calling a `needs:` or job-presence risk unverified.
- **Bot "looks good"** summaries are not verification.
- **Throwaway repros** go in a `git worktree add /tmp/<name> <sha>` checkout with `uv sync`. Remove it afterwards with `git worktree remove --force`.

## Retro — improve this skill

This skill is **two-way**: after the run, spend one beat on whether the run exposed something the
skill itself should encode. Most clean runs need no change — don't force it.

Propose an edit only on real signal:

- A case these instructions didn't cover and you had to improvise (a thread type, bot format, or
  GitLab position/API quirk the pitfalls miss).
- The user rewrote drafts in a consistent direction, overrode the dedupe/target rules, or repeated
  an instruction.
- A step here was wrong or stale (a `glab` field or endpoint changed, a position rule misfired).
- You repeated a manual workaround that belongs in the fetch/plan/post flow.

When a signal fires, **propose** the concrete edit: name the section, show before/after lines,
one sentence of why. Apply only after the user says yes — this file is global and durable, never
edit it silently. If nothing fired, say nothing — no "run went well" noise.
