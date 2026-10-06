---
name: fix-trivy-scan
description: >
  Fix failing Trivy CI jobs (trivy fs / trivy image scans) in any repo and
  ecosystem. First bumps every trivy pin to the latest release, then sorts each
  HIGH/CRITICAL finding: lockfile dependency bump (uv, npm, pnpm, yarn, poetry,
  cargo, go, bundler), base-image tag/digest bump for OS packages, misconfig
  fix, or an expiring suppression in the ignore file when no fix exists.
  Verifies locally with CI's exact command and trivy version. Never commits.
  Trigger: "trivy failed", "fix trivy", "trivy-scan failed",
  "trivy-image-scan failed", "upgrade trivy", or /fix-trivy-scan.
---

# Fix Trivy scan failures

Get the repo's Trivy CI jobs back to green with the smallest correct change. Trivy pins go stale and new CVEs land every week, so treat every run as two jobs: bring trivy up to date, then clear the findings.

## Pre-flight

1. Confirm CWD is a git repo. Find every trivy invocation and pin:
   ```bash
   git grep -nE 'trivy|aquasec' -- '*.yml' '*.yaml' Makefile '*.mk' '*.sh' Dockerfile* .trivyignore*
   ```
   Note each job's exact command: subcommand (`fs`/`image`/`config`), `--scanners`, `--severity`, `--ignorefile`, `--exit-code`, and target. Local verification replays these commands verbatim.
2. Get the failing job logs. Use the job IDs the user gave you, or the latest failed pipeline on the current branch:
   - GitLab: `glab api "projects/:id/pipelines/<pipeline_id>/jobs?per_page=100" | jq -r '.[] | select(.status=="failed") | "\(.id) \(.name)"'`, then `glab api "projects/:id/jobs/<job_id>/trace"`. `glab ci view` needs a TTY, so don't use it.
   - GitHub: `gh run list --branch "$(git branch --show-current)" --limit 5`, then `gh run view <run_id> --log-failed`.
   Don't read the raw log. Image-job summaries list every scanned file and can run to hundreds of KB. Save each log to a temp file and filter it:
   ```bash
   grep -E -B2 'Total: [1-9]|Failures: [1-9]|FATAL|ERROR' job.log   # each target with findings, with its Type
   grep -E 'Version: |(CVE|GHSA)-[0-9]+-[0-9]+ ' job.log            # trivy version + finding rows
   ```
   If a target shows a non-zero count that the rows don't explain (a misconfig or secret), read only that target's section.
3. If the log has no findings table and fails before scanning (registry auth, image pull, DB download), it's an infrastructure failure, not something this skill fixes. Report the error line and stop.

## Step 1 — Bring trivy up to date

1. Get the latest release: `gh api repos/aquasecurity/trivy/releases/latest --jq .tag_name` (strip the leading `v`).
2. If any pin is older, bump **every** pin in the repo to that version in one go: CI image tags, `trivy-action@` refs, version vars in Makefiles and scripts. Keep each pin's registry. If the image pull failed on `aquasec/trivy` (Docker Hub rate limit), switch it to `ghcr.io/aquasecurity/trivy`.
3. Read the release notes between the old and new versions (`gh release view v<new> -R aquasecurity/trivy`) for flag renames or removals that affect the commands from pre-flight. Update those commands if needed.
4. A stale pin alone causes failures such as DB schema or checks-bundle incompatibility, or `FATAL` lines asking you to update. If that was the only failure, go to Step 3.

## Step 2 — Clear each finding

Group findings by package. The same CVE often shows up in both jobs, once from the lockfile (`fs`) and once from the installed copy inside the image (`image`, targets like `app/.venv/.../METADATA` or `node_modules/.../package.json`). One lockfile fix clears both.

Classify by the target **Type** column:

| Type | Fix |
|---|---|
| Lockfile or language package (`uv`, `pip`, `poetry`, `python-pkg`, `npm`, `pnpm`, `yarn`, `node-pkg`, `cargo`, `gomod`, `gobinary`, `bundler`, `gemspec`) | Lockfile bump (2a) |
| OS distro (`alpine`, `wolfi`, `debian`, `ubuntu`, `redhat`, `chainguard`, …) | Base-image bump (2b) |
| Misconfiguration (`dockerfile`, `kubernetes`, `terraform`, `cloudformation`, …) with a non-zero count | Fix the file per the check's AVD link |
| Secret | **Stop and tell the user.** A real secret needs rotating first. Suppress only a confirmed false positive (2c) |
| No Fixed Version, or Status `affected`/`will_not_fix`/`fix_deferred` | Suppression (2c) |

### 2a. Lockfile bump

Bump only the vulnerable package to at least the Fixed Version with the ecosystem's single-package lockfile upgrade (e.g. `uv lock --upgrade-package <pkg>`), and use its why/tree command (e.g. `uv tree --invert --package <pkg>`) to find what pins it.

- Confirm the lockfile now holds a version ≥ Fixed Version. If the resolver held it back, a parent pins it (common for sibling packages released in lockstep, like `gcsfs` → `fsspec`). Upgrade the parent in the same command (`uv lock --upgrade-package <parent> --upgrade-package <pkg>`, and likewise for other tools). Use an override (`[tool.uv] override-dependencies`, npm `overrides`, pnpm `pnpm.overrides`, yarn `resolutions`) only if no parent release allows the fixed version, and only after the user confirms.
- Don't raise the manifest floor (`pyproject.toml`, `package.json`) unless resolution needs it. The lockfile pin is enough.
- If the bump crosses a major version, **ask before applying**. Show the changelog breaking-change notes and the repo's call sites (`git grep -n <import name>`).
- Run the repo's test command afterward (Makefile `test` target, `uv run pytest`, `npm test`, `cargo test`, `go test ./...`).

### 2b. Base-image bump

1. Find the `FROM` line that provides the vulnerable OS package. In a multi-stage build, only the final stage matters for `trivy image`.
2. Find the newest image for the same tag: `crane digest <image>:<tag>` (or `docker buildx imagetools inspect <image>:<tag>`). Pinned by digest → replace the digest and keep the tag. Pinned by tag → move to the newest patch tag on the same line (e.g. `3.14.4-alpine` → `3.14.5-alpine`). Never change the distro or major line without asking.
3. Update every `FROM` that references the same image.
4. If even the newest base still ships the vulnerable package and the distro has a fixed build, add an upgrade step for just that package in the final stage (`apk add --no-cache --upgrade <pkg>`, or `apt-get install -y --only-upgrade <pkg>`). If the distro has no fixed build, go to 2c.

### 2c. Suppression

Use this only when there is no fix, or for a confirmed false positive. **Get the user's OK for each entry**, then add it to the ignore file the job passes via `--ignorefile` (default `.trivyignore`), in that file's existing format, with a reason and an expiry of today + 30 days.

Always set an expiry. It forces a re-check once a fix ships.

## Step 3 — Verify locally with CI's exact command

Use the same trivy version as the CI pin. Check `trivy --version`. If it differs, run the container instead (`docker run --rm -v "$PWD:/src" -w /src ghcr.io/aquasecurity/trivy:<ver> <args>`), or `brew upgrade trivy` if the user agrees.

- **fs job:** scan a copy of only the git-tracked files, since untracked local files (build output, stray poms) cause scans and network calls that CI never makes. A new lockfile must be staged (`git add -N`) to be included:
  ```bash
  tmp=$(mktemp -d) && git ls-files -z | tar --null -T - -cf - | tar xf - -C "$tmp"
  (cd "$tmp" && trivy fs <CI flags verbatim> .); echo "exit=$?"; rm -rf "$tmp"
  ```
- **image job:** skip the build when every image finding is a language package (`python-pkg`, `node-pkg`, `gobinary`, …) that the fs job also reported, and the Dockerfile installs from the lockfile (`uv sync --frozen`, `npm ci`, `poetry install`, …). In that case the green fs scan already shows the image's copy is fixed. Build and scan the image only for OS findings, image-only findings, or a Dockerfile that installs outside the lockfile:
  ```bash
  docker build --platform linux/amd64 -t trivy-smoke:local .
  docker save trivy-smoke:local -o /tmp/trivy-smoke.tar
  trivy image --input /tmp/trivy-smoke.tar <CI flags verbatim>; echo "exit=$?"; rm -f /tmp/trivy-smoke.tar
  ```
  Use `--input`: `trivy image <tag>` can't read images from containerd-backed Docker (colima, Docker Desktop's containerd store). On Apple silicon the amd64 build runs under QEMU and is slow. If Docker isn't available, say the image job wasn't verified locally, and why.

Done when every replayed command exits 0. If one still fails, go back to Step 2 for the remaining findings.

## Report

Don't commit or push.
