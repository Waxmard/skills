---
name: address-review-comments
description: >
  Fetch all review comments on the current branch's PR/MR (GitHub or GitLab,
  human + AI reviewers alike) and produce a terse agree/disagree verdict for
  each by reading the referenced code. Read-only by default; after fixes land
  it can draft replies to copy-paste, or post them one by one with
  confirmation. Never resolves threads or edits files. Use when the user wants
  a second opinion on reviewer feedback before responding. Trigger: "review
  the pr comments", "agree or disagree with the comments", "go through the
  reviewer feedback", "/address-review-comments", "respond to the threads", "draft
  replies".
---

Pull every review comment on the current branch's open PR/MR and judge each by reading the code, as a terse per-comment verdict the user can paste back onto the thread as a reply.

The verdict run posts nothing, resolves nothing and edits nothing; replies are posted only through **Respond → Draft and post**.

Works with **GitHub** (`gh`) and **GitLab** (`glab`). All comments are in scope: bot reviewers (claude, coderabbit, copilot, etc.) and humans alike. No author filtering by default; user may pass an `--author <login>` filter to narrow.

## Pre-flight

1. Confirm CWD is in a git repo: `git rev-parse --git-dir`. If not, stop.
2. Read current branch: `git rev-parse --abbrev-ref HEAD`. Any branch is allowed regardless of its base/target — the gate is whether a PR/MR exists (step 5), not the branch name. A branch like `dev` may have an open `dev → main` PR; review it the same as any other.
3. Detect platform:
   - `git remote get-url origin` → if host is `github.com` → GitHub.
   - If host contains `gitlab` → GitLab.
   - Otherwise (self-hosted host with neither substring) probe the CLIs before asking: run `glab auth status` and `gh auth status` and pick the one logged in to the remote's host. Only ask the user if both fail or both match.
4. Verify CLI is installed and authed:
   - GitHub: `gh auth status` (must succeed).
   - GitLab: `glab auth status` (must succeed).
5. Resolve PR/MR number for current branch:
   - GitHub: `gh pr view --json number,url,headRefName,baseRefName,state,headRefOid,baseRefOid` → fail if no PR. Record `head_sha` = `headRefOid`, `base_sha` = `baseRefOid`, and `blob_base` = `url` minus the trailing `/pull/<n>` (e.g. `https://github.com/o/r`).
   - GitLab: `glab mr view --output json` → fail if no MR. Record `head_sha` = `.diff_refs.head_sha` (`.sha` if `diff_refs` is null), `base_sha` = `.diff_refs.base_sha`, and `blob_base` = `.web_url` minus the trailing `/-/merge_requests/<iid>`.
   - If state is not `OPEN` / `opened`, warn but continue (user may still want feedback on a merged PR).
6. Fetch the PR head so `git show <head_sha>:<path>` works locally, fork PRs included: GitHub `git fetch origin pull/<n>/head <baseRefName>`, GitLab `git fetch origin merge-requests/<iid>/head`. On GitHub, then set `base_sha` = `git merge-base <baseRefOid> <head_sha>`: `baseRefOid` is the base branch tip, while GitLab's `base_sha` is already the fork point. If the fetch fails, continue without links: replies use plain backticked `` `file:line` ``, and say once, before the verdicts, that links were skipped.

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

**In scope (default) = everything nobody has resolved.** That's open resolvable threads (`notes[0].resolved == false`) *and* non-resolvable top-level MR notes (`null`) — the latter carry reviewer-bot Questions and every human "why did you do it this way?" comment, which are real feedback with no Resolve button to click. Out of scope: resolved threads (`true`), threads where the MR author wrote the last note (already answered, ball is in the reviewer's court), system events, the MR author's own notes, and the reviewer bot's own status notes (markers in `references/local.md`) — those are status, not feedback.

The canonical filter (apply ALL of these unless `--include-resolved` is passed):

```bash
jq --arg me "$ME" '[.[]
  | select(.notes[0].system == false)              # drop "marked as draft", etc
  | select(.notes[0].author.username != $me)       # drop MR author's own notes
  | select(([.notes[] | select(.system == false)] | last | .author.username) != $me)  # drop threads the MR author already answered last; system "changed this line" notes don't count
  | select(.notes[0].resolved != true)             # drop resolved; keep open AND non-resolvable
  | select((.notes[0].body // "") | test("BOT_STATUS_MARKERS") | not)
]' "$DISC"
```

Replace `BOT_STATUS_MARKERS` with the reviewer bot's status-marker regex from `references/local.md` (machine-local); if the file is absent, drop that `select` line.

Note `resolved != true` (strict on `true` only): `true` = someone clicked Resolve (drop), `false` = open resolvable thread (keep), `null` = non-resolvable note, no thread state (keep).

If `--include-resolved` is passed: drop the `resolved` select and the last-human-note author select. If `--author <login>` is passed: add `| select(.notes[0].author.username == "<login>")`.

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
- **Exception:** if every in-scope comment references the same file and you've already read it, judge inline regardless of count — subagents would re-read the same diff.

Split a bot summary comment into its sub-bullets (`5a`, `5b`, …) **before** dispatch — each sub-bullet is its own unit of work and its own subagent.

Each subagent's prompt must include: the comment record (author, file, line, body, url), the platform, the repo root, `head_sha`, `base_sha`, `blob_base`, the platform's link format, the verdict criteria + output format below (including the reply-voice rule — a subagent writing in verdict voice costs a rewrite of every line), the Reply style block verbatim, and the read-only rule verbatim (no writes, no edits, no thread/approve ops — it only reads code, runs read-only `git show` / `git diff` to check its links, and returns a line). Subagents need `Read` plus that read-only git access.

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

````
**N. <verdict>** — `<file>:<line>` (@<author>)

```markdown
<reply, ≤ ~60 words (over budget → cut restated context first), per Reply style>
```

<url>
````

For non-anchored comments, drop the `` `file:line` `` segment.

**Write the reason as a reply, not a verdict.** The label / `file:line` / url are scaffolding for the user; the prose between them must stand alone as something they can paste straight onto the thread as a response to that reviewer. So: address the reviewer in the user's voice ("Good catch, but …" / "It is logged — …" / "Half right."), not the user in yours ("the bot misreads …" / "comment is wrong about …"). No verdict word inside the prose, no third-person reference to "the comment." Stay honest to the verdict — a `disagree` pushes back, a `partial` concedes the half that lands, a `needs-info` states what's missing or asks the question.

**Reply style**

- **Code in backticks:** wrap each identifier, path, flag, literal, and command in its own backticks. Backtick the atoms, not whole expressions: write `` `user_id` is `None` ``, not `` `user_id is None` ``. Language keywords used as plain English words (match, if, async) stay unformatted. Link text stays unformatted: `[<file>:<a>-<b>](…)`, not ``[`<file>`](…)``.
- **Linked references:** link every `file:line` in the reply prose, and every referenced symbol definition you can locate.
  - GitHub: `[<file>:<a>-<b>](<blob_base>/blob/<head_sha>/<path>#L<a>-L<b>)`, or `#L<a>` for a single line.
  - GitLab: `[<file>:<a>-<b>](<blob_base>/-/blob/<head_sha>/<path>#L<a>-<b>)`, or `#L<a>` for a single line.
  - Inline the link directly after the phrase it supports; never wrap it in parentheses.
  - Removed code (e.g. in a `stale` reply): pin to `base_sha` instead.
  - Before emitting, run `git show <sha>:<path>` for each link and check the lines match the claim. Fix or drop a link that doesn't.
- **Scaffolding stays plain:** the header `` `<file>:<line>` `` and the trailing `<url>` are for the user; keep them unlinked. Links go only in the reply prose.
- **Proof over assertion:** a `disagree` or `answer` that rests on behavior outside the diffed line traces the hops in one clause, with a link at each. One that rests on a command you ran quotes the command and the decisive output line.
- **Tone:** concrete, practical effect first. No hedging filler, no praise beyond a short opener like "Good catch, but", no "as discussed", no restating the reviewer's words back to them.

Emit the reply inside a fenced block tagged `markdown`, with no blockquote and no indent inside it. Rendered markdown strips the backticks and link URLs the user needs to paste. Use a four-backtick fence if the reply contains a triple-backtick fence.

Writing reply-shaped text is not posting it; post only through **Respond → Draft and post**.

Examples:

````
**3. disagree** — `_pr_render.py:94` (@review-bot)

```markdown
Duplicate `### Heading` collapse is already handled by the set-based diff [_pr_render.py:80-86](https://github.com/o/r/blob/abc1234/_pr_render.py#L80-L86) — the set drops dup lines within a section before this runs. Real-world PR bodies don't carry duplicate H3s anyway.
```

https://github.com/...

**4. agree** — `_pr_render.py:112` (@copilot)

```markdown
Right on both counts — the `existing == updated` short-circuit belongs before `_parse_sections` [_pr_render.py:112](https://github.com/o/r/blob/abc1234/_pr_render.py#L112), and the empty-string case (`not existing.strip()`) returns `""` so `main()` prints no summary banner. Adding a stderr hint for that.
```

https://github.com/...

**5. partial** — `_pr_render.py:38` (@claude)

```markdown
Agreed `n=9999` is a magic number. But `max(len(a), len(b))` still leaves a bounded window [_pr_render.py:38](https://github.com/o/r/blob/abc1234/_pr_render.py#L38) — going with `n=sys.maxsize`, or dropping to a single-pass walk.
```

https://github.com/...
````

### 4. Tally at the end

```
---
Summary: N comments — agree X / disagree Y / partial Z / stale A / defer B / needs-info C / answer D
```

Stop. Offer **Respond** only after the user says fixes have landed.

## Respond: replies after fixes land

Run when the user asks to respond to the threads after applying fixes.

1. **Pushed check.** Re-run pre-flight step 5. `git status --short` must be clean and `git rev-parse HEAD` must equal the new `head_sha`. If not, tell the user to push first and stop, so replies don't claim "fixed" against an old diff.
2. **Scope.** Re-fetch comments with the platform's filter (GitHub: the Skip list; GitLab: the canonical filter), which drops threads the user already answered. Reply to every remaining thread the fixes addressed, findings and Questions alike. Skip any thread the user says they're declining.
3. **Content.** One reply per thread in Reply style, links pinned to the new `head_sha`: what changed, plus the *why* only where the fix differs from or goes past the ask (different mechanism, wider scope, a bug found along the way). Answer a direct question in the thread before describing the change. Verify every link with `git show <head_sha>:<path>`.
   - **Link the fix commit.** Find the commit that changed the cited code: `git log -s --format='%h %H %s' <base_sha>..<head_sha> -L<a>,<b>:<path>` on the reply's main linked range at `head_sha`. Take the newest commit listed. Open a finding reply with `Fixed in [<short_sha>](<commit_url>).`. For a Question, answer first, then name the commit inline where the change is described. `<commit_url>` is `<blob_base>/-/commit/<sha>` on GitLab and `<blob_base>/commit/<sha>` on GitHub. The link text is the plain 8-char short sha, no backticks.
4. **Mode.** Ask once with the structured question tool: `Copy-paste` (recommended) or `Draft and post`.
   - **Copy-paste:** for each thread, emit the header line as normal markdown, then the reply inside its own fenced block tagged `markdown` so the raw source survives copy-paste (rendered markdown loses the backticks and link URLs), then the note URL as a plain line:

         **N.** `<file>:<line>` (@<author>)

         ```markdown
         <reply>
         ```

         <note_url>

     `<note_url>` is the comment's `html_url` on GitHub and `<mr_web_url>#note_<notes[0].id>` on GitLab.

     If a reply itself contains a triple-backtick fence, use a four-backtick outer fence.

   - **Draft and post:** confirm per `post-mr-review`'s **Confirm** section, with one `Post`/`Skip` question per reply and the body as preview. Write each body to a temp file, then post:
     - GitLab: per `post-mr-review`'s **Post** section, `POST projects/:id/merge_requests/<iid>/discussions/<discussion_id>/notes` with `{"body"}`.
     - GitHub inline comment: `gh api -X POST repos/<owner_repo>/pulls/<n>/comments/<root_id>/replies -F body=@<file>`, where `<root_id>` is the thread's first comment (no `in_reply_to_id`).
     - GitHub review summary or conversation comment: these have no thread, so `gh api -X POST repos/<owner_repo>/issues/<n>/comments -F body=@<file>`, with the body opening on a link to the comment's `html_url`.

     Then re-fetch and verify the new comment count. Never resolve or reopen threads.

## Args

- `--author <login>` — filter to one reviewer (repeat to allow multiple).
- `--include-resolved` (GitLab only) — include resolved discussion threads.
- `--pr <num>` / `--mr <iid>` — override auto-detect (e.g. review a PR on a branch other than HEAD).

## Hard rules

- **Read-only unless the user picks Draft and post** in Respond, and then post only replies confirmed in that same turn. Never `gh pr review`, `glab mr approve`, or any other write API.
- **Never resolve threads** — that's a write op too.
- **Never edit files.** Even if you agree with the fix. User explicitly chose summary-only output.
- **Never `git push`** or commit.
- **No author bias.** Judge claude / review-bot / copilot / human comments by the same standard. State disagreement plainly.
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
- **Push notes look like replies**: pushing a change to a commented line adds a `system: true` note "changed this line in version N of the diff", authored by the pusher. Judge "author answered last" on the last non-system note, or every fixed thread silently drops out.
- **GitLab null `position`**: MR-level notes and reviewer-bot Questions have `position: null`, and the local `jq` errors on `.position.new_path` (`cannot use null as iterable`). Always read it as `(.position // {}).new_path` / `.new_line`.
- **Cross-repo PRs (forks)**: anchored file paths are relative to the fork's branch, which is what's checked out locally. No special handling needed, but be aware if reading fails.
- **No PR for branch**: user may be on a branch with no PR yet — fail clearly with `gh pr create` / `glab mr create` hint, don't silently fall back to `main`.

## Retro

After the run, propose an edit to this skill only on real signal: a case these steps didn't cover, a
user correction or repeated instruction, a wrong or stale step, or a manual workaround you repeated.
Name the section, show before/after lines, give one sentence of why, and apply only after a yes, in
the Waxmard/skills source (`skills/address-review-comments/SKILL.md`), never the installed copy. If
nothing fired, say nothing. Skill-specific signals: a comment/thread type or reviewer-bot format not
handled, a platform quirk in the GH/GL fetch the pitfalls miss, a `gh`/`glab` field that changed, or
a filter rule that misfired.
