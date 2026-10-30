import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import wrap_up as w

ALL = [*w.ROW_SKILL.values(), "ponytail-audit"]


def facts(**kw):
    f = {
        "toplevel": "/repo", "run": "/repo/.git/wrap-up/run", "branch": "feat", "protected": False,
        "base": "origin/main", "mb": "m" * 40, "head0": "h" * 40, "from": "m" * 40, "mode": "full",
        "changed": ["a.py"], "changed_row2": ["a.py"], "added": 10, "added_row2": 10, "nondoc_added": 10,
        "file_lines": {"a.py": 10}, "test_changed": [], "doc_changed": [], "ui_changed": [],
        "manifests_changed": [], "repo_has_tests": True, "repo_has_ui": False, "others": 0, "renovate": 0,
        "scope": None, "installed": list(ALL),
    }
    f.update(kw)
    return f


def by_row(f):
    return {v["row"]: v for v in w.verdicts(f)}


class Verdicts(unittest.TestCase):
    def test_row3_threshold(self):
        self.assertEqual(by_row(facts(added=100))[3]["verdict"], "RUN")
        self.assertEqual(by_row(facts(added=99))[3]["verdict"], "skip")

    def test_row3_requirements_manifest(self):
        f = facts(manifests_changed=["requirements-dev.txt"])
        self.assertEqual(by_row(f)[3]["verdict"], "RUN")

    def test_row4_no_tests_in_repo(self):
        v = by_row(facts(repo_has_tests=False, added=500, nondoc_added=500))[4]
        self.assertEqual((v["verdict"], v["why"]), ("skip", "no test files in repo"))

    def test_row2_delta_skip_hint(self):
        v = by_row(facts(mode="delta", changed_row2=[]))[2]
        self.assertEqual(v["verdict"], "skip")
        self.assertIn("reply `full`", v["why"])

    def test_row7_protected(self):
        v = by_row(facts(renovate=2, protected=True, branch="main"))[7]
        self.assertEqual(v["verdict"], "skip")
        self.assertIn("protected branch", v["why"])

    def test_uninstalled(self):
        v = by_row(facts(installed=[s for s in ALL if s != "ponytail-review"], added=500))[3]
        self.assertEqual(v["verdict"], "skip")
        self.assertTrue(v["why"].startswith("not installed"))

    def test_lean_hint(self):
        scope = {"preflight": {"ok": True}, "state": {}, "in_scope": [{"state": {"settled": False}}]}
        v = by_row(facts(scope=scope, others=1))[1]
        self.assertEqual(v["verdict"], "RUN")
        self.assertTrue(v["why"].startswith("1 live tools"))
        self.assertTrue(v["why"].endswith("(lean: pick by number to include)"))


def run_rows(reply, **kw):
    f = facts(**kw)
    return w.parse_reply(reply, w.verdicts(f), f)


class ParseReply(unittest.TestCase):
    def rows(self, reply, **kw):
        return set(run_rows(reply, **kw)["rows"])

    def test_go(self):
        self.assertEqual(self.rows("go", added=500, nondoc_added=500), {2, 3, 4, 6})

    def test_numbers(self):
        self.assertEqual(self.rows("3 4"), {2, 3, 4})

    def test_none(self):
        self.assertEqual(self.rows("none", added=500), {2})

    def test_go_lean_drops_inline_rows(self):
        kw = {"renovate": 1}
        self.assertIn(7, self.rows("go", **kw))
        self.assertNotIn(7, self.rows("go lean", **kw))
        self.assertIn(7, self.rows("go 7 lean", **kw))

    def test_go_full_forces_rows(self):
        self.assertEqual(self.rows("go full"), {1, 2, 3, 4, 6})
        self.assertEqual(self.rows("go full", repo_has_ui=True), {1, 2, 3, 4, 5, 6})

    def test_default_clears_full(self):
        r = run_rows("run go default full default")["rows"]
        self.assertEqual({v["mode"] for v in r.values()}, {"default"})

    def test_override_order_irrelevant(self):
        a = run_rows("4@full:strong")["rows"][4]
        b = run_rows("4@strong:full")["rows"][4]
        self.assertEqual(a, b)
        self.assertEqual((a["mode"], a["tier"]), ("full", "strong"))

    def test_inline_tier_note(self):
        res = run_rows("go 1@strong")
        self.assertEqual(res["rows"][1]["tier"], "inline")
        self.assertEqual(sum("run inline" in n for n in res["notes"]), 1)

    def test_errors(self):
        for reply, msg in [
            ("none 3", "none can't be combined"), ("9", "no row 9"), ("bogus", "unrecognized token: bogus"),
            ("run", "empty reply"), ("4@fast:strong", "conflicting override"), ("4@x", "unrecognized token"),
        ]:
            with self.assertRaises(ValueError, msg=reply) as cm:
                run_rows(reply)
            self.assertIn(msg, str(cm.exception))

    def test_row2_delta_skip_dropped_unless_full(self):
        kw = {"mode": "delta", "changed_row2": [], "renovate": 1}
        self.assertEqual(self.rows("run 7", **kw), {7})
        self.assertIn(2, self.rows("2@full", **kw))

    def test_row3_full_uses_audit(self):
        self.assertEqual(run_rows("3@full")["rows"][3]["skill"], "ponytail-audit")


class BuildTasks(unittest.TestCase):
    def tasks(self, reply, **kw):
        f = facts(**kw)
        return w.build_tasks(w.parse_reply(reply, w.verdicts(f), f)["rows"], f)

    def test_shards_respect_limits(self):
        files = [f"d{i % 3}/f{i}.py" for i in range(31)]
        t = self.tasks("3", changed=files, file_lines={p: 10 for p in files})
        self.assertGreaterEqual(len(t), 2)
        for x in t:
            self.assertLessEqual(len(x["files"]), w.MAX_FILES_SHARD)
        self.assertEqual(sorted(p for x in t for p in x["files"]), sorted(files))

    def test_line_limit_splits_big_file(self):
        t = self.tasks("3", changed=["a.py", "b.py"], file_lines={"a.py": 1600, "b.py": 5})
        self.assertEqual([x["files"] for x in t], [["a.py"], ["b.py"]])

    def test_lockfile_only_diff(self):
        t = self.tasks("none", changed=["uv.lock"], file_lines={"uv.lock": 900})
        self.assertEqual((t[0]["id"], t[0]["files"]), ("A", []))
        self.assertNotIn(" -- ", t[0]["prompt"])

    def test_full_row_gets_own_task(self):
        ids = {x["id"]: x for x in self.tasks("go 4@full")}
        self.assertEqual(ids["F4"]["rows"], [4])
        self.assertEqual(ids["A"]["rows"], [2])

    def test_diff_pass_prompt_names_range_and_contract(self):
        t = self.tasks("3 4")[0]
        self.assertIn(f"git diff {'m' * 40}..{'h' * 40} -- a.py", t["prompt"])
        self.assertIn("/repo/.git/wrap-up/run/A.json", t["prompt"])
        self.assertEqual(t["rows"], [2, 3, 4])

    def test_strongest_tier_wins(self):
        self.assertEqual(self.tasks("3@strong 4")[0]["tier"], "strong")


def plan(picked, **modes):
    return {
        "picked": {str(n): {"skill": w.ROW_SKILL[n], "tier": "fast", "mode": modes.get(f"m{n}", "default"), "row": n}
                   for n in picked},
        "tasks": [{"id": "A", "rows": list(picked)}],
        "changed": ["a.py"],
    }


def fd(**kw):
    return {"file": "a.py", "line": 10, "severity": "important", "title": "t", "fix": "x", "rule": None, **kw}


def merge(picked, rows_findings, **modes):
    reports = {"A": {"reports": [{"row": n, "skill": w.ROW_SKILL[n], "complete": True, "findings": fs}
                                 for n, fs in rows_findings.items()]}}
    return w.merge_findings(plan(picked, **modes), reports)


class Merge(unittest.TestCase):
    def test_suggestion_needs_fix(self):
        r = merge([2], {2: [fd(severity="suggestion", fix=""), fd(severity="suggestion", line=50)]})
        self.assertEqual(len(r[2]["findings"]), 1)
        self.assertEqual(r[2]["excluded"], 1)

    def test_nit_kept_only_with_rule(self):
        r = merge([2], {2: [fd(severity="nit"), fd(severity="nit", rule="AGENTS.md", line=40)]})
        self.assertEqual([x["rule"] for x in r[2]["findings"]], ["AGENTS.md"])

    def test_cross_row_dedupe_within_three_lines(self):
        r = merge([2, 3], {2: [fd(line=10)], 3: [fd(line=12)]})
        self.assertEqual(len(r[2]["findings"]), 1)
        self.assertIn("(also: ponytail-review)", r[2]["findings"][0]["title"])
        self.assertEqual(r[3]["findings"], [])

    def test_distant_lines_both_kept(self):
        r = merge([2, 3], {2: [fd(line=10)], 3: [fd(line=20)]})
        self.assertEqual((len(r[2]["findings"]), len(r[3]["findings"])), (1, 1))

    def test_file_level_findings_not_deduped_across_rows(self):
        r = merge([2, 6], {2: [fd(line=None)], 6: [fd(line=None)]})
        self.assertEqual((len(r[2]["findings"]), len(r[6]["findings"])), (1, 1))

    def test_full_mode_outside_diff_needs_decision(self):
        r = merge([4], {4: [fd(file="other.py"), fd(file="a.py", line=1)]}, m4="full")
        self.assertEqual([x.get("needs_decision") for x in r[4]["findings"]], [True, None])

    def test_numbering(self):
        r = merge([2], {2: [fd(line=1), fd(line=50)]})
        self.assertEqual([x["id"] for x in r[2]["findings"]], ["2.1", "2.2"])

    def test_incomplete_note(self):
        reports = {"A": {"reports": [{"row": 2, "complete": False, "findings": []}]}}
        r = w.merge_findings(plan([2]), reports)
        self.assertEqual(r[2]["notes"], ["row 2 incomplete in A"])


if __name__ == "__main__":
    unittest.main()
