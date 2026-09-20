"""
Flask API — Step 3 (wiring), ties lexer + parser together.

One endpoint: POST /compile
  Input (JSON):  { "source": "2 + 3 * 4" }
  Output (JSON): { "tokens": [...], "ast": {...} }

If the source has a lexer or parser error, returns a JSON error
message with a 400 status instead of crashing the server.

Run with:  python app.py
Then it's live at:  http://127.0.0.1:5000
"""

from flask import Flask, request, jsonify
from lexer import Lexer
from parser import Parser

app = Flask(__name__)


@app.route("/compile", methods=["POST"])
def compile_source():
    data = request.get_json(silent=True)

    if not data or "source" not in data:
        return jsonify({"error": "Missing 'source' field in request body"}), 400

    source = data["source"]

    try:
        # Stage 1: Lexing
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        tokens_json = [t.to_dict() for t in tokens]

        # Stage 2: Parsing
        parser = Parser(tokens)
        ast = parser.parse()
        ast_json = ast.to_dict()

        return jsonify({
            "source": source,
            "tokens": tokens_json,
            "ast": ast_json,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/", methods=["GET"])
def home():
    # Simple sanity-check page so you know the server is alive
    return "Compiler backend is running. POST source code to /compile"


if __name__ == "__main__":
    app.run(debug=True)