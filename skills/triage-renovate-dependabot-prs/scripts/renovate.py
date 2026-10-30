#!/usr/bin/env python3
"""Pre-flight and per-branch discovery for the triage-renovate-dependabot-prs skill.

Usage: renovate.py [--allow-protected]
Run inside the repo; prints one JSON object. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROTECTED_RE = re.compile(r"main|master|dev|develop|release/.*|staging")
ECOSYSTEMS = [
    ("package-lock.json", "npm", "npm"), ("pnpm-lock.yaml", "pnpm", "pnpm"),
    ("yarn.lock", "yarn", "yarn"), ("uv.lock", "uv", "uv"),
    ("poetry.lock", "poetry", "poetry"), ("Cargo.toml", "cargo", "cargo"),
    ("go.mod", "go", "go"), ("Gemfile", "bundler", "bundle"),
    ("pom.xml", "maven", "mvn"), ("composer.json", "composer", "composer"),
    ("mix.exs", "mix", "mix"),
]
JS_LOCKS = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
MANIFESTS = [
    "package.json", "composer.json", "pyproject.toml", "requirements*.txt", "Pipfile",
    "Cargo.toml", "go.mod", "Gemfile", "build.gradle*", "mix.exs", "Dockerfile*",
    "docker-compose.*", "Containerfile", ".gitlab-ci.yml", ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
]
LOCKFILES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock", "poetry.lock", "Cargo.lock",
    "go.sum", "Gemfile.lock", "composer.lock", "mix.lock", "gradle.lockfile", "Pipfile.lock",
}
ONBOARDING_FILES = {
    "renovate.json", "renovate.json5", ".renovaterc", ".renovaterc.json",
    "dependabot.yml", "dependabot.yaml",
}
INFRA_RE = re.compile(
    r"(^|/)(\.gitlab-ci\.yml|\.github/workflows/[^/]+\.ya?ml|Dockerfile[^/]*|docker-compose\.[^/]+|Containerfile)$"
)
BUILD_RE = re.compile(
    r"(^|/)(tsconfig[^/]*\.json|vite\.config\.[^/]+|webpack\.config\.[^/]+|eslint\.config\.[^/]+"
    r"|biome\.jsonc?|\.golangci\.ya?ml)$"
)
URL_RE = re.compile(r"https?://\S+")
CONFLICT_RE = re.compile(r"CONFLICT \(([^)]+)\)")
VERSION_RE = re.compile(r"\d+(?:\.\d+)*")
REQ_FILE_RE = re.compile(r"requirements.*\.txt$")

DEP_RES = [
    (None, re.compile(r'^\s*"([^"]+)"\s*:\s*"([^"]*)"')),
    (None, re.compile(r'^\s*"([A-Za-z0-9_.\[\]-]+)\s*([<>=!~^][^"]*)"')),
    (None, re.compile(r'^\s*([A-Za-z0-9_.-]+)\s*=\s*(?:\{[^}]*?version\s*=\s*)?"([^"]+)"')),
    ("req", re.compile(r"^([A-Za-z0-9_.\[\]-]+)\s*([<>=!~]=?\s*\S+)")),
    ("gomod", re.compile(r"^\s*(?:require\s+)?([\w.\-]+\.[\w.\-/]+)\s+(v\S+)")),
    (
        "docker",
        re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?([^\s:@]+)((?::[^\s@]+)?(?:@sha256:[0-9a-f]+)?)"),
    ),
    (None, re.compile(r"""^\s*-?\s*image:\s*["']?([^\s:@"']+)[:@]([^\s"']+)""")),
    (None, re.compile(r"^\s*-?\s*component:\s*(\S+)@(\S+)")),
    (None, re.compile(r"""^\s*-?\s*uses:\s*["']?([\w.\-]+/[\w.\-/]+)@([^\s#"']+)""")),
    (None, re.compile(r"""^\s*gem\s+["']([^"']+)["']\s*,\s*["']([^"']+)""")),
    (None, re.compile(r'\{:(\w+),\s*"([^"]+)"')),
    (None, re.compile(r"""["']([\w.\-]+:[\w.\-]+):([^"'$]+)["']""")),
]


def git(*args: str, cwd: str | Path | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.rstrip("\n")


def git_ok(*args: str, cwd: str | Path | None = None) -> bool:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True
    ).returncode == 0


def parse_dep_line(path: str, line: str):
    base = os.path.basename(path)
    for gate, rx in DEP_RES:
        if gate == "req" and not (REQ_FILE_RE.match(base) or base == "Pipfile"):
            continue
        if gate == "gomod" and base != "go.mod":
            continue
        m = rx.search(line)
        if not m:
            continue
        spec = m.group(2)
        if gate == "docker":
            spec = spec.lstrip(":")
        return m.group(1), spec
    return None


def bump(old: str, new: str) -> str:
    if "sha256:" in old and "sha256:" in new and old.split("@")[0] == new.split("@")[0]:
        return "digest"
    mo, mn = VERSION_RE.search(old), VERSION_RE.search(new)
    if not mo or not mn:
        return "unknown"
    a = [int(x) for x in mo.group().split(".")][:3]
    b = [int(x) for x in mn.group().split(".")][:3]
    a += [0] * (3 - len(a))
    b += [0] * (3 - len(b))
    if a[0] != b[0] or (a[0] == 0 and b[0] == 0 and a[1] != b[1]):
        return "major"
    if a[1] != b[1]:
        return "minor"
    return "patch"


# ponytail: line-regex heuristic; "unknown" bumps send the model to the diff
def dep_changes(diff_text: str) -> list[dict]:
    per: dict[str, tuple[dict, dict]] = {}
    path = None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
            if path is not None:
                per.setdefault(path, ({}, {}))
        elif line.startswith("--- ") or not line or line[0] not in "+-" or path is None:
            continue
        else:
            dep = parse_dep_line(path, line[1:])
            if dep:
                per[path][0 if line[0] == "-" else 1][dep[0]] = dep[1]
    out = []
    for file, (old, new) in per.items():
        for name, spec in new.items():
            if name not in old:
                out.append({"file": file, "name": name, "old": None, "new": spec, "bump": "added"})
            elif old[name] != spec:
                out.append({"file": file, "name": name, "old": old[name], "new": spec,
                            "bump": bump(old[name], spec)})
        for name, spec in old.items():
            if name not in new:
                out.append({"file": file, "name": name, "old": spec, "new": None, "bump": "removed"})
    return out


def redundancy(changes: list[dict], head_texts: dict[str, str]):
    real = [c for c in changes if c["bump"] not in ("added", "removed")]
    if not real:
        return None
    satisfied = in_head = 0
    for c in real:
        text = head_texts.get(c["file"], "")
        in_head += c["name"] in text
        satisfied += any(c["name"] in ln and c["new"] in ln for ln in text.splitlines())
    if satisfied == len(real):
        return "payload already in HEAD"
    if in_head == 0:
        return "target dep no longer exists in HEAD"
    return None


def manifest_specs() -> list[str]:
    return [f":(glob)**/{m}" for m in MANIFESTS]


def detect_ecosystems(top: Path):
    has = lambda f: (top / f).exists()
    eco = [(e, t) for f, e, t in ECOSYSTEMS if has(f)]
    if has("package.json") and not any(has(f) for f in JS_LOCKS):
        eco.append(("npm", "npm"))
    if any(top.glob("build.gradle*")):
        eco.append(("gradle", None))
    if has("pyproject.toml") and not has("uv.lock") and not has("poetry.lock"):
        eco.append(("python", None))
    missing = sorted({t for _, t in eco if t and shutil.which(t) is None})
    return [e for e, _ in eco], missing


def predict_conflicts(top: str, r: str, notes: list[str]):
    p = subprocess.run(
        ["git", "merge-tree", "--write-tree", "--name-only", "HEAD", r],
        cwd=top, capture_output=True, text=True,
    )
    if p.returncode == 0:
        return []
    if p.returncode != 1:
        first = (p.stderr.strip().splitlines() or [""])[0]
        notes.append(f"merge-tree failed: {first}")
        return None
    lines = p.stdout.splitlines()[1:]
    files: list[str] = []
    rest = len(lines)
    for i, ln in enumerate(lines):
        if not ln:
            rest = i + 1
            break
        files.append(ln)
    types = sorted({m.group(1) for ln in lines[rest:] for m in [CONFLICT_RE.search(ln)] if m})
    return {"files": files, "types": types}


def branch_entry(top: str, b: str, notes: list[str]) -> dict:
    r = f"origin/{b}"
    subject = git("log", "-1", "--format=%s", r, cwd=top)
    body = git("log", "-1", "--format=%b", r, cwd=top)
    urls = []
    for u in URL_RE.findall(body):
        u = u.rstrip(")>.,")
        if u not in urls:
            urls.append(u)
    fork = git("log", "-1", "--format=%h %s (%cr)", git("merge-base", "HEAD", r, cwd=top), cwd=top)
    files = [f for f in git("diff", "--name-only", "-z", f"HEAD...{r}", cwd=top).split("\0") if f]
    added = deleted = 0
    for ln in git("diff", "--numstat", f"HEAD...{r}", cwd=top).splitlines():
        a, d, _ = ln.split("\t", 2)
        added += int(a) if a.isdigit() else 0
        deleted += int(d) if d.isdigit() else 0
    changes = dep_changes(
        git("diff", "-U0", "--no-color", f"HEAD...{r}", "--", *manifest_specs(), cwd=top)
    )
    head_texts = {}
    for f in {c["file"] for c in changes}:
        p = subprocess.run(["git", "show", f"HEAD:{f}"], cwd=top, capture_output=True, text=True)
        head_texts[f] = p.stdout if p.returncode == 0 else ""
    bases = [os.path.basename(f) for f in files]
    return {
        "branch": b,
        "subject": subject,
        "urls": urls[:10],
        "fork": fork,
        "files": files,
        "added": added,
        "deleted": deleted,
        "changes": changes,
        "lockfile_only": bool(files) and all(x in LOCKFILES for x in bases),
        "touches_infra": any(INFRA_RE.search(f) for f in files),
        "touches_build_config": any(BUILD_RE.search(f) for f in files),
        "onboarding": b == "renovate/configure" or (bool(bases) and all(x in ONBOARDING_FILES for x in bases)),
        "conflicts": predict_conflicts(top, r, notes),
        "small_diff": added + deleted < 200,
        "redundant": redundancy(changes, head_texts),
    }


def run(allow_protected: bool) -> int:
    try:
        top = git("rev-parse", "--show-toplevel")
    except subprocess.CalledProcessError:
        print("not a git repo", file=sys.stderr)
        return 1
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=top)
    if PROTECTED_RE.fullmatch(branch) and not allow_protected:
        print(
            f"protected branch `{branch}`: triage needs a feature branch as a buffer; "
            "switch branches or rerun with --allow-protected",
            file=sys.stderr,
        )
        return 3
    target_hint = next(
        (x for x in ("dev", "main") if x != branch and git_ok("rev-parse", "--verify", "-q", f"refs/heads/{x}", cwd=top)),
        None,
    )
    notes: list[str] = []
    if not git_ok("fetch", "origin", "--prune", cwd=top):
        notes.append("fetch failed: using cached remote refs")
    ecosystems, missing_tools = detect_ecosystems(Path(top))

    ls = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", "renovate/*", "dependabot/*"],
        cwd=top, capture_output=True, text=True,
    )
    if ls.returncode != 0:
        print(f"ls-remote failed: {(ls.stderr.strip().splitlines() or [''])[0]}", file=sys.stderr)
        return 1
    names = [ln.split("\t")[1].replace("refs/heads/", "", 1) for ln in ls.stdout.splitlines() if "\t" in ln]
    merged: list[str] = []
    branches: list[dict] = []
    for b in names:
        r = f"origin/{b}"
        if not git_ok("rev-parse", "--verify", "-q", r, cwd=top):
            branches.append({"branch": b, "error": "remote ref missing locally"})
        elif git_ok("merge-base", "--is-ancestor", r, "HEAD", cwd=top):
            merged.append(b)
        else:
            branches.append(branch_entry(top, b, notes))

    drift: list[str] = []
    if target_hint and git_ok("rev-parse", "--verify", "-q", f"origin/{target_hint}", cwd=top):
        out = git(
            "log", "--oneline", f"origin/{target_hint}..HEAD", "--",
            *manifest_specs(), *(f":(glob)**/{x}" for x in sorted(LOCKFILES)), cwd=top,
        )
        drift = out.splitlines()

    print(json.dumps({
        "branch": branch, "target_hint": target_hint, "notes": notes, "ecosystems": ecosystems,
        "missing_tools": missing_tools, "merged": merged, "branches": branches, "drift": drift,
    }, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--allow-protected", action="store_true")
    args = ap.parse_args()
    try:
        return run(args.allow_protected)
    except subprocess.CalledProcessError as e:
        cmd = " ".join(e.cmd) if isinstance(e.cmd, list) else str(e.cmd)
        print(f"{cmd} failed: {(e.stderr or '').strip()}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
