# AGENTS.md

Guidance for AI agents working in this repo.

## Layout
- `skills/<name>/SKILL.md` — portable skills, shipped as the `mw-skills` plugin (root `.claude-plugin/plugin.json`).
- `.claude-plugin/marketplace.json` and `.omp-plugin/marketplace.json` both list `mw-skills`.
- Gitignored, local-only: `skills/monthly-resume-refresh/`, `skills/work-summary/`, `skills/ticket-draft/references/`, `local.md`.

## Conventions
- Author new skills with Anthropic's [skill-creator](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) (omp: `omp plugin install skill-creator@claude-plugins-official`; Claude Code: `/plugin install skill-creator@claude-plugins-official`), then apply the layout and README rules here.
- A skill is its `SKILL.md`: frontmatter `name` + `description`, then the instructions. Run `scripts/check.sh` (tracked JSON + SKILL.md frontmatter) before committing; lefthook and CI run it too.
- Adding, removing, or renaming a skill: update the Skills table in `README.md` in the same commit.
- Keep the skills runnable on their own; `wrap-up` only orchestrates the others.
- Skills are harness-neutral; put omp/Claude Code specifics in a `## Harness notes` table (see `wrap-up`).
- Conventional Commits; see `.git-ai-instructions` for how types map here.
