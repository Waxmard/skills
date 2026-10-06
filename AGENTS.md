# AGENTS.md

Guidance for AI agents working in this repo.

## Layout
- `skills/<name>/SKILL.md` — portable skills, shipped as the `mw-skills` plugin (root `.claude-plugin/plugin.json`).
- `omp/skills/<name>/SKILL.md` — omp-only skills, shipped as the `mw-omp` plugin (`omp/.claude-plugin/plugin.json`).
- `.claude-plugin/marketplace.json` lists `mw-skills`; `.omp-plugin/marketplace.json` lists both plugins.
- Gitignored, local-only: `skills/monthly-resume-refresh/`, `skills/work-summary/`, `skills/ticket-draft/references/`, `local.md`.

## Conventions
- Author new skills with Anthropic's [skill-creator](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) (omp: `omp plugin install skill-creator@claude-plugins-official`; Claude Code: `/plugin install skill-creator@claude-plugins-official`), then apply the layout and README rules here.
- There is no build or test step. A skill is its `SKILL.md`: frontmatter `name` + `description`, then the instructions.
- Adding, removing, or renaming a skill: update the Skills table in `README.md` in the same commit.
- Keep the skills runnable on their own; `wrap-up` only orchestrates the others.
- Conventional Commits; see `.git-ai-instructions` for how types map here. release-please cuts releases from `feat`/`fix` on `main` and bumps `version` in both `plugin.json` files; never edit those versions by hand.
