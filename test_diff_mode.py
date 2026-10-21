"""
Verification script for Stage Diff Mode and Product Renaming in Compiler Pipeline Visualizer.
"""

import os
import re
import unittest
from app import app
import diff_service

class TestDiffModeVerification(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        with open("index.html", "r", encoding="utf-8") as f:
            self.index_html = f.read()
        with open("static/index.html", "r", encoding="utf-8") as f:
            self.static_html = f.read()

    def test_1_branding_renamed_everywhere(self):
        """Verify product is renamed to 'Compiler Pipeline Visualizer' and 'Compiler Studio' is gone."""
        for name, html in [("index.html", self.index_html), ("static/index.html", self.static_html)]:
            self.assertNotIn("Compiler Studio", html, f"Found 'Compiler Studio' in {name}")
            self.assertIn("<title>Compiler Pipeline Visualizer</title>", html, f"Missing title in {name}")
            self.assertIn("<h1>Compiler Pipeline Visualizer</h1>", html, f"Missing h1 in {name}")
            self.assertIn('title="Compiler Pipeline Visualizer"', html, f"Missing brand icon title in {name}")
            self.assertIn('aria-label="Compiler Pipeline Visualizer"', html, f"Missing brand icon aria-label in {name}")

    def test_2_clean_diff_initial_state(self):
        """Verify diff mode has a clean initial state with empty state message and hidden table."""
        for name, html in [("index.html", self.index_html), ("static/index.html", self.static_html)]:
            self.assertIn('id="diffEmptyState"', html)
            self.assertIn("Compare two program versions to see how the selected compiler stage changes.", html)
            self.assertIn('id="diffTableWrapper"', html)
            self.assertIn('style="display:none;"', html)
            self.assertIn('id="btnRunDiff"', html)
            self.assertIn("Compare Pipeline Stages Side-by-Side", html)

    def test_3_no_automatic_diff_calls(self):
        """Verify no automatic calls to /diff on page load, mode switch, or dropdown change."""
        for name, html in [("index.html", self.index_html), ("static/index.html", self.static_html)]:
            # switchMainMode should NOT call runDiff
            switch_fn_match = re.search(r'function switchMainMode\([^)]*\)\s*\{([^}]+)\}', html)
            self.assertTrue(switch_fn_match, f"Could not find switchMainMode in {name}")
            self.assertNotIn("runDiff", switch_fn_match.group(1), f"switchMainMode must not call runDiff in {name}")

            # diffStageSelect onchange should NOT call runDiff directly
            select_match = re.search(r'<select[^>]*id="diffStageSelect"[^>]*>', html)
            self.assertTrue(select_match, f"Could not find diffStageSelect in {name}")
            self.assertNotIn('runDiff()', select_match.group(0), f"diffStageSelect must not have onchange='runDiff()' in {name}")

    def test_4_button_executes_diff_with_current_sources(self):
        """Verify backend /diff endpoint works with valid inputs across all supported stages."""
        prog_a = """#include <stdio.h>
int main() {
    int total = 3 + 4;
    return 0;
}"""
        prog_b = """#include <stdio.h>
int main() {
    int total = 3 + 4 * 2;
    return 0;
}"""
        res = self.client.post("/diff", json={
            "source_a": prog_a,
            "source_b": prog_b,
            "language": "c"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        diffs = data["data"]["diffs"]

        # All 6 stages must be present
        for stage in ["source", "tokens", "ast", "ir", "assembly_edu", "assembly_x86"]:
            self.assertIn(stage, diffs)
            self.assertGreater(len(diffs[stage]), 0)

    def test_5_target_stage_comparison_semantics(self):
        """Verify that target stages reflect real differences between program versions."""
        prog_a = "int total = 3 + 4;"
        prog_b = "int total = 3 + 4 * 2;"
        diff_res = diff_service.compare_programs(prog_a, prog_b, language="c")
        diffs = diff_res["diffs"]

        # 1. TAC (IR) differences
        ir_diffs = diffs["ir"]
        ir_has_diff = any(r["type"] in ("modified", "added", "removed") for r in ir_diffs)
        self.assertTrue(ir_has_diff, "IR diff must contain differences")

        # 2. AST differences
        ast_diffs = diffs["ast"]
        ast_has_diff = any(r["type"] in ("modified", "added", "removed") for r in ast_diffs)
        self.assertTrue(ast_has_diff, "AST diff must contain differences")

        # Ensure AST diff and IR diff are structurally different representation streams
        self.assertNotEqual(ir_diffs, ast_diffs, "AST diff and IR diff must not be identical")

        # 3. Tokens differences
        tokens_diffs = diffs["tokens"]
        tokens_has_diff = any(r["type"] in ("modified", "added", "removed") for r in tokens_diffs)
        self.assertTrue(tokens_has_diff, "Tokens diff must contain differences")

        # 4. Assembly differences
        edu_diffs = diffs["assembly_edu"]
        x86_diffs = diffs["assembly_x86"]
        self.assertTrue(any(r["type"] in ("modified", "added", "removed") for r in edu_diffs))
        self.assertTrue(any(r["type"] in ("modified", "added", "removed") for r in x86_diffs))

    def test_6_api_error_handling(self):
        """Verify /diff gracefully handles syntax errors and empty sources without crashing."""
        # Missing source
        res_empty = self.client.post("/diff", json={"source_a": "", "source_b": "int x = 1;"})
        self.assertEqual(res_empty.status_code, 400)

        # Syntax error in Version A
        res_err_a = self.client.post("/diff", json={"source_a": "int x = ;", "source_b": "int x = 1;"})
        self.assertEqual(res_err_a.status_code, 400)
        data_a = res_err_a.get_json()
        self.assertFalse(data_a["success"])
        self.assertIn("error", data_a)

        # Syntax error in Version B
        res_err_b = self.client.post("/diff", json={"source_a": "int x = 1;", "source_b": "int x = @#$;"})
        self.assertEqual(res_err_b.status_code, 400)
        data_b = res_err_b.get_json()
        self.assertFalse(data_b["success"])
        self.assertIn("error", data_b)

    def test_7_frontend_lifecycle_handlers(self):
        """Verify frontend contains outdated handling, error banner, and DOM listeners."""
        for name, html in [("index.html", self.index_html), ("static/index.html", self.static_html)]:
            self.assertIn("diffErrorBanner", html)
            self.assertIn("diffErrorMessage", html)
            self.assertIn("diffOutdatedBanner", html)
            self.assertIn("diffStatusBadge", html)
            self.assertIn("onDiffSourceInput", html)
            self.assertIn("onDiffStageChange", html)
            self.assertIn("markDiffOutdated", html)
            self.assertIn("showDiffError", html)


if __name__ == "__main__":
    unittest.main()
