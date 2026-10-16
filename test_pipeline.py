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


if __name__ == "__main__":
    unittest.main()
