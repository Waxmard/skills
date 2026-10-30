#!/usr/bin/env python3
"""Deterministic half of the wrap-up skill.

Subcommands (all work on the repo containing the CWD):
  preflight [--missing NAME]...   facts, verdicts and the report table
  plan "<reply>"                  parse the user's reply, build review tasks
  prompt <task-id>                print one task's subagent prompt
  findings [--row N]              merge, filter and print subagent findings
  memo                            record the reviewed head after row 2

State lives in <git-path>/wrap-up/run/ (never committed). Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

TEST_RE = re.compile(
    r"(^|/)(test|tests|__tests__)/|\.(test|spec)\.[^/]+$|_test\.go$|\.bats$|^test_.*\.py$|/test_.*\.py$"
)
DOC_RE = re.compile(r"\.(md|mdx|rst|adoc)$")
UI_RE = re.compile(r"\.(tsx|jsx|vue|svelte|css|scss|html)$")
REQ_RE = re.compile(r"requirements.*\.txt$")
MANIFESTS = {"package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Gemfile"}
LOCK_EXCLUDES = [
    ":!*.lock", ":!package-lock.json", ":!pnpm-lock.yaml", ":!yarn.lock", ":!uv.lock",
    ":!poetry.lock", ":!Cargo.lock", ":!go.sum", ":!Gemfile.lock",
]
EXCLUDE_RE = re.compile(
    r"(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|uv\.lock|poetry\.lock|Cargo\.lock|go\.sum|Gemfile\.lock)$"
    r"|\.lock$|(^|/)__snapshots__/|\.snap$"
    r"|(^|/)(dist|build|coverage|vendor|third_party|node_modules)/"
    r"|\.min\.|\.map$|\.gen\.|\.generated\."
)
PROTECTED_RE = re.compile(r"main|master|dev|develop|release/.*|staging")

ROW_SKILL = {
    1: "tooling-sync", 2: "pr-review-toolkit", 3: "ponytail-review", 4: "test-audit",
    5: "interface-review", 6: "docs-audit", 7: "triage-renovate-dependabot-prs",
}
EXTERNAL = {"ponytail-review", "ponytail-audit"}
INLINE_TIER = "inline · fast+"
TIERS = {"fast", "strong"}
MODES = {"default", "lean", "full"}
SEVERITIES = ("critical", "important", "suggestion", "nit")
COMMIT_SUBJECT = {
    2: "fix: address pr-review-toolkit findings",
    3: "fix: address ponytail-review findings",
    4: "test: prune redundant test cases",
    5: "fix: address interface-review findings",
    6: "docs: trim redundant comments and docs",
}
MAX_FILES_ONE_TASK, MAX_LINES_ONE_TASK, MAX_FILES_SHARD, MAX_LINES_SHARD = 30, 1500, 15, 1500


def git(*args: str, cwd: str | Path | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.rstrip("\n")


def git_ok(*args: str, cwd: str | Path | None = None) -> bool:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True
    ).returncode == 0


def git_z(*args: str, cwd: str | Path) -> list[str]:
    return [p for p in git(*args, "-z", cwd=cwd).split("\0") if p]


def short(sha: str) -> str:
    return sha[:7]


def installed(facts: dict, row: int) -> bool:
    return ROW_SKILL[row] in facts["installed"]


def verdicts(f: dict) -> list[dict]:
    """The 7-row verdict table from a facts dict."""
    out: list[dict] = []
    A = f["added"]

    def row(n: int, verdict: str, why: str, tier: str = "fast") -> None:
        out.append({"row": n, "skill": ROW_SKILL[n], "verdict": verdict, "tier": tier, "why": why})

    scope = f.get("scope")
    if scope is None:
        row(1, "skip", "mw-kit not found; pick 1 to clone it into ~/.cache/mw-kit", INLINE_TIER)
    elif not scope.get("preflight", {}).get("ok"):
        row(1, "skip", str(scope.get("preflight", {}).get("error")), INLINE_TIER)
    elif scope.get("state", {}).get("all_settled"):
        row(1, "skip", f"nothing new since last sync ({scope['state'].get('last_sync')})", INLINE_TIER)
    else:
        live = sum(1 for r in scope.get("in_scope", []) if not r.get("state", {}).get("settled"))
        orphans = len(scope.get("state", {}).get("orphaned_tools") or [])
        why = f"{live} live tools" + (f", {orphans} orphaned" if orphans else "")
        row(1, "RUN", why, INLINE_TIER)

    if not f["changed_row2"]:
        if f["mode"] == "delta":
            why = f"no new commits since last review {short(f['from'])}; reply `full` to re-review"
        else:
            why = f"no commits ahead of {f['base']}"
        row(2, "skip", why)
    elif f["mode"] == "delta":
        row(2, "always", f"delta: {len(f['changed_row2'])} files, +{f['added_row2']} lines since last review {short(f['from'])}")
    else:
        row(2, "always", f"{len(f['changed'])} files, +{A} lines vs {f['base']}")

    parts = []
    if A >= 100:
        parts.append(f"+{A} lines")
    if f["manifests_changed"]:
        parts.append("deps changed: " + ", ".join(f["manifests_changed"]))
    if parts:
        row(3, "RUN", "; ".join(parts))
    else:
        row(3, "skip", f"small diff (+{A}), no manifest changes")

    parts = []
    if f["test_changed"]:
        parts.append(f"{len(f['test_changed'])} test files changed")
    if f["nondoc_added"] >= 100:
        parts.append(f"+{f['nondoc_added']} non-doc lines")
    if f["repo_has_tests"] and parts:
        row(4, "RUN", "; ".join(parts))
    elif not f["repo_has_tests"]:
        row(4, "skip", "no test files in repo")
    else:
        row(4, "skip", f"no test files changed, small diff (+{A})")

    if f["ui_changed"]:
        row(5, "RUN", f"{len(f['ui_changed'])} UI files changed")
    else:
        row(5, "skip", "no UI files in diff")

    parts = []
    if f["doc_changed"]:
        parts.append(f"{len(f['doc_changed'])} doc files changed")
    if A >= 100:
        parts.append(f"+{A} lines")
    if parts:
        row(6, "RUN", "; ".join(parts))
    else:
        row(6, "skip", f"no doc files changed, small diff (+{A})")

    if f["renovate"] > 0 and not f["protected"]:
        row(7, "RUN", f"{f['renovate']} unmerged bot branches", INLINE_TIER)
    elif f["protected"]:
        row(7, "skip", f"protected branch: triage refuses on `{f['branch']}`", INLINE_TIER)
    else:
        row(7, "skip", "no unmerged renovate/dependabot branches", INLINE_TIER)

    for r in out:
        if not installed(f, r["row"]):
            r["verdict"] = "skip"
            r["why"] = "not installed"
            if r["row"] in (3, 4):
                r["why"] += (
                    " (omp: `/marketplace add DietrichGebert/ponytail` then `/marketplace install ponytail@ponytail`; "
                    "Claude Code: `/plugin marketplace add DietrichGebert/ponytail` then `/plugin install ponytail@ponytail`)"
                )
        elif f["others"] >= 1 and r["row"] in (1, 7) and r["verdict"] == "RUN":
            r["why"] += " (lean: pick by number to include)"
    return out


def parse_reply(reply: str, vs: list[dict], facts: dict) -> dict:
    """Reply grammar -> {"rows": {N: {mode, tier, skill}}, "notes": [...]}. Raises ValueError."""
    toks = reply.lower().split()
    if toks and toks[0] == "run":
        toks = toks[1:]
    if not toks:
        raise ValueError("empty reply")
    go = none = False
    gmode = "default"
    nums: set[int] = set()
    over: dict[int, dict] = {}
    notes: list[str] = []

    def check_row(n: int) -> int:
        if not 1 <= n <= 7:
            raise ValueError(f"no row {n}")
        return n

    for t in toks:
        m = re.fullmatch(r"(\d+)@(.*)", t)
        if t == "go":
            go = True
        elif t == "none":
            none = True
        elif t in MODES:
            gmode = t
        elif t.isdigit():
            nums.add(check_row(int(t)))
        elif m:
            n = check_row(int(m.group(1)))
            parts = m.group(2).split(":")
            tiers = [p for p in parts if p in TIERS]
            modes = [p for p in parts if p in MODES]
            if len(tiers) + len(modes) != len(parts):
                raise ValueError(f"unrecognized token: {t}")
            if len(tiers) > 1 or len(modes) > 1:
                raise ValueError(f"conflicting override: {t}")
            o = over.setdefault(n, {})
            if tiers:
                o["tier"] = tiers[0]
            if modes:
                o["mode"] = modes[0]
        else:
            raise ValueError(f"unrecognized token: {t}")

    if none and (nums or over):
        raise ValueError("none can't be combined with row numbers")
    if none and go:
        raise ValueError("none can't be combined with go")

    explicit = nums | set(over)
    from_go = go or (not none and not nums and not over)
    if none:
        picked = {2}
    elif from_go:
        picked = {2} | {v["row"] for v in vs if v["verdict"] == "RUN"} | explicit
    else:
        picked = {2} | explicit

    if gmode == "lean":
        picked -= {1, 7} - explicit
    if gmode == "full" and from_go:
        picked |= {r for r in (1, 3, 4, 6) if installed(facts, r)}
        if facts["repo_has_ui"] and installed(facts, 5):
            picked.add(5)

    def mode_of(n: int) -> str:
        m = over.get(n, {}).get("mode")
        return gmode if m in (None, "default") else m

    verdict_of = {v["row"]: v["verdict"] for v in vs}
    if verdict_of[2] == "skip" and mode_of(2) != "full":
        picked.discard(2)
    for n in sorted(picked):
        if not installed(facts, n):
            picked.discard(n)
            notes.append(f"row {n} {ROW_SKILL[n]}: not installed")

    rows: dict[int, dict] = {}
    if any("tier" in over.get(n, {}) for n in (1, 7)):
        notes.append("rows 1 and 7 run inline; switch the session's model instead")
    for n in sorted(picked):
        tier = "inline" if n in (1, 7) else over.get(n, {}).get("tier", "fast")
        mode = mode_of(n)
        skill = ROW_SKILL[n]
        if n == 3 and mode == "full" and "ponytail-audit" in facts["installed"]:
            skill = "ponytail-audit"
        rows[n] = {"mode": mode, "tier": tier, "skill": skill}
    return {"rows": rows, "notes": notes}


def shard_files(files: list[str], lines: dict[str, int]) -> list[list[str]]:
    total = sum(lines.get(f, 0) for f in files)
    if len(files) <= MAX_FILES_ONE_TASK and total <= MAX_LINES_ONE_TASK:
        return [files]
    ordered = sorted(files, key=lambda f: (f.split("/")[0] if "/" in f else ".", f))
    shards: list[list[str]] = []
    cur: list[str] = []
    cl = 0
    for f in ordered:
        n = lines.get(f, 0)
        if cur and (len(cur) + 1 > MAX_FILES_SHARD or cl + n > MAX_LINES_SHARD):
            shards.append(cur)
            cur, cl = [], 0
        cur.append(f)
        cl += n
    if cur:
        shards.append(cur)
    return shards


SHARED_BLOCK = (
    "You are a read-only reviewer in repo `{toplevel}`. Make no edits and no git writes (no checkout, "
    "switch, stash, commit). Read via `git diff`/`git show`/file reads only. The one file you write is "
    "your findings file, `{out}`. Write it with your file-write tool, or `cat > {out} <<'EOF'` with a "
    "quoted delimiter. Skip each skill's prerequisite check, self-refresh block, range resolution, memo, "
    "and subagent fan-out: wrap-up resolved the range, and this task is already the fan-out."
)

CONTRACT = """When done, write `{out}`:
`{{"task": "{tid}", "reports": [{{"row": <N>, "skill": "<name>", "complete": true, "summary": "<the skill report's header line and its net:/verdict line>", "findings": [{{"file": "<repo path>", "line": <int or null>, "severity": "critical|important|suggestion|nit", "tag": "<the skill's tag>", "title": "<one line>", "why": "<1-2 sentences>", "fix": "<concrete change or empty>", "rule": "<project rule cited, or null>", "needs_decision": <bool>}}]}}]}}`

One report per row in this task, in row order.

Severity mapping:
- pr-review-toolkit: Critical -> critical, Important -> important, Suggestions -> suggestion.
- interface-review: HIGH -> critical, MEDIUM -> important, LOW and Pre-existing -> suggestion.
- test-audit, docs-audit, ponytail-review, ponytail-audit: every finding -> important; an item the skill calls optional or taste -> nit.

Set `needs_decision` true when the finding has two valid fixes of different shape, changes behavior or user-facing copy, deletes pre-existing tests, or you are unsure it is real.

If a skill fails partway, still write its report with `"complete": false` and the findings so far.

Reply with one line per row, `row <N> <skill>: <count> findings`, and nothing else."""

LEAN_RULE = (
    "Lean mode: review `git diff {mb}..{head0}` for high-confidence cuts only (`delete:`, `stdlib:`, "
    "`native:`, unneeded deps; omit minor `shrink:` nits) and report only definite improvements. Omit "
    "style nits, minor refactors, naming, and speculative or optional suggestions. If nothing qualifies, say so."
)
DELTA_RULE = (
    "Delta: review only `git diff {frm}..{head0}`, the commits since the last review. The full branch "
    "diff `git diff {mb}..{head0}` is context only; report findings only on lines changed in the first "
    "range, unless a change there breaks code elsewhere in the full range."
)


def build_prompt(tid: str, rows: list[int], picked: dict, f: dict, files: list[str], kind: str) -> str:
    out = f"{f['run']}/{tid}.json"
    mb, head0 = f["mb"], f["head0"]
    parts = [SHARED_BLOCK.format(toplevel=f["toplevel"], out=out), ""]
    if kind == "diff":
        if files:
            pathspec = " ".join(shlex.quote(p) for p in files)
            parts.append(
                f"Read `git diff {mb}..{head0} -- {pathspec}` once. Then load each skill below and apply "
                "it to that diff in order. Reuse what you already read; open other files only as each "
                "skill directs, reading only the enclosing block needed to confirm a finding. You own "
                "findings on the files listed here; read any other file to confirm, but report only on these files."
            )
        else:
            parts.append(
                f"`git diff {mb}..{head0}` contains only machine-authored files (lockfiles, snapshots, "
                "generated or vendored output). Report zero findings for each row below, with a summary saying so."
            )
        parts.append("")
        for n in rows:
            m = picked[n]["mode"]
            if n == 2:
                line = f"- Row 2: `pr-review-toolkit` (mode: {m})"
                if f["mode"] == "delta" and m != "full":
                    line += ". " + DELTA_RULE.format(frm=f["from"], mb=mb, head0=head0)
            elif n == 3:
                line = "- Row 3: `ponytail-review`"
                if m == "lean":
                    line += ". " + LEAN_RULE.format(mb=mb, head0=head0)
            elif n == 4:
                line = f"- Row 4: `test-audit` (mode: {m})"
            else:
                line = f"- Row 6: `docs-audit` (mode: {m})"
            parts.append(line)
    elif kind == "ui":
        parts.append(
            f"Load `interface-review` (mode: `{picked[5]['mode']}`), target `{mb}...{head0}`. "
            f"UI files in scope: `{' '.join(files)}`."
        )
    else:
        n = rows[0]
        sk = picked[n]["skill"]
        if n == 3 and sk == "ponytail-review":
            parts.append("Load `ponytail-review` (mode: full) across all repo source files for a whole-repository pass.")
        else:
            parts.append(f"Load `{sk}` (mode: full) for a whole-repository pass.")
    parts += ["", CONTRACT.format(out=out, tid=tid)]
    return "\n".join(parts)


def build_tasks(picked: dict, f: dict) -> list[dict]:
    """picked: {row: {mode, tier, skill}} -> list of {id, rows, tier, files, prompt}."""
    tasks: list[dict] = []
    diff_rows = [n for n in (2, 3, 4, 6) if n in picked and picked[n]["mode"] != "full"]
    if diff_rows:
        tier = "strong" if any(picked[n]["tier"] == "strong" for n in diff_rows) else "fast"
        files = [p for p in f["changed"] if not EXCLUDE_RE.search(p)]
        shards = shard_files(files, f["file_lines"]) if files else [[]]
        for i, shard in enumerate(shards, 1):
            tid = "A" if len(shards) == 1 else f"A{i}"
            tasks.append({"id": tid, "rows": diff_rows, "tier": tier, "files": shard,
                          "prompt": build_prompt(tid, diff_rows, picked, f, shard, "diff")})
    if 5 in picked:
        tasks.append({"id": "I", "rows": [5], "tier": picked[5]["tier"], "files": f["ui_changed"],
                      "prompt": build_prompt("I", [5], picked, f, f["ui_changed"], "ui")})
    for n in (2, 3, 4, 6):
        if n in picked and picked[n]["mode"] == "full":
            tid = f"F{n}"
            tasks.append({"id": tid, "rows": [n], "tier": picked[n]["tier"], "files": [],
                          "prompt": build_prompt(tid, [n], picked, f, [], "full")})
    return tasks


def todo_list(picked: dict) -> list[str]:
    items = []
    last_review = max((n for n in picked if 2 <= n <= 6), default=None)
    for n in sorted(picked):
        items.append(f"Row {n}: {picked[n]['skill']}")
        if n == last_review:
            items.append("Fix review findings")
    items.append("Close: completion summary")
    return items


def _near(a, b) -> bool:
    try:
        return abs(int(a) - int(b)) <= 3
    except (TypeError, ValueError):
        return False


def merge_findings(plan: dict, reports: dict[str, dict]) -> dict[int, dict]:
    """Combine shards, filter, dedupe across rows, number. Returns {row: {...}}."""
    picked = {int(k): v for k, v in plan["picked"].items()}
    changed = set(plan.get("changed", []))
    rows: dict[int, dict] = {}
    for n in sorted(picked):
        if 2 <= n <= 6:
            rows[n] = {"skill": picked[n]["skill"], "tier": picked[n]["tier"], "summaries": [],
                       "findings": [], "incomplete": [], "excluded": 0, "notes": []}
    for t in plan["tasks"]:
        for rep in reports.get(t["id"], {}).get("reports", []):
            n = rep.get("row")
            if n not in rows:
                continue
            r = rows[n]
            if rep.get("summary"):
                r["summaries"].append(str(rep["summary"]))
            if rep.get("complete") is not True:
                r["incomplete"].append(t["id"])
            skill = rep.get("skill") or r["skill"]
            for fd in rep.get("findings", []):
                if isinstance(fd, dict):
                    r["findings"].append({**fd, "skill": skill})

    kept_all: list[tuple[int, dict]] = []
    for n in sorted(rows):
        r = rows[n]
        full = picked[n]["mode"] == "full"
        kept = []
        for fd in r["findings"]:
            sev = fd.get("severity", "important")
            keep = (
                sev in ("critical", "important")
                or (sev == "suggestion" and bool(fd.get("fix")))
                or (sev == "nit" and fd.get("rule") is not None)
                or sev not in SEVERITIES
            )
            if not keep:
                r["excluded"] += 1
                continue
            if full and fd.get("file") not in changed:
                fd["needs_decision"] = True
            dup = next(
                (k for kn, k in kept_all
                 if kn != n and k.get("file") == fd.get("file") and _near(k.get("line"), fd.get("line"))),
                None,
            )
            if dup is not None:
                also = dup.setdefault("_also", [])
                if fd["skill"] != dup["skill"] and fd["skill"] not in also:
                    also.append(fd["skill"])
                    dup["title"] = f"{dup.get('title', '')} (also: {fd['skill']})"
                continue
            kept.append(fd)
            kept_all.append((n, fd))
        for k, fd in enumerate(kept, 1):
            fd["id"] = f"{n}.{k}"
        r["findings"] = kept
        if r["incomplete"]:
            r["notes"].append(f"row {n} incomplete in {', '.join(r['incomplete'])}")
    return rows


def format_finding(fd: dict) -> str:
    loc = fd.get("file", "?") + (f":{fd['line']}" if fd.get("line") is not None else "")
    tag = f"{fd['tag']}: " if fd.get("tag") else ""
    lines = [f"{fd['id']} [{fd.get('severity', 'important')}] `{loc}` {tag}{fd.get('title', '')}"]
    if fd.get("why"):
        lines.append(f"   why: {fd['why']}")
    if fd.get("fix"):
        lines.append(f"   fix: {fd['fix']}")
    if fd.get("needs_decision"):
        lines.append("   DECISION")
    return "\n".join(lines)


def numstat(rng: str, top: str) -> list[tuple[int, int, str]]:
    recs = git("diff", "--numstat", "-z", rng, "--", ".", *LOCK_EXCLUDES, cwd=top).split("\0")
    out, i = [], 0
    while i < len(recs):
        r = recs[i]
        if not r:
            i += 1
            continue
        a, d, p = r.split("\t", 2)
        if p == "":
            p, i = recs[i + 2], i + 3
        else:
            i += 1
        out.append((0 if a == "-" else int(a), 0 if d == "-" else int(d), p))
    return out


def collect_facts(top: str, missing: list[str]) -> dict:
    notes: list[str] = []
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=top)
    is_protected = bool(PROTECTED_RE.fullmatch(branch))
    if is_protected:
        notes.append(f"on protected branch `{branch}`: reviewing unpushed commits; gate commits will land here")

    if not git_ok("fetch", "origin", "--prune", cwd=top):
        notes.append("fetch failed: using cached remote refs")
    try:
        base = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=top)
    except subprocess.CalledProcessError:
        base = "origin/main"
    if not git_ok("rev-parse", "--verify", "-q", base, cwd=top):
        base = "origin/master"
    if (
        branch != "dev"
        and git_ok("rev-parse", "--verify", "-q", "origin/dev", cwd=top)
        and git_ok("merge-base", "--is-ancestor", "origin/dev", "HEAD", cwd=top)
        and not git_ok("merge-base", "--is-ancestor", "origin/dev", git("merge-base", "HEAD", base, cwd=top), cwd=top)
    ):
        base = "origin/dev"
    mb = git("merge-base", "HEAD", base, cwd=top)
    head0 = git("rev-parse", "HEAD", cwd=top)
    wdir = wrap_dir(top)
    memo = wdir / branch
    last = memo.read_text().strip() if memo.exists() else ""
    frm, mode = mb, "full"
    if (
        last
        and git_ok("merge-base", "--is-ancestor", mb, last, cwd=top)
        and git_ok("merge-base", "--is-ancestor", last, head0, cwd=top)
    ):
        frm, mode = last, "delta"

    changed = git_z("diff", "--name-only", f"{mb}...{head0}", cwd=top)
    ns = numstat(f"{mb}...{head0}", top)
    added = sum(a for a, _, _ in ns)
    nondoc_added = sum(a for a, _, p in ns if not DOC_RE.search(p))
    file_lines = {p: a + d for a, d, p in ns}
    if mode == "delta":
        changed_row2 = git_z("diff", "--name-only", f"{frm}...{head0}", cwd=top)
        added_row2 = sum(a for a, _, _ in numstat(f"{frm}...{head0}", top))
    else:
        changed_row2, added_row2 = changed, added

    tracked = git_z("ls-files", cwd=top)
    status = git("status", "--short", cwd=top)
    uncommitted = len(status.splitlines())
    if uncommitted:
        notes.append(f"{uncommitted} uncommitted files: reviews below cover committed work only")

    me = git("config", "user.email", cwd=top) if git_ok("config", "user.email", cwd=top) else ""
    name = git("config", "user.name", cwd=top) if git_ok("config", "user.name", cwd=top) else ""
    others = 0
    if me:
        emails = set(git("log", "--format=%ae", "-n", "200", base, cwd=top).split())
        others = sum(
            1 for e in emails
            if e.lower() != me.lower()
            and not (name and f"+{name}@users.noreply".lower() in e.lower())
            and not re.search(r"\[bot\]|renovate|dependabot", e, re.I)
        )

    renovate = 0
    ls = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", "renovate/*", "dependabot/*"],
        cwd=top, capture_output=True, text=True,
    )
    if ls.returncode != 0:
        notes.append("renovate/dependabot check failed: ls-remote error")
    else:
        for line in ls.stdout.splitlines():
            b = line.split("\t", 1)[-1].removeprefix("refs/heads/") if "\t" in line else ""
            if b and not git_ok("merge-base", "--is-ancestor", f"origin/{b}", "HEAD", cwd=top):
                renovate += 1

    kit = Path(os.environ.get("MW_KIT") or Path.home() / ".cache" / "mw-kit")
    scope = None
    if (kit / "scripts" / "scope.py").exists():
        p = subprocess.run([sys.executable, str(kit / "scripts" / "scope.py"), top], capture_output=True, text=True)
        try:
            if p.returncode != 0:
                raise ValueError
            scope = json.loads(p.stdout)
        except ValueError:
            err = (p.stderr.splitlines() or ["bad output"])[0]
            scope = {"preflight": {"ok": False, "error": f"scope.py failed: {err}"}}

    skills_dir = Path(__file__).resolve().parents[2]
    inst = [
        s for s in [*ROW_SKILL.values(), "ponytail-audit"]
        if s not in missing and (s in EXTERNAL or (skills_dir / s / "SKILL.md").exists())
    ]

    facts = {
        "toplevel": top, "run": str(wdir / "run"), "branch": branch, "protected": is_protected,
        "base": base, "mb": mb, "head0": head0, "from": frm, "mode": mode, "last": last,
        "changed": changed, "changed_row2": changed_row2, "added": added, "added_row2": added_row2,
        "nondoc_added": nondoc_added, "file_lines": file_lines,
        "test_changed": [p for p in changed if TEST_RE.search(p)],
        "doc_changed": [p for p in changed if DOC_RE.search(p)],
        "ui_changed": [p for p in changed if UI_RE.search(p)],
        "manifests_changed": [p for p in changed if p.rsplit("/", 1)[-1] in MANIFESTS or REQ_RE.search(p.rsplit("/", 1)[-1])],
        "repo_has_tests": any(TEST_RE.search(p) for p in tracked),
        "repo_has_ui": any(UI_RE.search(p) for p in tracked),
        "baseline": status, "uncommitted": uncommitted, "others": others, "renovate": renovate,
        "scope": scope, "installed": inst, "notes": notes,
    }
    facts["verdicts"] = verdicts(facts)
    return facts


def save_preflight(facts: dict) -> None:
    run = Path(facts["run"])
    run.mkdir(parents=True, exist_ok=True)
    (run / "preflight.json").write_text(json.dumps(facts, indent=1))


def render_report(f: dict) -> str:
    out = [f"> {n}" for n in f["notes"]]
    if out:
        out.append("")
    out += ["| # | Skill | Verdict | Tier | Why |", "|---|---|---|---|---|"]
    for v in f["verdicts"]:
        out.append(f"| {v['row']} | `{v['skill']}` | {v['verdict']} | {v['tier']} | {v['why']} |")
    out += [
        "",
        "- Legend: `fast`/`strong` = runs as a subagent on that model class (Harness notes). `inline` = runs "
        "in this session because it prompts you; the tier is the recommended strength for this session.",
        f"- Parallelism: Row 1 runs first, inline, and stops at Gate A if it changed files. Then one parallel "
        f"wave, pinned to `{short(f['head0'])}`: rows 2, 3, 4 and 6 share one diff pass (sharded by directory "
        "on large diffs), and rows 5 and any full-mode row run as their own reviewers. Gate F walks findings "
        "one row at a time, with a commit gate after each row that changes files. Row 7 runs last, inline.",
        "- Always: Pre-flight is cheap. To run the picks on a stronger model, start a new session there and "
        "invoke wrap-up with `run <your reply>`.",
    ]
    if f["others"] >= 1:
        out.append(
            f"- Lean suggested: {f['others']} other authors on `{f['base']}`. Add `lean` to your reply to limit "
            "changes to definite improvements. Your choice; it's off unless you type it."
        )
    out += [
        "",
        "Reply `go` to run the RUN rows, numbers to choose from 1 and 3–7 (e.g. `3 4 7`), or `none` for only "
        "row 2. Override a tier with `N@fast|strong` (rows 2–6) or a scope mode with `default`, `lean`, "
        "`full`, or `N@default|lean|full` (e.g. `go default`, `go lean`, `go full`, `go 4@full`, `2@full:strong`).",
    ]
    return "\n".join(out)


def toplevel() -> str:
    try:
        return git("rev-parse", "--show-toplevel")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("not a git repo", file=sys.stderr)
        raise SystemExit(1)


def cmd_preflight(a: argparse.Namespace) -> int:
    facts = collect_facts(toplevel(), a.missing)
    save_preflight(facts)
    print(render_report(facts))
    return 0


def wrap_dir(top: str) -> Path:
    return Path(top) / git("rev-parse", "--git-path", "wrap-up", cwd=top)


def load_facts(top: str, missing: list[str]) -> dict:
    p = wrap_dir(top) / "run" / "preflight.json"
    if p.exists():
        try:
            f = json.loads(p.read_text())
            memo = Path(f["run"]).parent / f["branch"]
            last = memo.read_text().strip() if memo.exists() else ""
            if f["head0"] == git("rev-parse", "HEAD", cwd=top) and f["last"] == last and not (
                set(missing) & set(f["installed"])
            ):
                return f
        except (ValueError, KeyError, OSError):
            pass
    f = collect_facts(top, missing)
    save_preflight(f)
    return f


def cmd_plan(a: argparse.Namespace) -> int:
    top = toplevel()
    f = load_facts(top, a.missing)
    try:
        res = parse_reply(" ".join(a.reply), f["verdicts"], f)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    picked = res["rows"]
    tasks = build_tasks(picked, f)
    run = Path(f["run"])
    for old in run.glob("*.json"):
        if old.name != "preflight.json":
            old.unlink()
    plan = {
        k: f[k] for k in ("head0", "mb", "from", "mode", "base", "branch", "baseline", "changed", "run", "toplevel")
    }
    plan["picked"] = {str(n): {**v, "row": n} for n, v in picked.items()}
    plan["tasks"] = tasks
    (run / "plan.json").write_text(json.dumps(plan, indent=1))
    print(json.dumps({
        "picked": [{"row": n, "skill": v["skill"], "mode": v["mode"], "tier": v["tier"]} for n, v in picked.items()],
        "notes": res["notes"],
        "inline_before": [1] if 1 in picked else [],
        "tasks": [{"id": t["id"], "rows": t["rows"], "tier": t["tier"], "files_count": len(t["files"])} for t in tasks],
        "inline_after": [7] if 7 in picked else [],
        "todo": todo_list(picked),
    }, ensure_ascii=False))
    return 0


def load_plan() -> dict:
    top = toplevel()
    try:
        return json.loads((wrap_dir(top) / "run" / "plan.json").read_text())
    except (OSError, ValueError):
        print("no plan: run `wrap_up.py plan \"<reply>\"` first", file=sys.stderr)
        raise SystemExit(2)


def cmd_prompt(a: argparse.Namespace) -> int:
    for t in load_plan()["tasks"]:
        if t["id"] == a.task:
            print(t["prompt"])
            return 0
    print(f"no task {a.task}", file=sys.stderr)
    return 2


def read_reports(plan: dict) -> tuple[dict[str, dict], list[str]]:
    reports: dict[str, dict] = {}
    bad: list[str] = []
    for t in plan["tasks"]:
        try:
            d = json.loads((Path(plan["run"]) / f"{t['id']}.json").read_text())
            if not isinstance(d, dict) or not isinstance(d.get("reports"), list):
                raise ValueError
            have = {r.get("row") for r in d["reports"] if isinstance(r, dict)}
            if not set(t["rows"]) <= have:
                raise ValueError
            d["reports"] = [r for r in d["reports"] if isinstance(r, dict)]
            reports[t["id"]] = d
        except (OSError, ValueError):
            bad.append(f"missing: {t['id']} (rows {', '.join(map(str, t['rows']))}); rerun with: wrap_up.py prompt {t['id']}")
    return reports, bad


def cmd_findings(a: argparse.Namespace) -> int:
    plan = load_plan()
    reports, bad = read_reports(plan)
    if bad:
        print("\n".join(bad))
        return 1
    rows = merge_findings(plan, reports)
    if a.row is None:
        for n, r in rows.items():
            dec = sum(1 for fd in r["findings"] if fd.get("needs_decision"))
            print(f"row {n} {r['skill']}: {len(r['findings'])} findings ({dec} need decision, {r['excluded']} excluded)")
        for r in rows.values():
            for note in r["notes"]:
                print(f"note: {note}")
        return 0
    r = rows.get(a.row)
    if r is None:
        print(f"row {a.row} not picked", file=sys.stderr)
        return 2
    if not r["findings"]:
        print(f"### Gate F: {r['skill']}\nno findings to fix")
        return 0
    print(f"### {r['skill']} ({r['tier']})")
    if r["summaries"]:
        print(" | ".join(r["summaries"]))
    for note in r["notes"]:
        print(f"note: {note}")
    print()
    for fd in r["findings"]:
        print(format_finding(fd))
    print(f"\ncommit: {COMMIT_SUBJECT[a.row]}")
    return 0


def cmd_memo(a: argparse.Namespace) -> int:
    plan = load_plan()
    if "2" not in plan["picked"]:
        print("row 2 not picked; memo unchanged")
        return 0
    for t in plan["tasks"]:
        if 2 not in t["rows"]:
            continue
        try:
            d = json.loads((Path(plan["run"]) / f"{t['id']}.json").read_text())
            rep = next(r for r in d["reports"] if r.get("row") == 2)
            ok = rep.get("complete") is True
        except (OSError, ValueError, KeyError, StopIteration, TypeError):
            ok = False
        if not ok:
            print(f"row 2 incomplete in {t['id']}; memo not written")
            return 1
    memo = Path(plan["run"]).parent / plan["branch"]
    memo.parent.mkdir(parents=True, exist_ok=True)
    memo.write_text(plan["head0"] + "\n")
    print(f"memo: {plan['branch']} -> {short(plan['head0'])}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("preflight", cmd_preflight), ("plan", cmd_plan)):
        p = sub.add_parser(name)
        p.add_argument("--missing", action="append", default=[], metavar="NAME")
        if name == "plan":
            p.add_argument("reply", nargs="+")
        p.set_defaults(fn=fn)
    p = sub.add_parser("prompt")
    p.add_argument("task")
    p.set_defaults(fn=cmd_prompt)
    p = sub.add_parser("findings")
    p.add_argument("--row", type=int)
    p.set_defaults(fn=cmd_findings)
    p = sub.add_parser("memo")
    p.set_defaults(fn=cmd_memo)
    a = ap.parse_args()
    try:
        return a.fn(a)
    except subprocess.CalledProcessError as e:
        print(f"git {' '.join(e.cmd[1:])} failed: {(e.stderr or '').strip()}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
