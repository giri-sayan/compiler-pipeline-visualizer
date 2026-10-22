"""
Automated Test Suite for Compiler Pipeline Visualizer.
Verifies end-to-end functionality across all 5 compiler stages + diff engine.
"""

import unittest
from lexer import Lexer, PREPROCESSOR, TYPE, IDENTIFIER, NUMBER, PLUS, MUL, SEMICOLON
from parser import Parser
import semantic
from ir_generator import generate_ir
from codegen import generate_code
from explainer import generate_explanation
import diff_service
from app import app


class TestCompilerPipeline(unittest.TestCase):

    def test_c_lexer_with_include(self):
        src = """#include <stdio.h>
// calculate sum
int main() {
    int total = 3 + 4 * 2;
    return 0;
}"""
        lexer = Lexer(src, language="c")
        tokens = lexer.tokenize()
        token_types = [t.type for t in tokens]

        self.assertIn(PREPROCESSOR, token_types)
        self.assertIn(TYPE, token_types)
        self.assertIn(IDENTIFIER, token_types)
        self.assertIn(NUMBER, token_types)
        self.assertIn(SEMICOLON, token_types)

        # Check preprocessor value
        prep_tok = [t for t in tokens if t.type == PREPROCESSOR][0]
        self.assertEqual(prep_tok.value, "#include <stdio.h>")

    def test_c_parser_precedence(self):
        src = "int x = 2 + 3 * 4;"
        tokens = Lexer(src).tokenize()
        ast = Parser(tokens).parse_program()
        ast_dict = ast.to_dict()

        statements = ast_dict["statements"]
        self.assertEqual(len(statements), 1)
        var_decl = statements[0]
        self.assertEqual(var_decl["type"], "VarDecl")
        self.assertEqual(var_decl["name"], "x")

        # Root of expr is +
        expr = var_decl["value"]
        self.assertEqual(expr["type"], "BinOp")
        self.assertEqual(expr["op"], "+")
        self.assertEqual(expr["left"]["value"], 2)

        # Right child is *
        right = expr["right"]
        self.assertEqual(right["type"], "BinOp")
        self.assertEqual(right["op"], "*")
        self.assertEqual(right["left"]["value"], 3)
        self.assertEqual(right["right"]["value"], 4)

    def test_semantic_analysis_valid(self):
        src = """#include <stdio.h>
int main() {
    int a = 10;
    int b = a + 5;
    return 0;
}"""
        tokens = Lexer(src).tokenize()
        ast = Parser(tokens).parse_program()
        errors, declared, symbol_table = semantic.analyze(ast)

        self.assertEqual(len(errors), 0)
        self.assertIn("a", declared)
        self.assertIn("b", declared)

    def test_semantic_analysis_undeclared_variable(self):
        src = """#include <stdio.h>
int main() {
    int a = 10;
    int b = a + unknown_variable;
    return 0;
}"""
        tokens = Lexer(src).tokenize()
        ast = Parser(tokens).parse_program()
        errors, declared, symbol_table = semantic.analyze(ast)

        self.assertGreaterEqual(len(errors), 1)
        self.assertTrue(any("unknown_variable" in e.message for e in errors))

    def test_ir_generation(self):
        src = """#include <stdio.h>
int main() {
    int total = 3 + 4 * 2;
    return 0;
}"""
        tokens = Lexer(src).tokenize()
        ast = Parser(tokens).parse_program()
        ir = generate_ir(ast)

        self.assertIn("quadruples", ir)
        self.assertIn("tac_text", ir)
        self.assertGreaterEqual(len(ir["quadruples"]), 4)

        # Check TAC contains operations
        tac = ir["tac_text"]
        self.assertIn("*", tac)
        self.assertIn("+", tac)
        self.assertIn("total", tac)

    def test_target_codegen(self):
        src = "int total = 3 + 4 * 2;"
        tokens = Lexer(src).tokenize()
        ast = Parser(tokens).parse_program()
        ir = generate_ir(ast)
        target = generate_code(ir)

        self.assertIn("x86_64", target)
        self.assertIn("educational", target)

        # Check x86_64 contains instructions
        x86 = target["x86_64"]
        self.assertIn("movl", x86)
        self.assertIn("imull", x86)
        self.assertIn("addl", x86)

        # Check educational assembly contains LOAD/STORE
        edu = target["educational"]
        self.assertIn("LOAD", edu)
        self.assertIn("STORE", edu)
        self.assertIn("MUL", edu)
        self.assertIn("ADD", edu)

    def test_toy_language_support(self):
        src = """x = 5
y = x + 2
z = (x + y) * 3"""
        tokens = Lexer(src, language="toy").tokenize()
        ast = Parser(tokens).parse_program()
        errors, declared, symbols = semantic.analyze(ast)
        ir = generate_ir(ast)
        target = generate_code(ir)

        self.assertEqual(len(errors), 0)
        self.assertEqual(declared, ["x", "y", "z"])
        self.assertGreater(len(ir["quadruples"]), 0)

    def test_diff_service(self):
        prog_a = "int total = 3 + 4;"
        prog_b = "int total = 3 + 4 * 2;"
        diff_res = diff_service.compare_programs(prog_a, prog_b, language="c")

        self.assertIn("diffs", diff_res)
        self.assertIn("ir", diff_res["diffs"])
        self.assertIn("tokens", diff_res["diffs"])
        self.assertIn("ast", diff_res["diffs"])

    def test_parentheses_override_precedence(self):
        # (2 + 3) * 4 -> multiplication at root, addition is left child
        src = "int y = (2 + 3) * 4;"
        tokens = Lexer(src).tokenize()
        ast = Parser(tokens).parse_program()
        ast_dict = ast.to_dict()

        var_decl = ast_dict["statements"][0]
        expr = var_decl["value"]
        self.assertEqual(expr["type"], "BinOp")
        self.assertEqual(expr["op"], "*")
        self.assertEqual(expr["right"]["value"], 4)

        left = expr["left"]
        self.assertEqual(left["type"], "BinOp")
        self.assertEqual(left["op"], "+")
        self.assertEqual(left["left"]["value"], 2)
        self.assertEqual(left["right"]["value"], 3)

    def test_associativity_left_to_right(self):
        # 10 - 4 - 2 -> left-associative ((10 - 4) - 2)
        src = "int z = 10 - 4 - 2;"
        tokens = Lexer(src).tokenize()
        ast = Parser(tokens).parse_program()
        var_decl = ast.to_dict()["statements"][0]
        expr = var_decl["value"]

        self.assertEqual(expr["op"], "-")
        self.assertEqual(expr["right"]["value"], 2)
        self.assertEqual(expr["left"]["op"], "-")
        self.assertEqual(expr["left"]["left"]["value"], 10)
        self.assertEqual(expr["left"]["right"]["value"], 4)

    def test_unary_operators_and_negative_literals(self):
        src = "int x = -5; int y = -x;"
        tokens = Lexer(src).tokenize()
        ast = Parser(tokens).parse_program()
        ir = generate_ir(ast)
        target = generate_code(ir)

        # IR should contain unary minus
        self.assertTrue(any(q["op"] == "UNARY_MINUS" for q in ir["quadruples"]))
        # x86-64 must contain negl instruction and literal 5
        self.assertIn("negl", target["x86_64"])
        self.assertIn("$5", target["x86_64"])
        # Educational assembly should contain NEG
        self.assertIn("NEG", target["educational"])

    def test_comparison_and_conditional_code_generation(self):
        src = """int main() {
    int score = 85;
    int bonus = 0;
    if (score > 80) {
        bonus = 10;
    } else {
        bonus = 2;
    }
    return 0;
}"""
        tokens = Lexer(src).tokenize()
        ast = Parser(tokens).parse_program()
        ir = generate_ir(ast)
        target = generate_code(ir)

        # IR checks
        ops = [q["op"] for q in ir["quadruples"]]
        self.assertIn(">", ops)
        self.assertIn("IF_FALSE", ops)
        self.assertIn("GOTO", ops)
        self.assertIn("LABEL", ops)

        # x86-64 checks: must have comparison, setg, and conditional branch
        x86 = target["x86_64"]
        self.assertIn("cmpl\t$80", x86)
        self.assertIn("setg\t%al", x86)
        self.assertIn("movzbl\t%al, %eax", x86)
        self.assertIn("je\tL0", x86)

        # Educational pseudo-assembly checks
        edu = target["educational"]
        self.assertIn("CMP_GT", edu)
        self.assertIn("BR_FALSE", edu)

    def test_all_relational_operators(self):
        operators = [("==", "sete", "CMP_EQ"),
                     ("!=", "setne", "CMP_NE"),
                     ("<", "setl", "CMP_LT"),
                     ("<=", "setle", "CMP_LE"),
                     (">", "setg", "CMP_GT"),
                     (">=", "setge", "CMP_GE")]
        for op, x86_set, edu_op in operators:
            src = f"int cond = (a {op} b);"
            tokens = Lexer(src).tokenize()
            ast = Parser(tokens).parse_program()
            ir = generate_ir(ast)
            target = generate_code(ir)

            self.assertIn(x86_set, target["x86_64"])
            self.assertIn(edu_op, target["educational"])

    def test_uninitialized_variable_detection(self):
        src = "int a; int b = a + 1;"
        tokens = Lexer(src).tokenize()
        ast = Parser(tokens).parse_program()
        errors, declared, syms = semantic.analyze(ast)

        # Should produce a warning for uninitialized 'a'
        self.assertTrue(any("without being initialized" in e.message for e in errors))
        uninit_sym = [s for s in syms if s["name"] == "a"][0]
        self.assertFalse(uninit_sym["initialized"])

    def test_syntax_error_and_unsupported_diagnostics(self):
        # Empty assignment
        with self.assertRaises(Exception) as ctx:
            Parser(Lexer("int x = ;").tokenize()).parse_program()
        self.assertIn("Syntax error", str(ctx.exception))

        # Unsupported while loop
        with self.assertRaises(Exception) as ctx:
            Parser(Lexer("while (1) { int x = 1; }").tokenize()).parse_program()
        self.assertIn("Unsupported construct", str(ctx.exception))
        self.assertIn("while", str(ctx.exception))

        # Dangling else
        with self.assertRaises(Exception) as ctx:
            Parser(Lexer("else { int x = 1; }").tokenize()).parse_program()
        self.assertIn("without matching 'if'", str(ctx.exception))

    def test_api_compile_endpoint(self):
        client = app.test_client()

        # 1. Valid program: pipeline_success = True, semantic_valid = True
        res = client.post("/compile", json={"source": "int x = 2 + 3 * 4;", "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["pipeline_success"])
        self.assertTrue(data["semantic_valid"])
        self.assertFalse(data["has_semantic_errors"])
        self.assertIn("ir", data)
        self.assertIn("assembly", data)

        # 2. Semantic error: success = False, pipeline_success = True, semantic_valid = False, ir blocked
        res_sem = client.post("/compile", json={"source": "int x = missing_var + 1;", "language": "c"})
        self.assertEqual(res_sem.status_code, 200)
        data_sem = res_sem.get_json()
        self.assertFalse(data_sem["success"])
        self.assertTrue(data_sem["pipeline_success"])
        self.assertFalse(data_sem["semantic_valid"])
        self.assertTrue(data_sem["has_semantic_errors"])
        self.assertEqual(data_sem["stage"], "Semantic Analyzer")
        self.assertEqual(data_sem["stages"]["semantic"], "failed")
        self.assertEqual(data_sem["stages"]["ir"], "blocked")
        self.assertEqual(data_sem["stages"]["asm"], "blocked")
        self.assertGreaterEqual(len(data_sem["semantic_errors"]), 1)

        # 3. Syntax error: success = False, stage = Parser
        res_syn = client.post("/compile", json={"source": "int x = ;", "language": "c"})
        self.assertEqual(res_syn.status_code, 200)
        data_syn = res_syn.get_json()
        self.assertFalse(data_syn["success"])
        self.assertEqual(data_syn["stage"], "Parser")
        self.assertIn("tokens", data_syn)

        # 4. Empty source: HTTP 400
        res_empty = client.post("/compile", json={"source": "   ", "language": "c"})
        self.assertEqual(res_empty.status_code, 400)
        self.assertIn("error", res_empty.get_json())
        self.assertIn("diagnostics", res_empty.get_json())

    def test_api_presets_and_diff(self):
        client = app.test_client()

        # Presets endpoint
        pres = client.get("/presets")
        self.assertEqual(pres.status_code, 200)
        pdata = pres.get_json()
        self.assertIn("c_complete", pdata)
        self.assertIn("c_conditional", pdata)
        self.assertIn("c_precedence", pdata)
        self.assertIn("c_lexical_error", pdata)
        self.assertIn("c_syntax_error", pdata)
        self.assertIn("c_semantic_error", pdata)
        self.assertIn("c_semantic_warning", pdata)

        # Diff endpoint - valid comparison
        diff_res = client.post("/diff", json={
            "source_a": "int total = 3 + 4;",
            "source_b": "int total = 3 + 4 * 2;",
            "language": "c"
        })
        self.assertEqual(diff_res.status_code, 200)
        ddata = diff_res.get_json()
        self.assertTrue(ddata["success"])
        self.assertIn("diffs", ddata["data"])
        diffs = ddata["data"]["diffs"]
        for stg in ["source", "tokens", "ast", "ir", "assembly_edu", "assembly_x86"]:
            self.assertIn(stg, diffs)
            self.assertIsInstance(diffs[stg], list)

        # Verify comparison semantics: AST diff contains structural tree differences, IR contains TAC differences
        ast_diff_types = [r["type"] for r in diffs["ast"]]
        ir_diff_types = [r["type"] for r in diffs["ir"]]
        self.assertTrue(any(t in ["added", "modified", "removed"] for t in ast_diff_types))
        self.assertTrue(any(t in ["added", "modified", "removed"] for t in ir_diff_types))

        # Diff endpoint - empty input returns HTTP 400
        diff_empty = client.post("/diff", json={"source_a": "", "source_b": "int x = 1;"})
        self.assertEqual(diff_empty.status_code, 400)
        self.assertIn("error", diff_empty.get_json())

        # Diff endpoint - invalid syntax returns HTTP 400 with error message
        diff_err = client.post("/diff", json={"source_a": "int x = ;", "source_b": "int x = 1;"})
        self.assertEqual(diff_err.status_code, 400)
        err_json = diff_err.get_json()
        self.assertFalse(err_json["success"])
        self.assertIn("error", err_json)

    def test_frontend_branding_and_diff_structure(self):
        client = app.test_client()
        res = client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")

        # 1. Product renaming
        self.assertIn("<title>Compiler Pipeline Visualizer</title>", html)
        self.assertIn("<h1>Compiler Pipeline Visualizer</h1>", html)
        self.assertNotIn("Compiler Studio", html)

        # 2. Stage Diff mode initial state
        self.assertIn('id="diffEmptyState"', html)
        self.assertIn("Compare two program versions to see how the selected compiler stage changes.", html)
        self.assertIn('id="diffTableWrapper"', html)
        self.assertIn('style="display:none;"', html)
        self.assertIn("Compare Pipeline Stages Side-by-Side", html)

        # 3. Target stage selector options
        for stg_val in ["ir", "ast", "tokens", "assembly_edu", "assembly_x86", "source"]:
            self.assertIn(f'value="{stg_val}"', html)

        # 4. Verify no automatic runDiff on switchMainMode
        self.assertNotIn("if (mode === 'diff' && !currentDiffData)", html)
        self.assertNotIn("onchange=\"runDiff()\"", html)

    def test_structured_diagnostics_and_stage_statuses(self):
        client = app.test_client()

        # 1. Lexical error: tokens failed, ast/semantic/ir/asm/explain blocked
        res_lex = client.post("/compile", json={"source": "int total = 3 @ 4;", "language": "c"})
        self.assertEqual(res_lex.status_code, 200)
        data_lex = res_lex.get_json()
        self.assertFalse(data_lex["success"])
        self.assertEqual(data_lex["stage"], "Lexer")
        self.assertEqual(data_lex["stages"]["tokens"], "failed")
        self.assertEqual(data_lex["stages"]["ast"], "blocked")
        self.assertEqual(data_lex["stages"]["semantic"], "blocked")
        self.assertEqual(data_lex["stages"]["ir"], "blocked")
        self.assertEqual(data_lex["stages"]["asm"], "blocked")
        self.assertGreaterEqual(len(data_lex["diagnostics"]), 1)
        diag_lex = data_lex["diagnostics"][0]
        self.assertEqual(diag_lex["stage"], "Lexer")
        self.assertEqual(diag_lex["severity"], "error")
        self.assertEqual(diag_lex["line"], 1)
        self.assertEqual(diag_lex["col"], 15)
        self.assertIn("@", diag_lex["message"])

        # 2. Syntax error: tokens passed, ast failed, semantic/ir/asm/explain blocked
        res_syn = client.post("/compile", json={"source": "int total = 3 + ;", "language": "c"})
        self.assertEqual(res_syn.status_code, 200)
        data_syn = res_syn.get_json()
        self.assertFalse(data_syn["success"])
        self.assertEqual(data_syn["stage"], "Parser")
        self.assertEqual(data_syn["stages"]["tokens"], "passed")
        self.assertEqual(data_syn["stages"]["ast"], "failed")
        self.assertEqual(data_syn["stages"]["semantic"], "blocked")
        self.assertEqual(data_syn["stages"]["ir"], "blocked")
        self.assertEqual(data_syn["stages"]["asm"], "blocked")
        self.assertGreaterEqual(len(data_syn["diagnostics"]), 1)
        diag_syn = data_syn["diagnostics"][0]
        self.assertEqual(diag_syn["stage"], "Parser")
        self.assertEqual(diag_syn["severity"], "error")
        self.assertEqual(diag_syn["line"], 1)
        self.assertEqual(diag_syn["col"], 17)
        self.assertIn("Syntax error", diag_syn["message"])

        # 3. Semantic warning: tokens/ast passed, semantic warning, ir/asm passed
        res_warn = client.post("/compile", json={"source": "int a; int b = a + 5;", "language": "c"})
        self.assertEqual(res_warn.status_code, 200)
        data_warn = res_warn.get_json()
        self.assertTrue(data_warn["success"])
        self.assertFalse(data_warn["semantic_valid"])
        self.assertFalse(data_warn["has_semantic_errors"])
        self.assertEqual(data_warn["stages"]["semantic"], "warning")
        self.assertEqual(data_warn["stages"]["ir"], "passed")
        diag_warn = [d for d in data_warn["diagnostics"] if d["severity"] == "warning"][0]
        self.assertEqual(diag_warn["stage"], "Semantic Analyzer")
        self.assertEqual(diag_warn["line"], 1)

    def test_lexer_error_unterminated_string(self):
        from lexer import Lexer, LexerError
        with self.assertRaises(LexerError) as ctx:
            Lexer('char* s = "unterminated;').tokenize()
        self.assertIn("Unterminated string", str(ctx.exception))
        self.assertEqual(ctx.exception.line, 1)

    def test_parser_error_missing_parenthesis(self):
        from parser import Parser, ParserError
        with self.assertRaises(ParserError) as ctx:
            Parser(Lexer("int x = (2 + 3;").tokenize()).parse_program()
        self.assertIn("Syntax error", str(ctx.exception))
        self.assertIsNotNone(ctx.exception.line)
        self.assertIsNotNone(ctx.exception.col)


    def test_unknown_function_name_diagnosed_with_suggestion(self):
        client = app.test_client()
        source = """#include <stdio.h>

int main() {
    int total = 3 + 4 * 2;
    rintf("Result = %d\\n", total);
    return 0;
}"""
        res = client.post("/compile", json={"source": source, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        # Overall compilation must fail
        self.assertFalse(data["success"])
        self.assertTrue(data["pipeline_success"])
        self.assertFalse(data["semantic_valid"])
        self.assertTrue(data["has_semantic_errors"])
        self.assertEqual(data["stage"], "Semantic Analyzer")

        # Stage statuses: upstream stages passed, downstream blocked
        stages = data["stages"]
        self.assertEqual(stages["source"], "passed")
        self.assertEqual(stages["tokens"], "passed")
        self.assertEqual(stages["ast"], "passed")
        self.assertEqual(stages["semantic"], "failed")
        self.assertEqual(stages["ir"], "blocked")
        self.assertEqual(stages["asm"], "blocked")
        self.assertEqual(stages["explain"], "blocked")

        # Upstream results preserved for inspection
        self.assertIn("tokens", data)
        self.assertGreater(len(data["tokens"]), 0)
        self.assertIn("ast", data)
        self.assertIn("statements", data["ast"])

        # Downstream results must NOT be present as valid compiler output
        self.assertNotIn("ir", data)
        self.assertNotIn("assembly", data)

        # Precise diagnostics with line, col, and typo suggestion
        self.assertGreaterEqual(len(data["diagnostics"]), 1)
        diag = data["diagnostics"][0]
        self.assertEqual(diag["stage"], "Semantic Analyzer")
        self.assertEqual(diag["line"], 5)
        self.assertEqual(diag["col"], 5)
        self.assertEqual(diag["severity"], "error")
        self.assertIn("Unknown function 'rintf'", diag["message"])
        self.assertIn("Did you mean 'printf'?", diag["message"])

    def test_keyword_typo_return_diagnosed_with_suggestion(self):
        source = """#include <stdio.h>

int main() {
    int total = 3 + 4 * 2;
    printf("Result = %d\\n", total);
    eturn 0;
}"""
        client = app.test_client()
        res = client.post("/compile", json={"source": source, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertFalse(data["success"])
        self.assertEqual(data["stage"], "Parser")
        self.assertEqual(data["stages"]["ast"], "failed")
        self.assertEqual(data["stages"]["semantic"], "blocked")
        self.assertEqual(data["stages"]["ir"], "blocked")

        self.assertGreaterEqual(len(data["diagnostics"]), 1)
        diag = data["diagnostics"][0]
        self.assertEqual(diag["stage"], "Parser")
        self.assertEqual(diag["line"], 6)
        self.assertEqual(diag["col"], 5)
        self.assertEqual(diag["severity"], "error")
        self.assertIn("Unknown keyword or statement 'eturn'", diag["message"])
        self.assertIn("Did you mean 'return'?", diag["message"])

    def test_keyword_typo_type_and_control_flow(self):
        from parser import Parser, ParserError
        # 1. Type keyword typo: itn
        tokens1 = Lexer("int main() { itn x = 5; }", language="c").tokenize()
        with self.assertRaises(ParserError) as ctx1:
            Parser(tokens1, language="c").parse_program()
        self.assertIn("Unknown type or keyword 'itn'", str(ctx1.exception))
        self.assertIn("Did you mean 'int'?", str(ctx1.exception))
        self.assertEqual(ctx1.exception.line, 1)

        # 2. Control flow keyword typo: fi
        tokens2 = Lexer("int main() { fi (x > 0) { } }", language="c").tokenize()
        with self.assertRaises(ParserError) as ctx2:
            Parser(tokens2, language="c").parse_program()
        self.assertIn("Unknown keyword or statement 'fi'", str(ctx2.exception))
        self.assertIn("Did you mean 'if'?", str(ctx2.exception))

    def test_c_program_requires_main_entry_point(self):
        # 1. Typo in main: ain()
        source_ain = """#include <stdio.h>

int ain() {
    int total = 3 + 4 * 2;
    printf("Result = %d\\n", total);
    return 0;
}"""
        client = app.test_client()
        res = client.post("/compile", json={"source": source_ain, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["stage"], "Semantic Analyzer")
        self.assertEqual(data["stages"]["semantic"], "failed")
        self.assertEqual(data["stages"]["ir"], "blocked")
        self.assertEqual(data["stages"]["asm"], "blocked")

        self.assertGreaterEqual(len(data["diagnostics"]), 1)
        diag = data["diagnostics"][0]
        self.assertEqual(diag["stage"], "Semantic Analyzer")
        self.assertEqual(diag["line"], 3)
        self.assertEqual(diag["col"], 5)
        self.assertIn("Unknown entry point function 'ain'", diag["message"])
        self.assertIn("Did you mean 'main'?", diag["message"])

        # 2. Missing main altogether with custom function
        source_no_main = """#include <stdio.h>

int calculate() {
    return 42;
}"""
        res_nm = client.post("/compile", json={"source": source_no_main, "language": "c"})
        self.assertEqual(res_nm.status_code, 200)
        data_nm = res_nm.get_json()
        self.assertFalse(data_nm["success"])
        self.assertEqual(data_nm["stage"], "Semantic Analyzer")
        self.assertIn("Missing 'main' function", data_nm["diagnostics"][0]["message"])

    def test_undeclared_identifier_with_typo_suggestion(self):
        source = """int main() {
    int count = 10;
    int x = cont + 1;
    return 0;
}"""
        tokens = Lexer(source, language="c").tokenize()
        ast = Parser(tokens, language="c").parse_program()
        errors, declared, syms = semantic.analyze(ast, language="c")

        self.assertGreaterEqual(len(errors), 1)
        err = [e for e in errors if "cont" in e.message][0]
        self.assertEqual(err.line, 3)
        self.assertEqual(err.severity, "error")
        self.assertIn("Variable 'cont' used before it was declared or assigned", err.message)
        self.assertIn("Did you mean 'count'?", err.message)

    def test_forgotten_header_suggestion(self):
        source = """int main() {
    int x = sqrt(16);
    return 0;
}"""
        tokens = Lexer(source, language="c").tokenize()
        ast = Parser(tokens, language="c").parse_program()
        errors, declared, syms = semantic.analyze(ast, language="c")

        self.assertGreaterEqual(len(errors), 1)
        err = [e for e in errors if "sqrt" in e.message][0]
        self.assertIn("Unknown function 'sqrt'", err.message)
        self.assertIn("Did you forget to '#include <math.h>'?", err.message)

    def test_unterminated_multiline_comment(self):
        from lexer import Lexer, LexerError
        src = "/* this is an unterminated comment\nint x = 5;"
        with self.assertRaises(LexerError) as ctx:
            Lexer(src, language="c").tokenize()
        self.assertIn("Unterminated multi-line comment", str(ctx.exception))
        self.assertEqual(ctx.exception.line, 1)
        self.assertEqual(ctx.exception.col, 1)

    def test_malformed_numeric_literals(self):
        from lexer import Lexer, LexerError
        # Invalid suffix like 123abc
        with self.assertRaises(LexerError) as ctx:
            Lexer("int x = 123abc;", language="c").tokenize()
        self.assertIn("Malformed numeric literal", str(ctx.exception))
        self.assertEqual(ctx.exception.line, 1)

        # Multiple decimal points like 1.2.3
        with self.assertRaises(LexerError) as ctx:
            Lexer("float y = 1.2.3;", language="c").tokenize()
        self.assertIn("multiple decimal points", str(ctx.exception))
        self.assertEqual(ctx.exception.line, 1)

    def test_missing_semicolon_in_c(self):
        from parser import Parser, ParserError
        src = """int main() {
    int x = 5
    return 0;
}"""
        tokens = Lexer(src, language="c").tokenize()
        with self.assertRaises(ParserError) as ctx:
            Parser(tokens, language="c").parse_program()
        self.assertIn("expected ';'", str(ctx.exception))
        self.assertEqual(ctx.exception.line, 3)

    def test_unclosed_or_mismatched_braces(self):
        from parser import Parser, ParserError
        src = """int main() {
    int x = 5;
"""
        tokens = Lexer(src, language="c").tokenize()
        with self.assertRaises(ParserError) as ctx:
            Parser(tokens, language="c").parse_program()
        self.assertIn("expected '}'", str(ctx.exception))

    def test_trailing_comma_in_function_call(self):
        from parser import Parser, ParserError
        src = """#include <stdio.h>
int main() {
    printf("hello", );
    return 0;
}"""
        tokens = Lexer(src, language="c").tokenize()
        with self.assertRaises(ParserError) as ctx:
            Parser(tokens, language="c").parse_program()
        self.assertIn("trailing ','", str(ctx.exception).lower())
        self.assertEqual(ctx.exception.line, 3)

    def test_duplicate_variable_declaration_same_scope(self):
        source = """int main() {
    int x = 1;
    int x = 2;
    return 0;
}"""
        tokens = Lexer(source, language="c").tokenize()
        ast = Parser(tokens, language="c").parse_program()
        errors, declared, syms = semantic.analyze(ast, language="c")

        self.assertTrue(any(
            e.severity == "error" and "Redeclaration of variable 'x'" in e.message
            for e in errors
        ))

    def test_valid_full_compilation_all_stages_pass(self):
        client = app.test_client()
        source = """#include <stdio.h>

int main() {
    int total = 3 + 4 * 2;
    printf("Result = %d\\n", total);
    return 0;
}"""
        res = client.post("/compile", json={"source": source, "language": "c"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertTrue(data["success"])
        self.assertTrue(data["pipeline_success"])
        self.assertTrue(data["semantic_valid"])
        self.assertFalse(data["has_semantic_errors"])

        # All 7 stages passed
        stages = data["stages"]
        for stg in ["source", "tokens", "ast", "semantic", "ir", "asm", "explain"]:
            self.assertEqual(stages[stg], "passed")

        # Downstream artifacts generated
        self.assertIn("ir", data)
        self.assertIn("quadruples", data["ir"])
        self.assertIn("assembly", data)
        self.assertIn("x86_64", data["assembly"])
        self.assertIn("educational", data["assembly"])
        self.assertIn("explanation", data)
        self.assertGreater(len(data["explanation"]), 0)


if __name__ == "__main__":
    unittest.main()
