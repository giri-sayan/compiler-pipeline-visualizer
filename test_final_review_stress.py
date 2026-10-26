"""
Final Review — Full Compiler Pipeline Regression and Stress Test Suite.

Covers:
  - Phase 2: Large-input stress tests (3,000 and 4,000 lines) across all frontends.
  - Phase 3: Error detection at large line numbers (~1,000, ~3,000, ~3,900) across
             syntax errors, undefined identifiers, incomplete expressions, and invalid constructs.
             Ensures line numbers are accurately parsed and NEVER default to line 1.
  - Phase 4: Stage success/failure invariants (passed vs blocked vs warning).
  - Phase 5: Language-specific regression testing across C, Python, C++, Java, JS, Toy Lang.
  - Phase 6: API and HTTP integration testing (/compile, /diff, /presets, /).
"""

import time
import json
import unittest
from app import app
from languages.c_lang import CCompiler
from languages.python_lang import PythonCompiler
from languages.cpp_lang import CPPCompiler
from languages.java_lang import JavaCompiler
from languages.js_lang import JSCompiler
from languages.toy_lang import ToyCompiler


def generate_c_source(num_lines: int = 3000) -> str:
    lines = [
        "#include <stdio.h>",
        "// Compiler Pipeline Visualizer — Realistic C Benchmark",
        "int helper(int a, int b) {",
        "    int temp = a * 2 + (b - 3);",
        "    if (temp > 10) {",
        "        return temp * 2;",
        "    } else {",
        "        return temp + 5;",
        "    }",
        "}",
        "int main() {",
        "    int acc = 0;",
        "    int factor = 2;",
    ]
    block_id = 0
    while len(lines) < num_lines - 4:
        block_id += 1
        lines.append(f"    // Block {block_id}: arithmetic and conditional logic")
        lines.append(f"    int v{block_id} = (acc + {block_id % 17}) * factor - ({block_id % 7});")
        lines.append(f"    if (v{block_id} > 50) {{")
        lines.append(f"        acc = acc + helper(v{block_id}, factor);")
        lines.append(f"    }} else {{")
        lines.append(f"        acc = acc + (v{block_id} * 2);")
        lines.append(f"    }}")
        lines.append("")
    while len(lines) < num_lines - 3:
        lines.append("    acc = acc + 1;")
    lines.append('    printf("Final accumulator: %d\\n", acc);')
    lines.append("    return 0;")
    lines.append("}")
    return "\n".join(lines)


def generate_python_source(num_lines: int = 3000) -> str:
    lines = [
        "# Compiler Pipeline Visualizer — Realistic Python Benchmark",
        "class Calculator:",
        "    def __init__(self, base: int):",
        "        self.base = base",
        "",
        "    def step(self, val: int) -> int:",
        "        if val > 50:",
        "            return val * 2 + self.base",
        "        else:",
        "            return val + self.base",
        "",
        "def compute(x: int, y: int) -> int:",
        "    return (x * 3) + (y - 5)",
        "",
        "def main():",
        "    calc = Calculator(10)",
        "    total = 0",
        "    scale = 2",
    ]
    block_id = 0
    while len(lines) < num_lines - 4:
        block_id += 1
        lines.append(f"    # Step {block_id}: realistic calculations")
        lines.append(f"    item_{block_id} = (total + {block_id % 19}) * scale - ({block_id % 5})")
        lines.append(f"    if item_{block_id} > 100:")
        lines.append(f"        total = total + compute(item_{block_id}, scale)")
        lines.append(f"    else:")
        lines.append(f"        total = total + calc.step(item_{block_id})")
        lines.append("")
    while len(lines) < num_lines - 2:
        lines.append("    total = total + 1")
    lines.append("    print(total)")
    lines.append("main()")
    return "\n".join(lines)


def generate_cpp_source(num_lines: int = 3000) -> str:
    lines = [
        "#include <iostream>",
        "using namespace std;",
        "// Compiler Pipeline Visualizer — Realistic C++ Benchmark",
        "int calc(int a, int b) {",
        "    int r = (a * 2) + (b - 4);",
        "    if (r > 30) {",
        "        return r * 2;",
        "    } else {",
        "        return r + 8;",
        "    }",
        "}",
        "int main() {",
        "    int total = 0;",
        "    int scale = 3;",
    ]
    block_id = 0
    while len(lines) < num_lines - 4:
        block_id += 1
        lines.append(f"    // Step {block_id}")
        lines.append(f"    int item{block_id} = (total + {block_id % 11}) * scale - ({block_id % 6});")
        lines.append(f"    if (item{block_id} > 40) {{")
        lines.append(f"        total = total + calc(item{block_id}, scale);")
        lines.append(f"    }} else {{")
        lines.append(f"        total = total + item{block_id};")
        lines.append(f"    }}")
        lines.append("")
    while len(lines) < num_lines - 3:
        lines.append("    total = total + 1;")
    lines.append("    cout << total << endl;")
    lines.append("    return 0;")
    lines.append("}")
    return "\n".join(lines)


def generate_java_source(num_lines: int = 3000) -> str:
    lines = [
        "// Compiler Pipeline Visualizer — Realistic Java Benchmark",
        "public class Main {",
        "    public static int calc(int a, int b) {",
        "        int r = (a * 2) + (b - 4);",
        "        if (r > 30) {",
        "            return r * 2;",
        "        } else {",
        "            return r + 8;",
        "        }",
        "    }",
        "    public static void main(String[] args) {",
        "        int total = 0;",
        "        int scale = 3;",
    ]
    block_id = 0
    while len(lines) < num_lines - 5:
        block_id += 1
        lines.append(f"        // Step {block_id}")
        lines.append(f"        int item{block_id} = (total + {block_id % 11}) * scale - ({block_id % 6});")
        lines.append(f"        if (item{block_id} > 40) {{")
        lines.append(f"            total = total + calc(item{block_id}, scale);")
        lines.append(f"        }} else {{")
        lines.append(f"            total = total + item{block_id};")
        lines.append(f"        }}")
        lines.append("")
    while len(lines) < num_lines - 3:
        lines.append("        total = total + 1;")
    lines.append("        System.out.println(total);")
    lines.append("    }")
    lines.append("}")
    return "\n".join(lines)


def generate_js_source(num_lines: int = 3000) -> str:
    lines = [
        "// Compiler Pipeline Visualizer — Realistic JavaScript Benchmark",
        "function calc(a, b) {",
        "    let r = (a * 2) + (b - 4);",
        "    if (r > 30) {",
        "        return r * 2;",
        "    } else {",
        "        return r + 8;",
        "    }",
        "}",
        "function main() {",
        "    let total = 0;",
        "    let scale = 3;",
    ]
    block_id = 0
    while len(lines) < num_lines - 4:
        block_id += 1
        lines.append(f"    // Step {block_id}")
        lines.append(f"    let item{block_id} = (total + {block_id % 11}) * scale - ({block_id % 6});")
        lines.append(f"    if (item{block_id} > 40) {{")
        lines.append(f"        total = total + calc(item{block_id}, scale);")
        lines.append(f"    }} else {{")
        lines.append(f"        total = total + item{block_id};")
        lines.append(f"    }}")
        lines.append("")
    while len(lines) < num_lines - 3:
        lines.append("    total = total + 1;")
    lines.append("    console.log(total);")
    lines.append("}")
    lines.append("main();")
    return "\n".join(lines)


def generate_toy_source(num_lines: int = 3000) -> str:
    lines = [
        "# Compiler Pipeline Visualizer — Realistic Toy Lang Benchmark",
        "acc = 0",
        "scale = 3",
    ]
    block_id = 0
    while len(lines) < num_lines - 2:
        block_id += 1
        lines.append(f"# Step {block_id}")
        lines.append(f"acc = (acc + {block_id % 13}) * scale - ({block_id % 7})")
        lines.append("")
    while len(lines) < num_lines - 1:
        lines.append("acc = acc + 1")
    lines.append("print(acc)")
    return "\n".join(lines)


class TestPhase2LargeInputStress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def _run_benchmark(self, lang: str, generator_fn, line_counts=(3000, 4000)):
        for target in line_counts:
            src = generator_fn(target)
            actual_lines = len(src.splitlines())
            self.assertGreaterEqual(actual_lines, target - 10, f"{lang} lines must reach ~{target}")

            t0 = time.perf_counter()
            res = self.client.post("/compile", json={"source": src, "language": lang})
            elapsed_ms = (time.perf_counter() - t0) * 1000

            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            payload_kb = len(res.data) / 1024

            self.assertTrue(data.get("success"), f"{lang} compilation failed on {actual_lines} lines: {data.get('error')}")
            self.assertTrue(data.get("pipeline_success"))
            self.assertTrue(data.get("syntax_valid"))
            self.assertTrue(data.get("semantic_valid"))
            self.assertEqual(data.get("stages", {}).get("tokens"), "passed")
            self.assertEqual(data.get("stages", {}).get("ast"), "passed")
            self.assertEqual(data.get("stages", {}).get("ir"), "passed")
            self.assertEqual(data.get("stages", {}).get("asm"), "passed")

            # Check token stream completeness
            tokens = data.get("tokens") or []
            self.assertGreater(len(tokens), 1000, f"{lang} must produce rich token stream")

            # Check AST completeness
            ast_dict = data.get("ast") or {}
            self.assertIn("type", ast_dict)

            # Record metrics
            print(f"  [BENCHMARK] {lang.upper():6} {actual_lines:4} lines | {elapsed_ms:7.2f} ms | {len(tokens):5} tokens | {payload_kb:6.1f} KB payload")

    def test_c_large_inputs_3000_and_4000_lines(self):
        self._run_benchmark("c", generate_c_source, [3000, 4000])

    def test_python_large_inputs_3000_and_4000_lines(self):
        self._run_benchmark("python", generate_python_source, [3000, 4000])

    def test_cpp_large_inputs_3000_and_4000_lines(self):
        self._run_benchmark("cpp", generate_cpp_source, [3000, 4000])

    def test_java_large_inputs_3000_and_4000_lines(self):
        self._run_benchmark("java", generate_java_source, [3000, 4000])

    def test_javascript_large_inputs_3000_and_4000_lines(self):
        self._run_benchmark("js", generate_js_source, [3000, 4000])

    def test_toy_lang_large_inputs_3000_and_4000_lines(self):
        self._run_benchmark("toy", generate_toy_source, [3000, 4000])


class TestPhase3LargeLineNumberErrors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_c_syntax_error_missing_brace_at_line_3900(self):
        lines = ["#include <stdio.h>", "int main() {"]
        lines.extend(["    int x = 1;" for _ in range(3898)])
        # Missing closing brace
        src = "\n".join(lines)
        res = self.client.post("/compile", json={"source": src, "language": "c"})
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertGreaterEqual(len(data["diagnostics"]), 1)
        diag = data["diagnostics"][0]
        self.assertEqual(diag["stage"], "Parser")
        self.assertGreaterEqual(diag["line"], 3890, "Missing closing brace must report EOF line, NOT line 1")
        self.assertNotEqual(diag["line"], 1)

    def test_c_undefined_identifier_at_line_1000(self):
        lines = ["#include <stdio.h>", "int main() {", "    int acc = 0;"]
        lines.extend([f"    acc = acc + {i % 10};" for i in range(996)])
        lines.append("    int res = undef_variable_at_1000 + 5;")  # Line 1000
        lines.append("    return 0;")
        lines.append("}")
        src = "\n".join(lines)
        res = self.client.post("/compile", json={"source": src, "language": "c"})
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertTrue(data.get("has_semantic_errors"))
        self.assertFalse(data.get("semantic_valid"))
        diag = [d for d in data["diagnostics"] if "undef_variable_at_1000" in d["message"]][0]
        self.assertEqual(diag["stage"], "Semantic Analyzer")
        self.assertEqual(diag["line"], 1000, f"Expected error at line 1000, got {diag['line']}")
        self.assertNotEqual(diag["line"], 1)

    def test_c_incomplete_expression_at_line_3000(self):
        lines = ["#include <stdio.h>", "int main() {", "    int acc = 0;"]
        lines.extend([f"    acc = acc + {i % 10};" for i in range(2996)])
        lines.append("    int faulty = acc + ;")  # Line 3000
        lines.append("    return 0;")
        lines.append("}")
        src = "\n".join(lines)
        res = self.client.post("/compile", json={"source": src, "language": "c"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertEqual(diag["stage"], "Parser")
        self.assertEqual(diag["line"], 3000, f"Expected parser error at line 3000, got {diag['line']}")
        self.assertNotEqual(diag["line"], 1)

    def test_c_unsupported_construct_at_line_3900(self):
        lines = ["#include <stdio.h>", "int main() {", "    int acc = 0;"]
        lines.extend([f"    acc = acc + {i % 10};" for i in range(3896)])
        lines.append("    while (acc > 0) { acc = acc - 1; }")  # Line 3900
        lines.append("    return 0;")
        lines.append("}")
        src = "\n".join(lines)
        res = self.client.post("/compile", json={"source": src, "language": "c"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertEqual(diag["stage"], "Parser")
        self.assertEqual(diag["line"], 3900, f"Expected unsupported construct error at line 3900, got {diag['line']}")
        self.assertIn("while", diag["message"])
        self.assertNotEqual(diag["line"], 1)

    def test_python_undefined_identifier_at_line_1000(self):
        lines = ["def main():", "    acc = 0"]
        lines.extend([f"    acc = acc + {i % 10}" for i in range(997)])
        lines.append("    print(ghost_var_1000)")  # Line 1000
        src = "\n".join(lines)
        res = self.client.post("/compile", json={"source": src, "language": "python"})
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertTrue(data.get("has_semantic_errors"))
        diag = [d for d in data["diagnostics"] if "ghost_var_1000" in d["message"]][0]
        self.assertEqual(diag["line"], 1000, f"Expected error at line 1000, got {diag['line']}")
        self.assertNotEqual(diag["line"], 1)

    def test_python_syntax_error_at_line_3000(self):
        lines = ["def main():", "    acc = 0"]
        lines.extend([f"    acc = acc + {i % 10}" for i in range(2997)])
        lines.append("    if acc >:")  # Line 3000: syntax error
        lines.append("        pass")
        lines.append("main()")
        src = "\n".join(lines)
        res = self.client.post("/compile", json={"source": src, "language": "python"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertEqual(diag["stage"], "Parser")
        self.assertEqual(diag["line"], 3000, f"Expected syntax error at line 3000, got {diag['line']}")
        self.assertNotEqual(diag["line"], 1)

    def test_cpp_typo_at_line_3000(self):
        lines = ["#include <iostream>", "using namespace std;", "int main() {", "    int acc = 0;"]
        lines.extend([f"    acc = acc + {i % 10};" for i in range(2995)])
        lines.append("    coutt << acc << endl;")  # Line 3000
        lines.append("    return 0;")
        lines.append("}")
        src = "\n".join(lines)
        res = self.client.post("/compile", json={"source": src, "language": "cpp"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertEqual(diag["line"], 3000, f"Expected typo error at line 3000, got {diag['line']}")
        self.assertIn("cout", diag["message"])
        self.assertNotEqual(diag["line"], 1)

    def test_java_typo_at_line_3000(self):
        lines = ["public class Main {", "    public static void main(String[] args) {", "        int acc = 0;"]
        lines.extend([f"        acc = acc + {i % 10};" for i in range(2996)])
        lines.append('        System.out.prntln("Total: " + acc);')  # Line 3000
        lines.append("    }")
        lines.append("}")
        src = "\n".join(lines)
        res = self.client.post("/compile", json={"source": src, "language": "java"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertEqual(diag["line"], 3000, f"Expected typo error at line 3000, got {diag['line']}")
        self.assertIn("println", diag["message"])
        self.assertNotEqual(diag["line"], 1)

    def test_js_typo_at_line_3000(self):
        lines = ["function main() {", "    let acc = 0;"]
        lines.extend([f"    acc = acc + {i % 10};" for i in range(2997)])
        lines.append("    conosle.log(acc);")  # Line 3000
        lines.append("}")
        lines.append("main();")
        src = "\n".join(lines)
        res = self.client.post("/compile", json={"source": src, "language": "js"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertEqual(diag["line"], 3000, f"Expected typo error at line 3000, got {diag['line']}")
        self.assertIn("console", diag["message"])
        self.assertNotEqual(diag["line"], 1)

    def test_toy_syntax_error_at_line_3900(self):
        lines = ["acc = 0"]
        lines.extend([f"acc = acc + {i % 10}" for i in range(3898)])
        lines.append("acc = 5 +")  # Line 3900
        src = "\n".join(lines)
        res = self.client.post("/compile", json={"source": src, "language": "toy"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertEqual(diag["stage"], "Parser")
        self.assertEqual(diag["line"], 3900, f"Expected syntax error at line 3900, got {diag['line']}")
        self.assertNotEqual(diag["line"], 1)


class TestPhase4PipelineStates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_all_stages_passed_for_valid_program(self):
        c_src = """#include <stdio.h>
int main() {
    int x = 10;
    int y = x * 2;
    printf("Result = %d\\n", y);
    return 0;
}"""
        res = self.client.post("/compile", json={"source": c_src, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["pipeline_success"])
        self.assertTrue(data["syntax_valid"])
        self.assertTrue(data["semantic_valid"])
        self.assertFalse(data["has_semantic_errors"])

        stages = data["stages"]
        for stg in ["source", "tokens", "ast", "semantic", "ir", "asm", "explain"]:
            self.assertEqual(stages.get(stg), "passed", f"Stage '{stg}' must be 'passed'")

    def test_lexical_error_blocks_downstream_stages(self):
        c_src = 'int main() { printf("Unterminated string); return 0; }'
        res = self.client.post("/compile", json={"source": c_src, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertFalse(data["syntax_valid"])

        stages = data["stages"]
        self.assertEqual(stages["source"], "passed")
        self.assertEqual(stages["tokens"], "failed")
        for stg in ["ast", "semantic", "ir", "asm", "explain"]:
            self.assertEqual(stages[stg], "blocked", f"Stage '{stg}' must be 'blocked' on lexical failure")

    def test_syntax_error_blocks_downstream_stages(self):
        c_src = "int main() { int x = (3 + ; return 0; }"
        res = self.client.post("/compile", json={"source": c_src, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertFalse(data["syntax_valid"])

        stages = data["stages"]
        self.assertEqual(stages["source"], "passed")
        self.assertEqual(stages["tokens"], "passed")
        self.assertEqual(stages["ast"], "failed")
        for stg in ["semantic", "ir", "asm", "explain"]:
            self.assertEqual(stages[stg], "blocked", f"Stage '{stg}' must be 'blocked' on syntax failure")

    def test_semantic_error_blocks_codegen_and_execution(self):
        c_src = "int main() { int x = undefined_var + 1; return 0; }"
        res = self.client.post("/compile", json={"source": c_src, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertTrue(data["syntax_valid"])
        self.assertFalse(data["semantic_valid"])
        self.assertTrue(data["has_semantic_errors"])

        stages = data["stages"]
        self.assertEqual(stages["source"], "passed")
        self.assertEqual(stages["tokens"], "passed")
        self.assertEqual(stages["ast"], "passed")
        self.assertEqual(stages["semantic"], "failed")
        for stg in ["ir", "asm", "explain"]:
            self.assertEqual(stages[stg], "blocked", f"Stage '{stg}' must be 'blocked' on semantic failure")

    def test_empty_source_validation(self):
        res = self.client.post("/compile", json={"source": "   \n\t  ", "language": "c"})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["stages"]["source"], "failed")
        for stg in ["tokens", "ast", "semantic", "ir", "asm", "explain"]:
            self.assertEqual(data["stages"][stg], "blocked")

    def test_exceeds_10000_lines_validation(self):
        lines = ["// comment" for _ in range(10005)]
        res = self.client.post("/compile", json={"source": "\n".join(lines), "language": "c"})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("exceeds maximum limit", data["error"])

    def test_unsupported_language_validation(self):
        res = self.client.post("/compile", json={"source": "fn main() {}", "language": "rust"})
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("rust", data["error"].lower())


class TestPhase5LanguageRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_all_six_languages_compile_valid_presets(self):
        p_res = self.client.get("/presets")
        self.assertEqual(p_res.status_code, 200)
        presets = p_res.get_json()
        languages_tested = set()

        for p_id, p in presets.items():
            lang = p.get("language")
            if p.get("category") not in ("error", "warning") and "unsupported" not in p.get("name", "").lower():
                res = self.client.post("/compile", json={"source": p["source"], "language": lang})
                self.assertEqual(res.status_code, 200, f"Preset '{p['name']}' HTTP error: {res.status_code}")
                data = res.get_json()
                self.assertTrue(data["success"], f"Preset '{p['name']}' ({lang}) failed: {data.get('error')}")
                self.assertTrue(data["semantic_valid"])
                languages_tested.add(lang)

        for expected in ["c", "python", "cpp", "java", "js", "toy"]:
            self.assertIn(expected, languages_tested, f"No valid presets tested for '{expected}'")

    def test_c_semantic_warning_preset_reports_warning(self):
        p_res = self.client.get("/presets")
        presets = p_res.get_json()
        self.assertIn("c_semantic_warning", presets)
        p = presets["c_semantic_warning"]
        res = self.client.post("/compile", json={"source": p["source"], "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertFalse(data["has_semantic_errors"])
        self.assertGreaterEqual(len(data.get("diagnostics", [])), 1)
        self.assertEqual(data["diagnostics"][0]["severity"], "warning")

    def test_cross_language_isolation(self):
        # Compiling Python code as C must be rejected with C diagnostics
        py_code = "def hello():\n    print('Hello World')\nhello()"
        res_c = self.client.post("/compile", json={"source": py_code, "language": "c"})
        self.assertFalse(res_c.get_json()["success"])

        # Then immediately compiling C code as C must succeed cleanly
        c_code = "#include <stdio.h>\nint main() { printf(\"OK\\n\"); return 0; }"
        res_c_ok = self.client.post("/compile", json={"source": c_code, "language": "c"})
        self.assertTrue(res_c_ok.get_json()["success"])

    def test_unsupported_loop_in_c_educational_subset(self):
        loop_code = "int main() { for (int i = 0; i < 10; i++) {} return 0; }"
        res = self.client.post("/compile", json={"source": loop_code, "language": "c"})
        data = res.get_json()
        self.assertFalse(data["success"])
        diag = data["diagnostics"][0]
        self.assertEqual(diag["stage"], "Parser")
        self.assertIn("not supported", diag["message"].lower())


class TestPhase6Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_get_root_serves_html(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Compiler Pipeline Visualizer", res.data)
        self.assertIn(b"<!DOCTYPE html>", res.data)

    def test_get_presets_returns_all_supported_languages(self):
        res = self.client.get("/presets")
        self.assertEqual(res.status_code, 200)
        presets = res.get_json()
        found_langs = {p.get("language") for p in presets.values()}
        for expected in ["c", "cpp", "java", "python", "js", "toy"]:
            self.assertIn(expected, found_langs)
        for p_id, p in presets.items():
            self.assertIn("name", p)
            self.assertIn("source", p)
            self.assertIn("language", p)

    def test_post_diff_endpoint(self):
        left_src = "int main() { int x = 10; return 0; }"
        right_src = "int main() { int x = 20; return 0; }"
        res = self.client.post("/diff", json={
            "source_a": left_src,
            "source_b": right_src,
            "language": "c"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("program_a", data["data"])
        self.assertIn("program_b", data["data"])
        self.assertIn("diffs", data["data"])

    def test_post_diff_multi_language(self):
        py_a = "def main():\n    x = 10\n    print(x)\nmain()"
        py_b = "def main():\n    x = 20\n    print(x)\nmain()"
        res = self.client.post("/diff", json={
            "source_a": py_a,
            "source_b": py_b,
            "language": "python"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("program_a", data["data"])
        self.assertIn("program_b", data["data"])
        self.assertIn("diffs", data["data"])

    def test_error_handling_malformed_json(self):
        res = self.client.post("/compile", data="NOT_JSON", content_type="application/json")
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Malformed JSON", data["diagnostics"][0]["message"])


if __name__ == "__main__":
    unittest.main()
