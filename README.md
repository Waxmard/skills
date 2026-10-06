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
| `interface-design` | `ui-taste` | `npx skills add dammyjay93/interface-design` |
| `emil-design-eng` | `ui-taste` | `npx skills add emilkowalski/skills` |
| `transitions-dev`, `transitions-polish` | `ui-taste` | `npx skills add Jakubantalik/transitions.dev` |

## Local overrides

A `local.md` file in a skill directory holds machine-specific details, such as
internal hostnames or exemplar paths. Git ignores it, and the skill reads it
first when present.

## Credits

Adapted from:

- [pr-review-toolkit](https://github.com/anthropics/claude-code/tree/main/plugins/pr-review-toolkit)
  by Anthropic: the `pr-review-toolkit` lens set.
- [Google developer documentation style guide](https://developers.google.com/style):
  the rules in `docs-style`.
- [skill-creator](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator)
  by Anthropic: used to author these skills.

Builds on:

- [ponytail](https://github.com/DietrichGebert/ponytail) by Dietrich Gebert:
  `ponytail-review` in `wrap-up`.
- [frontend-design](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/frontend-design)
  by Anthropic: the process `ui-taste` layers on.
- [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills):
  `web-design-guidelines` in `wrap-up` and `ui-taste`.
- [jakubkrehel/skills](https://github.com/jakubkrehel/skills): `better-*` and
  `interface-review` in `wrap-up` and `ui-taste`.
- [interface-design](https://github.com/Dammyjay93/interface-design):
  craft guidance in `ui-taste`.
- [emilkowalski/skills](https://github.com/emilkowalski/skills):
  `emil-design-eng` in `ui-taste`.
- [transitions.dev](https://transitions.dev)
  ([repo](https://github.com/Jakubantalik/transitions.dev)): motion
  snippets and timing in `ui-taste`.

## License

[MIT](LICENSE)
