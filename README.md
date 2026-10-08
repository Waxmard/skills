# skills

Agent skills for Git and MR work, docs, tooling sync and UI, shipped as one
plugin (`mw-skills`). They run in Pi, Antigravity, Codex, Claude Code, omp,
OpenCode, and many more agents.

```text
branch grew too much ──▶ split-branch ──▶ one MR per theme
reviewing an MR      ──▶ pr-review-toolkit ──▶ post-mr-review ──▶ MR threads
review came back     ──▶ address-review-comments ──▶ verdicts, then replies
before merge         ──▶ wrap-up ─┬─▶ tooling-sync ◀── Waxmard/mw-kit playbook
                                  ├─▶ pr-review-toolkit, ponytail-review,
                                  │   web-design-guidelines, interface-review
                                  └─▶ triage-renovate-dependabot-prs
```

## Prerequisites

Skills run on macOS and Linux; on Windows, use WSL. `free-disk-space` is
macOS only. Most skills need `git`, plus `gh` or `glab` logged in to your
forge for PR and MR work; some also need `jq` or `python3`. Each skill lists
its exact tools under `## Prerequisites & Required Tools` and checks them
before it starts.

## Install

Pi, Antigravity, Codex, OpenCode, and
[many more](https://github.com/vercel-labs/skills#supported-agents):

```sh
npx skills add Waxmard/skills                  # detects your installed agents and asks
npx skills add Waxmard/skills -a pi -a codex   # just these; ids: pi, antigravity, codex, opencode
```

omp and Claude Code install it as a plugin:

```text
/marketplace add Waxmard/skills                # omp
/marketplace install mw-skills@waxmard

/plugin marketplace add Waxmard/skills         # Claude Code
/plugin install mw-skills@waxmard
```

If you installed `mw-omp` earlier, uninstall it. Its skills ship in `mw-skills`
now.

## Skills

| Skill | What |
|---|---|
| `address-review-comments` | Gives an agree or disagree verdict on each review comment on the current PR or MR, then drafts or posts replies once fixes land. |
| `docs-style` | Applies Google developer documentation style to prose written into files. |
| `fix-trivy-scan` | Upgrades Trivy and clears failing scan findings with dependency, base-image, or expiring-ignore fixes. |
| `free-disk-space` | Reclaims macOS disk space from dev caches, VM disks, build artifacts, and old toolchains. |
| `post-mr-review` | Turns review findings into GitLab MR comments and posts only what you confirm. |
| `pr-review-toolkit` | Reviews an MR, PR, or local branch through bug, error-handling, test, type, comment, and simplification lenses. |
| `resolve-merge-conflicts` | Walks through conflicts one file at a time during a merge, rebase, or cherry-pick. |
| `split-branch` | Splits a scope-crept branch into branches that merge in any order without conflicts. |
| `ticket-draft` | Drafts a ticket title, description, and weight for Jira, GitLab, GitHub, or Linear. |
| `tooling-sync` | Compares a repo's tooling against the mw-kit playbook and applies the updates you pick. |
| `triage-renovate-dependabot-prs` | Merges Renovate and Dependabot bump branches one at a time with risk review and post-merge checks. |
| `ui-taste` | Adds personal UI preferences on top of `frontend-design`, and reviews a UI against them. |
| `wrap-up` | Runs an end-of-branch pre-flight that picks which review skills are worth running. |

`tooling-sync` reads its playbook from
[Waxmard/mw-kit](https://github.com/Waxmard/mw-kit), using `$MW_KIT` when set
and a clone in `~/.cache/mw-kit` otherwise.

A `local.md` in a skill's directory holds machine-specific details such as
hostnames or exemplar paths. Git ignores it, and the skill reads it
first.

## Companions

`wrap-up` and `ui-taste` call skills from other repos. `wrap-up` skips a
missing one and prints its install line.

| Companion | Used by |
|---|---|
| `ponytail-review` | `wrap-up` |
| `frontend-design` | `ui-taste` |
| `web-design-guidelines` | `wrap-up`, `ui-taste` |
| `better-*`, `interface-review` | `wrap-up`, `ui-taste` |
| `interface-design` | `ui-taste` |
| `emil-design-eng` | `ui-taste` |
| `transitions-dev`, `transitions-polish` | `ui-taste` |

```text
/marketplace add DietrichGebert/ponytail                 # ponytail-review, omp
/marketplace install ponytail@ponytail
/plugin marketplace add DietrichGebert/ponytail          # ponytail-review, Claude Code
/plugin install ponytail@ponytail
/plugin marketplace add anthropics/claude-plugins-official
/plugin install frontend-design@claude-plugins-official  # frontend-design
```

```sh
npx skills add vercel-labs/agent-skills        # web-design-guidelines
npx skills add jakubkrehel/skills              # better-*, interface-review
npx skills add dammyjay93/interface-design     # interface-design
npx skills add emilkowalski/skills             # emil-design-eng
npx skills add Jakubantalik/transitions.dev    # transitions-dev, transitions-polish
```

## Layout

| Path | What |
|---|---|
| `skills/<name>/SKILL.md` | One skill: frontmatter `name` and `description`, then the instructions |
| `.claude-plugin/`, `.omp-plugin/` | Marketplace and plugin manifests |
| `scripts/check.sh` | Validates tracked JSON and SKILL.md frontmatter; lefthook and CI run it |

## Credits

Adapted from:

- [Jack Furton (Krog)](https://github.com/JackFurton): the README shape here
  and in `docs-style`, and the hop-tracing and command-proof rules in
  `post-mr-review`, `address-review-comments` and `pr-review-toolkit`.
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
