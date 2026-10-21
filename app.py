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
import re
from flask import Flask, request, jsonify, send_from_directory
from lexer import Lexer, LexerError
from parser import Parser, ParserError
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
    "c_lexical_error": {
        "name": "C Lexical Error (Unrecognized '@' Character)",
        "language": "c",
        "source": """#include <stdio.h>

int main() {
    int total = 3 @ 4;
    return 0;
}"""
    },
    "c_syntax_error": {
        "name": "C Syntax Error (Missing Operand '3 + ;')",
        "language": "c",
        "source": """#include <stdio.h>

int main() {
    int total = 3 + ;
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
    "c_semantic_warning": {
        "name": "C Semantic Warning (Uninitialized Var)",
        "language": "c",
        "source": """#include <stdio.h>

int main() {
    int a;
    int b = a + 5;
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


def make_diagnostic(stage, err, default_line=None, default_col=None, severity="error"):
    line = getattr(err, "line", None) or getattr(err, "line_number", None) or default_line
    col = getattr(err, "col", None) or default_col
    msg = str(err)
    if line is None:
        m_line = re.search(r'line\s+(\d+)', msg, re.IGNORECASE)
        if m_line:
            line = int(m_line.group(1))
    if col is None:
        m_col = re.search(r'col(?:umn)?\s+(\d+)', msg, re.IGNORECASE)
        if m_col:
            col = int(m_col.group(1))
    return {
        "stage": getattr(err, "stage", stage),
        "message": msg,
        "line": line,
        "col": col,
        "severity": getattr(err, "severity", severity)
    }


@app.route("/compile", methods=["POST"])
def compile_source():
    data = request.get_json(silent=True) or {}
    source = data.get("source", "")
    language = data.get("language", "c")

    if not source.strip():
        return jsonify({
            "error": "Source code cannot be empty",
            "diagnostics": [{
                "stage": "Source",
                "message": "Source code cannot be empty",
                "line": 1,
                "col": 1,
                "severity": "error"
            }],
            "stages": {
                "source": "failed",
                "tokens": "blocked",
                "ast": "blocked",
                "semantic": "blocked",
                "ir": "blocked",
                "asm": "blocked",
                "explain": "blocked",
            }
        }), 400

    raw_lines = source.split("\n")
    line_results = []

    # 1. Whole-Program Lexical Analysis
    try:
        lexer = Lexer(source, language=language)
        tokens = lexer.tokenize()
        tokens_list = [t.to_dict() for t in tokens]
    except Exception as e:
        diag = make_diagnostic("Lexer", e)
        partial_tokens = [t.to_dict() for t in getattr(lexer, "tokens_so_far", [])]
        return jsonify({
            "success": False,
            "pipeline_success": False,
            "stage": "Lexer",
            "error": str(e),
            "diagnostics": [diag],
            "stages": {
                "source": "passed",
                "tokens": "failed",
                "ast": "blocked",
                "semantic": "blocked",
                "ir": "blocked",
                "asm": "blocked",
                "explain": "blocked",
            },
            "tokens": partial_tokens,
            "lines": [{"line": diag.get("line") or 1, "source": source, "error": str(e)}],
        }), 200

    # 2. Whole-Program Syntax Analysis (AST)
    try:
        parser = Parser(tokens)
        ast = parser.parse_program()
        ast_dict = ast.to_dict()
    except Exception as e:
        diag = make_diagnostic("Parser", e)
        return jsonify({
            "success": False,
            "pipeline_success": False,
            "stage": "Parser",
            "error": str(e),
            "diagnostics": [diag],
            "stages": {
                "source": "passed",
                "tokens": "passed",
                "ast": "failed",
                "semantic": "blocked",
                "ir": "blocked",
                "asm": "blocked",
                "explain": "blocked",
            },
            "tokens": tokens_list,
            "lines": [{"line": diag.get("line") or 1, "source": source, "error": str(e)}],
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
    try:
        semantic_errors, declared_vars, symbol_table = semantic.analyze(ast)
    except Exception as e:
        diag = make_diagnostic("Semantic Analyzer", e)
        return jsonify({
            "success": False,
            "pipeline_success": False,
            "stage": "Semantic Analyzer",
            "error": f"Semantic analysis error: {e}",
            "diagnostics": [diag],
            "stages": {
                "source": "passed",
                "tokens": "passed",
                "ast": "passed",
                "semantic": "failed",
                "ir": "blocked",
                "asm": "blocked",
                "explain": "blocked",
            },
            "tokens": tokens_list,
            "ast": ast_dict,
            "lines": line_results,
        }), 200

    # 4. Intermediate Representation (Three-Address Code & Quadruples)
    try:
        ir_data = generate_ir(ast)
    except Exception as e:
        diag = make_diagnostic("IR Generator", e)
        return jsonify({
            "success": False,
            "pipeline_success": False,
            "stage": "IR Generator",
            "error": f"IR generation error: {e}",
            "diagnostics": [diag],
            "stages": {
                "source": "passed",
                "tokens": "passed",
                "ast": "passed",
                "semantic": "passed",
                "ir": "failed",
                "asm": "blocked",
                "explain": "blocked",
            },
            "tokens": tokens_list,
            "ast": ast_dict,
            "lines": line_results,
        }), 200

    # 5. Target Code Generation (x86-64 & Educational RISC)
    try:
        assembly_data = generate_code(ir_data)
    except Exception as e:
        diag = make_diagnostic("Code Generator", e)
        return jsonify({
            "success": False,
            "pipeline_success": False,
            "stage": "Code Generator",
            "error": f"Code generation error: {e}",
            "diagnostics": [diag],
            "stages": {
                "source": "passed",
                "tokens": "passed",
                "ast": "passed",
                "semantic": "passed",
                "ir": "passed",
                "asm": "failed",
                "explain": "blocked",
            },
            "tokens": tokens_list,
            "ast": ast_dict,
            "ir": ir_data,
            "lines": line_results,
        }), 200

    # 6. Guided Educational Explanation
    try:
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
    except Exception as e:
        explanation = []

    semantic_diagnostics = [e.to_dict() if hasattr(e, "to_dict") else e for e in semantic_errors]
    has_semantic_errors = any(
        (e.severity if hasattr(e, "severity") else e.get("severity", "error")) == "error"
        for e in semantic_errors
    )
    semantic_valid = len(semantic_errors) == 0

    if has_semantic_errors:
        semantic_stage_status = "failed"
    elif len(semantic_errors) > 0:
        semantic_stage_status = "warning"
    else:
        semantic_stage_status = "passed"

    stages_status = {
        "source": "passed",
        "tokens": "passed",
        "ast": "passed",
        "semantic": semantic_stage_status,
        "ir": "passed",
        "asm": "passed",
        "explain": "passed",
    }

    return jsonify({
        "success": True,
        "pipeline_success": True,
        "semantic_valid": semantic_valid,
        "has_semantic_errors": has_semantic_errors,
        "diagnostics": semantic_diagnostics,
        "stages": stages_status,
        "language": language,
        "lines": line_results,
        "tokens": tokens_list,
        "ast": ast_dict,
        "semantic_errors": semantic_diagnostics,
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
    app.run(debug=True, use_reloader=False, port=5000)
