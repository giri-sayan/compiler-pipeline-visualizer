"""
Regression test suite for Source Workspace line-number gutter synchronization.
Verifies:
  1. A short program with 7 lines.
  2. A 100-line program.
  3. The complete 5,000-line stress-test program with scroll synchronization.
  4. Blank lines and trailing newline handling.
  5. Pasting a new program after a large program.
  6. Loading a file and switching presets.
  7. A syntax error near line 4,900 and verifying Jump to Error selects the correct line.
  8. Mirror synchronization between index.html and static/index.html.
"""

import filecmp
import json
import os
import subprocess
import unittest
from app import app


class TestGutterLineNumbers(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_1_html_mirrors_identical(self):
        """index.html and static/index.html must be strictly bit-for-bit identical."""
        self.assertTrue(
            filecmp.cmp("index.html", "static/index.html", shallow=False),
            "index.html and static/index.html must be identical",
        )

    def test_2_css_gutter_structure_in_html(self):
        """Both HTML files must contain the absolute gutter and responsive textarea CSS."""
        for path in ["index.html", "static/index.html"]:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn(".code-editor-wrapper", content)
            self.assertIn("position: absolute;", content)
            self.assertIn("line-numbers-gutter", content)
            self.assertIn("overflow-y: hidden;", content)
            self.assertIn("jumpToLocation", content)
            self.assertIn("highlightOffendingSource", content)
            self.assertIn("updateLineNumbers", content)

    def test_3_browser_dom_seven_tests_in_edge(self):
        """
        Executes headless Edge to verify the live DOM and layout
        in the actual browser engine across all 7 scenarios specified in the requirements.
        """
        harness_js = os.path.join(os.path.dirname(__file__), "_test_browser_gutter_harness.js")
        if not os.path.exists(harness_js):
            self.skipTest("Browser gutter harness script not found")

        edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if not os.path.exists(edge_exe):
            self.skipTest("msedge.exe not found on system")

        res = subprocess.run(["node", harness_js], capture_output=True, text=True, timeout=20)
        self.assertEqual(res.returncode, 0, f"Node browser harness failed: {res.stderr}")
        out = json.loads(res.stdout.strip())

        # Verification 1: Short 7-line program
        t1 = out["test1_7lines"]
        self.assertEqual(t1["lineCount"], 7)
        self.assertEqual(t1["gutterDivs"], 7)
        self.assertEqual(t1["gutterFirst"], "1")
        self.assertEqual(t1["gutterLast"], "7")
        self.assertEqual(t1["pillText"], "7 lines")

        # Verification 2: 100-line program
        t2 = out["test2_100lines"]
        self.assertEqual(t2["lineCount"], 100)
        self.assertEqual(t2["gutterDivs"], 100)
        self.assertEqual(t2["gutterFirst"], "1")
        self.assertEqual(t2["gutterLast"], "100")
        self.assertEqual(t2["pillText"], "100 lines")

        # Verification 3: 5,000-line program with bottom scrolling
        t3 = out["test3_5000lines"]
        self.assertEqual(t3["totalLines"], 5000)
        self.assertEqual(t3["gutterDivs"], 5000)
        self.assertGreater(t3["gutterScrollTop"], 50000)
        self.assertEqual(t3["editorScrollTop"], t3["gutterScrollTop"])
        self.assertTrue(t3["scrolledToFinal"], "Visible gutter numbers at bottom must reach line 5000")
        self.assertNotEqual(t3["visibleLast"], "27", "Must never remain frozen at line 27")

        # Verification 4: Blank lines and trailing newline
        t4 = out["test4_blankAndTrailing"]
        self.assertEqual(t4["totalLines"], 4)
        self.assertEqual(t4["gutterDivs"], 4)
        self.assertEqual(t4["lastGutterText"], "4")

        # Verification 5: Pasting short after large program
        t5 = out["test5_pasteAfterLarge"]
        self.assertEqual(t5["totalLines"], 2)
        self.assertEqual(t5["gutterDivs"], 2)
        self.assertEqual(t5["gutterLast"], "2")
        self.assertEqual(t5["pillText"], "2 lines")

        # Verification 6: Switching presets
        t6 = out["test6_switchPreset"]
        self.assertEqual(t6["gutterDivs"], t6["totalLines"])
        self.assertEqual(t6["gutterLast"], str(t6["totalLines"]))

        # Verification 7: Syntax error near line 4,900 and jump to location
        t7 = out["test7_jumpTo4900"]
        self.assertIn("gutter-error-line", t7["highlightedChildClass"])
        self.assertTrue(t7["scrollSynchronized"])
        self.assertGreater(t7["gutterScrollTop"], 80000)

    def test_4_backend_compilation_with_exact_line_match(self):
        """Verify the compiler processes all 5,000 lines without mismatch."""
        lines = [
            "#include <stdio.h>",
            "int main() {",
            "    int total = 0;",
        ]
        for i in range(1, 4996):
            lines.append(f"    int value_{i} = {i % 10};")
        lines.append("    total = value_1 + value_2;")
        lines.append('    printf("Total: %d\\n", total);')
        lines.append("    return 0;")
        lines.append("}")

        source = "\n".join(lines)
        self.assertEqual(len(source.splitlines()), 5002)

        res = self.client.post("/compile", json={"source": source, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["execution"]["output"].strip(), "Total: 3")
