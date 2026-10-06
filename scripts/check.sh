#!/usr/bin/env bash
# Validates tracked JSON and SKILL.md frontmatter (name matches dir, description present).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

git ls-files -z '*.json' | xargs -0 jq empty

fail=0
while IFS= read -r f; do
  fm=$(awk 'NR==1 && $0!="---" {exit} NR>1 && $0=="---" {exit} NR>1' "$f")
  dir=$(basename "$(dirname "$f")")
  grep -qx "name: $dir" <<<"$fm" || { echo "$f: frontmatter name must be '$dir'"; fail=1; }
  grep -q '^description:' <<<"$fm" || { echo "$f: frontmatter missing description"; fail=1; }
done < <(git ls-files '*/SKILL.md')
exit "$fail"
