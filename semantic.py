"""
Semantic Analyzer — Step 3 of the compiler pipeline (new for 40% milestone).

Takes a PROGRAM: a list of AST nodes (one per line of source), already
converted to dicts (via .to_dict()), and checks a real semantic rule:

    A variable must be ASSIGNED before it is USED.

This is exactly the kind of check a real compiler does after parsing
and before generating code — parsing only checks grammar/structure,
it has no idea whether 'x' was ever actually given a value.

Example that should PASS:
    x = 5
    y = x + 2

Example that should FAIL:
    y = x + 2      <- x was never assigned anywhere before this
"""


class SemanticError:
    def __init__(self, message, line_number):
        self.message = message
        self.line_number = line_number

    def to_dict(self):
        return {"message": self.message, "line": self.line_number}


def _check_expr(node, declared, line_number, errors):
    """Recursively walk an expression node, flagging undeclared identifiers."""
    node_type = node["type"]

    if node_type == "Number":
        return  # numbers are always fine, nothing to check

    if node_type == "Identifier":
        name = node["name"]
        if name not in declared:
            errors.append(SemanticError(
                f"Variable '{name}' used before it was assigned a value",
                line_number
            ))
        return

    if node_type == "BinOp":
        _check_expr(node["left"], declared, line_number, errors)
        _check_expr(node["right"], declared, line_number, errors)
        return


def analyze(program):
    """
    program: list of dicts, each like {"line": 1, "ast": {...}}
             (one entry per successfully parsed source line, in order)

    Returns: (errors, declared_vars)
        errors        -> list of SemanticError
        declared_vars -> sorted list of variable names that got assigned
    """
    declared = set()
    errors = []

    for entry in program:
        line_number = entry["line"]
        node = entry["ast"]

        if node["type"] == "Assign":
            # Check the right-hand side BEFORE declaring the variable,
            # so "x = x + 1" correctly fails if x was never set before.
            _check_expr(node["value"], declared, line_number, errors)
            declared.add(node["name"])
        else:
            _check_expr(node, declared, line_number, errors)

    return errors, sorted(declared)


# ---- Quick manual test ----
if __name__ == "__main__":
    from lexer import Lexer
    from parser import Parser

    def run_program(lines):
        program = []
        for i, line in enumerate(lines, start=1):
            tokens = Lexer(line).tokenize()
            ast = Parser(tokens).parse()
            program.append({"line": i, "ast": ast.to_dict()})
        return program

    print("--- Test 1: should PASS (x declared before use) ---")
    good = run_program(["x = 5", "y = x + 2"])
    errors, declared = analyze(good)
    print("Declared:", declared)
    print("Errors:", [e.to_dict() for e in errors])

    print("\n--- Test 2: should FAIL (x used before declared) ---")
    bad = run_program(["y = x + 2", "x = 5"])
    errors, declared = analyze(bad)
    print("Declared:", declared)
    print("Errors:", [e.to_dict() for e in errors])
