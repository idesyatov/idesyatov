#!/usr/bin/env python3
"""Offline tests for the pure helpers in update_languages.py (no network)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import update_languages as ul


class FmtBytes(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(ul.fmt_bytes(0), "0 B")
        self.assertEqual(ul.fmt_bytes(1023), "1023 B")

    def test_kb(self):
        self.assertEqual(ul.fmt_bytes(1024), "1 KB")
        self.assertEqual(ul.fmt_bytes(2048), "2 KB")

    def test_mb(self):
        self.assertEqual(ul.fmt_bytes(1024 ** 2), "1.0 MB")
        self.assertEqual(ul.fmt_bytes(int(1.5 * 1024 ** 2)), "1.5 MB")


class BuildBlock(unittest.TestCase):
    def test_pct_and_names(self):
        out = ul.build_block({"Go": 720, "Python": 280})
        self.assertIn("Go", out)
        self.assertIn("72%", out)
        self.assertIn("28%", out)

    def test_limited_to_top(self):
        agg = {f"L{i}": (10 - i) for i in range(8)}
        out = ul.build_block(agg)
        self.assertEqual(out.count('y="'), ul.TOP)

    def test_name_is_escaped(self):
        out = ul.build_block({"C<>&": 100})
        self.assertNotIn("C<>&", out)
        self.assertIn("C&lt;&gt;&amp;", out)


class ReplaceMarker(unittest.TestCase):
    def test_replaces_between_markers(self):
        svg = "a<!-- X:START -->OLD<!-- X:END -->b"
        self.assertEqual(
            ul.replace_marker(svg, "X", "NEW"),
            "a<!-- X:START -->NEW<!-- X:END -->b",
        )

    def test_value_treated_literally(self):
        # backreference-looking text must survive verbatim, not be expanded
        svg = "<!-- X:START -->old<!-- X:END -->"
        out = ul.replace_marker(svg, "X", r"\1\g<0>&")
        self.assertIn(r"\1\g<0>&", out)


class BuildStats(unittest.TestCase):
    def test_rows(self):
        orig = ul.search_count
        ul.search_count = lambda kind, query: 42
        try:
            out = ul.build_stats({"Go": 1024, "Python": 1024})
        finally:
            ul.search_count = orig
        self.assertIn("languages", out)   # row label
        self.assertIn("2 KB", out)        # Σ code = fmt_bytes(2048)
        self.assertIn("42", out)          # mocked search counts


if __name__ == "__main__":
    unittest.main()
