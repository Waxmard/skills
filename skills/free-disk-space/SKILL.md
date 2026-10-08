---
name: free-disk-space
description: Reclaim disk space on macOS by auditing and clearing dev caches, container VM disks, build artifacts, stale toolchain versions, and offloading large media. Tuned for a polyglot dev machine (colima/docker, mise/nvm/rbenv/conda, go/cargo/gradle/npm, ollama). Trigger - "free disk space", "disk is full", "clean up my mac", "reclaim space", "what's eating my disk", or /free-disk-space.
---

# Free disk space (macOS)

## Prerequisites & Required Tools

Runs on macOS only.

- Built in: `df`, `du`, `tmutil`, `rsync`, `trash` (in `/usr/bin` on current macOS; on older versions, `brew install trash`)
- `git`, for the worktree audit (step 7)
- Every cleanup tool (brew, go, cargo, npm, pnpm, yarn, uv, pip, docker, colima, mise, nvm, rbenv, conda, ollama) is optional; ground rule 5 guards each one

## Ground rules

1. **Measure the data volume**: `df -h /System/Volumes/Data`. Plain `df /` reports the sealed system snapshot and is misleading.
2. **Trash frees nothing until emptied.** `~/.Trash` is on the same APFS volume — moving a file there does not reclaim a byte. When free space is critically low (< 5G), prefer tool-native cleanup and direct removal of regenerable caches; reserve `trash` for anything judgement-dependent, and empty it in the same session.
3. **Tool-native over manual**: `brew cleanup --prune=all`, `go clean -cache -modcache`, `cargo cache --autoclean`, `npm cache clean --force`, `pnpm store prune`, `docker system prune`, `mise prune`. These know what's safe; `rm -rf` doesn't.
4. **Never touch GUI app data**: `~/Library/Application Support/<App>` and `~/Library/Containers/<App>` hold logins, licenses, and unsynced state. Skip unless the user names the app and accepts the loss. `~/Library/Caches/<App>` is usually safe but ask first.
5. **Guard every command**: `command -v X >/dev/null 2>&1` before invoking. This machine's toolchain varies.
6. **Sizes before prompts**: never ask "delete X?" without stating what X costs. `du -sh` first.
7. **Report deltas**: `df` before and after each tier, so the user sees what actually worked.

## Workflow

### 1. Assess

Before step 1, check the prerequisites:
```bash
for t in df du tmutil rsync trash git; do command -v "$t" >/dev/null || echo "missing: $t"; done
```
If anything prints, stop and name what's missing.

```bash
df -h /System/Volumes/Data
ls /Volumes
tmutil listlocalsnapshots /
```

Local APFS snapshots can hold tens of GB hostage. If any exist and the user is desperate, `tmutil deletelocalsnapshots <date>` — ask first, it costs Time Machine restore points.

### 2. Survey

Targeted, never a full-home scan:

```bash
du -sh ~/* ~/.[a-zA-Z]* 2>/dev/null | sort -hr | head -25
du -sh /Applications /Library 2>/dev/null
```

Then drill only into what ranks. Present a table: path, size, what it is, reclaim verdict.

### 3. Tier A — regenerable caches (no prompt)

Run only what's installed. Report each one's yield.

```bash
brew cleanup --prune=all                       # also: rm -rf "$(brew --cache)"
go clean -cache -testcache -modcache
cargo cache --autoclean                        # fallback: rm -rf ~/.cargo/registry/cache
npm cache clean --force
pnpm store prune
yarn cache clean
uv cache clean
pip cache purge
rm -rf ~/Library/Caches/{pip,pypoetry,ms-playwright,Cypress,electron,node-gyp}
rm -rf ~/.gradle/caches/build-cache-* ~/.gradle/caches/modules-2/files-2.1
rm -rf ~/.cache/{puppeteer,ms-playwright,yarn,pnpm,uv,pre-commit,huggingface/hub}
docker system prune -f                         # non-destructive: dangling only
```

Inspect `~/.cache/*` by size before wholesale removal — some tools stash non-regenerable state there.

Run each `rm -rf` as its own command, never chained after a glob: zsh aborts the **entire** command line on an unmatched glob (`no matches found`), so a trailing `~/.gradle/caches/build-cache-*` silently cancels every path listed before it. Verify with `df` deltas per tier rather than trusting exit status.

### 4. Tier B — container VM disks (ask, high yield)

colima and Rancher Desktop VM disk images grow monotonically; deleting images inside the VM does **not** shrink the host file.

```bash
du -sh ~/.colima ~/Library/Application\ Support/rancher-desktop 2>/dev/null
colima list
```

Check the backend before assuming the file can't shrink:

```bash
grep -E '^vmType' ~/.colima/_lima/<profile>/lima.yaml
ls -lh ~/.colima/_lima/<profile>/diffdisk     # apparent size
du -sh  ~/.colima/_lima/<profile>/diffdisk    # blocks actually allocated
```

With `vmType: vz` and a raw sparse `diffdisk`, the guest mounts with online discard — freeing blocks **inside** the VM punches holes in the host file live, no recreate needed. Watch `du` drop mid-prune. `fstrim -av` afterwards is then a no-op on `/` (that's expected, not a failure). qemu/qcow2 backends do *not* behave this way and need a recreate or `qemu-img convert` to compact.

So, cheapest first:
- `docker image prune -af` + `docker builder prune -af` — non-destructive, only images with no container and dangling build cache.
- `docker volume prune -f` removes **anonymous volumes only**; named ones (`backend_postgres-data`) survive by design. It leaves orphaned `buildx_buildkit_<builder>0_state` volumes behind when the builder container is gone; those are pure build cache and often the biggest line in `docker system df`. Check `docker buildx du --builder <name>`, and for builders whose container no longer exists, `docker volume rm buildx_buildkit_<name>0_state` directly.
- Recreate the VM: `colima delete <profile>` then `colima start`. **Destroys all images, containers, and volumes in that profile.** Last resort — only if the backend can't shrink in place.
- Rancher Desktop: Troubleshooting → Factory Reset, same caveat.

Always confirm which runtime is actually in use before proposing deletion of the other.

### 5. Tier C — toolchain versions & models (ask)

```bash
mise ls; nvm ls; rbenv versions; conda env list
ollama list
du -sh ~/.nvm ~/.rbenv ~/miniconda3 ~/.ollama ~/.pub-cache ~/.bun ~/.minikube
```

Prune non-current versions (`mise prune`, `nvm uninstall <v>`), unused conda envs, and ollama models the user names. Never remove the active/global version.

### 6. Tier D — repo build artifacts (ask once, then batch)

```bash
find ~/<code-dirs> -type d \( -name node_modules -o -name target -o -name .next -o -name dist -o -name build -o -name .venv \) \
  -prune -not -newermt '30 days ago' -exec du -sh {} +
```

Present the total, then remove in one pass. `-not -newermt` keeps active projects intact. Re-install cost is a `npm i` / `cargo build`, so this is low-risk — but confirm no repo has uncommitted generated output that matters.

### 7. Audit git worktrees

For each `git worktree list` entry: check `git status --porcelain` and `git log @{u}..` for unpushed commits. Remove **only** clean, fully-merged branches via `git worktree remove` + `git branch -d` (never `-D`).

### 8. Tier E — media offload (ask)

`~/Music`, `~/Pictures`, `~/Movies`, `~/Downloads`. Check whether the library is already cloud-backed (Apple Music / iCloud Photos) before proposing anything — if it is, "optimize storage" in the app beats manual moves.

To offload to external:

```bash
rsync -a --info=progress2 <src>/ /Volumes/<drive>/<dst>/
diff <(du -s <src> | cut -f1) <(du -s /Volumes/<drive>/<dst> | cut -f1)   # verify before removing
trash <src> && ln -s /Volumes/<drive>/<dst> <src>
```

Warn: symlinked paths break every time the drive is unmounted. Apps that index those paths (Photos, Music) may misbehave.

### 9. Wrap up

- `df -h /System/Volumes/Data` — state total reclaimed.
- List what's sitting in Trash and ask the user to empty it (the space isn't back until they do).
- List what was deliberately preserved and why.
