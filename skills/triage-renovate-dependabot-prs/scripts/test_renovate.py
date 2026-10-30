import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import renovate as r


def diff(path, old, new):
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-{old}\n+{new}\n"


class Bump(unittest.TestCase):
    def test_pairs(self):
        cases = [
            ("package.json", '    "eslint": "^9.1.0",', '    "eslint": "^10.0.0",', "major"),
            ("Cargo.toml", 'serde = "0.4.1"', 'serde = "0.5.0"', "major"),
            ("go.mod", "\tgithub.com/x/y v1.2.3", "\tgithub.com/x/y v1.3.0", "minor"),
            ("pyproject.toml", '    "ruff>=0.5.0",', '    "ruff>=0.5.1",', "patch"),
            ("Dockerfile", "FROM node:20@sha256:aaa", "FROM node:20@sha256:bbb", "digest"),
        ]
        for path, old, new, want in cases:
            with self.subTest(path=path):
                (c,) = r.dep_changes(diff(path, old, new))
                self.assertEqual(c["bump"], want)

    def test_added_removed_unknown(self):
        d = "+++ b/package.json\n+    \"new\": \"1.0.0\",\n-    \"gone\": \"1.0.0\",\n"
        self.assertEqual([c["bump"] for c in r.dep_changes(d)], ["added", "removed"])
        self.assertEqual(r.bump("latest", "next"), "unknown")


class Redundancy(unittest.TestCase):
    CH = [{"file": "package.json", "name": "eslint", "old": "^9.0.0", "new": "^10.0.0", "bump": "major"}]

    def test_already_in_head(self):
        head = {"package.json": '"eslint": "^10.0.0"\n'}
        self.assertEqual(r.redundancy(self.CH, head), "payload already in HEAD")

    def test_dep_gone(self):
        self.assertEqual(r.redundancy(self.CH, {"package.json": '"other": "1"\n'}),
                         "target dep no longer exists in HEAD")

    def test_mixed(self):
        ch = self.CH + [{"file": "package.json", "name": "vite", "old": "^5.0.0", "new": "^6.0.0", "bump": "major"}]
        head = {"package.json": '"eslint": "^10.0.0"\n"other": "1"\n'}
        self.assertIsNone(r.redundancy(ch, head))


if __name__ == "__main__":
    unittest.main()
