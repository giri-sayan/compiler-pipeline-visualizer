"""
Semantic Analyzer — Step 3 of the compiler pipeline.

Validates semantic rules and constructs the Symbol Table:
  1. Scope checks (global vs function scope).
  2. Variables must be declared / assigned before use.
  3. Detects uninitialized variables and type consistency.
  4. Records type, scope, and line metadata for every symbol.
"""


class SemanticError:
    def __init__(self, message, line_number=1, severity="error", col=None):
        self.message = message
        self.line_number = line_number
        self.line = line_number
        self.col = col
        self.severity = severity
        self.stage = "Semantic Analyzer"

    def to_dict(self):
        return {
            "stage": self.stage,
            "message": self.message,
            "line": self.line_number,
            "col": self.col,
            "severity": self.severity,
        }

    def __repr__(self):
        col_str = f", col={self.col}" if self.col is not None else ""
        return f"SemanticError({self.message!r}, line={self.line_number}{col_str}, severity={self.severity})"


class Symbol:
    def __init__(self, name, datatype, scope="global", line=1, initialized=False, col=None):
        self.name = name
        self.datatype = datatype
        self.scope = scope
        self.line = line
        self.col = col
        self.initialized = initialized

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.datatype,
            "scope": self.scope,
            "line": self.line,
            "col": self.col,
            "initialized": self.initialized,
            "status": "Initialized" if self.initialized else "Declared (Uninitialized)",
        }


def _check_expression(expr, symbol_table, scope, line, errors):
    """Recursively validates an expression node against the symbol table."""
    if not expr or not isinstance(expr, dict):
        return

    etype = expr.get("type")
    expr_line = expr.get("line", line)
    expr_col = expr.get("col", None)

    if etype == "Number" or etype == "String":
        return

    if etype == "Identifier":
        name = expr.get("name")
        # Check standard C built-ins or pre-defined identifiers
        builtins = {"printf", "scanf", "puts", "getchar", "NULL", "true", "false", "print"}
        if name in builtins:
            return

        # Check if declared in current scope or global scope
        sym = symbol_table.get((scope, name)) or symbol_table.get(("global", name))
        if sym is None:
            errors.append(SemanticError(
                f"Variable '{name}' used before it was declared or assigned",
                expr_line,
                severity="error",
                col=expr_col
            ))
        elif not sym.initialized:
            errors.append(SemanticError(
                f"Variable '{name}' used without being initialized with a value",
                expr_line,
                severity="warning",
                col=expr_col
            ))

    elif etype == "BinOp":
        _check_expression(expr.get("left"), symbol_table, scope, line, errors)
        _check_expression(expr.get("right"), symbol_table, scope, line, errors)

    elif etype == "UnaryOp":
        _check_expression(expr.get("operand"), symbol_table, scope, line, errors)

    elif etype == "FunctionCall":
        fname = expr.get("name")
        # Function arguments check
        for arg in expr.get("args", []):
            _check_expression(arg, symbol_table, scope, line, errors)


def _process_statement(stmt, symbol_table, scope, errors):
    """Processes a single statement dict, updating the symbol table and recording errors."""
    if not stmt or not isinstance(stmt, dict):
        return

    stype = stmt.get("type")
    line = stmt.get("line", 1)
    col = stmt.get("col", None)

    if stype == "Include":
        # #include directive — valid preprocessor stage
        return

    elif stype == "VarDecl":
        datatype = stmt.get("datatype", "auto")
        name = stmt.get("name")
        init_val = stmt.get("value")

        key = (scope, name)
        if key in symbol_table:
            errors.append(SemanticError(
                f"Variable '{name}' re-declared in the same scope '{scope}'",
                line,
                severity="warning",
                col=col
            ))

        if init_val:
            _check_expression(init_val, symbol_table, scope, line, errors)
            symbol_table[key] = Symbol(name, datatype, scope=scope, line=line, initialized=True, col=col)
        else:
            symbol_table[key] = Symbol(name, datatype, scope=scope, line=line, initialized=False, col=col)

    elif stype == "Assign":
        name = stmt.get("name")
        val = stmt.get("value")

        # Check right-hand side first
        _check_expression(val, symbol_table, scope, line, errors)

        key = (scope, name)
        if key in symbol_table:
            symbol_table[key].initialized = True
        elif ("global", name) in symbol_table:
            symbol_table[("global", name)].initialized = True
        else:
            # In Toy/Python language, assignment acts as implicit declaration
            symbol_table[key] = Symbol(name, "auto", scope=scope, line=line, initialized=True, col=col)

    elif stype == "FunctionDef":
        fname = stmt.get("name")
        ret_type = stmt.get("return_type", "void")
        # Register function symbol in global scope
        symbol_table[("global", fname)] = Symbol(fname, f"function() -> {ret_type}", scope="global", line=line, initialized=True, col=col)

        func_scope = fname
        # Register parameters
        for p in stmt.get("params", []):
            pname = p.get("name")
            ptype = p.get("type", "auto")
            if pname:
                symbol_table[(func_scope, pname)] = Symbol(pname, ptype, scope=func_scope, line=line, initialized=True)

        # Walk body
        for body_stmt in stmt.get("body", []):
            _process_statement(body_stmt, symbol_table, func_scope, errors)

    elif stype == "Return":
        val = stmt.get("value")
        if val:
            _check_expression(val, symbol_table, scope, line, errors)

    elif stype == "FunctionCall":
        _check_expression(stmt, symbol_table, scope, line, errors)

    elif stype == "If":
        _check_expression(stmt.get("condition"), symbol_table, scope, line, errors)
        for s in stmt.get("then_branch", []):
            _process_statement(s, symbol_table, scope, errors)
        for s in stmt.get("else_branch", []):
            _process_statement(s, symbol_table, scope, errors)

    elif stype == "BinOp" or stype == "Identifier" or stype == "Number":
        _check_expression(stmt, symbol_table, scope, line, errors)


def analyze(program):
    """
    Analyzes an AST program or legacy line-by-line list.

    Returns:
        (errors, declared_vars, symbol_table_list)
        - errors: list of SemanticError
        - declared_vars: sorted list of assigned/declared variable names
        - symbol_table_list: list of Symbol dicts for frontend visualization
    """
    symbol_table = {}  # (scope, name) -> Symbol
    errors = []

    # Handle various input formats
    if hasattr(program, "to_dict"):
        prog_dict = program.to_dict()
    elif isinstance(program, dict):
        prog_dict = program
    elif isinstance(program, list):
        # Legacy list: [{"line": 1, "ast": {...}}, ...]
        statements = []
        for entry in program:
            if isinstance(entry, dict) and "ast" in entry:
                ast_entry = entry["ast"]
                if isinstance(ast_entry, dict) and "line" not in ast_entry:
                    ast_entry["line"] = entry.get("line", 1)
                statements.append(ast_entry)
            elif isinstance(entry, dict):
                statements.append(entry)
        prog_dict = {"type": "Program", "statements": statements}
    else:
        prog_dict = {"type": "Program", "statements": []}

    statements = prog_dict.get("statements", [])
    if not statements and prog_dict.get("type") not in ("Program", None):
        # Single top-level statement passed
        statements = [prog_dict]

    for stmt in statements:
        _process_statement(stmt, symbol_table, scope="global", errors=errors)

    symbol_table_list = [sym.to_dict() for sym in symbol_table.values()]
    declared_vars = sorted(list({sym.name for sym in symbol_table.values() if not sym.datatype.startswith("function")}))

    return errors, declared_vars, symbol_table_list


if __name__ == "__main__":
    from lexer import Lexer
    from parser import Parser

    c_sample = '''#include <stdio.h>
int main() {
    int total = 3 + 4 * 2;
    int unused;
    int err = unknown_var + 1;
    return 0;
}'''

    tokens = Lexer(c_sample).tokenize()
    ast = Parser(tokens).parse_program()
    errs, declared, syms = analyze(ast)

    print("Symbol Table:")
    for s in syms:
        print(" ", s)
    print("\nErrors / Warnings:")
    for e in errs:
        print(" ", e)
