#!/usr/bin/env python3
"""GitLab MR plumbing for post-mr-review and address-review-comments.

Subcommands (run inside the repo; `glab api` resolves :id from it):
  context [--mr IID] [--branch NAME]        MR facts as JSON
  discussions [--mr IID] [--branch NAME] [--scope all|open] [--include-resolved] [--author LOGIN]...
  post SPEC --mr IID [--apply]              validate (default) or post a JSON spec

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

MR = "projects/:id/merge_requests"
BOT_RE = re.compile(r"(?i)renovate|dependabot|coderabbit|copilot|(^|[-_])bot([-_]|$)|\[bot\]")
STATUS_RE = re.compile(r"Suggested MR title and description|:looks-good\b|REVIEW_INCOMPLETE")
QUESTION_MARKER_RE = re.compile(r"<!-- [^>]*:questions:")
BLOB_LINK_RE = re.compile(r"/-/blob/[0-9a-f]{7,40}/([^#\s)]+)#L(\d+)")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
REQUIRED = {
    "inline": ("path", "line", "body"),
    "reply": ("discussion_id", "body"),
    "general": ("body",),
    "reopen": ("discussion_id",),
    "edit": ("discussion_id", "note_id", "body"),
}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.rstrip("\n")


def git_ok(*args: str) -> bool:
    return subprocess.run(["git", *args], capture_output=True, text=True).returncode == 0


def glab(path: str) -> Any:
    out = subprocess.run(["glab", "api", path], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def glab_write(method: str, path: str, body: dict | None) -> Any:
    cmd = ["glab", "api", "-X", method, path, *(["--input", "-"] if body is not None else [])]
    out = subprocess.run(
        cmd, input=None if body is None else json.dumps(body), capture_output=True, text=True, check=True
    ).stdout
    return json.loads(out) if out.strip() else {}


def load_context(mr: str | None, branch: str | None) -> dict:
    if mr:
        iid = int(mr)
    else:
        branch = branch or git("rev-parse", "--abbrev-ref", "HEAD")
        out = subprocess.run(
            ["glab", "mr", "list", "--source-branch", branch, "-F", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        found = json.loads(out or "[]")
        if not found:
            print(f"no MR for branch {branch}; create one with glab mr create", file=sys.stderr)
            raise SystemExit(3)
        iid = found[0]["iid"]
    m = glab(f"{MR}/{iid}")
    refs = m.get("diff_refs") or {}
    ctx = {
        "iid": iid,
        "project_id": m["project_id"],
        "web_url": m["web_url"],
        "blob_base": m["web_url"].split("/-/merge_requests/")[0],
        "state": m["state"],
        "title": m["title"],
        "author": m["author"]["username"],
        "me": glab("user")["username"],
        "source_branch": m["source_branch"],
        "head_sha": refs.get("head_sha") or m["sha"],
        "base_sha": refs.get("base_sha"),
        "start_sha": refs.get("start_sha"),
        "fetched": git_ok("fetch", "-q", "origin", f"merge-requests/{iid}/head"),
    }
    if m["state"] != "opened":
        ctx["warning"] = f"MR is {m['state']}"
    return ctx


def fetch_discussions(iid: int) -> list:
    out: list = []
    page = 1
    while True:
        batch = glab(f"{MR}/{iid}/discussions?per_page=100&page={page}")
        if not batch:
            return out
        out.extend(batch)
        page += 1


def check_identity(discussions: list, iid: int) -> int:
    return sum(1 for d in discussions if d["notes"][0].get("noteable_iid") != iid)


def normalize(d: dict, me: str, web_url: str) -> dict:
    notes = d["notes"]
    first = notes[0]
    talk = [n for n in notes if not n.get("system")]
    pos = first.get("position") or {}
    path, line = pos.get("new_path"), pos.get("new_line")
    body = first.get("body") or ""
    if path is None and QUESTION_MARKER_RE.search(body):
        mt = BLOB_LINK_RE.search(body)
        if mt:
            path, line = mt.group(1), int(mt.group(2))
    author = first["author"]["username"]
    kind = "me" if author == me else "bot" if BOT_RE.search(author) or QUESTION_MARKER_RE.search(body) else "human"
    mine = [i for i, n in enumerate(talk) if n["author"]["username"] == me]
    return {
        "id": d["id"],
        "note_id": first["id"],
        "author": author,
        "kind": kind,
        "path": path,
        "line": line,
        "resolved": first.get("resolved"),
        "resolved_by": (first.get("resolved_by") or {}).get("username"),
        "system": bool(first.get("system")),
        "body": body,
        "replies": [
            {"id": n["id"], "author": n["author"]["username"], "body": n.get("body") or ""} for n in talk[1:]
        ],
        "last_author": talk[-1]["author"]["username"] if talk else None,
        "after_me": len(talk) - 1 - mine[-1] if mine else None,
        "pushed_after": any(n.get("system") and "changed this line" in (n.get("body") or "") for n in notes[1:]),
        "url": f"{web_url}#note_{first['id']}",
    }


def select(records: list, mr_author: str, scope: str, include_resolved: bool, authors: list) -> list:
    out = [r for r in records if not r["system"]]
    if scope == "open":
        out = [r for r in out if r["author"] != mr_author]
        if not include_resolved:
            out = [r for r in out if r["last_author"] != mr_author and r["resolved"] is not True]
        out = [r for r in out if not STATUS_RE.search(r["body"])]
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


def anchor(lm: dict, path: str, line: int, side: str = "new") -> dict | None:
    if side == "old":
        for key, e in lm.items():
            if e["old_path"] == path and line in e["deleted"]:
                return {"old_path": path, "new_path": key, "old_line": line}
        return None
    e = lm.get(path)
    if e is None:
        return None
    if line in e["added"]:
        return {"old_path": e["old_path"], "new_path": path, "new_line": line}
    if line in e["context"]:
        return {"old_path": e["old_path"], "new_path": path, "new_line": line, "old_line": e["context"][line]}
    return None


def build_request(item: dict, ctx: dict, lm: dict) -> tuple:
    kind = item.get("kind")
    if kind not in REQUIRED:
        raise ValueError(f"unknown kind: {kind}")
    for field in REQUIRED[kind]:
        if item.get(field) in (None, ""):
            raise ValueError(f"missing {field}")
    base = f"{MR}/{ctx['iid']}/discussions"
    if kind == "inline":
        a = anchor(lm, item["path"], int(item["line"]), item.get("side", "new"))
        if a is None:
            raise ValueError(
                f"{item['path']}:{item['line']} is not in the diff; move it to the general comment or a changed line"
            )
        pos = {
            "position_type": "text",
            "base_sha": ctx["base_sha"],
            "start_sha": ctx["start_sha"],
            "head_sha": ctx["head_sha"],
            **a,
        }
        return "POST", base, {"body": item["body"], "position": pos}
    if kind == "reply":
        return "POST", f"{base}/{item['discussion_id']}/notes", {"body": item["body"]}
    if kind == "general":
        return "POST", base, {"body": item["body"]}
    if kind == "reopen":
        return "PUT", f"{base}/{item['discussion_id']}?resolved=false", None
    return "PUT", f"{base}/{item['discussion_id']}/notes/{item['note_id']}", {"body": item["body"]}


def describe(item: dict, body: dict | None) -> str:
    kind = item["kind"]
    if kind == "inline":
        pos = body["position"]
        nums = ", ".join(f"{k} {pos[k]}" for k in ("new_line", "old_line") if k in pos)
        return f"{item['path']}:{item['line']} ({nums})"
    if kind == "general":
        return "general"
    return f"thread {item['discussion_id']}"


def my_note_count(iid: int, me: str) -> int:
    return sum(
        1
        for d in fetch_discussions(iid)
        for n in d["notes"]
        if not n.get("system") and n["author"]["username"] == me
    )


def have_commit(sha: str | None) -> bool:
    return bool(sha) and git_ok("cat-file", "-e", f"{sha}^{{commit}}")


def cmd_context(a: argparse.Namespace) -> int:
    print(json.dumps(load_context(a.mr, a.branch), indent=2))
    return 0


def cmd_discussions(a: argparse.Namespace) -> int:
    ctx = load_context(a.mr, a.branch)
    iid = ctx["iid"]
    raw = fetch_discussions(iid)
    bad = check_identity(raw, iid)
    if bad:
        print(f"stale data: {bad} discussions not from MR {iid}", file=sys.stderr)
        return 1
    records = [normalize(d, ctx["me"], ctx["web_url"]) for d in raw]
    kept = select(records, ctx["author"], a.scope, a.include_resolved, a.author)
    for n, r in enumerate(kept, 1):
        r["n"] = n
    print(json.dumps(
        {"iid": iid, "mr_author": ctx["author"], "me": ctx["me"], "count": len(kept), "discussions": kept},
        indent=2,
    ))
    return 0


def cmd_post(a: argparse.Namespace) -> int:
    with open(a.spec) as f:
        items = json.load(f)
    ctx = load_context(a.mr, None)
    lm: dict = {}
    if any(i.get("kind") == "inline" for i in items):
        if not (have_commit(ctx["start_sha"]) and have_commit(ctx["head_sha"])):
            git_ok("fetch", "-q", "origin")
        for sha in (ctx["start_sha"], ctx["head_sha"]):
            if not have_commit(sha):
                print(f"cannot build line map: {sha} not available locally", file=sys.stderr)
                return 1
        lm = line_map(git("diff", "--no-color", "--no-ext-diff", "-M", "--unified=3", ctx["start_sha"], ctx["head_sha"]))
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
    iid = ctx["iid"]
    before = my_note_count(iid, ctx["me"])
    rows: list = []
    inline_resps: list = []
    for i, (item, (method, path, body)) in enumerate(zip(items, reqs), 1):
        try:
            resp = glab_write(method, path, body)
        except subprocess.CalledProcessError as e:
            print_table(rows)
            print(f"item {i} failed: {(e.stderr or '').strip()}")
            return 1
        note_id = resp["notes"][0]["id"] if "notes" in resp else resp["id"]
        rows.append((i, item["kind"], describe(item, body), f"{ctx['web_url']}#note_{note_id}"))
        if item["kind"] == "inline":
            inline_resps.append((i, resp))
    print_table(rows)
    expected = sum(1 for it in items if it["kind"] in ("inline", "reply", "general"))
    got = my_note_count(iid, ctx["me"]) - before
    problem = None
    if got != expected:
        problem = f"new notes by {ctx['me']}: expected {expected}, got {got}"
    else:
        for i, resp in inline_resps:
            if not resp["notes"][0].get("position"):
                problem = f"item {i}: inline note has null position"
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
        p.add_argument("--mr")
        p.add_argument("--branch")
        if name == "discussions":
            p.add_argument("--scope", choices=("all", "open"), default="all")
            p.add_argument("--include-resolved", action="store_true")
            p.add_argument("--author", action="append", default=[], metavar="LOGIN")
        p.set_defaults(fn=fn)
    p = sub.add_parser("post")
    p.add_argument("spec")
    p.add_argument("--mr", required=True)
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
