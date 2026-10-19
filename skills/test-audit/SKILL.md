---
name: test-audit
description: >
  Audits unit, integration, and CLI tests in a branch diff or across a whole
  repository to prune tautological assertions, static prompt/prose substring
  checks, constant/lookup-table echoes, cross-layer CLI-to-unit duplicates,
  same-path duplicates, and stale tests while preserving genuine domain and
  boundary coverage. Supports lean (diff hunks only), default (branch test
  files + tests covering changed modules), and full (whole-repo test suite)
  modes. Trigger: "audit tests", "prune tests", "clean up tests", "trim
  redundant tests", "test audit", "test suite spa day", or /test-audit.
---

Audits tests to cut redundant, tautological, and brittle cases while keeping genuine domain and boundary coverage intact.

## Prerequisites & Required Tools

Runs on macOS and Linux (on Windows, use WSL).

- `git`

Install missing tools with the OS package manager (Homebrew on macOS; apt, dnf, or pacman on Linux) or the tool's official release binaries.

## 1. Scope Resolution (`lean` / default / `full`)

Before step 1, check the prerequisites:
```bash
command -v git >/dev/null || echo "missing: git"
```
Missing `git`: stop.

1. Confirm repo: `git rev-parse --git-dir`. If it fails, stop: "not a git repo".
2. Resolve the mode from invocation args or caller instructions (`lean`, default, or `full`) and determine the base range (`<mb>...<head0>` when passed by `wrap-up`, or `$(git merge-base HEAD origin/main 2>/dev/null || echo origin/master)...HEAD` plus uncommitted working-tree changes when run standalone):
   - **`lean` (Diff hunks only)**: Inspect only test functions or blocks added or modified in the diff (`git diff <start>..<head>` when called from `wrap-up`, or the branch + working-tree diff standalone). Flag only clear bloat added in the diff; never flag untouched tests.
   - **Default (Branch scope — touched test files + tests for changed modules)**: Inspect:
     1. Every test file changed in the branch diff (`<mb>...<head0>`), in full; and
     2. Existing test files that directly test the production modules changed in the branch diff (mapped by filename convention such as `foo.py` → `test_foo.py`, `lib/foo.sh` → `test/lib/foo.bats`, `foo.ts` → `foo.test.ts` / `foo.spec.ts`, `foo.go` → `foo_test.go`, or by direct imports/sources).
     Read each in-scope test file alongside the production module(s) it covers. If invoked standalone on a clean branch with no commits ahead of base and no dirty files, default automatically to `full` (whole-repo pass) and state that in the scope line.
   - **`full` (Whole-repo test suite pass)**: Discover and audit all test files in the repository (`test/`, `tests/`, `__tests__/`, `*.test.*`, `*.spec.*`, `*_test.go`, `*.bats`, `test_*.py`) alongside the production modules they test.

## 2. Audit Lenses (What to Cut or Consolidate)

Read each in-scope test file alongside the production module(s) it covers. Classify every removable or consolidatable test with one of these 6 tags:

- **`prose-substring` (`delete`)**: Tests asserting that static prompt files (`.txt`, `.md`) or source files contain literal prose phrases or substrings (especially when a build or check target already enforces template-to-output sync).
- **`tautology` (`delete` or `fold`)**: Non-empty or type-only smoke checks (`isinstance(x, str) and len(x) > 0`), assertions whose expected value is copied from or computed with the code under test, seeded-cache/mock echo checks, snapshot assertions (`toMatchSnapshot`) on components that already have explicit behavioral assertions, or bare renders/starts/does-not-throw checks when sibling tests already assert exact behavioral output. If a non-empty check is the only guard on a field, fold a 1-line `assert x.strip()` into an existing behavioral test and delete the standalone test.
- **`constant-echo` (`delete`)**: Tests whose expected value is a hardcoded lookup-table row or constant string echo, pure argument forwarding/wiring with no parsing, boundary, or branching logic, or tests that only verify third-party framework/stdlib behavior rather than application logic.
- **`cross-layer-dup` (`collapse` or `delete`)**: CLI/subprocess/integration/e2e tests (for example, BATS shelling out to Python/Node/Go CLIs, or API/UI wrapper tests) re-testing input matrices, flag combinations, or edge cases already covered by unit tests at the lower layer. Collapse N subprocess matrix tests down to 1 integration forwarder smoke test and delete the duplicate cases; also delete cross-file duplicate tests asserting the same helper branch in multiple test files.
- **`same-path-dup` (`consolidate` or `delete`)**: Multiple test functions, separate subprocess invocations, or multi-environment matrix runs exercising the exact same code branch with trivially different inputs where no boundary or edge condition differs. Consolidate into a single test (or parametrized table) or delete the redundant rows.
- **`stale` (`delete` or `rename`)**: Obsolete assertions, dead fixtures, or test files named after retired/renamed commands or concepts.

## 3. What to Keep (Hard Guardrails)

- Never delete or weaken tests for genuine domain or boundary logic: parsing external formats, data/pricing/permission rules, error and edge conditions, security/auth/path-traversal boundaries (for example, root `/` vs relative paths), state/git-graph invariants, concurrency, or bug-fix regressions.
- When collapsing `cross-layer-dup` suites, always keep 1 end-to-end smoke test proving the CLI/bridge wiring works.
- Never add new Playwright, Cypress, or browser e2e specs; flag unrequested new e2e specs in a diff for deletion (confirming with the user).

## 4. Execution & Delegation

- **Small scope (≤ 5 test files)**: Audit inline in the current session.
- **Large scope or `full` whole-repo pass (> 5 test files)**: Group test files by suite/directory (for example, `test/python/`, `test/lib/`, `test/bin/`) and fan out parallel read-only subagents on a fast, low-cost model. Each subagent reads its assigned test files and the production modules they test, classifying every test file and reporting exact test names, line ranges, tag, and justification.

## 5. Output Format & Fix Loop

Print a single `1..N` numbered findings list so the user or `wrap-up` Gate F can reference items by number:

```markdown
# Test Audit Report (<mode>: <N> test files inspected)

1. **`<file>:<line-range>`** — `<tag>` (`delete` | `consolidate` | `collapse` | `rename`): `<test_name>`
   - *Why*: <1-2 sentences citing the production code or duplicate test at `other_file:line`>.
   - *Fix*: <delete lines X-Y | merge into `<target_test>` at line Z | collapse to 1 smoke test>.
```

End with: `net: -<C> test cases, -<L> lines (<F> whole files to delete).` If nothing qualifies: `Test suite is lean. Nothing to prune.`

- **Read-only vs standalone**: When invoked as a read-only review (such as inside `wrap-up`'s review wave), make no edits and return the report verbatim. When invoked standalone, default to stop-and-fix after presenting the report (allowing the user to exclude numbers), apply the deletions/consolidations, and run the project's test suite and linters to verify all remaining tests pass.
