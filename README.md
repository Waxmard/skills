# skills

Agent skills for Git and PR workflows, documentation, tooling sync, and UI work.
The skills install as plugins in omp and Claude Code, and through `npx skills`
for Antigravity, Codex, Gemini CLI, and other agents.

## Install

In omp, add the marketplace and install the plugin:

```text
/marketplace add Waxmard/skills
/marketplace install mw-skills@waxmard
```

If you installed `mw-omp` earlier, uninstall it; its skills now ship in `mw-skills`.

In Claude Code, add the marketplace and install the plugin:

```text
/plugin marketplace add Waxmard/skills
/plugin install mw-skills@waxmard
```

For other agents, run `npx skills`. Pass `-a antigravity` or `-a codex` to
target one agent.

```bash
npx skills add Waxmard/skills
```

## Skills

| Skill | What it does |
|---|---|
| `docs-style` | Applies Google developer documentation style to prose written into files. |
| `fix-trivy-scan` | Upgrades Trivy and clears failing scan findings with dependency, base-image, or expiring-ignore fixes. |
| `free-disk-space` | Reclaims macOS disk space from dev caches, VM disks, build artifacts, and old toolchains. |
| `post-mr-review` | Turns review findings into GitLab MR comments and posts only what you confirm. |
| `pr-review-toolkit` | Reviews an MR, PR, or local branch through bug, error-handling, test, type, comment, and simplification lenses. |
| `resolve-merge-conflicts` | Walks through conflicts one file at a time during a merge, rebase, or cherry-pick. |
| `review-pr-comments` | Gives a read-only agree or disagree verdict on each review comment on the current PR or MR. |
| `split-branch` | Splits a scope-crept branch into branches that merge in any order without conflicts. |
| `ticket-draft` | Drafts a ticket title, description, and weight for Jira, GitLab, GitHub, or Linear. |
| `tooling-sync` | Compares a repo's tooling against the mw-kit playbook and applies the updates you pick. |
| `triage-renovate-dependabot-prs` | Merges Renovate and Dependabot bump branches one at a time with risk review and post-merge checks. |
| `ui-taste` | Adds personal UI preferences on top of `frontend-design`. |
| `wrap-up` | Runs an end-of-branch pre-flight that picks which review skills are worth running. |

`tooling-sync` reads its playbook from
[Waxmard/mw-kit](https://github.com/Waxmard/mw-kit). It uses `$MW_KIT` when
set, and otherwise clones mw-kit to `~/.cache/mw-kit`.

## Companions

Some skills call or pair with skills from other repos. Install these
companions for the full workflow. `wrap-up` skips a missing companion and
prints its install line.

| Companion | Used by | Install |
|---|---|---|
| ponytail (`ponytail-review`) | `wrap-up` | `/marketplace add DietrichGebert/ponytail`, then `/marketplace install ponytail@ponytail` |
| `frontend-design` | `ui-taste` | `/plugin marketplace add anthropics/claude-plugins-official`, then `/plugin install frontend-design@claude-plugins-official` |
| `web-design-guidelines` | `wrap-up`, `ui-taste` | `npx skills add vercel-labs/agent-skills` |
| `better-*`, `interface-review` | `wrap-up`, `ui-taste` | `npx skills add jakubkrehel/skills` |

## Local overrides

A `local.md` file in a skill directory holds machine-specific details, such as
internal hostnames or exemplar paths. Git ignores it, and the skill reads it
first when present.

## Credits

The `pr-review-toolkit` lens set is adapted from Anthropic's
[pr-review-toolkit plugin](https://github.com/anthropics/claude-code/tree/main/plugins/pr-review-toolkit).

## License

[MIT](LICENSE)
