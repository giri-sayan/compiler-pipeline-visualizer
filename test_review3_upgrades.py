"""
Test Suite for Review 3 Upgrades:
  1. Large-input processing (up to 5,000 lines) & linear scaling.
  2. Multi-language frontends: C, C++, Java, Python, JavaScript, Toy.
  3. Precise line/column diagnostics & typo suggestions across all frontends.
  4. Safe Sandboxed Execution (TAC VM + native runners) capturing stdout and exit codes.
  5. Language specifications & Diff Mode multi-language interoperability.
  6. Dark theme support in frontend DOM.
"""

import unittest
import time
from app import app
from languages import get_compiler, LANGUAGE_SPECS
from tac_vm import TACVirtualMachine


class TestReview3Upgrades(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    # ================= 1. Large-Input Reliability & Benchmarks =================

    def test_large_input_100_lines(self):
        body = "\n".join(f"    int v_{i} = {i} * 2 + 1;" for i in range(1, 95))
        source = f"""#include <stdio.h>
int main() {{
    int total = 0;
{body}
    return 0;
}}"""
        t0 = time.perf_counter()
        res = self.client.post("/compile", json={"source": source, "language": "c"})
        elapsed = time.perf_counter() - t0

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertLess(elapsed, 2.0, f"100 lines took {elapsed:.2f}s, expected < 2.0s")
        self.assertIn("execution", data)

    def test_large_input_1000_lines(self):
        body = "\n".join(f"    int v_{i} = {i} * 2 + 1;" for i in range(1, 995))
        source = f"""#include <stdio.h>
int main() {{
    int total = 0;
{body}
    return 0;
}}"""
        t0 = time.perf_counter()
        res = self.client.post("/compile", json={"source": source, "language": "c"})
        elapsed = time.perf_counter() - t0

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertLess(elapsed, 3.0, f"1,000 lines took {elapsed:.2f}s, expected < 3.0s")

    def test_large_input_3000_lines(self):
        body = "\n".join(f"    int v_{i} = {i} * 2 + 1;" for i in range(1, 2995))
        source = f"""#include <stdio.h>
int main() {{
    int total = 0;
{body}
    return 0;
}}"""
        t0 = time.perf_counter()
        res = self.client.post("/compile", json={"source": source, "language": "c"})
        elapsed = time.perf_counter() - t0

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertLess(elapsed, 5.0, f"3,000 lines took {elapsed:.2f}s, expected < 5.0s")

    def test_large_input_5000_lines(self):
        body = "\n".join(f"    int v_{i} = {i} * 2 + 1;" for i in range(1, 4995))
        source = f"""#include <stdio.h>
int main() {{
    int total = 0;
{body}
    return 0;
}}"""
        t0 = time.perf_counter()
        res = self.client.post("/compile", json={"source": source, "language": "c"})
        elapsed = time.perf_counter() - t0

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertLess(elapsed, 8.0, f"5,000 lines took {elapsed:.2f}s, expected < 8.0s")
        # Verify tokens count exceeds 30,000 without crashing
        self.assertGreater(len(data["tokens"]), 30000)

    def test_input_limit_exceeded(self):
        # 10,005 lines should be rejected safely
        source = "int x = 1;\n" * 10005
        res = self.client.post("/compile", json={"source": source, "language": "c"})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("exceeds maximum limit", data["error"])

    # ================= 2. Multi-Language Frontends =================

    def test_c_compiler_and_execution(self):
        source = """#include <stdio.h>
int main() {
    int x = 10;
    int y = 25;
    int total = x + y;
    printf("Total = %d\\n", total);
    return 0;
}"""
        res = self.client.post("/compile", json={"source": source, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("Total = 35", data["execution"]["output"])
        self.assertEqual(data["execution"]["exit_code"], 0)

    def test_cpp_compiler_and_execution(self):
        source = """#include <iostream>
using namespace std;

class Adder {
public:
    int calculate(int a, int b) {
        return a + b;
    }
};

int main() {
    Adder adder;
    int total = adder.calculate(30, 12);
    cout << "CPP Sum = " << total << endl;
    return 0;
}"""
        res = self.client.post("/compile", json={"source": source, "language": "cpp"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("CPP Sum = 42", data["execution"]["output"])
        self.assertEqual(data["stages"]["tokens"], "passed")
        self.assertEqual(data["stages"]["ast"], "passed")
        self.assertEqual(data["stages"]["semantic"], "passed")
        self.assertEqual(data["stages"]["ir"], "passed")
        self.assertEqual(data["stages"]["asm"], "passed")

    def test_java_compiler_and_execution(self):
        source = """public class Main {
    public static void main(String[] args) {
        int base = 20;
        int factor = 4;
        int product = base * factor + 5;
        System.out.println("Java Value: " + product);
    }
}"""
        res = self.client.post("/compile", json={"source": source, "language": "java"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("Java Value: 85", data["execution"]["output"])
        self.assertEqual(data["stages"]["ast"], "passed")
        self.assertEqual(data["stages"]["ir"], "passed")

    def test_python_compiler_and_execution(self):
        source = """def get_multiplier(n):
    return n * 3

def main():
    val = get_multiplier(7)
    print("Python Computed:", val)

main()"""
        res = self.client.post("/compile", json={"source": source, "language": "python"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("Python Computed: 21", data["execution"]["output"])
        self.assertEqual(data["stages"]["ast"], "passed")

    def test_javascript_compiler_and_execution(self):
        source = """function multiply(a, b) {
    let result = a * b;
    return result;
}

let x = 8;
let y = 6;
let total = multiply(x, y);
console.log("JS Multiplied:", total);"""
        res = self.client.post("/compile", json={"source": source, "language": "js"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("JS Multiplied: 48", data["execution"]["output"])

    def test_toy_compiler_and_execution(self):
        source = """a = 15
b = 25
total = a + b * 2"""
        res = self.client.post("/compile", json={"source": source, "language": "toy"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["execution"]["exit_code"], 0)

    # ================= 3. Precise Diagnostics & Typo Suggestions =================

    def test_cpp_typo_coutt(self):
        source = """#include <iostream>
using namespace std;
int main() {
    coutt << "Hello" << endl;
    return 0;
}"""
        res = self.client.post("/compile", json={"source": source, "language": "cpp"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertEqual(diag["line"], 4)
        self.assertIn("cout", diag["message"])

    def test_cpp_missing_main_entry_point(self):
        source = """#include <iostream>
using namespace std;
void helper() {
    cout << "No main" << endl;
}"""
        res = self.client.post("/compile", json={"source": source, "language": "cpp"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertIn("main", diag["message"].lower())

    def test_java_typo_println(self):
        source = """public class Main {
    public static void main(String[] args) {
        System.out.prntln("Hello");
    }
}"""
        res = self.client.post("/compile", json={"source": source, "language": "java"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertEqual(diag["line"], 3)
        self.assertIn("println", diag["message"])

    def test_java_missing_main_entry_point(self):
        source = """public class Main {
    public void start() {
        System.out.println("Hello");
    }
}"""
        res = self.client.post("/compile", json={"source": source, "language": "java"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertIn("public static void main", diag["message"])

    def test_python_typo_pirnt(self):
        source = """pirnt("Typo error")"""
        res = self.client.post("/compile", json={"source": source, "language": "python"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertEqual(diag["line"], 1)
        self.assertIn("print", diag["message"])

    def test_js_typo_console(self):
        source = """conosle.log("Typo error");"""
        res = self.client.post("/compile", json={"source": source, "language": "js"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertEqual(diag["line"], 1)
        self.assertIn("console", diag["message"])

    # ================= 4. Safe TAC Virtual Machine Limits =================

    def test_tac_vm_step_limit(self):
        # Create an infinite TAC loop: Label L0 -> goto L0
        infinite_ir = {
            "quadruples": [
                {"op": "LABEL", "arg1": None, "arg2": None, "result": "L0"},
                {"op": "GOTO", "arg1": None, "arg2": None, "result": "L0"}
            ]
        }
        vm = TACVirtualMachine(infinite_ir, max_steps=500)
        res = vm.run()
        self.assertTrue(res["executed"])
        self.assertFalse(res["success"])
        self.assertIn("limit (500) exceeded", res["output"])

    # ================= 5. Endpoints & Diff Interoperability =================

    def test_languages_endpoint(self):
        res = self.client.get("/languages")
        self.assertEqual(res.status_code, 200)
        specs = res.get_json()
        for lang in ["c", "cpp", "java", "python", "js", "toy"]:
            self.assertIn(lang, specs)
            self.assertIn("name", specs[lang])
            self.assertIn("features", specs[lang])
            self.assertIn("limitations", specs[lang])

    def test_multi_language_diff(self):
        # Python diff
        py_a = "x = 10\nprint(x)"
        py_b = "x = 10\ny = 20\nprint(x + y)"
        res = self.client.post("/diff", json={"source_a": py_a, "source_b": py_b, "language": "python"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        diffs = data["data"]["diffs"]
        self.assertIn("ir", diffs)
        self.assertIn("ast", diffs)

    # ================= 6. Frontend Theme & Invariants =================

    def test_theme_toggle_elements_in_html(self):
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn('id="btnThemeToggle"', html)
        self.assertIn(':root[data-theme="dark"]', html)
        self.assertIn('initTheme', html)
        self.assertIn('toggleTheme', html)
        self.assertIn('id="languageSpecsModal"', html)
        self.assertIn('id="stageExec"', html)
        self.assertIn('id="programTerminalOutput"', html)

    def test_theme_tokens_present_in_html(self):
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()
        # Ensure central tokens are defined
        for token in [
            "--ast-cat-prog-bg", "--ast-cat-prog-val",
            "--ast-cat-func-bg", "--ast-cat-func-val",
            "--ast-cat-decl-bg", "--ast-cat-decl-val",
            "--ast-cat-assign-bg", "--ast-cat-assign-val",
            "--ast-cat-ctrl-bg", "--ast-cat-ctrl-val",
            "--ast-cat-cond-bg", "--ast-cat-cond-val",
            "--ast-diff-a-bg", "--ast-diff-a-val",
            "--ast-diff-b-bg", "--ast-diff-b-val",
            "--explainer-takeaway-bg", "--explainer-takeaway-text",
            "--diff-row-added-bg", "--diff-row-added-text",
            "--diff-row-removed-bg", "--diff-row-removed-text",
            "--gutter-error-bg", "--gutter-error-text",
            "--chip-error-bg", "--chip-error-text"
        ]:
            self.assertIn(token, html, f"Missing token {token}")

    def test_wcag_aa_contrast_for_all_ast_nodes(self):
        import re

        def hex_to_rgb(hex_code):
            hex_code = hex_code.lstrip("#")
            return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

        def relative_luminance(rgb):
            def channel_lum(c):
                s = c / 255.0
                return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
            r, g, b = [channel_lum(c) for c in rgb]
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        def contrast_ratio(hex1, hex2):
            l1 = relative_luminance(hex_to_rgb(hex1))
            l2 = relative_luminance(hex_to_rgb(hex2))
            return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()

        # Check light theme AST nodes
        for cat in ["prog", "func", "decl", "assign", "ret", "inc", "call", "op", "ctrl", "cond", "then", "else", "num", "id", "str"]:
            bg_match = re.search(rf"--ast-cat-{cat}-bg:\s*(#[0-9a-fA-F]{{6}})", html)
            typ_match = re.search(rf"--ast-cat-{cat}-type:\s*(#[0-9a-fA-F]{{6}})", html)
            val_match = re.search(rf"--ast-cat-{cat}-val:\s*(#[0-9a-fA-F]{{6}})", html)
            self.assertTrue(bg_match and typ_match and val_match, f"Could not find tokens for category {cat}")
            bg, typ, val = bg_match.group(1), typ_match.group(1), val_match.group(1)
            cr_type = contrast_ratio(typ, bg)
            cr_val = contrast_ratio(val, bg)
            self.assertGreaterEqual(cr_type, 4.5, f"Light category {cat} type contrast {cr_type:.2f} < 4.5")
            self.assertGreaterEqual(cr_val, 4.5, f"Light category {cat} val contrast {cr_val:.2f} < 4.5")

        # Check dark theme Explainer Takeaway
        self.assertIn("--explainer-takeaway-text: #E2E8F0;", html)
        self.assertIn("--explainer-takeaway-bg: #172033;", html)
        cr_explainer_dark = contrast_ratio("#E2E8F0", "#172033")
        self.assertGreaterEqual(cr_explainer_dark, 7.0, f"Dark Explainer Takeaway contrast {cr_explainer_dark:.2f} < 7.0")

    def test_static_index_html_in_sync(self):
        import filecmp
        self.assertTrue(
            filecmp.cmp("index.html", "static/index.html", shallow=False),
            "index.html and static/index.html are out of sync!"
        )


class TestLanguageSwitchingAndPresets(unittest.TestCase):
    """
    Automated regression tests covering:
      1. Switching from C to Java loads valid Java code and Java presets.
      2. Switching from Java to Python loads valid Python code and Python presets.
      3. Switching between all supported languages updates preset list correctly.
      4. Changing presets loads expected source code.
      5. Valid examples pass supported frontend's validation.
      6. Invalid examples produce appropriate language-specific diagnostics.
      7. C code is never accidentally processed as Java, Java never processed as C.
      8. Changing languages clears previous diagnostics and compilation outputs.
      9. Editing source code and running again updates results.
      10. All existing pipeline and diff tests continue to pass.
    """
    def setUp(self):
        self.client = app.test_client()

    def test_switch_c_to_java_presets_and_code(self):
        res = self.client.get("/presets")
        self.assertEqual(res.status_code, 200)
        presets = res.get_json()

        # Java default preset exists and contains valid Java code
        self.assertIn("java_complete", presets)
        java_preset = presets["java_complete"]
        self.assertEqual(java_preset["language"], "java")
        self.assertIn("public class Main", java_preset["source"])
        self.assertIn("System.out.println", java_preset["source"])

        # Compile Java default code with Java compiler
        comp_res = self.client.post("/compile", json={"source": java_preset["source"], "language": "java"})
        self.assertEqual(comp_res.status_code, 200)
        data = comp_res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["stages"]["ast"], "passed")
        self.assertEqual(data["stages"]["ir"], "passed")
        self.assertIn("Java Computed Result", data["execution"]["output"])

    def test_switch_java_to_python_presets_and_code(self):
        res = self.client.get("/presets")
        self.assertEqual(res.status_code, 200)
        presets = res.get_json()

        # Python default preset exists and contains valid Python code
        self.assertIn("python_complete", presets)
        py_preset = presets["python_complete"]
        self.assertEqual(py_preset["language"], "python")
        self.assertIn("def ", py_preset["source"])
        self.assertIn("print(", py_preset["source"])

        # Compile Python default code with Python compiler
        comp_res = self.client.post("/compile", json={"source": py_preset["source"], "language": "python"})
        self.assertEqual(comp_res.status_code, 200)
        data = comp_res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["stages"]["tokens"], "passed")
        self.assertEqual(data["stages"]["ast"], "passed")

    def test_all_supported_languages_preset_isolation(self):
        res = self.client.get("/presets")
        self.assertEqual(res.status_code, 200)
        presets = res.get_json()

        supported_langs = ["c", "cpp", "java", "python", "js", "toy"]
        for lang in supported_langs:
            lang_presets = [p for p in presets.values() if p["language"] == lang]
            self.assertGreaterEqual(len(lang_presets), 4, f"Language {lang} should have at least 4 presets")

            # Check that every preset in lang_presets is strictly labeled for lang
            for lp in lang_presets:
                self.assertEqual(lp["language"], lang)

    def test_changing_presets_loads_expected_source_code(self):
        res = self.client.get("/presets")
        presets = res.get_json()

        # Verify arithmetic preset in C
        self.assertIn("c_precedence", presets)
        self.assertIn("2 + 3 * 4", presets["c_precedence"]["source"])

        # Verify variables preset in C++
        self.assertIn("cpp_variables", presets)
        self.assertIn("double ratio", presets["cpp_variables"]["source"])

        # Verify while loop preset in Python
        self.assertIn("python_loops", presets)
        self.assertIn("while i <= 5:", presets["python_loops"]["source"])

        # Verify functions preset in JS
        self.assertIn("js_functions", presets)
        self.assertIn("function multiply", presets["js_functions"]["source"])

    def test_valid_examples_pass_frontend_validation(self):
        defaults = {
            "c": "c_complete",
            "cpp": "cpp_complete",
            "java": "java_complete",
            "python": "python_complete",
            "js": "js_complete",
            "toy": "toy_pipeline"
        }
        res = self.client.get("/presets")
        presets = res.get_json()

        for lang, preset_key in defaults.items():
            self.assertIn(preset_key, presets)
            source = presets[preset_key]["source"]
            comp_res = self.client.post("/compile", json={"source": source, "language": lang})
            self.assertEqual(comp_res.status_code, 200, f"Preset {preset_key} failed HTTP status")
            data = comp_res.get_json()
            self.assertTrue(data["success"], f"Default preset {preset_key} for {lang} failed compilation: {data.get('error')} {data.get('diagnostics')}")
            self.assertEqual(data["stages"]["tokens"], "passed")
            self.assertEqual(data["stages"]["ast"], "passed")

    def test_invalid_examples_produce_accurate_language_diagnostics(self):
        invalid_cases = [
            ("c", "c_semantic_error", "rintf", "printf"),
            ("cpp", "cpp_error", "coutt", "cout"),
            ("java", "java_error", "prntln", "println"),
            ("python", "python_error", "pirnt", "print"),
            ("js", "js_error", "conosle", "console"),
        ]
        res = self.client.get("/presets")
        presets = res.get_json()

        for lang, preset_key, typo_term, expected_hint in invalid_cases:
            self.assertIn(preset_key, presets)
            source = presets[preset_key]["source"]
            comp_res = self.client.post("/compile", json={"source": source, "language": lang})
            data = comp_res.get_json()
            self.assertFalse(data["success"], f"Invalid preset {preset_key} should have failed")
            diags = data.get("diagnostics", [])
            self.assertGreaterEqual(len(diags), 1)
            msg = diags[0]["message"]
            self.assertIn(expected_hint, msg)
            self.assertIsNotNone(diags[0]["line"])

    def test_cross_language_rejection(self):
        c_source = """#include <stdio.h>
int main() {
    printf("Hello\\n");
    return 0;
}"""
        # C code in Java mode must fail
        java_res = self.client.post("/compile", json={"source": c_source, "language": "java"})
        self.assertFalse(java_res.get_json()["success"])

        # C code in Python mode must fail
        py_res = self.client.post("/compile", json={"source": c_source, "language": "python"})
        self.assertFalse(py_res.get_json()["success"])

        java_source = """public class Main {
    public static void main(String[] args) {
        System.out.println("Hello");
    }
}"""
        # Java code in C mode must fail
        c_res = self.client.post("/compile", json={"source": java_source, "language": "c"})
        self.assertFalse(c_res.get_json()["success"])

    def test_language_switch_lifecycle_and_clearing(self):
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()
        # Verify onLanguageChange invokes resetToInitialState and resets diagnostics/compiler state
        self.assertIn("function onLanguageChange()", html)
        self.assertIn("resetToInitialState", html)
        self.assertIn("updateLanguageCapsules(newLang)", html)
        self.assertIn("updateActiveLanguageBadge(newLang)", html)
        self.assertIn("updatePresetDropdown(newLang", html)

    def test_editing_source_code_and_running_again(self):
        # 1. Compile initial version
        src1 = """#include <stdio.h>
int main() {
    int total = 10;
    printf("Total = %d\\n", total);
    return 0;
}"""
        res1 = self.client.post("/compile", json={"source": src1, "language": "c"})
        self.assertEqual(res1.status_code, 200)
        self.assertIn("Total = 10", res1.get_json()["execution"]["output"])

        # 2. Compile edited version with different calculation
        src2 = """#include <stdio.h>
int main() {
    int total = 10 * 5 + 3;
    printf("Total = %d\\n", total);
    return 0;
}"""
        res2 = self.client.post("/compile", json={"source": src2, "language": "c"})
        self.assertEqual(res2.status_code, 200)
        self.assertIn("Total = 53", res2.get_json()["execution"]["output"])

    def test_frontend_dom_preset_and_capsule_invariants(self):
        import filecmp
        self.assertTrue(filecmp.cmp("index.html", "static/index.html", shallow=False))

        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()

        # Invariants:
        self.assertIn('selectTargetLanguage', html)
        self.assertIn('updatePresetDropdown', html)
        self.assertIn('DEFAULT_PRESETS_BY_LANG', html)
        self.assertIn('EMBEDDED_PRESETS', html)
        self.assertIn('id="activeLanguageBadge"', html)
        self.assertIn('onSourceInput', html)
        self.assertIn('isSourceModified', html)
        # Verify static preset options only contain C presets (toy_pipeline removed)
        self.assertNotIn('<option value="toy_pipeline">Toy Language: Multi-line Variable Assignment</option>', html)
        # Verify renderExecution is declared and called
        self.assertIn('function renderExecution(execData)', html)
        self.assertIn('renderExecution(null)', html)
        self.assertIn('renderExecution(data.execution || null)', html)

    def test_backend_unsupported_language_returns_consistent_json(self):
        res = self.client.post("/compile", json={"source": "int x = 1;", "language": "ruby"})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertFalse(data["pipeline_success"])
        self.assertIn("Unsupported language 'ruby'", data["error"])
        self.assertIn("diagnostics", data)
        self.assertGreaterEqual(len(data["diagnostics"]), 1)
        self.assertEqual(data["stages"]["source"], "failed")

    def test_backend_malformed_json_returns_consistent_json(self):
        res = self.client.post("/compile", data="not a json payload", content_type="application/json")
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Invalid JSON", data["error"])
        self.assertIn("diagnostics", data)

    def test_backend_unexpected_server_error_returns_json_500_without_traceback(self):
        from unittest.mock import patch
        with patch("app.get_compiler", side_effect=RuntimeError("Simulated internal crash")):
            res = self.client.post("/compile", json={"source": "int x = 1;", "language": "c"})
            self.assertEqual(res.status_code, 500)
            data = res.get_json()
            self.assertFalse(data["success"])
            self.assertIn("Internal compiler error", data["error"])
            self.assertNotIn("Traceback", data["error"])
            self.assertIn("diagnostics", data)

    def test_frontend_distinguishes_error_categories(self):
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()

        # Invariants ensuring proper error distinction:
        self.assertIn("Network Connection Error", html)
        self.assertIn("Backend Exception (HTTP 500)", html)
        self.assertIn("Server Response Protocol Error", html)
        # Verify old swallowed error call is removed:
        self.assertNotIn("resetToInitialState('Error running compiler. Check network connection.');", html)

    def test_all_languages_execution_payload(self):
        tests = [
            ("c", "#include <stdio.h>\nint main() { printf(\"Test C\\n\"); return 0; }", "Test C"),
            ("cpp", "#include <iostream>\nusing namespace std;\nint main() { cout << \"Test CPP\" << endl; return 0; }", "Test CPP"),
            ("java", "public class Main { public static void main(String[] args) { System.out.println(\"Test Java\"); } }", "Test Java"),
            ("python", "def main():\n    print(\"Test Python\")\n\nmain()", "Test Python"),
            ("js", "console.log(\"Test JS\");", "Test JS"),
            ("toy", "x = 10\ny = 20\nz = x + y", "status code 0")
        ]

        for lang, src, expected_snippet in tests:
            res = self.client.post("/compile", json={"source": src, "language": lang})
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["success"], f"Language {lang} compile failed: {data.get('error')}")
            self.assertIn("execution", data)
            exec_data = data["execution"]
            self.assertTrue(exec_data.get("executed"))
            self.assertIn(expected_snippet, exec_data.get("output", ""))


class TestPythonAstVisualization(unittest.TestCase):
    """
    Verification tests for Python AST visualization and recursive tree rendering.
    Validates complete tree preservation across all 7 required source shapes.
    """

    def setUp(self):
        self.app = app
        self.client = app.test_client()

    def test_1_simple_assignment_and_arithmetic(self):
        source = "x = 10 + 20 * 3"
        res = self.client.post("/compile", json={"source": source, "language": "python"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        ast = data["ast"]
        self.assertEqual(ast["type"], "Program")
        self.assertEqual(len(ast["statements"]), 1)
        assign = ast["statements"][0]
        self.assertEqual(assign["type"], "Assign")
        self.assertEqual(assign["name"], "x")

        # Check binary expression hierarchy
        binop_add = assign["value"]
        self.assertEqual(binop_add["type"], "BinOp")
        self.assertEqual(binop_add["op"], "+")
        self.assertEqual(binop_add["left"]["type"], "Number")
        self.assertEqual(binop_add["left"]["value"], 10)

        binop_mul = binop_add["right"]
        self.assertEqual(binop_mul["type"], "BinOp")
        self.assertEqual(binop_mul["op"], "*")
        self.assertEqual(binop_mul["left"]["value"], 20)
        self.assertEqual(binop_mul["right"]["value"], 3)

        # Check explicit children array for recursive rendering
        self.assertIn("children", assign)
        self.assertTrue(len(assign["children"]) > 0)
        self.assertIn("children", binop_add)
        self.assertTrue(len(binop_add["children"]) >= 2)

    def test_2_function_with_parameters_and_return(self):
        source = """def add(a, b):
    return a + b
"""
        res = self.client.post("/compile", json={"source": source, "language": "python"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        ast = data["ast"]
        fn = ast["statements"][0]
        self.assertEqual(fn["type"], "FunctionDef")
        self.assertEqual(fn["name"], "add")

        # Verify parameters are preserved and present as children
        params = fn["params"]
        self.assertEqual(len(params), 2)
        self.assertEqual([p["name"] for p in params], ["a", "b"])
        param_children = [c for c in fn["children"] if c.get("badge") == "param"]
        self.assertEqual(len(param_children), 2)

        # Verify body and return
        body = fn["body"]
        self.assertEqual(len(body), 1)
        ret = body[0]
        self.assertEqual(ret["type"], "Return")
        self.assertEqual(ret["value"]["type"], "BinOp")
        self.assertEqual(ret["value"]["op"], "+")

    def test_3_class_with_method(self):
        source = """class Calculator:
    def multiply(self, x, y):
        return x * y
"""
        res = self.client.post("/compile", json={"source": source, "language": "python"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        ast = data["ast"]
        cls = ast["statements"][0]
        self.assertEqual(cls["type"], "ClassDef")
        self.assertEqual(cls["name"], "Calculator")

        # Crucial check: class must NOT be truncated to 0 or 2 nodes!
        self.assertTrue(len(cls["members"]) >= 1)
        method = cls["members"][0]
        self.assertEqual(method["type"], "FunctionDef")
        self.assertEqual(method["name"], "multiply")
        self.assertEqual([p["name"] for p in method["params"]], ["self", "x", "y"])

        # Check children array on ClassDef contains member method
        member_children = [c for c in cls["children"] if c.get("badge") == "member"]
        self.assertTrue(len(member_children) >= 1)

    def test_4_if_else_statement(self):
        source = """if score >= 90:
    grade = 100
else:
    grade = 50
"""
        res = self.client.post("/compile", json={"source": source, "language": "python"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        ast = data["ast"]
        if_node = ast["statements"][0]
        self.assertEqual(if_node["type"], "If")
        self.assertEqual(if_node["condition"]["type"], "BinOp")
        self.assertEqual(if_node["condition"]["op"], ">=")
        self.assertEqual(len(if_node["then_branch"]), 1)
        self.assertEqual(len(if_node["else_branch"]), 1)

        # Check badges in children
        badges = [c.get("badge") for c in if_node["children"]]
        self.assertIn("test", badges)
        self.assertIn("then", badges)
        self.assertIn("else", badges)

    def test_5_loop_with_nested_body(self):
        source = """for i in [1, 2, 3]:
    while n > 0:
        n = n - 1
"""
        res = self.client.post("/compile", json={"source": source, "language": "python"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        ast = data["ast"]
        for_node = ast["statements"][0]
        self.assertEqual(for_node["type"], "For")
        self.assertEqual(for_node["iter"]["type"], "List")
        self.assertEqual(len(for_node["iter"]["elements"]), 3)

        # Check nested while loop
        self.assertEqual(len(for_node["body"]), 1)
        while_node = for_node["body"][0]
        self.assertEqual(while_node["type"], "While")
        self.assertEqual(while_node["condition"]["type"], "BinOp")
        self.assertEqual(len(while_node["body"]), 1)

    def test_6_list_dict_and_function_call(self):
        source = """data = {"key": [10, 20]}
print("Result:", data["key"][0], sep=" ")
"""
        res = self.client.post("/compile", json={"source": source, "language": "python"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        ast = data["ast"]
        assign = ast["statements"][0]
        dict_node = assign["value"]
        self.assertEqual(dict_node["type"], "Dict")
        self.assertEqual(len(dict_node["entries"]), 1)
        entry = dict_node["entries"][0]
        self.assertEqual(entry["key"]["value"], "key")
        self.assertEqual(entry["value"]["type"], "List")
        self.assertEqual(len(entry["value"]["elements"]), 2)

        # Check function call with keywords and subscript
        call = ast["statements"][1]
        self.assertEqual(call["type"], "FunctionCall")
        self.assertEqual(call["name"], "print")
        self.assertEqual(len(call["args"]), 2)
        self.assertEqual(len(call["keywords"]), 1)
        self.assertEqual(call["keywords"][0]["arg"], "sep")

    def test_7_invalid_python_syntax_diagnostic(self):
        source = """def broken:
    pass
"""
        res = self.client.post("/compile", json={"source": source, "language": "python"})
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("diagnostics", data)
        diag = data["diagnostics"][0]
        self.assertEqual(diag["stage"], "Parser")
        self.assertEqual(diag["line"], 1)
        self.assertIn("Syntax error", diag["message"])

    def test_8_frontend_ast_renderer_invariants(self):
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()

        # Invariants ensuring recursive tree rendering:
        self.assertIn("extractAstNodeChildren(node)", html)
        self.assertIn("ntype === 'ClassDef'", html)
        self.assertIn("ntype === 'While'", html)
        self.assertIn("ntype === 'For'", html)
        self.assertIn("ntype === 'List'", html)
        self.assertIn("ntype === 'Dict'", html)
        self.assertIn("ntype === 'AugAssign'", html)
        self.assertIn("ch.badge", html)


if __name__ == "__main__":
    unittest.main()
