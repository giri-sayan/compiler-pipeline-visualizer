"""
Flask API — wires lexer + parser + semantic analyzer together.

Now handles a full multi-line PROGRAM (not just one line), because
semantic analysis (checking a variable was declared before use) only
makes sense across multiple lines.

One endpoint: POST /compile
  Input (JSON):  { "source": "x = 5\ny = x + 2" }
  Output (JSON): {
      "lines": [ { "line": 1, "source": "x = 5", "tokens": [...], "ast": {...} }, ... ],
      "semantic_errors": [ {"message": ..., "line": ...}, ... ],
      "declared_vars": ["x", "y"]
  }

If a specific LINE has a lexer/parser error, that line gets an
"error" field instead of tokens/ast, and it's simply skipped during
semantic analysis (no point checking a line that didn't even parse).

Run with:  python app.py
Then it's live at:  http://127.0.0.1:5000
"""

from flask import Flask, request, jsonify
from lexer import Lexer
from parser import Parser
import semantic

app = Flask(__name__)


@app.route("/compile", methods=["POST"])
def compile_source():
    data = request.get_json(silent=True)

    if not data or "source" not in data:
        return jsonify({"error": "Missing 'source' field in request body"}), 400

    source = data["source"]
    raw_lines = source.split("\n")

    line_results = []
    program_for_semantic = []  # only successfully-parsed lines go here

    for i, line in enumerate(raw_lines, start=1):
        stripped = line.strip()
        if stripped == "":
            continue  # skip blank lines, don't count them as statements

        entry = {"line": i, "source": stripped}

        try:
            tokens = Lexer(stripped).tokenize()
            entry["tokens"] = [t.to_dict() for t in tokens]

            ast = Parser(tokens).parse()
            ast_dict = ast.to_dict()
            entry["ast"] = ast_dict

            program_for_semantic.append({"line": i, "ast": ast_dict})

        except Exception as e:
            entry["error"] = str(e)

        line_results.append(entry)

    semantic_errors, declared_vars = semantic.analyze(program_for_semantic)

    return jsonify({
        "lines": line_results,
        "semantic_errors": [e.to_dict() for e in semantic_errors],
        "declared_vars": declared_vars,
    })


@app.route("/")
def home():
    return app.send_static_file("index.html")


if __name__ == "__main__":
    app.run(debug=True)
