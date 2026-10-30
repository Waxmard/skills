import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gitlab_mr as g

URL = "https://gitlab.example.com/group/repo/-/merge_requests/7"


def note(nid, author, body="x", system=False, **kw):
    n = {"id": nid, "author": {"username": author}, "body": body, "system": system, "noteable_iid": 7}
    n.update(kw)
    return n


def disc(did, *notes):
    return {"id": did, "notes": list(notes)}


def rec(author="jdoe", body="x", last_author=None, resolved=None, system=False):
    return {
        "author": author, "body": body, "last_author": last_author or author,
        "resolved": resolved, "system": system,
    }


class Normalize(unittest.TestCase):
    def test_bot_question_path_from_blob_link(self):
        body = f"<!-- review-bot:questions:1 -->\nSee [a.py:12]({'https://h/p/-/blob/' + 'a' * 40 + '/src/a.py#L12'})"
        r = g.normalize(disc("d", note(1, "review-bot", body, position=None)), "me", URL)
        self.assertEqual((r["path"], r["line"], r["kind"]), ("src/a.py", 12, "bot"))

    def test_human_blob_link_without_marker_keeps_path_none(self):
        body = "look at https://h/p/-/blob/" + "a" * 40 + "/src/a.py#L12"
        r = g.normalize(disc("d", note(1, "jdoe", body)), "me", URL)
        self.assertIsNone(r["path"])

    def test_push_note_not_a_reply(self):
        d = disc(
            "d",
            note(1, "jdoe"),
            note(2, "me", "answer"),
            note(3, "me", "changed this line in version 2", system=True),
        )
        r = g.normalize(d, "me", URL)
        self.assertEqual(r["after_me"], 0)
        self.assertTrue(r["pushed_after"])
        self.assertEqual(r["last_author"], "me")

    def test_after_me_counts_later_replies_and_none_when_absent(self):
        d = disc("d", note(1, "jdoe"), note(2, "me"), note(3, "jdoe"), note(4, "jdoe"))
        self.assertEqual(g.normalize(d, "me", URL)["after_me"], 2)
        self.assertIsNone(g.normalize(disc("d", note(1, "jdoe")), "me", URL)["after_me"])

    def test_kinds(self):
        kinds = {
            a: g.normalize(disc("d", note(1, a)), "me", URL)["kind"]
            for a in ("review-bot", "project_12_bot_ab", "jdoe", "me")
        }
        self.assertEqual(
            kinds, {"review-bot": "bot", "project_12_bot_ab": "bot", "jdoe": "human", "me": "me"}
        )

    def test_position_and_url(self):
        pos = {"new_path": "a.py", "new_line": 3}
        r = g.normalize(disc("d", note(5, "jdoe", position=pos)), "me", URL)
        self.assertEqual((r["path"], r["line"], r["url"]), ("a.py", 3, URL + "#note_5"))


class Select(unittest.TestCase):
    def sel(self, recs, **kw):
        args = {"scope": "open", "include_resolved": False, "authors": []}
        args.update(kw)
        return g.select(recs, "author", args["scope"], args["include_resolved"], args["authors"])

    def test_open_drops_mr_author_note(self):
        self.assertEqual(self.sel([rec("author"), rec("jdoe")]), [rec("jdoe")])

    def test_last_author_mr_author_dropped_unless_include_resolved(self):
        r = rec("jdoe", last_author="author")
        self.assertEqual(self.sel([r]), [])
        self.assertEqual(self.sel([r], include_resolved=True), [r])

    def test_resolved_flag(self):
        recs = [rec(resolved=True), rec(resolved=False), rec(resolved=None)]
        self.assertEqual(self.sel(recs), recs[1:])

    def test_status_comment_dropped(self):
        self.assertEqual(self.sel([rec(body="<!-- review-bot:looks-good -->")]), [])

    def test_author_filter_and_all_scope(self):
        recs = [rec("a1"), rec("a2"), rec("a1", system=True)]
        self.assertEqual(self.sel(recs, scope="all", authors=["a1"]), [recs[0]])
        self.assertEqual(self.sel(recs, scope="all"), recs[:2])


class Identity(unittest.TestCase):
    def test_counts_foreign_discussions(self):
        ds = [disc("a", note(1, "x")), disc("b", note(2, "x", noteable_iid=9))]
        self.assertEqual(g.check_identity(ds, 7), 1)


DIFF = """diff --git a/a.py b/a.py
index 111..222 100644
--- a/a.py
+++ b/a.py
@@ -1,4 +1,5 @@
 one
-two
+TWO
+extra
 three
 four
diff --git a/old.py b/new.py
similarity index 90%
rename from old.py
rename to new.py
--- a/old.py
+++ b/new.py
@@ -10,2 +10,3 @@
 ten
+eleven
 twelve
diff --git a/gone.py b/gone.py
deleted file mode 100644
--- a/gone.py
+++ /dev/null
@@ -1,2 +0,0 @@
--- x
-y
"""


class Anchors(unittest.TestCase):
    def setUp(self):
        self.lm = g.line_map(DIFF)

    def test_added_line_has_only_new_line(self):
        self.assertEqual(g.anchor(self.lm, "a.py", 2), {"old_path": "a.py", "new_path": "a.py", "new_line": 2})

    def test_context_line_has_both(self):
        self.assertEqual(
            g.anchor(self.lm, "a.py", 4),
            {"old_path": "a.py", "new_path": "a.py", "new_line": 4, "old_line": 3},
        )

    def test_outside_hunk_is_none(self):
        self.assertIsNone(g.anchor(self.lm, "a.py", 99))
        self.assertIsNone(g.anchor(self.lm, "missing.py", 1))

    def test_rename_keeps_old_path(self):
        self.assertEqual(
            g.anchor(self.lm, "new.py", 11), {"old_path": "old.py", "new_path": "new.py", "new_line": 11}
        )

    def test_old_side_anchors_deleted_line(self):
        self.assertEqual(
            g.anchor(self.lm, "a.py", 2, side="old"), {"old_path": "a.py", "new_path": "a.py", "old_line": 2}
        )
        self.assertIsNone(g.anchor(self.lm, "a.py", 1, side="old"))

    def test_deleted_file_keyed_by_old_path(self):
        self.assertEqual(g.anchor(self.lm, "gone.py", 1, side="old")["new_path"], "gone.py")


CTX = {"iid": 7, "base_sha": "b", "start_sha": "s", "head_sha": "h"}


class BuildRequest(unittest.TestCase):
    def test_inline_outside_diff(self):
        with self.assertRaisesRegex(ValueError, "is not in the diff"):
            g.build_request({"kind": "inline", "path": "a.py", "line": 99, "body": "x"}, CTX, g.line_map(DIFF))

    def test_inline_position(self):
        _, path, body = g.build_request(
            {"kind": "inline", "path": "a.py", "line": 2, "body": "x"}, CTX, g.line_map(DIFF)
        )
        self.assertTrue(path.endswith("/7/discussions"))
        self.assertEqual(body["position"]["head_sha"], "h")
        self.assertEqual(body["position"]["new_line"], 2)

    def test_missing_field_and_unknown_kind(self):
        with self.assertRaisesRegex(ValueError, "missing discussion_id"):
            g.build_request({"kind": "reply", "body": "x"}, CTX, {})
        with self.assertRaisesRegex(ValueError, "unknown kind: nope"):
            g.build_request({"kind": "nope"}, CTX, {})

    def test_reopen(self):
        self.assertEqual(
            g.build_request({"kind": "reopen", "discussion_id": "abc"}, CTX, {}),
            ("PUT", "projects/:id/merge_requests/7/discussions/abc?resolved=false", None),
        )

    def test_reply_and_edit_paths(self):
        _, p, _ = g.build_request({"kind": "reply", "discussion_id": "abc", "body": "x"}, CTX, {})
        self.assertTrue(p.endswith("/discussions/abc/notes"))
        m, p, _ = g.build_request(
            {"kind": "edit", "discussion_id": "abc", "note_id": 5, "body": "x"}, CTX, {}
        )
        self.assertEqual((m, p.rsplit("/", 3)[-3:]), ("PUT", ["abc", "notes", "5"]))


if __name__ == "__main__":
    unittest.main()
