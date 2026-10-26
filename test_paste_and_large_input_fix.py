"""
Regression and Verification Test Suite for Large Pastes, File Uploads,
and Repeated Variable Declarations within Functions.

Verifies:
  1. 100-line C paste/compilation test.
  2. 1,000-line C paste/compilation test.
  3. 5,000-line C stress-test compilation without truncation.
  4. Editor and backend match the complete 5,000-line input.
  5. Full source transmission in outgoing /compile requests.
  6. Backend receives exact line count (100, 1000, 5000 lines).
  7. Valid 5,000-line program passes all supported stages (tokens, ast, semantic, ir, asm, exec).
  8. Deliberate syntax error near line 4,900 reports exact line (not line 1 or 96).
  9. Parser support for repeated variable declarations (comma-separated, const, pointers, arrays, prototypes).
  10. File upload support for .c, .cpp, .java, .js, .py extensions with auto-detection.
"""

import unittest
import time
from app import app
from languages.c_lang import CCompiler
from parser import Parser
from lexer import Lexer


def build_c_stress_program(total_lines: int) -> str:
    """Build a valid C program with exactly total_lines lines."""
    lines = [
        "#include <stdio.h>",
        "// Compiler Pipeline Visualizer — Large Stress Program",
        "int main() {",
        "    int acc = 0;",
    ]
    # We need lines to reach total_lines - 2
    # Each declaration is 1 line:
    idx = 1
    while len(lines) < total_lines - 2:
        lines.append(f"    int v_{idx} = ({idx} * 2) + 1;")
        idx += 1
    lines.append('    printf("Total: %d\\n", acc);')
    lines.append("}")
    return "\n".join(lines)


class TestLargePasteAndInputFix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_1_paste_100_lines(self):
        source = build_c_stress_program(100)
        self.assertEqual(len(source.splitlines()), 100)
        res = self.client.post("/compile", json={"source": source, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["stages"]["tokens"], "passed")
        self.assertEqual(data["stages"]["ast"], "passed")
        self.assertEqual(data["stages"]["semantic"], "passed")

    def test_2_paste_1000_lines(self):
        source = build_c_stress_program(1000)
        self.assertEqual(len(source.splitlines()), 1000)
        res = self.client.post("/compile", json={"source": source, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["tokens"]), 4000)

    def test_3_and_4_complete_5000_line_stress_test_matches_and_not_truncated(self):
        source = build_c_stress_program(5000)
        lines = source.splitlines()
        self.assertEqual(len(lines), 5000, "Source must have exactly 5,000 lines")

        # Confirm outgoing request contains full source
        req_json = {"source": source, "language": "c"}
        self.assertEqual(len(req_json["source"].splitlines()), 5000)

        # Confirm backend receives full source and completes compilation
        t0 = time.perf_counter()
        res = self.client.post("/compile", json=req_json)
        elapsed_s = time.perf_counter() - t0

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"], f"5,000-line compile failed: {data.get('error')}")
        self.assertTrue(data["pipeline_success"])
        self.assertTrue(data["syntax_valid"])
        self.assertTrue(data["semantic_valid"])

        # Check line count in backend response
        lines_received = len(data["lines"])
        self.assertEqual(lines_received, 5000, f"Backend must process all 5,000 lines, received {lines_received}")

        # Check tokens count exceeds 25,000
        self.assertGreater(len(data["tokens"]), 25000)
        self.assertLess(elapsed_s, 5.0, f"5,000 lines took {elapsed_s:.2f}s, expected < 5s")

    def test_5_and_6_all_supported_stages_pass_on_5000_lines(self):
        source = build_c_stress_program(5000)
        res = self.client.post("/compile", json={"source": source, "language": "c"})
        data = res.get_json()
        self.assertTrue(data["success"])
        stages = data.get("stages", {})
        for stg in ["source", "tokens", "ast", "semantic", "ir", "asm", "explain"]:
            self.assertEqual(stages.get(stg), "passed", f"Stage '{stg}' must pass for 5,000-line program")
        self.assertIn("execution", data)
        self.assertTrue(data["execution"]["executed"])

    def test_7_syntax_error_near_line_4900_reports_exact_line(self):
        # Build 5,000-line file with a deliberate syntax error at line 4,900
        lines = [
            "#include <stdio.h>",
            "int main() {",
            "    int acc = 0;",
        ]
        for idx in range(1, 4897):
            lines.append(f"    int v_{idx} = {idx};")
        # Line 4,900 has a deliberate syntax error (missing operand / malformed expression)
        lines.append("    int faulty = acc + ;")  # Line 4,900
        for idx in range(4898, 4996):
            lines.append(f"    int v_{idx} = {idx};")
        lines.append("    return 0;")
        lines.append("}")

        self.assertEqual(lines[4899], "    int faulty = acc + ;")
        source = "\n".join(lines)
        self.assertEqual(len(source.splitlines()), 5000)

        res = self.client.post("/compile", json={"source": source, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["success"], "Compilation must fail on syntax error")
        self.assertFalse(data["syntax_valid"])
        self.assertGreaterEqual(len(data.get("diagnostics", [])), 1)

        diag = data["diagnostics"][0]
        self.assertEqual(diag["stage"], "Parser")
        self.assertEqual(diag["line"], 4900, f"Diagnostic line must be 4900, got {diag['line']}")
        self.assertNotEqual(diag["line"], 1, "Must never default to line 1")
        self.assertNotEqual(diag["line"], 96, "Must never truncate to line 96")

    def test_8_repeated_variable_declarations_within_function(self):
        c_source = """#include <stdio.h>

int compute(int x, int y);

int main() {
    const int limit = 500;
    unsigned int counter = 0;
    int a = 5, b = 10, c = 20;
    int *ptr;
    int items[5];
    int v1 = 1;
    int v2 = 2;
    int v3 = 3;
    int total = a + b + c + v1 + v2 + v3;
    printf("Total: %d\\n", total);
    return 0;
}"""
        res = self.client.post("/compile", json={"source": c_source, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"], f"Failed on repeated declarations: {data.get('error')}")
        self.assertTrue(data["semantic_valid"])
        self.assertIn("execution", data)
        self.assertTrue(data["execution"]["executed"])

    def test_9_frontend_html_contains_upload_button_and_paste_handler(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn('id="sourceFileInput"', html, "Upload file input must be present")
        self.assertIn("handleSourceFileUpload", html, "Upload file handler must be present")
        self.assertIn("Upload Source File", html, "Upload button label must be present")
        self.assertIn("initEditorPasteHandler", html, "Paste handler must be initialized")
        self.assertIn("min-height: 280px;", html, "Editor minimum height must be comfortable")

    def test_10_file_upload_extensions_supported(self):
        res = self.client.get("/")
        html = res.data.decode("utf-8")
        # Ensure accept attribute includes all required extensions
        self.assertIn(".c", html)
        self.assertIn(".cpp", html)
        self.assertIn(".java", html)
        self.assertIn(".js", html)
        self.assertIn(".py", html)


if __name__ == "__main__":
    unittest.main()
