---
name: address-review-comments
description: >
  Use when checking, evaluating, or replying to review comments or threads on a
  PR or MR (GitHub or GitLab, human or AI reviewers), or when the user asks
  what reviewers said. Judges each comment against the code
  (agree/disagree/answer) and can post confirmed replies; never resolves
  threads or edits files. Trigger: "review the PR comments", "review the MR
  comments", "reviewer feedback", "respond to threads", "post replies", or
  /address-review-comments.
---

Pull every review comment on the current branch's open PR/MR and judge each by reading the code, as a terse per-comment verdict with a reply ready to post on the thread.

The verdict run posts nothing, resolves nothing and edits nothing; replies are posted only through **Respond → Draft and post**.

Works with **GitHub** (`gh`) and **GitLab** (`glab`). All comments are in scope: bot reviewers (claude, coderabbit, copilot, etc.) and humans alike. No author filtering by default; user may pass an `--author <login>` filter to narrow.

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- `git`
- `gh` (GitHub) or `glab` (GitLab), logged in to the PR/MR's host
- `python3` and the `post-mr-review` skill (`scripts/gitlab_mr.py`), for GitLab MRs

Install missing tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## Pre-flight

`<skill-dir>` is the directory this SKILL.md was loaded from; `<mr-script>` is `<skill-dir>/../post-mr-review/scripts/gitlab_mr.py`. Before step 1, check the prerequisites:
```bash
command -v git >/dev/null || echo "missing: git"
command -v gh >/dev/null || command -v glab >/dev/null || echo "missing: gh or glab"
```
If anything prints, stop and tell the user what to install. Step 4 checks the platform CLI's login.

1. Confirm CWD is in a git repo: `git rev-parse --git-dir`. If not, stop.
2. Read current branch: `git rev-parse --abbrev-ref HEAD`. Any branch is allowed regardless of its base/target — the gate is whether a PR/MR exists (step 5), not the branch name. A branch like `dev` may have an open `dev → main` PR; review it the same as any other.
3. Detect platform:
   - `git remote get-url origin` → if host is `github.com` → GitHub.
   - If host contains `gitlab` → GitLab.
   - Otherwise (self-hosted host with neither substring) probe the CLIs before asking: run `glab auth status` and `gh auth status` and pick the one logged in to the remote's host. Only ask the user if both fail or both match.
4. Verify CLI is installed and authed:
   - GitHub: `gh auth status` (must succeed).
   - GitLab: `glab auth status` (must succeed), `command -v python3`, and `[ -f "<mr-script>" ]`.
5. Resolve PR/MR for current branch:
   - GitHub: `gh pr view --json number,url,headRefName,baseRefName,state,headRefOid,baseRefOid` → fail if no PR. Record `head_sha` = `headRefOid`, `base_sha` = `baseRefOid`, and `blob_base` = `url` minus the trailing `/pull/<n>` (e.g. `https://github.com/o/r`). If state is not `OPEN`, warn but continue (user may still want feedback on a merged PR). Fetch the PR head so `git show <head_sha>:<path>` works locally, fork PRs included: `git fetch origin pull/<n>/head <baseRefName>`, then set `base_sha` = `git merge-base <baseRefOid> <head_sha>` (`baseRefOid` is the base branch tip). If the fetch fails, continue without links: replies use plain backticked `` `file:line` ``, and say once, before the verdicts, that links were skipped.
   - GitLab: run `python3 -B "<mr-script>" context` (plus `--mr <iid>` when given). Exit 3: stop and relay stderr, with a `glab mr create` hint. Take `head_sha`, `base_sha`, and `blob_base` from it (`base_sha` is already the fork point). If it reports a `warning` (e.g. the MR is merged), relay it and continue. If `fetched` is false, continue without links: replies use plain backticked `` `file:line` ``, and say once, before the verdicts, that links were skipped.

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

Run `python3 -B "<mr-script>" discussions --scope open`, plus `--include-resolved` and `--author <login>` (repeatable) from Args. A non-zero exit means a failed or stale fetch: stop and relay stderr.

**In scope (default) = everything nobody has resolved.** That's open resolvable threads (`notes[0].resolved == false`) *and* non-resolvable top-level MR notes (`null`) — the latter carry reviewer-bot Questions and every human "why did you do it this way?" comment, which are real feedback with no Resolve button to click. Out of scope: resolved threads (`true`), threads where the MR author wrote the last note (already answered, ball is in the reviewer's court), system events, the MR author's own notes, and the reviewer bot's own status notes (markers in `references/local.md`) — those are status, not feedback.

## Normalize

For each comment build a record (GitLab records from `gitlab_mr.py` are already numbered by `n` and carry `id`, `author`, `path`, `line`, `body`, `url`):

| Field | Source |
|---|---|
| `id` | `id` (GH) / `id` (GL) |
| `author` | `user.login` (GH) / `author` (GL) |
| `path` | `path` (GH inline) / `path` (GL) — empty if not anchored |
| `line` | `line` or `original_line` (GH) / `line` (GL) — empty if not anchored |
| `body` | `body` |
| `url` | `html_url` (GH) / `url` (GL) |

Number them 1..N in the order returned. Output the list to the user before judging, so they see the scope.

**Silent drop.** Only in-scope (post-filter) discussions exist for the rest of this run. Do NOT mention, count, or acknowledge anything the filter removed — no "skipping N resolved threads," no "ignoring the author's own notes," no tally of what was dropped. The user considers that noise. If the filter leaves zero discussions, say only that there are none to review.

## Per-comment verdict loop

Each comment is judged independently by reading the live code — there is no shared reasoning between comments, so this stage **fans out**.

**Dispatch rule:**
- **< 4 in-scope comments**, or all comments in one group: judge them inline yourself, in order.
- **Otherwise**, split bot summary comments into sub-bullets (`5a`, `5b`, …) first, then group by `path`: a sub-bullet joins the group of the file it cites, and all unanchored comments form one group. Split any group over 6 comments into chunks of 6. Spawn one subagent per group in one batch (see Harness notes), on a mid-tier model where the harness lets you choose. Each runs steps 1 to 3 for every comment in its group, reading each file once, and returns **only** its verdict lines, one per comment, in comment order. Collect the lines, group and order them per step 3, then do the tally (step 4) yourself.

Each subagent's prompt must include: its group's comment records (author, path, line, body, url), the platform, the repo root, `head_sha`, `base_sha`, `blob_base`, the platform's link format, the verdict criteria + output format below (including the reply-voice rule: a subagent writing in verdict voice costs a rewrite of every line), the Reply style block verbatim, and the read-only rule verbatim (no writes, no edits, no thread/approve ops, no loading other skills or reading outside the repo; it only reads tracked repo files, runs read-only `git show` / `git diff` to check its links, and returns its lines). Subagents need file-read access plus that read-only git access.

For each comment (inline or in a subagent), in order:

### 1. Read the referenced code

- If the comment is anchored (`path` + `line`): read that file around the line (±30 lines context). Don't trust the diff snippet in the comment body; it may be stale if newer commits were pushed.
- If the comment cites a different file/symbol in the body but isn't anchored there: read the cited target.
- If the comment is purely conceptual (no code reference): no read needed.
- Stay inside the repo's tracked files (`git ls-files`) and git history (`git log`, `git show`, `git diff`). Never load other skills (apart from `post-mr-review` when posting) or read external directories, caches (`~/.cache`), or untracked local state (such as `.tooling-sync.json`) to explain or justify code.

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

Emit `answer` verdicts first under a `### Questions` heading, then every other verdict under `### Findings`. Within each group keep comment order and the original numbers (`2`, `5b`). Omit an empty group's heading.

Format (markdown, terse):

````
**N. <verdict>** — `<file>:<line>` (@<author>)

```markdown
<reply, ≤ ~60 words (over budget → cut restated context first), per Reply style>
```

<<url>>
````

For non-anchored comments, drop the `` `file:line` `` segment.

Wrap the trailing url in angle brackets (`<https://…>`). A bare url line repeats near-verbatim across comments (only the numeric note id changes), which can trip agent harness stream-loop guards and retry the turn forever; a line ending in `>` is skipped by those guards and still renders as a link.

**Write the reason as a reply, not a verdict.** The label / `file:line` / url are scaffolding for the user; the prose between them must stand alone as something they can paste straight onto the thread as a response to that reviewer. So: address the reviewer in the user's voice ("Good catch, but …" / "It is logged — …" / "Half right."), not the user in yours ("the bot misreads …" / "comment is wrong about …"). No verdict word inside the prose, no third-person reference to "the comment." Stay honest to the verdict — a `disagree` pushes back, a `partial` concedes the half that lands, a `needs-info` states what's missing or asks the question.

**Reply style**

- **Code in backticks:** wrap each identifier, path, flag, literal, and command in its own backticks. Backtick the atoms, not whole expressions: write `` `user_id` is `None` ``, not `` `user_id is None` ``. Language keywords used as plain English words (match, if, async) stay unformatted. Link text stays unformatted: `[<file>:<a>-<b>](…)`, not ``[`<file>`](…)``.
- **Linked references:** link every `file:line` in the reply prose, and every referenced symbol definition you can locate.
  - GitHub: `[<file>:<a>-<b>](<blob_base>/blob/<head_sha>/<path>#L<a>-L<b>)`, or `#L<a>` for a single line.
  - GitLab: `[<file>:<a>-<b>](<blob_base>/-/blob/<head_sha>/<path>#L<a>-<b>)`, or `#L<a>` for a single line.
  - Inline the link directly after the phrase it supports; never wrap it in parentheses.
  - Removed code (e.g. in a `stale` reply): pin to `base_sha` instead.
  - Before emitting, run `git show <sha>:<path>` for each link and check the lines match the claim. Fix or drop a link that doesn't.
- **Scaffolding stays plain:** the header `` `<file>:<line>` `` and the trailing `<url>` are for the user; never wrap them in `[text](…)` link syntax. Links go only in the reply prose.
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

<https://github.com/...>

**4. agree** — `_pr_render.py:112` (@copilot)

```markdown
Right on both counts — the `existing == updated` short-circuit belongs before `_parse_sections` [_pr_render.py:112](https://github.com/o/r/blob/abc1234/_pr_render.py#L112), and the empty-string case (`not existing.strip()`) returns `""` so `main()` prints no summary banner. Adding a stderr hint for that.
```

<https://github.com/...>

**5. partial** — `_pr_render.py:38` (@claude)

```markdown
Agreed `n=9999` is a magic number. But `max(len(a), len(b))` still leaves a bounded window [_pr_render.py:38](https://github.com/o/r/blob/abc1234/_pr_render.py#L38) — going with `n=sys.maxsize`, or dropping to a single-pass walk.
```

<https://github.com/...>
````

### 4. Tally at the end

```
---
Summary: N comments — agree X / disagree Y / partial Z / stale A / defer B / needs-info C / answer D
```

Then run **Respond → Stage 1**. With no `answer` verdicts it skips straight to the fix list.

## Respond: post or draft replies

Replies go out in two stages: answers to reviewer questions first, then fix replies once fixes land. Question answers claim no code change, so they don't wait for a push.

### Stage 1: Question replies

Runs right after the tally. With no `answer` verdicts, skip to step 4.

1. **Flag questions that need a change.** Ask once with the structured question tool, multi-select: "Which questions need a code change?". Give one option per `answer` verdict, labelled `N. <file>:<line>` (the question's first few words when unanchored), plus `None`. If the tool caps the option count, split the options across several questions in the same call. Unless the user already asked to post, put the **Posting** mode question in the same call.
2. **Hold flagged questions.** A flagged question joins the fix list (step 4) and gets its reply in Stage 2: the answer first, then the fix. Don't post it now.
3. **Post the rest.** Post every unflagged `answer` reply per **Posting**, reusing the drafted reply as-is. Skip the pushed check: these replies claim no change, and their links pin `head_sha`, which is already on the remote.
4. **Fix list.** Print the threads that need a code change, in comment order: `agree` and `partial` verdicts plus flagged questions.

       **Fix list**
       - **N.** `<file>:<line>` — <change, one clause>

   Then add one line: address these (or a subset), push, then ask to post the Stage 2 replies. If the list is empty, say there's nothing to fix and offer to post the remaining finding replies.

### Stage 2: Fix replies

Run when the user asks to post or respond to the remaining threads, either after fixes land or right away for threads that need no fix.

1. **Pushed check.** Re-run pre-flight step 5. `git status --short` must be clean and `git rev-parse HEAD` must equal the new `head_sha`. If not, tell the user to push first and stop, so replies don't claim "fixed" against an old diff.
2. **Scope.** Re-fetch comments with the platform's filter (GitHub: the Skip list; GitLab: `discussions --scope open`), which drops threads the user already answered. Reply to every remaining in-scope thread (or the subset the user asked to post). Skip any thread the user says they're declining. Question replies posted in Stage 1 drop out here, because the author now wrote the last note.
3. **Content.** If posting a verdict reply as-is (no code change for that thread), reuse the reply already drafted in the verdict run. If fixes landed for the thread, draft a reply in Reply style with links pinned to the new `head_sha`: what changed, plus the *why* only where the fix differs from or goes past the ask (different mechanism, wider scope, a bug found along the way). Answer a direct question in the thread before describing the change. Verify every link with `git show <head_sha>:<path>`.
   - **Link the fix commit** (when a fix landed). Find the commit that changed the cited code: `git log -s --format='%h %H %s' <base_sha>..<head_sha> -L<a>,<b>:<path>` on the reply's main linked range at `head_sha`. Take the newest commit listed. Open a finding reply with `Fixed in [<short_sha>](<commit_url>).`. For a Question, answer first, then name the commit inline where the change is described. `<commit_url>` is `<blob_base>/-/commit/<sha>` on GitLab and `<blob_base>/commit/<sha>` on GitHub. The link text is the plain 8-char short sha, no backticks.
4. **Mode.** Post per **Posting**.

### Posting

If the user explicitly asked to post (e.g. "post it", "post the replies"), use **Draft and post** directly. If they already picked a mode earlier in this run, reuse it. Otherwise ask once with the structured question tool: `Draft and post` (recommended) or `Copy-paste`.

- **Draft and post:** confirm per `post-mr-review`'s **Confirm** section, with one `Post`/`Skip` question per reply and the body as preview. Then post:
  - GitLab: write a spec of `reply` items (`{"kind": "reply", "discussion_id": "<record id>", "body": "..."}`) for the replies answered `Post`, run `python3 -B "<mr-script>" post <spec> --mr <iid> --apply`, and report its table; it verifies the new note count.
  - GitHub inline comment: write each body to a temp file and run `gh api -X POST repos/<owner_repo>/pulls/<n>/comments/<root_id>/replies -F body=@<file>`, where `<root_id>` is the thread's first comment (no `in_reply_to_id`), then re-fetch and verify the new comment count.
  - GitHub review summary or conversation comment: these have no thread, so run `gh api -X POST repos/<owner_repo>/issues/<n>/comments -F body=@<file>` with the body opening on a link to the comment's `html_url`, then re-fetch and verify the new comment count.

  Never resolve or reopen threads.
- **Copy-paste:** for each thread, emit the header line as normal markdown, then the reply inside its own fenced block tagged `markdown` so the raw source survives copy-paste (rendered markdown loses the backticks and link URLs), then the note URL in angle brackets on its own line:

      **N.** `<file>:<line>` (@<author>)

      ```markdown
      <reply>
      ```

      <<note_url>>

  `<note_url>` is the comment's `html_url` on GitHub and `<mr_web_url>#note_<notes[0].id>` on GitLab.

  If a reply itself contains a triple-backtick fence, use a four-backtick outer fence.

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
- **Stay inside the repo; load no other skills.** Judge each comment strictly from the repo's tracked files and git history. Never load unrelated skills (`tooling-sync`, audit skills, etc.) or read external playbooks, caches, or untracked dotfiles to justify a verdict; reviewers and CI only see the repo itself.

## Common pitfalls

- **Already-fixed comments**: If reviewer requested a change already present/resolved in current HEAD, mark **`disagree`** (e.g., "Already addressed in commit `c833a09` — lockfile regenerated and CI passing").
- **Force-push staleness**: comments anchored to lines that no longer exist (`line: null` on GH, missing `position` on GL) — mark **stale**, don't guess at the new location.
- **Outdated review threads**: GH marks a review comment `outdated: true` when the file changed since. Still worth assessing — the underlying point may still apply elsewhere — but flag it.
- **Suggestion blocks**: GitHub `suggestion` blocks (\`\`\`suggestion ... \`\`\`) are concrete diffs. Read them carefully; they're often more precise than prose comments and easier to verdict.
- **Bot summary comments**: many AI reviewers (coderabbit, claude) post one big "summary" review-level comment listing N findings as a bulleted list. Don't treat it as one comment — split each bullet into its own verdict line. Number them `5a`, `5b`, `5c` under the parent index.
- **Threaded replies**: GH `in_reply_to_id` and GL `discussion_id` chain replies. Don't re-verdict each reply — judge the root comment, note if a reply changed the ask.
- **Cross-repo PRs (forks)**: anchored file paths are relative to the fork's branch, which is what's checked out locally. No special handling needed, but be aware if reading fails.
- **No PR for branch**: user may be on a branch with no PR yet — fail clearly with `gh pr create` / `glab mr create` hint, don't silently fall back to `main`.

## Harness notes

| Step says | omp | Claude Code | Other agents |
|---|---|---|---|
| spawn subagents | one `task` call, default agent when tasks run shell commands (`scout` has no `bash`); `task` returns at once, so `wait` until every agent settles before using results or ending the turn | Agent tool calls in one message | no subagents: run inline and say so |
| ask the user | `ask` tool | AskUserQuestion | plain-text question |
| run the script | `bash` tool | the shell | the shell |

## Retro

After the run, propose an edit to this skill only on real signal: a case these steps didn't cover, a
user correction or repeated instruction, a wrong or stale step, or a manual workaround you repeated.
Name the section, show before/after lines, give one sentence of why, and apply only after a yes, in
the skills repo source (`skills/address-review-comments/SKILL.md`), never the installed copy. If
nothing fired, say nothing. Skill-specific signals: a comment/thread type or reviewer-bot format not
handled, a platform quirk in the GH/GL fetch the pitfalls miss, a `gh`/`glab` field that changed, or
a filter rule that misfired.
