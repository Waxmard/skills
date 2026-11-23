import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import github_pr as g

URL = "https://github.com/owner/repo/pull/7"


def gcomment(cid, author, body="x", url=None):
    return {
        "databaseId": cid,
        "author": None if author is None else {"login": author},
        "body": body,
        "url": url or f"{URL}#discussion_r{cid}",
    }


def gthread(tid, *comments, path="a.py", line=3, original_line=3, resolved=False, resolved_by=None, outdated=False):
    return {
        "id": tid,
        "isResolved": resolved,
        "isOutdated": outdated,
        "resolvedBy": None if resolved_by is None else {"login": resolved_by},
        "path": path,
        "line": line,
        "originalLine": original_line,
        "comments": {"nodes": list(comments)},
    }


def rec(author="jdoe", body="x", last_author=None, resolved=None):
    return {
        "author": author,
        "body": body,
        "last_author": last_author or author,
        "resolved": resolved,
    }


class Normalize(unittest.TestCase):
    def test_thread_kinds_and_ghost_author(self):
        cases = {
            "coderabbitai[bot]": "bot",
            "copilot-pull-request-reviewer": "bot",
            "claude": "bot",
            "dependabot": "bot",
            "jdoe": "human",
            "me": "me",
            None: "human",
        }
        for author, expected in cases.items():
            t = gthread("T1", gcomment(10, author))
            r = g.normalize_thread(t, "me")
            self.assertEqual(r["kind"], expected)
            self.assertEqual(r["author"], author or "ghost")

    def test_thread_after_me_resolved_and_outdated(self):
        t = gthread(
            "T2",
            gcomment(1, "jdoe", "why?"),
            gcomment(2, "me", "because"),
            gcomment(3, "jdoe", "still?"),
            gcomment(4, None, "ping"),
            line=None,
            original_line=15,
            resolved=True,
            resolved_by="alice",
            outdated=True,
        )
        r = g.normalize_thread(t, "me")
        self.assertEqual(r["id"], "T2")
        self.assertEqual(r["comment_id"], 1)
        self.assertEqual(r["surface"], "thread")
        self.assertEqual(r["line"], 15)
        self.assertTrue(r["resolved"])
        self.assertEqual(r["resolved_by"], "alice")
        self.assertTrue(r["outdated"])
        self.assertEqual(r["after_me"], 2)
        self.assertEqual(r["last_author"], "ghost")
        self.assertEqual([x["author"] for x in r["replies"]], ["me", "jdoe", "ghost"])

    def test_thread_without_me_or_comments(self):
        self.assertIsNone(g.normalize_thread(gthread("T0"), "me"))
        r = g.normalize_thread(gthread("T1", gcomment(1, "jdoe")), "me")
        self.assertIsNone(r["after_me"])

    def test_issue_comment_and_review(self):
        ic = g.normalize_issue_comment(
            {"id": 55, "user": {"login": "me"}, "body": "note", "html_url": f"{URL}#issuecomment-55"},
            "me",
        )
        self.assertEqual(
            (ic["id"], ic["comment_id"], ic["surface"], ic["kind"], ic["after_me"], ic["last_author"]),
            ("55", 55, "issue", "me", 0, "me"),
        )
        self.assertIsNone(ic["path"])
        self.assertIsNone(ic["resolved"])

        rv = g.normalize_review(
            {"id": 88, "user": None, "body": "summary", "html_url": f"{URL}#pullrequestreview-88"},
            "me",
        )
        self.assertEqual(
            (rv["id"], rv["comment_id"], rv["surface"], rv["author"], rv["kind"], rv["after_me"]),
            ("88", 88, "review", "ghost", "human", None),
        )


class Select(unittest.TestCase):
    def sel(self, recs, **kw):
        args = {"scope": "open", "include_resolved": False, "authors": []}
        args.update(kw)
        return g.select(recs, "author", args["scope"], args["include_resolved"], args["authors"])

    def test_open_drops_pr_author_and_status(self):
        recs = [
            rec("author"),
            rec("bot", "<!-- x:looks-good -->"),
            rec("bot", "REVIEW_INCOMPLETE"),
            rec("jdoe", "real issue"),
        ]
        self.assertEqual(self.sel(recs), [recs[3]])

    def test_resolved_and_last_author_filters(self):
        r_reply = rec("jdoe", last_author="author")
        r_res = rec("jdoe", resolved=True)
        r_open = rec("jdoe", resolved=False)
        r_none = rec("jdoe", resolved=None)
        self.assertEqual(self.sel([r_reply, r_res, r_open, r_none]), [r_open, r_none])
        self.assertEqual(
            self.sel([r_reply, r_res, r_open, r_none], include_resolved=True),
            [r_reply, r_res, r_open, r_none],
        )

    def test_all_scope_and_authors(self):
        recs = [rec("a1"), rec("a2"), rec("author")]
        self.assertEqual(self.sel(recs, scope="all"), recs)
        self.assertEqual(self.sel(recs, scope="all", authors=["a1"]), [recs[0]])


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

    def test_new_side_added_and_context(self):
        self.assertEqual(g.anchor(self.lm, "a.py", 2), {"path": "a.py", "line": 2, "side": "RIGHT"})
        self.assertEqual(g.anchor(self.lm, "a.py", 4), {"path": "a.py", "line": 4, "side": "RIGHT"})

    def test_old_side_deleted_and_context(self):
        self.assertEqual(g.anchor(self.lm, "a.py", 2, side="old"), {"path": "a.py", "line": 2, "side": "LEFT"})
        self.assertEqual(g.anchor(self.lm, "a.py", 3, side="old"), {"path": "a.py", "line": 3, "side": "LEFT"})
        self.assertEqual(g.anchor(self.lm, "gone.py", 1, side="old"), {"path": "gone.py", "line": 1, "side": "LEFT"})
        self.assertEqual(g.anchor(self.lm, "old.py", 10, side="old"), {"path": "new.py", "line": 10, "side": "LEFT"})

    def test_multiline_start_line(self):
        self.assertEqual(
            g.anchor(self.lm, "a.py", 3, start_line=2),
            {"path": "a.py", "line": 3, "side": "RIGHT", "start_line": 2, "start_side": "RIGHT"},
        )
        self.assertEqual(
            g.anchor(self.lm, "a.py", 2, side="old", start_line=1),
            {"path": "a.py", "line": 2, "side": "LEFT", "start_line": 1, "start_side": "LEFT"},
        )
        self.assertIsNone(g.anchor(self.lm, "a.py", 3, start_line=3))
        self.assertIsNone(g.anchor(self.lm, "a.py", 3, start_line=4))
        self.assertIsNone(g.anchor(self.lm, "a.py", 3, start_line=99))

    def test_outside_diff(self):
        self.assertIsNone(g.anchor(self.lm, "a.py", 99))
        self.assertIsNone(g.anchor(self.lm, "a.py", 99, side="old"))
        self.assertIsNone(g.anchor(self.lm, "missing.py", 1))


CTX = {"number": 7, "owner_repo": "owner/repo", "head_sha": "h"}


class BuildRequest(unittest.TestCase):
    def setUp(self):
        self.lm = g.line_map(DIFF)

    def test_inline_and_multiline(self):
        m, p, b = g.build_request(
            {"kind": "inline", "path": "a.py", "line": 3, "start_line": 2, "body": "fix"}, CTX, self.lm
        )
        self.assertEqual((m, p), ("POST", "repos/owner/repo/pulls/7/comments"))
        self.assertEqual(
            b,
            {
                "body": "fix",
                "commit_id": "h",
                "path": "a.py",
                "line": 3,
                "side": "RIGHT",
                "start_line": 2,
                "start_side": "RIGHT",
            },
        )

    def test_inline_old_side(self):
        _, _, b = g.build_request(
            {"kind": "inline", "path": "a.py", "line": 2, "side": "old", "body": "gone"}, CTX, self.lm
        )
        self.assertEqual(b["side"], "LEFT")
        self.assertEqual(b["line"], 2)

    def test_reply_general_reopen_edit(self):
        self.assertEqual(
            g.build_request({"kind": "reply", "comment_id": 12, "body": "ok"}, CTX, self.lm),
            ("POST", "repos/owner/repo/pulls/7/comments/12/replies", {"body": "ok"}),
        )
        self.assertEqual(
            g.build_request({"kind": "general", "body": "summary"}, CTX, self.lm),
            ("POST", "repos/owner/repo/issues/7/comments", {"body": "summary"}),
        )
        self.assertEqual(
            g.build_request({"kind": "reopen", "thread_id": "PRRT_1"}, CTX, self.lm),
            ("GRAPHQL", "unresolveReviewThread", {"threadId": "PRRT_1"}),
        )
        self.assertEqual(
            g.build_request({"kind": "edit", "comment_id": 12, "body": "new"}, CTX, self.lm),
            ("PATCH", "repos/owner/repo/pulls/comments/12", {"body": "new"}),
        )
        self.assertEqual(
            g.build_request({"kind": "edit", "comment_id": 15, "surface": "issue", "body": "new"}, CTX, self.lm),
            ("PATCH", "repos/owner/repo/issues/comments/15", {"body": "new"}),
        )

    def test_errors(self):
        with self.assertRaisesRegex(ValueError, "is not in the diff"):
            g.build_request({"kind": "inline", "path": "a.py", "line": 99, "body": "x"}, CTX, self.lm)
        with self.assertRaisesRegex(ValueError, "missing comment_id"):
            g.build_request({"kind": "reply", "body": "x"}, CTX, self.lm)
        with self.assertRaisesRegex(ValueError, "unknown kind: nope"):
            g.build_request({"kind": "nope"}, CTX, self.lm)


class FetchDiscussions(unittest.TestCase):
    def test_paginated_graphql_and_review_filtering(self):
        p1 = '{"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[{"id":"T1"}]}}}}}\n'
        p2 = '{"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[{"id":"T2"}]}}}}}'
        reviews = [
            [{"id": 1, "state": "PENDING", "body": "draft"}],
            [{"id": 2, "state": "COMMENTED", "body": "   "}, {"id": 3, "state": "CHANGES_REQUESTED", "body": "fix"}],
        ]
        issues = [[{"id": 4, "body": "hi"}]]
        with mock.patch.object(g, "gh", return_value=p1 + p2), mock.patch.object(
            g, "gh_json", side_effect=[issues, reviews]
        ):
            threads, got_issues, got_reviews = g.fetch_discussions("owner/repo", 7)
        self.assertEqual([t["id"] for t in threads], ["T1", "T2"])
        self.assertEqual(got_issues, [{"id": 4, "body": "hi"}])
        self.assertEqual(got_reviews, [{"id": 3, "state": "CHANGES_REQUESTED", "body": "fix"}])


if __name__ == "__main__":
    unittest.main()
