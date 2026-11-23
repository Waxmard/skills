#!/usr/bin/env bash
# Validates tracked JSON, runs tracked test_*.py, and checks SKILL.md frontmatter (name matches dir, description present).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

git ls-files -z '*.json' | xargs -0 jq empty
git ls-files -z '*/test_*.py' | xargs -0 -n1 python3 -B

fail=0
while IFS= read -r f; do
  fm=$(awk 'NR==1 && $0!="---" {exit} NR>1 && $0=="---" {exit} NR>1' "$f")
  dir=$(basename "$(dirname "$f")")
  grep -qx "name: $dir" <<<"$fm" || { echo "$f: frontmatter name must be '$dir'"; fail=1; }
  grep -q '^description:' <<<"$fm" || { echo "$f: frontmatter missing description"; fail=1; }
done < <(git ls-files '*/SKILL.md')

python3 -B - <<'PY' || fail=1
import importlib.util
import json
import os
import re
import subprocess
import sys

tracked_files = sorted(
    subprocess.check_output(["git", "ls-files", "skills/*/SKILL.md"], text=True).splitlines()
)
tracked_names = {p.split("/")[1] for p in tracked_files}
errors = []

with open("README.md", encoding="utf-8") as fh:
    readme = fh.read()
m = re.search(r"(?ms)^## Skills\n(.*?)(?=^## |\Z)", readme)
if not m:
    errors.append("README.md: missing '## Skills' section")
else:
    readme_names = set(re.findall(r"(?m)^\|\s*`([^`]+)`\s*\|", m.group(1)))
    for name in sorted(tracked_names - readme_names):
        errors.append(f"README.md: missing '## Skills' row for tracked skill '{name}'")
    for name in sorted(readme_names - tracked_names):
        errors.append(f"README.md: '## Skills' row '{name}' has no tracked skills/{name}/SKILL.md")

for path in tracked_files:
    with open(path, encoding="utf-8") as fh:
        body = fh.read()
    if re.search(r"(?m)^```(?:bash|sh)\b", body) and not re.search(
        r"(?m)^## Prerequisites & Required Tools$", body
    ):
        errors.append(f"{path}: has bash/sh code block but is missing '## Prerequisites & Required Tools' heading")

spec = importlib.util.spec_from_file_location("wrap_up", "skills/wrap-up/scripts/wrap_up.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
for name in sorted((set(mod.ROW_SKILL.values()) - set(mod.EXTERNAL)) - tracked_names):
    errors.append(f"skills/wrap-up/scripts/wrap_up.py: ROW_SKILL references unknown skill '{name}'")

with open("scripts/skill-budgets.json", encoding="utf-8") as fh:
    budgets = json.load(fh)
tracked_set = set(tracked_files)
budget_keys = set(budgets.keys())
for path in sorted(tracked_set - budget_keys):
    errors.append(f"scripts/skill-budgets.json: missing budget entry for '{path}'")
for path in sorted(budget_keys - tracked_set):
    errors.append(f"scripts/skill-budgets.json: stale budget entry for '{path}'")
for path in sorted(tracked_set & budget_keys):
    actual = os.path.getsize(path)
    cap = budgets[path]
    if actual > cap:
        errors.append(
            f"{path}: {actual} bytes exceeds budget {cap} in scripts/skill-budgets.json; trim the skill or raise its cap deliberately"
        )

if errors:
    for err in errors:
        print(err, file=sys.stderr)
    sys.exit(1)
PY
exit "$fail"
