---
name: fix-security-scan
description: >
  Use when Semgrep, Trivy, or CI security scans (SAST, vulnerability,
  container, or filesystem) fail, or to remediate SAST/CVE findings and upgrade
  Semgrep or Trivy pins. Bumps Semgrep and Trivy to latest, resolves SAST rules
  and HIGH/CRITICAL/MEDIUM CVEs via code fixes, lockfile or base-image bumps,
  misconfig fixes, or scoped suppressions (# nosemgrep / expiring .trivyignore),
  and verifies locally; never commits. Trigger: "security scan failed",
  "semgrep failed", "fix semgrep", "trivy failed", "fix trivy", "CI security
  scan failed", "container scan failed", "fix CVEs", or /fix-security-scan.
---

# Fix security scan failures

Get the repo's Semgrep and Trivy CI jobs back to green with the smallest correct change: bring scanner pins up to date, clear the findings, and verify locally.

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- `git`
- `gh`, logged in (Step 1 looks up Semgrep and Trivy releases with `gh api`, on any forge; GitHub repos also read run logs with it)
- `glab`, logged in, and `jq`, for GitLab CI logs
- `semgrep`, for repos with Semgrep jobs (or `docker` to run the pinned `semgrep/semgrep` image)
- `trivy` at the CI-pinned version, or `docker` to run the pinned trivy image, for repos with Trivy jobs
- `docker`, for `trivy image` jobs that need a local build
- `crane` (optional; `docker buildx imagetools inspect` works instead)
- The repo's package manager for lockfile bumps (uv, npm, pnpm, yarn, poetry, cargo, go, or bundler)

Install missing tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## Pre-flight

Before step 1, check the prerequisites:
```bash
for t in git gh; do command -v "$t" >/dev/null || echo "missing: $t"; done
gh auth status >/dev/null 2>&1 || echo "gh: not logged in"
command -v semgrep >/dev/null || command -v docker >/dev/null || echo "missing: semgrep (or docker)"
command -v trivy >/dev/null || command -v docker >/dev/null || echo "missing: trivy (or docker)"
# GitLab repos only:
for t in glab jq; do command -v "$t" >/dev/null || echo "missing: $t"; done
glab auth status >/dev/null 2>&1 || echo "glab: not logged in"
```
If a required tool for the repo's scanners prints as missing, stop and tell the user what to install or log in to. Check `docker` and the package manager when a step first needs them; if one is missing then, stop and name it.

1. Confirm CWD is a git repo. Find every Semgrep and Trivy invocation, config, and pin:
   ```bash
   git grep -nE 'semgrep|trivy|aquasec' -- '*.yml' '*.yaml' Makefile '*.mk' '*.sh' Dockerfile* .trivyignore* .semgrep*
   ```
   Note each job's exact command:
   - **Semgrep**: subcommand (`semgrep ci` or `semgrep scan`), `SEMGREP_RULES` or `--config` packs, `--exclude-rule` flags, and whether `--sarif --output=...` is set.
   - **Trivy**: subcommand (`fs`/`image`/`config`), `--scanners`, `--severity`, `--ignorefile`, `--exit-code`, env vars (such as `TRIVY_INCLUDE_DEV_DEPS`), and target. Note both PR-gate steps (often `severity: CRITICAL`) and non-PR SARIF steps (often `severity: CRITICAL,HIGH,MEDIUM` without `exit-code: '1'`), which still surface findings in the Security tab on merge.
2. Get the failing job logs. Use the job IDs the user gave you, or the latest failed pipeline on the current branch:
   - GitLab: `glab api "projects/:id/pipelines/<pipeline_id>/jobs?per_page=100" | jq -r '.[] | select(.status=="failed") | "\(.id) \(.name)"'`, then `glab api "projects/:id/jobs/<job_id>/trace"`. `glab ci view` needs a TTY, so don't use it.
   - GitHub: `gh run list --branch "$(git branch --show-current)" --limit 5`, then `gh run view <run_id> --log-failed`.
   Filter the logs by scanner:
   - **Semgrep logs**: Check the summary (`Findings: N (N blocking)`) and the diff-scan merge base (`Using <sha> as the merge-base`). When CI runs `semgrep ci --sarif --output=semgrep.sarif`, Semgrep writes the finding details only to the SARIF file and omits the finding rows from the job log. Replay the command locally without `--sarif --output=...` (Step 2a) to print the exact rule IDs, files, and line numbers.
   - **Trivy logs**: Don't read the raw log; image-job summaries can run to hundreds of KB. Save each log to a temp file and filter it:
     ```bash
     grep -E -B2 'Total: [1-9]|Failures: [1-9]|FATAL|ERROR' job.log   # each target with findings, with its Type
     grep -E 'Version: |(CVE|GHSA)-[0-9]+-[0-9]+ ' job.log            # trivy version + finding rows
     ```
     Steps with `format: sarif` write findings to the SARIF file instead of the log; run `trivy` locally with `format: table` to inspect them. If a target shows a non-zero count that the rows don't explain (a misconfig or secret), read only that target's section.
3. If a job fails before or after scanning due to infrastructure (registry auth, image pull, DB download, or SARIF upload `Code scanning is not enabled`), report the error line and stop.

## Step 1 — Bring scanner pins up to date

1. Get the latest releases for the scanners in use:
   - Semgrep: `gh api repos/semgrep/semgrep/releases/latest --jq .tag_name` (strip leading `v`). Confirm the Docker tag is published (`crane digest semgrep/semgrep:<ver>` or `docker buildx imagetools inspect semgrep/semgrep:<ver>`) before bumping `semgrep/semgrep:<ver>`.
   - Trivy: `gh api repos/aquasecurity/trivy/releases/latest --jq .tag_name` (strip leading `v`).
2. If any pin is older, bump **every** pin in the repo to that version in one go: CI container image tags (`semgrep/semgrep:<ver>`, `ghcr.io/aquasecurity/trivy:<ver>`), `trivy-action` `version:` inputs, and version vars in Makefiles and scripts. Keep each pin's registry (and keep `trivy-action` SHA-pinned). If a Trivy image pull failed on `aquasec/trivy` (Docker Hub rate limit), switch it to `ghcr.io/aquasecurity/trivy`.
3. For Trivy version bumps, read the release notes between the old and new versions (`gh release view v<new> -R aquasecurity/trivy`) for flag renames or removals that affect the commands from pre-flight, and update those commands if needed.
4. A stale Trivy pin alone causes failures such as DB schema or checks-bundle incompatibility, or `FATAL` lines asking you to update. If that was the only failure and local scans are clean, go to Step 3.

## Step 2 — Clear each finding

### 2a. Semgrep (SAST) findings

If the CI log hid the finding rows behind `--sarif --output=...`, run Semgrep locally without those two flags to print the findings:
```bash
# PR diff scan (matches semgrep ci in GitHub Actions):
SEMGREP_RULES="<packs from workflow>" semgrep ci --baseline-commit=<merge_base> <CI --exclude-rule flags>
# Full repo scan (catches findings outside the baseline diff or on GitLab):
semgrep scan --error --config <pack1> --config <pack2> <CI --exclude-rule flags> .
```

Resolve each finding:

- **Real code or config issue**: Fix the code, Dockerfile, or workflow at the flagged line (parameterized query, safe API, non-root `USER`, hardened config value).
- **Restoring a dropped playbook pragma**: If a recent config edit dropped a standard inline pragma from the `mw-kit` playbook (for example, `default-days: 3 # nosemgrep: package_managers.dependabot.dependabot-missing-cooldown.dependabot-missing-cooldown` in `.github/dependabot.yml`), restore the `# nosemgrep: <rule-id>` pragma on each flagged line.
- **New suppression or rule exclusion**: Use `# nosemgrep: <rule-id>` (always with the exact rule ID, never bare `# nosemgrep`) or a workflow `--exclude-rule=<rule-id>` only for a confirmed false positive or deliberate policy tradeoff. **Get the user's OK for each new suppression** before applying it.

### 2b. Trivy findings — classify by target Type

Group findings by package. The same CVE often shows up in both jobs, once from the lockfile (`fs`) and once from the installed copy inside the image (`image`, targets like `app/.venv/.../METADATA` or `node_modules/.../package.json`). One lockfile fix clears both. Also check the full severity set configured in the workflow (`CRITICAL,HIGH,MEDIUM` if SARIF jobs use it), not only the PR-gate severity.

| Type | Fix |
|---|---|
| Lockfile or language package (`uv`, `pip`, `poetry`, `python-pkg`, `npm`, `pnpm`, `yarn`, `node-pkg`, `cargo`, `gomod`, `gobinary`, `bundler`, `gemspec`) | Lockfile bump (2c) |
| OS distro (`alpine`, `wolfi`, `debian`, `ubuntu`, `redhat`, `chainguard`, …) | Base-image bump (2d) |
| Misconfiguration (`dockerfile`, `kubernetes`, `terraform`, `cloudformation`, …) with a non-zero count | Fix the file per the check's AVD link |
| Secret | **Stop and tell the user.** A real secret needs rotating first. Suppress only a confirmed false positive (2e) |
| No Fixed Version, or Status `affected`/`will_not_fix`/`fix_deferred` | Suppression (2e) |

### 2c. Lockfile bump

Bump only the vulnerable package to at least the Fixed Version with the ecosystem's single-package lockfile upgrade (e.g. `uv lock --upgrade-package <pkg>`, `npm update <pkg>`), and use its why/tree command (e.g. `uv tree --invert --package <pkg>`, `npm ls <pkg>`) to find what pins it.

- Confirm the lockfile now holds a version ≥ Fixed Version. If the resolver held it back, a parent pins it (common for sibling packages released in lockstep, like `gcsfs` → `fsspec`). Upgrade the parent in the same command (`uv lock --upgrade-package <parent> --upgrade-package <pkg>`, and likewise for other tools). Use an override (`[tool.uv] override-dependencies`, npm `overrides`, pnpm `pnpm.overrides`, yarn `resolutions`) only if no parent release allows the fixed version, and only after the user confirms.
- Don't raise the manifest floor (`pyproject.toml`, `package.json`) unless resolution needs it.
- If the bump crosses a major version, **ask before applying**. Check whether the parent package's import/call style (`require`, ESM `default`, CJS) remains compatible with the new major, and show the repo's call sites (`git grep -n <import name>`).
- Run the repo's test command afterward (Makefile `test` or `ci` target, `uv run pytest`, `npm test`, `cargo test`, `go test ./...`).

### 2d. Base-image bump

1. Find the `FROM` line that provides the vulnerable OS package. In a multi-stage build, only the final stage matters for `trivy image`.
2. Find the newest image for the same tag: `crane digest <image>:<tag>` (or `docker buildx imagetools inspect <image>:<tag>`). Pinned by digest → replace the digest and keep the tag. Pinned by tag → move to the newest patch tag on the same line (e.g. `3.14.4-alpine` → `3.14.5-alpine`). Never change the distro or major line without asking.
3. Update every `FROM` that references the same image.
4. If even the newest base still ships the vulnerable package and the distro has a fixed build, add an upgrade step for just that package in the final stage (`apk add --no-cache --upgrade <pkg>`, or `apt-get install -y --only-upgrade <pkg>`). If the distro has no fixed build, go to 2e.

### 2e. Trivy suppression

Use this only when there is no fix, or for a confirmed false positive. **Get the user's OK for each entry**, then add it to the ignore file the job passes via `--ignorefile` (default `.trivyignore` or `.trivyignore.yaml`), in that file's existing format, with a reason and an expiry of today + 30 days.

Always set an expiry. It forces a re-check once a fix ships.

## Step 3 — Verify locally with CI's exact commands

- **Semgrep job**: Run the workflow's exact rule packs and exclusions without `--sarif --output=...` (or via `docker run --rm -v "$PWD:/src" -w /src semgrep/semgrep:<ver>` if `semgrep` is not installed locally):
  ```bash
  SEMGREP_RULES="<packs from workflow>" semgrep ci --baseline-commit=<merge_base> <CI --exclude-rule flags>
  semgrep scan --error --config <pack1> --config <pack2> <CI --exclude-rule flags> .
  ```
- **Trivy fs job**: Use the same trivy version as the CI pin (`trivy --version`; if it differs, run `docker run --rm -v "$PWD:/src" -w /src ghcr.io/aquasecurity/trivy:<ver> <args>`, or `brew upgrade trivy` if the user agrees). Scan a copy of only the git-tracked files, since untracked local files (build output, stray poms) cause scans and network calls that CI never makes. A new lockfile must be staged (`git add -N`) to be included:
  ```bash
  tmp=$(mktemp -d) && git ls-files -z | tar --null -T - -cf - | tar xf - -C "$tmp"
  (cd "$tmp" && trivy fs <CI env and flags verbatim> .); echo "exit=$?"; rm -rf "$tmp"
  ```
- **Trivy image job**: Skip the build when every image finding is a language package (`python-pkg`, `node-pkg`, `gobinary`, …) that the fs job also reported, and the Dockerfile installs from the lockfile (`uv sync --frozen`, `npm ci`, `poetry install`, …). In that case the green fs scan already shows the image's copy is fixed. Build and scan the image only for OS findings, image-only findings, or a Dockerfile that installs outside the lockfile:
  ```bash
  docker build --platform linux/amd64 -t trivy-smoke:local .
  docker save trivy-smoke:local -o /tmp/trivy-smoke.tar
  trivy image --input /tmp/trivy-smoke.tar <CI flags verbatim>; echo "exit=$?"; rm -f /tmp/trivy-smoke.tar
  ```
  Use `--input`: `trivy image <tag>` can't read images from containerd-backed Docker (colima, Docker Desktop's containerd store). On Apple silicon the amd64 build runs under QEMU and is slow. Note that running `trivy image` against a remote Docker Official Image reference (rather than a locally built image) reads the remote Docker Scout SBOM attestation, which can report vendored pip packages not flagged in a local build. If Docker isn't available, say the image job wasn't verified locally, and why.

Done when every replayed command exits 0. If one still fails, go back to Step 2 for the remaining findings.

## Report

Don't commit or push.
