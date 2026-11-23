#!/usr/bin/env python3
"""GitHub PR plumbing for post-pr-review.

Subcommands (run inside the repo; `gh` resolves owner/repo from it):
  context [--pr NUM] [--branch NAME]        PR facts as JSON
  discussions [--pr NUM] [--branch NAME] [--scope all|open] [--include-resolved] [--author LOGIN]...
  post SPEC --pr NUM [--apply]              validate (default) or post a JSON spec

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

BOT_RE = re.compile(r"(?i)dependabot|coderabbit|copilot|claude|(^|[-_])bot([-_]|$)|\[bot\]")
STATUS_RE = re.compile(r":looks-good\b|REVIEW_INCOMPLETE")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
REQUIRED = {
    "inline": ("path", "line", "body"),
    "reply": ("comment_id", "body"),
    "general": ("body",),
    "reopen": ("thread_id",),
    "edit": ("comment_id", "body"),
}

THREADS_QUERY = """query($owner: String!, $name: String!, $number: Int!, $endCursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          resolvedBy { login }
          path
          line
          originalLine
          comments(first: 100) {
            nodes {
              databaseId
              author { login }
              body
              url
            }
          }
        }
      }
    }
  }
}"""

UNRESOLVE_MUTATION = """mutation($id: ID!) {
  unresolveReviewThread(input: {threadId: $id}) {
    thread { isResolved }
  }
}"""


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.rstrip("\n")


def git_ok(*args: str) -> bool:
    return subprocess.run(["git", *args], capture_output=True, text=True).returncode == 0


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def gh_json(*args: str, body: dict | None = None) -> Any:
    cmd = ["gh", *args, *(["--input", "-"] if body is not None else [])]
    out = subprocess.run(
        cmd, input=None if body is None else json.dumps(body), capture_output=True, text=True, check=True
    ).stdout
    return json.loads(out) if out.strip() else {}


def have_commit(sha: str | None) -> bool:
    return bool(sha) and git_ok("cat-file", "-e", f"{sha}^{{commit}}")


def _login(actor: dict | None) -> str:
    return (actor or {}).get("login") or "ghost"


def _kind(author: str, me: str) -> str:
    return "me" if author == me else "bot" if BOT_RE.search(author) else "human"


def _flatten(data: Any) -> list[dict]:
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for item in data:
        if isinstance(item, list):
            out.extend(item)
        elif isinstance(item, dict):
            out.append(item)
    return out


def load_context(pr: str | None, branch: str | None) -> dict:
    owner_repo = gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()
    sel = pr or branch or git("rev-parse", "--abbrev-ref", "HEAD")
    try:
        data = gh_json(
            "pr",
            "view",
            sel,
            "--json",
            "number,url,state,title,author,headRefName,baseRefName,headRefOid,baseRefOid",
        )
    except subprocess.CalledProcessError:
        print(f"no PR for {sel}; create one with gh pr create", file=sys.stderr)
        raise SystemExit(3)
    me = gh("api", "user", "--jq", ".login").strip()
    num = data["number"]
    head_ref = data["headRefName"]
    base_ref = data["baseRefName"]
    head_oid = data["headRefOid"]
    base_oid = data["baseRefOid"]
    fetched = git_ok("fetch", "-q", "origin", f"pull/{num}/head", base_ref)
    base_sha = git("merge-base", base_oid, head_oid) if have_commit(base_oid) and have_commit(head_oid) else base_oid
    url = data["url"]
    state = data["state"]
    ctx: dict[str, Any] = {
        "number": num,
        "owner_repo": owner_repo,
        "web_url": url,
        "blob_base": url.rsplit("/pull/", 1)[0],
        "state": state,
        "title": data["title"],
        "author": _login(data.get("author")),
        "me": me,
        "head_ref": head_ref,
        "base_ref": base_ref,
        "head_sha": head_oid,
        "base_sha": base_sha,
        "fetched": fetched,
    }
    if state != "OPEN":
        ctx["warning"] = f"PR is {state}"
    return ctx


def fetch_discussions(owner_repo: str, num: int) -> tuple[list[dict], list[dict], list[dict]]:
    owner, name = owner_repo.split("/", 1)
    raw = gh(
        "api",
        "graphql",
        "--paginate",
        "-f",
        f"query={THREADS_QUERY}",
        "-F",
        f"owner={owner}",
        "-F",
        f"name={name}",
        "-F",
        f"number={num}",
    )
    dec = json.JSONDecoder()
    threads: list[dict] = []
    idx, length = 0, len(raw)
    while idx < length:
        while idx < length and raw[idx].isspace():
            idx += 1
        if idx >= length:
            break
        page, idx = dec.raw_decode(raw, idx)
        pr_node = ((page.get("data") or {}).get("repository") or {}).get("pullRequest") or {}
        threads.extend((pr_node.get("reviewThreads") or {}).get("nodes") or [])

    issues = _flatten(gh_json("api", f"repos/{owner_repo}/issues/{num}/comments", "--paginate", "--slurp"))
    reviews = [
        r
        for r in _flatten(gh_json("api", f"repos/{owner_repo}/pulls/{num}/reviews", "--paginate", "--slurp"))
        if r.get("state") != "PENDING" and (r.get("body") or "").strip()
    ]
    return threads, issues, reviews


def normalize_thread(t: dict, me: str) -> dict | None:
    comments = (t.get("comments") or {}).get("nodes") or []
    if not comments:
        return None
    first = comments[0]
    author = _login(first.get("author"))
    mine = [i for i, c in enumerate(comments) if _login(c.get("author")) == me]
    line = t.get("line") if t.get("line") is not None else t.get("originalLine")
    return {
        "id": t["id"],
        "comment_id": first["databaseId"],
        "surface": "thread",
        "author": author,
        "kind": _kind(author, me),
        "path": t.get("path"),
        "line": line,
        "resolved": t.get("isResolved"),
        "resolved_by": (t.get("resolvedBy") or {}).get("login"),
        "outdated": bool(t.get("isOutdated")),
        "body": first.get("body") or "",
        "replies": [
            {"id": c["databaseId"], "author": _login(c.get("author")), "body": c.get("body") or ""}
            for c in comments[1:]
        ],
        "last_author": _login(comments[-1].get("author")),
        "after_me": len(comments) - 1 - mine[-1] if mine else None,
        "url": first.get("url") or "",
    }


def normalize_issue_comment(c: dict, me: str) -> dict:
    author = _login(c.get("user"))
    return {
        "id": str(c["id"]),
        "comment_id": c["id"],
        "surface": "issue",
        "author": author,
        "kind": _kind(author, me),
        "path": None,
        "line": None,
        "resolved": None,
        "resolved_by": None,
        "outdated": False,
        "body": c.get("body") or "",
        "replies": [],
        "last_author": author,
        "after_me": 0 if author == me else None,
        "url": c.get("html_url") or "",
    }


def normalize_review(r: dict, me: str) -> dict:
    author = _login(r.get("user"))
    return {
        "id": str(r["id"]),
        "comment_id": r["id"],
        "surface": "review",
        "author": author,
        "kind": _kind(author, me),
        "path": None,
        "line": None,
        "resolved": None,
        "resolved_by": None,
        "outdated": False,
        "body": r.get("body") or "",
        "replies": [],
        "last_author": author,
        "after_me": 0 if author == me else None,
        "url": r.get("html_url") or "",
    }


def select(
    records: list[dict], pr_author: str, scope: str, include_resolved: bool, authors: list[str]
) -> list[dict]:
    out = list(records)
    if scope == "open":
        out = [r for r in out if r["author"] != pr_author and not STATUS_RE.search(r["body"])]
        if not include_resolved:
            out = [r for r in out if r["last_author"] != pr_author and r["resolved"] is not True]
    if authors:
        out = [r for r in out if r["author"] in authors]
    return out


def line_map(diff_text: str) -> dict:
    files: dict = {}
    old = new = None
    cur = None
    o_rem = n_rem = 0
    o_ln = n_ln = 0
    for raw in diff_text.split("\n"):
        if o_rem > 0 or n_rem > 0:
            tag = raw[:1]
            if tag == " " or raw == "":
                cur["context"][n_ln] = o_ln
                o_ln += 1
                n_ln += 1
                o_rem -= 1
                n_rem -= 1
            elif tag == "+":
                cur["added"].add(n_ln)
                n_ln += 1
                n_rem -= 1
            elif tag == "-":
                cur["deleted"].add(o_ln)
                o_ln += 1
                o_rem -= 1
            continue
        if raw.startswith("diff --git "):
            old = new = cur = None
        elif raw.startswith("--- "):
            old = None if raw[4:] == "/dev/null" else raw[6:]
        elif raw.startswith("+++ "):
            new = None if raw[4:] == "/dev/null" else raw[6:]
            key = new or old
            cur = files.setdefault(key, {"old_path": old or new, "added": set(), "context": {}, "deleted": set()})
        elif cur is not None and (h := HUNK_RE.match(raw)):
            o_ln, n_ln = int(h.group(1)), int(h.group(3))
            o_rem = int(h.group(2) if h.group(2) is not None else 1)
            n_rem = int(h.group(4) if h.group(4) is not None else 1)
    return files


def anchor(lm: dict, path: str, line: int, side: str = "new", start_line: int | None = None) -> dict | None:
    if side == "old":
        for key, e in lm.items():
            if e["old_path"] == path or key == path:
                valid = e["deleted"] | set(e["context"].values())
                if line in valid:
                    out: dict[str, Any] = {"path": key, "line": line, "side": "LEFT"}
                    if start_line is not None:
                        if start_line >= line or start_line not in valid:
                            return None
                        out["start_line"] = start_line
                        out["start_side"] = "LEFT"
                    return out
        return None
    if side != "new":
        return None
    e = lm.get(path)
    if e is None:
        return None
    valid = e["added"] | set(e["context"])
    if line not in valid:
        return None
    out = {"path": path, "line": line, "side": "RIGHT"}
    if start_line is not None:
        if start_line >= line or start_line not in valid:
            return None
        out["start_line"] = start_line
        out["start_side"] = "RIGHT"
    return out


def build_request(item: dict, ctx: dict, lm: dict) -> tuple[str, str, dict]:
    kind = item.get("kind")
    if kind not in REQUIRED:
        raise ValueError(f"unknown kind: {kind}")
    for field in REQUIRED[kind]:
        if item.get(field) in (None, ""):
            raise ValueError(f"missing {field}")
    repo = ctx["owner_repo"]
    num = ctx["number"]
    if kind == "inline":
        start_line = int(item["start_line"]) if item.get("start_line") is not None else None
        a = anchor(lm, item["path"], int(item["line"]), item.get("side", "new"), start_line)
        if a is None:
            raise ValueError(
                f"{item['path']}:{item['line']} is not in the diff; move it to the general comment or a changed line"
            )
        return ("POST", f"repos/{repo}/pulls/{num}/comments", {"body": item["body"], "commit_id": ctx["head_sha"], **a})
    if kind == "reply":
        return ("POST", f"repos/{repo}/pulls/{num}/comments/{item['comment_id']}/replies", {"body": item["body"]})
    if kind == "general":
        return ("POST", f"repos/{repo}/issues/{num}/comments", {"body": item["body"]})
    if kind == "reopen":
        return ("GRAPHQL", "unresolveReviewThread", {"threadId": item["thread_id"]})
    seg = "issues" if item.get("surface") == "issue" else "pulls"
    return ("PATCH", f"repos/{repo}/{seg}/comments/{item['comment_id']}", {"body": item["body"]})


def describe(item: dict, body: dict) -> str:
    kind = item["kind"]
    if kind == "inline":
        span = f"{body['start_line']}-{body['line']}" if "start_line" in body else str(body["line"])
        return f"{body['path']}:{span} ({body['side']})"
    if kind == "general":
        return "general"
    if kind == "reopen":
        return f"thread {item['thread_id']}"
    return f"comment {item['comment_id']}"


def my_comment_count(owner_repo: str, num: int, me: str) -> int:
    pull_comments = _flatten(gh_json("api", f"repos/{owner_repo}/pulls/{num}/comments", "--paginate", "--slurp"))
    issue_comments = _flatten(gh_json("api", f"repos/{owner_repo}/issues/{num}/comments", "--paginate", "--slurp"))
    return sum(1 for c in (*pull_comments, *issue_comments) if _login(c.get("user")) == me)


def cmd_context(a: argparse.Namespace) -> int:
    print(json.dumps(load_context(a.pr, a.branch), indent=2))
    return 0


def cmd_discussions(a: argparse.Namespace) -> int:
    ctx = load_context(a.pr, a.branch)
    threads, issues, reviews = fetch_discussions(ctx["owner_repo"], ctx["number"])
    raw_records = (
        [normalize_thread(t, ctx["me"]) for t in threads]
        + [normalize_issue_comment(c, ctx["me"]) for c in issues]
        + [normalize_review(r, ctx["me"]) for r in reviews]
    )
    records = [r for r in raw_records if r is not None]
    kept = select(records, ctx["author"], a.scope, a.include_resolved, a.author)
    for n, r in enumerate(kept, 1):
        r["n"] = n
    print(json.dumps(
        {"number": ctx["number"], "pr_author": ctx["author"], "me": ctx["me"], "count": len(kept), "discussions": kept},
        indent=2,
    ))
    return 0


def cmd_post(a: argparse.Namespace) -> int:
    with open(a.spec) as f:
        items = json.load(f)
    ctx = load_context(a.pr, None)
    num = ctx["number"]
    lm: dict = {}
    if any(i.get("kind") == "inline" for i in items):
        if not (have_commit(ctx["base_sha"]) and have_commit(ctx["head_sha"])):
            git_ok("fetch", "-q", "origin", f"pull/{num}/head", ctx["base_ref"])
        for sha in (ctx["base_sha"], ctx["head_sha"]):
            if not have_commit(sha):
                print(f"cannot build line map: {sha} not available locally", file=sys.stderr)
                return 1
        lm = line_map(git("diff", "--no-color", "--no-ext-diff", "-M", "--unified=3", ctx["base_sha"], ctx["head_sha"]))
    reqs, errors = [], []
    for i, item in enumerate(items, 1):
        try:
            reqs.append(build_request(item, ctx, lm))
        except ValueError as e:
            errors.append(f"item {i}: {e}")
    if errors:
        print("\n".join(errors))
        return 2
    if not a.apply:
        for i, (item, (_, _, body)) in enumerate(zip(items, reqs), 1):
            print(f"{i} {item['kind']} {describe(item, body)} ok")
        return 0
    before = my_comment_count(ctx["owner_repo"], num, ctx["me"])
    rows: list = []
    inline_resps: list = []
    for i, (item, (method, path, body)) in enumerate(zip(items, reqs), 1):
        try:
            if method == "GRAPHQL":
                resp = gh_json("api", "graphql", "-f", f"query={UNRESOLVE_MUTATION}", "-F", f"id={body['threadId']}")
            else:
                resp = gh_json("api", "-X", method, path, body=body)
        except subprocess.CalledProcessError as e:
            print_table(rows)
            print(f"item {i} failed: {(e.stderr or '').strip()}")
            return 1
        rows.append((i, item["kind"], describe(item, body), resp.get("html_url") or ctx["web_url"]))
        if item["kind"] == "inline":
            inline_resps.append((i, resp))
    print_table(rows)
    expected = sum(1 for it in items if it["kind"] in ("inline", "reply", "general"))
    got = my_comment_count(ctx["owner_repo"], num, ctx["me"]) - before
    problem = None
    if got != expected:
        problem = f"new comments by {ctx['me']}: expected {expected}, got {got}"
    else:
        for i, resp in inline_resps:
            if resp.get("line") is None and resp.get("original_line") is None:
                problem = f"item {i}: inline comment has null line and original_line"
                break
    print(f"verify: FAILED: {problem}" if problem else "verify: ok")
    return 1 if problem else 0


def print_table(rows: list) -> None:
    print("| # | kind | target | url |")
    print("|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(str(c) for c in r) + " |")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("context", cmd_context), ("discussions", cmd_discussions)):
        p = sub.add_parser(name)
        p.add_argument("--pr")
        p.add_argument("--branch")
        if name == "discussions":
            p.add_argument("--scope", choices=("all", "open"), default="all")
            p.add_argument("--include-resolved", action="store_true")
            p.add_argument("--author", action="append", default=[], metavar="LOGIN")
        p.set_defaults(fn=fn)
    p = sub.add_parser("post")
    p.add_argument("spec")
    p.add_argument("--pr", required=True)
    p.add_argument("--apply", action="store_true")
    p.set_defaults(fn=cmd_post)
    a = ap.parse_args()
    try:
        return a.fn(a)
    except subprocess.CalledProcessError as e:
        print(f"{' '.join(e.cmd[:3])} failed: {(e.stderr or '').strip()}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
