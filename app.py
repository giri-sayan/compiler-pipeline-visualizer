"""
Flask API — Comprehensive Compiler Pipeline Visualizer Server.

Wires together all 5 pipeline stages + pedagogical explainer + diff mode:
  Stage 1: Lexer (Tokens)
  Stage 2: Parser (AST)
  Stage 3: Semantic Analyzer (Symbol Table & Scope Diagnostics)
  Stage 4: IR Generator (Three-Address Code & Quadruples)
  Stage 5: Target Code Generator (x86-64 & Educational Pseudo-Assembly)
  Plus:
    - Multi-language support (C with #include, Toy Mini-Lang, Python)
    - Full Guided Educational Explanations
    - Side-by-Side Stage Diff Mode
"""

import os
from flask import Flask, request, jsonify, send_from_directory
from lexer import Lexer
from parser import Parser
import semantic
from ir_generator import generate_ir
from codegen import generate_code
from explainer import generate_explanation
import diff_service

app = Flask(__name__, static_folder="static")

PRESETS = {
    "c_complete": {
        "name": "C Program (#include & main)",
        "language": "c",
        "source": """#include <stdio.h>

int main() {
    int total = 3 + 4 * 2;
    printf("Result = %d\\n", total);
    return 0;
}"""
    },
    "c_precedence": {
        "name": "C Precedence Demo (int x = 2 + 3 * 4;)",
        "language": "c",
        "source": """#include <stdio.h>

int main() {
    int x = 2 + 3 * 4;
    int y = (2 + 3) * 4;
    return 0;
}"""
    },
    "c_semantic_error": {
        "name": "C Semantic Error (Undeclared Var)",
        "language": "c",
        "source": """#include <stdio.h>

int main() {
    int a = 10;
    int b = a + missing_var;
    return 0;
}"""
    },
    "c_conditional": {
        "name": "C Control Flow (if / else)",
        "language": "c",
        "source": """#include <stdio.h>

int main() {
    int score = 85;
    int bonus = 0;
    if (score > 80) {
        bonus = 10;
    } else {
        bonus = 2;
    }
    return 0;
}"""
    },
    "toy_pipeline": {
        "name": "Toy Mini-Lang (x = 5, y = x + 2)",
        "language": "toy",
        "source": """x = 5
y = x + 2
z = (x + y) * 3"""
    },
}


@app.route("/compile", methods=["POST"])
def compile_source():
    data = request.get_json(silent=True) or {}
    source = data.get("source", "")
    language = data.get("language", "c")

    if not source.strip():
        return jsonify({"error": "Source code cannot be empty"}), 400

    raw_lines = source.split("\n")
    line_results = []

    # 1. Whole-Program Lexical Analysis
    try:
        lexer = Lexer(source, language=language)
        tokens = lexer.tokenize()
        tokens_list = [t.to_dict() for t in tokens]
    except Exception as e:
        return jsonify({
            "success": False,
            "stage": "Lexer",
            "error": str(e),
            "lines": [{"line": 1, "source": source, "error": str(e)}],
        }), 200

    # 2. Whole-Program Syntax Analysis (AST)
    try:
        parser = Parser(tokens)
        ast = parser.parse_program()
        ast_dict = ast.to_dict()
    except Exception as e:
        return jsonify({
            "success": False,
            "stage": "Parser",
            "error": str(e),
            "tokens": tokens_list,
            "lines": [{"line": 1, "source": source, "error": str(e)}],
        }), 200

    # Build per-line breakdown for backward compatibility
    for i, line in enumerate(raw_lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        line_entry = {"line": i, "source": stripped}
        line_toks = [t for t in tokens_list if t.get("line") == i and t.get("type") != "EOF"]
        line_entry["tokens"] = line_toks
        line_results.append(line_entry)

    # 3. Semantic Analysis & Symbol Table
    semantic_errors, declared_vars, symbol_table = semantic.analyze(ast)

    # 4. Intermediate Representation (Three-Address Code & Quadruples)
    ir_data = generate_ir(ast)

    # 5. Target Code Generation (x86-64 & Educational RISC)
    assembly_data = generate_code(ir_data)

    # 6. Guided Educational Explanation
    explanation = generate_explanation(
        tokens=tokens_list,
        ast=ast,
        semantic_info={
            "errors": [e.to_dict() if hasattr(e, "to_dict") else e for e in semantic_errors],
            "declared_vars": declared_vars,
            "symbol_table": symbol_table,
        },
        ir_data=ir_data,
        assembly_data=assembly_data,
        language=language,
    )

    return jsonify({
        "success": True,
        "language": language,
        "lines": line_results,
        "tokens": tokens_list,
        "ast": ast_dict,
        "semantic_errors": [e.to_dict() if hasattr(e, "to_dict") else e for e in semantic_errors],
        "declared_vars": declared_vars,
        "symbol_table": symbol_table,
        "ir": ir_data,
        "assembly": assembly_data,
        "explanation": explanation,
    })


@app.route("/diff", methods=["POST"])
def diff_programs():
    data = request.get_json(silent=True) or {}
    source_a = data.get("source_a", "")
    source_b = data.get("source_b", "")
    language = data.get("language", "c")

    if not source_a.strip() or not source_b.strip():
        return jsonify({"error": "Both Program A and Program B sources are required"}), 400

    try:
        comparison = diff_service.compare_programs(source_a, source_b, language=language)
        return jsonify({"success": True, "data": comparison})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/presets", methods=["GET"])
def get_presets():
    return jsonify(PRESETS)


@app.route("/")
def home():
    static_html = os.path.join(app.root_path, "static", "index.html")
    if os.path.exists(static_html):
        return app.send_static_file("index.html")
    return send_from_directory(app.root_path, "index.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
