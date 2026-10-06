---
name: review-pr-comments
description: >
  Fetch all review comments on the current branch's PR/MR (GitHub or GitLab,
  human + AI reviewers alike) and produce a terse agree/disagree verdict for
  each by reading the referenced code. Read-only — never posts replies, never
  resolves threads, never edits files. Use when the user wants a second
  opinion on reviewer feedback before responding. Trigger: "review the pr
  comments", "agree or disagree with the comments", "go through the reviewer
  feedback", "/review-pr-comments".
---

Pull every review comment on the current branch's open PR/MR and judge each one by reading the actual code. Output is a terse per-comment verdict list, each verdict worded so the user can paste it straight back onto the thread as a reply. No replies posted, no threads resolved, no code edits.

Works with both **GitHub** (`gh`) and **GitLab** (`glab`). All comments are in scope — bot reviewers (claude, pupcoder, coderabbit, copilot, the company review bot, etc.) and humans both. No author filtering by default; user may pass an `--author <login>` filter to narrow.

## Pre-flight

1. Confirm CWD is in a git repo: `git rev-parse --git-dir`. If not, stop.
2. Read current branch: `git rev-parse --abbrev-ref HEAD`. Any branch is allowed regardless of its base/target — the gate is whether a PR/MR exists (step 5), not the branch name. A branch like `dev` may have an open `dev → main` PR; review it the same as any other.
3. Detect platform:
   - `git remote get-url origin` → if host is `github.com` → GitHub.
   - If host contains `gitlab` → GitLab.
   - Otherwise (self-hosted host with neither substring, e.g. a company GitLab) probe the CLIs before asking: run `glab auth status` and `gh auth status` and pick the one logged in to the remote's host. Only ask the user if both fail or both match.
4. Verify CLI is installed and authed:
   - GitHub: `gh auth status` (must succeed).
   - GitLab: `glab auth status` (must succeed).
5. Resolve PR/MR number for current branch:
   - GitHub: `gh pr view --json number,url,headRefName,state,headRefOid,baseRefOid` → fail if no PR. Record `head_sha` = `headRefOid`, `base_sha` = `baseRefOid`, and `blob_base` = `url` minus the trailing `/pull/<n>` (e.g. `https://github.com/o/r`).
   - GitLab: `glab mr view --output json` → fail if no MR. Record `head_sha` = `.diff_refs.head_sha` (`.sha` if `diff_refs` is null), `base_sha` = `.diff_refs.base_sha`, and `blob_base` = `.web_url` minus the trailing `/-/merge_requests/<iid>`.
   - If state is not `OPEN` / `opened`, warn but continue (user may still want feedback on a merged PR).
6. `git fetch origin <head branch>` so `git show <head_sha>:<path>` works locally. If the fetch fails, continue without links: replies use plain backticked `` `file:line` ``, and say once, before the verdicts, that links were skipped.

## Fetch comments

### GitHub

Three endpoints — all three needed for full coverage:

```bash
OWNER_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
PR=$(gh pr view --json number -q .number)

# Inline code-review comments (anchored to file + line)
gh api "repos/${OWNER_REPO}/pulls/${PR}/comments" --paginate

# Review-level summaries (top-level review body, no file anchor)
gh api "repos/${OWNER_REPO}/pulls/${PR}/reviews" --paginate

# PR-conversation comments (the "Conversation" tab, no file anchor)
gh api "repos/${OWNER_REPO}/issues/${PR}/comments" --paginate
```

Skip:
- Comments authored by the PR author themself (they're not reviewer feedback).
- Comments in `state: PENDING` reviews (drafts not yet submitted).
- Empty / whitespace-only bodies (some bots post empty review wrappers).
- Threads whose most recent comment (last in the `in_reply_to_id` chain) is by the PR author — the author already answered; the next move is the reviewer's.

If `--author <login>` is passed, post-filter to that login.

### GitLab

**Only fetch from `discussions`** — it's the only endpoint that exposes resolved state, and every note belongs to a discussion. Do NOT also hit `/notes` (it duplicates the same content without `resolved`, and you'll double-count).

```bash
PROJ=$(glab repo view --output json | jq -r .path_with_namespace)
PROJ_ID=$(glab repo view --output json | jq -r .id)
MR=$(glab mr view --output json | jq -r .iid)
ENCPROJ=$(printf %s "$PROJ" | jq -sRr @uri)
ME=$(glab mr view --output json | jq -r .author.username)  # MR author, not you

# Per-project+MR temp path — NEVER a shared /tmp/discussions.json. A hardcoded
# shared path lets a prior run's data (a different repo/MR) survive when the
# fetch below writes nothing on failure, so you silently review the wrong MR.
DISC=/tmp/glab-discussions-${PROJ_ID}-mr${MR}.json
rm -f "$DISC" "$DISC.tmp"

set -o pipefail
glab api "projects/${ENCPROJ}/merge_requests/${MR}/discussions" --paginate > "$DISC.tmp" || {
  echo "FETCH FAILED — aborting (do not filter stale data)"; rm -f "$DISC.tmp"; exit 1; }
mv "$DISC.tmp" "$DISC"

# Identity guard: every note must belong to THIS MR. If noteable_iid != $MR,
# the file is stale/cross-repo — abort rather than review someone else's MR.
WRONG=$(jq --argjson mr "$MR" '[.[] | .notes[0].noteable_iid | select(. != $mr)] | length' "$DISC")
[ "$WRONG" = "0" ] || { echo "STALE DATA: $WRONG notes not from MR $MR — aborting"; exit 1; }
```

**In scope (default) = everything nobody has resolved.** That's open resolvable threads (`notes[0].resolved == false`) *and* non-resolvable top-level MR notes (`null`) — the latter carry reviewer-bot Questions and every human "why did you do it this way?" comment, which are real feedback with no Resolve button to click. Out of scope: resolved threads (`true`), threads where the MR author wrote the last note (already answered, ball is in the reviewer's court), system events, the MR author's own notes, and the reviewer bot's own review surfaces (the looks-good summary, the suggested MR description, the incomplete-review banner) — those are status, not feedback.

The canonical filter (apply ALL of these unless `--include-resolved` is passed):

```bash
jq --arg me "$ME" '[.[]
  | select(.notes[0].system == false)              # drop "marked as draft", etc
  | select(.notes[0].author.username != $me)       # drop MR author's own notes
  | select(.notes[-1].author.username != $me)      # drop threads the MR author already answered last
  | select(.notes[0].resolved != true)             # drop resolved; keep open AND non-resolvable
  | select((.notes[0].body // "") | test("Suggested MR title and description|BOT_STATUS_MARKERS") | not)
]' "$DISC"
```

Replace `BOT_STATUS_MARKERS` with the reviewer bot's status-marker regex from `references/local.md` (machine-local); drop that alternative if the file is absent.

Note `resolved != true` (strict on `true` only): `true` = someone clicked Resolve (drop), `false` = open resolvable thread (keep), `null` = non-resolvable note, no thread state (keep).

If `--include-resolved` is passed: drop the `resolved` select and the `notes[-1]` author select. If `--author <login>` is passed: add `| select(.notes[0].author.username == "<login>")`.

## Normalize

For each comment build a record:

| Field | Source |
|---|---|
| `id` | `id` (GH) / `id` (GL) |
| `author` | `user.login` (GH) / `author.username` (GL) |
| `file` | `path` (GH inline) / `(.position // {}).new_path` (GL inline) — empty if not anchored |
| `line` | `line` or `original_line` (GH) / `(.position // {}).new_line` (GL) — empty if not anchored |
| `body` | `body` |
| `url` | `html_url` (GH) / `position` + MR URL (GL) |

Number them 1..N in the order returned. Output the list to the user before judging, so they see the scope.

**Silent drop.** Only in-scope (post-filter) discussions exist for the rest of this run. Do NOT mention, count, or acknowledge anything the filter removed — no "skipping N resolved threads," no "ignoring the author's own notes," no tally of what was dropped. The user considers that noise. If the filter leaves zero discussions, say only that there are none to review.

## Per-comment verdict loop

Each comment is judged independently by reading the live code — there is no shared reasoning between comments, so this stage **fans out**.

**Dispatch rule:**
- **< 4 in-scope comments** → judge them inline yourself, in order. Spawn overhead beats the parallelism win below this count.
- **≥ 4** → fan out one **Sonnet** subagent per comment (Agent tool, `model: sonnet`), launched in parallel (all tool calls in a single message). Each subagent runs steps 1–3 and returns **only** its one verdict line as its final message. Collect the lines, sort back into comment order, then do the tally (step 4) yourself.
- **Exception:** if every in-scope comment references the same file and you've already read it, judge inline regardless of count — subagents would just re-read the same diff.

Split a bot summary comment into its sub-bullets (`5a`, `5b`, …) **before** dispatch — each sub-bullet is its own unit of work and its own subagent.

Each subagent's prompt must include: the comment record (author, file, line, body, url), the platform, the repo root, `head_sha`, `base_sha`, `blob_base`, the platform's link format, the verdict criteria + output format below (including the reply-voice rule — a subagent writing in verdict voice costs a rewrite of every line), the Reply style block verbatim, and the read-only rule verbatim (no writes, no edits, no thread/approve ops — it only reads code and returns a line). Subagents inherit `Read`; that's all they need.

For each comment (inline or in a subagent), in order:

### 1. Read the referenced code

- If the comment is anchored (`file` + `line`): use `Read` on that file around the line (±30 lines context). Don't trust the diff snippet in the comment body — it may be stale if newer commits were pushed.
- If the comment cites a different file/symbol in the body but isn't anchored there: use `Read` on the cited target.
- If the comment is purely conceptual (no code reference): no read needed.

### 2. Assess

Pick one verdict per comment:

| Verdict | When |
|---|---|
| **agree** | Comment correctly identifies a real bug, smell, or improvement, and the suggested fix (if any) is sound. |
| **disagree** | Comment is wrong (misreads code, asserts false bug) OR requested fix is already implemented in current HEAD. |
| **partial** | Comment identifies a real issue but the suggested fix is wrong / over-scoped / under-scoped. Or: half the points land, half don't. |
| **stale** | Comment refers to code that no longer exists at the cited location (newer commits removed/changed it). |
| **defer** | Comment is a stylistic / preference call with no objective right answer — flag for the user to decide. |
| **needs-info** | Can't judge without info outside the diff (runtime behavior, external system state, user intent). Say what's missing. |
| **answer** | Comment is a question, not a finding (reviewer-bot `Question,` notes, human "why did you…?"). Answer it from the code; no agree/disagree applies. If it asks whether something was *verified* against live state you can't reach, say plainly that it wasn't and give the risk — don't downgrade to **needs-info**, the reviewer is asking the author, not you. |

Be willing to push back on bots and humans equally. Past reviewers being usually-right doesn't make this comment right.

### 3. Emit one line

Format (markdown, terse):

```
**N. <verdict>** — `<file>:<line>` (@<author>)

<reply, ≤ ~60 words, per Reply style>

<url>
```

For non-anchored comments, drop the `` `file:line` `` segment.

**Write the reason as a reply, not a verdict.** The label / `file:line` / url are scaffolding for the user; the prose between them must stand alone as something they can paste straight onto the thread as a response to that reviewer. So: address the reviewer in the user's voice ("Good catch, but …" / "It is logged — …" / "Half right."), not the user in yours ("the bot misreads …" / "comment is wrong about …"). No verdict word inside the prose, no third-person reference to "the comment." Stay honest to the verdict — a `disagree` pushes back, a `partial` concedes the half that lands, a `needs-info` states what's missing or asks the question.

**Reply style**

- **Code in backticks:** wrap every identifier, path, flag, literal, and command in backticks.
- **Linked references:** link every `file:line` in the reply prose, and every referenced symbol definition you can locate.
  - GitHub: ``[`<file>:<a>-<b>`](<blob_base>/blob/<head_sha>/<path>#L<a>-L<b>)``, or `#L<a>` for a single line.
  - GitLab: ``[`<file>:<a>-<b>`](<blob_base>/-/blob/<head_sha>/<path>#L<a>-<b>)``, or `#L<a>` for a single line.
  - Removed code (e.g. in a `stale` reply): pin to `base_sha` instead.
  - Before emitting, run `git show <sha>:<path>` for each link and check the lines match the claim. Fix or drop a link that doesn't.
- **Scaffolding stays plain:** the header `` `<file>:<line>` `` and the trailing `<url>` are for the user; keep them unlinked. Links go only in the reply prose.
- **Budget:** reply prose at or under ~60 words. Over budget → cut restated context first.
- **Tone:** concrete, practical effect first. No hedging filler, no praise beyond a short opener like "Good catch, but", no "as discussed", no restating the reviewer's words back to them.

Emit the reply as bare text: no `>` blockquote, no leading indent. Both end up in the user's copy.

Still **read-only** — writing reply-shaped text is not posting it. Never post it yourself.

Examples:

```
**3. disagree** — `_pr_render.py:94` (@review-bot)

Duplicate `### Heading` collapse is already handled by the set-based diff in [`_pr_render.py:80-86`](https://github.com/o/r/blob/abc1234/_pr_render.py#L80-L86) — the set drops dup lines within a section before this runs. Real-world PR bodies don't carry duplicate H3s anyway.

https://github.com/...

**4. agree** — `_pr_render.py:112` (@pupcoder)

Right on both counts — the `existing == updated` short-circuit belongs before `_parse_sections` ([`_pr_render.py:112`](https://github.com/o/r/blob/abc1234/_pr_render.py#L112)), and the empty-string case (`not existing.strip()`) returns `""` so `main()` prints no summary banner. Adding a stderr hint for that.

https://github.com/...

**5. partial** — `_pr_render.py:38` (@claude)

Agreed `n=9999` is a magic number. But `max(len(a), len(b))` still leaves a bounded window in [`_pr_render.py:38`](https://github.com/o/r/blob/abc1234/_pr_render.py#L38) — going with `n=sys.maxsize`, or dropping to a single-pass walk.

https://github.com/...
```

### 4. Tally at the end

```
---
Summary: N comments — agree X / disagree Y / partial Z / stale A / defer B / needs-info C / answer D
```

Stop. Do not offer to apply fixes, post replies, or resolve threads. User asked for verdicts only.

## Follow-up: replies after fixes land

If the user later applies fixes and asks whether/how to respond, draft replies **only for
Questions** (reviewer-bot `Question,` notes, human "why…?" notes — the non-resolvable ones). Findings
get no reply: the fix plus Resolve is the response. Each reply is bare text: what changed, in one
line, plus the *why* only where the fix differs from or goes past what the question implied
(different mechanism, wider scope, a pre-existing bug found along the way). Tell the user to post
after pushing, so replies don't claim "fixed" against the old diff. Follow-up replies use the same
Reply style (backticks, links pinned to the new `head_sha` after the push, budget, tone). Still
read-only: never post or resolve.

## Args

- `--author <login>` — filter to one reviewer (repeat to allow multiple).
- `--include-resolved` (GitLab only) — include resolved discussion threads.
- `--pr <num>` / `--mr <iid>` — override auto-detect (e.g. review a PR on a branch other than HEAD).

## Hard rules

- **Read-only.** Never `gh pr review`, `gh pr comment`, `glab mr note`, `glab mr approve`, or any write API.
- **Never resolve threads** — that's a write op too.
- **Never edit files.** Even if you agree with the fix. User explicitly chose summary-only output.
- **Never `git push`** or commit.
- **No author bias.** Judge claude / review-bot / pupcoder / human comments by the same standard. State disagreement plainly.
- **Cite the live code, not the comment's diff snippet.** Snippets go stale after force-pushes.
- **No noise about dropped threads.** Filtered-out discussions (resolved, system, author's own, bot review surfaces) are invisible — never mention or count them.

## Common pitfalls

- **Already-fixed comments**: If reviewer requested a change already present/resolved in current HEAD, mark **`disagree`** (e.g., "Already addressed in commit `c833a09` — lockfile regenerated and CI passing").
- **Force-push staleness**: comments anchored to lines that no longer exist (`line: null` on GH, missing `position` on GL) — mark **stale**, don't guess at the new location.
- **Outdated review threads**: GH marks a review comment `outdated: true` when the file changed since. Still worth assessing — the underlying point may still apply elsewhere — but flag it.
- **Suggestion blocks**: GitHub `suggestion` blocks (\`\`\`suggestion ... \`\`\`) are concrete diffs. Read them carefully; they're often more precise than prose comments and easier to verdict.
- **Bot summary comments**: many AI reviewers (coderabbit, claude) post one big "summary" review-level comment listing N findings as a bulleted list. Don't treat it as one comment — split each bullet into its own verdict line. Number them `5a`, `5b`, `5c` under the parent index.
- **Threaded replies**: GH `in_reply_to_id` and GL `discussion_id` chain replies. Don't re-verdict each reply — judge the root comment, note if a reply changed the ask.
- **GitLab resolved-state semantics**: a discussion's resolved state lives on each note as `notes[i].resolved` (`true` / `false` / `null`). `true` = explicitly closed; `false` = open, resolvable; `null` = non-resolvable (e.g. general MR-level note, reviewer-bot Question). Default scope drops only `true`. Don't infer resolved state from "the conversation looks settled" — only the boolean counts. The one exception is author-replied-last, which is filtered out (see filter).
- **GitLab null `position`**: MR-level notes and reviewer-bot Questions have `position: null`, and the local `jq` errors on `.position.new_path` (`cannot use null as iterable`). Always read it as `(.position // {}).new_path` / `.new_line`.
- **Reviewer-bot Questions**: posted as standalone notes marked with an HTML-comment key (exact marker in `references/local.md`), rendering `Question, 🛡️ *Security Architect*` above the body and a markdown file link (not a `position`) below it — so `file`/`line` come from that link, not the normalize table's `position.new_path`. They're `individual_note`, never resolvable, and don't gate approval. Verdict **answer**: reply with the fact the reviewer is missing, not a judgement of the question. Re-reviews re-post them keyed by text hash, so an unchanged question survives every run — if the thread already carries your reply, say so on one line instead of re-answering.
- **Cross-repo PRs (forks)**: anchored file paths are relative to the fork's branch, which is what's checked out locally. No special handling needed, but be aware if reading fails.
- **No PR for branch**: user may be on a branch with no PR yet — fail clearly with `gh pr create` / `glab mr create` hint, don't silently fall back to `main`.

## Retro — improve this skill

This skill is **two-way**: after the run, spend one beat on whether the run exposed something the
skill itself should encode. Most clean runs need no change — don't force it.

Propose an edit only on real signal:

- A case these instructions didn't cover and you had to improvise (a comment/thread type or
  reviewer-bot format not handled, a platform quirk in the GH/GL fetch the pitfalls miss).
- The user disagreed with how you verdicted or scoped, or repeated an instruction.
- A step here was wrong or stale (a `gh`/`glab` field changed, a filter rule misfired).
- You repeated a manual workaround that belongs in the fetch/verdict flow.

When a signal fires, **propose** the concrete edit: name the section, show before/after lines,
one sentence of why. Apply only after the user says yes — this file is global and durable, never
edit it silently. If nothing fired, say nothing — no "run went well" noise.
