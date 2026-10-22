"""
Semantic Analyzer — Step 3 of the compiler pipeline.

Validates semantic rules and constructs the Symbol Table:
  1. Scope checks (global vs function scope).
  2. Variables must be declared / assigned before use.
  3. Detects uninitialized variables and type consistency.
  4. Records type, scope, and line metadata for every symbol.
  5. Validates function calls against standard headers and user definitions with typo suggestions.
"""

import difflib
import re

# Standard C headers and their supported functions
HEADER_BUILTINS = {
    "stdio.h": {"printf", "scanf", "puts", "gets", "getchar", "putchar", "perror", "fprintf", "sprintf", "snprintf"},
    "stdlib.h": {"malloc", "free", "exit", "abort", "abs", "atoi", "atol", "rand", "srand", "system"},
    "math.h": {"sqrt", "pow", "sin", "cos", "tan", "floor", "ceil", "log", "exp", "fabs"},
    "string.h": {"strlen", "strcpy", "strncpy", "strcmp", "strncmp", "strcat", "strncat", "memcpy", "memset"},
}

ALL_C_STANDARD_FUNCTIONS = set()
for funcs in HEADER_BUILTINS.values():
    ALL_C_STANDARD_FUNCTIONS.update(funcs)

GLOBAL_BUILTIN_CONSTANTS = {"NULL", "true", "false"}
TOY_BUILTIN_FUNCTIONS = {"print", "len", "range", "input"}


class SemanticError:
    def __init__(self, message, line_number=1, severity="error", col=None):
        self.message = message
        self.line_number = line_number
        self.line = line_number
        self.col = col
        self.column = col
        self.severity = severity
        self.stage = "Semantic Analyzer"

    def to_dict(self):
        return {
            "stage": self.stage,
            "message": self.message,
            "line": self.line_number,
            "col": self.col,
            "column": self.col,
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


def _check_expression(expr, symbol_table, scope, line, errors, included_headers=None, language="c"):
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
        if name in GLOBAL_BUILTIN_CONSTANTS:
            return

        # Check if declared in current scope or global scope
        sym = symbol_table.get((scope, name)) or symbol_table.get(("global", name))
        if sym is None:
            # Check if this identifier is a known function in included headers
            if language == "c" and included_headers:
                if any(name in HEADER_BUILTINS.get(hdr, set()) for hdr in included_headers):
                    return
            if language in ("toy", "python") and name in TOY_BUILTIN_FUNCTIONS:
                return

            declared_names = [n for (s, n) in symbol_table.keys() if s in (scope, "global")]
            matches = difflib.get_close_matches(name, declared_names, n=1, cutoff=0.6)
            hint = f". Did you mean '{matches[0]}'?" if matches else ""
            errors.append(SemanticError(
                f"Variable '{name}' used before it was declared or assigned{hint}",
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
        _check_expression(expr.get("left"), symbol_table, scope, line, errors, included_headers, language)
        _check_expression(expr.get("right"), symbol_table, scope, line, errors, included_headers, language)

    elif etype == "UnaryOp":
        _check_expression(expr.get("operand"), symbol_table, scope, line, errors, included_headers, language)

    elif etype == "FunctionCall":
        fname = expr.get("name")

        # 1. Check function arguments
        for arg in expr.get("args", []):
            _check_expression(arg, symbol_table, scope, line, errors, included_headers, language)

        # 2. Check function definition or declaration
        is_known = False

        # User-defined function or symbol in symbol table
        sym = symbol_table.get(("global", fname)) or symbol_table.get((scope, fname))
        if sym is not None:
            if not sym.datatype.startswith("function"):
                errors.append(SemanticError(
                    f"Called object '{fname}' is not a function (declared as '{sym.datatype}')",
                    expr_line,
                    severity="error",
                    col=expr_col
                ))
                return
            is_known = True

        # Toy / Python language builtins
        if not is_known and language in ("toy", "python"):
            if fname in TOY_BUILTIN_FUNCTIONS:
                is_known = True

        # C language standard library functions
        if not is_known and language == "c":
            if included_headers:
                for hdr in included_headers:
                    if hdr in HEADER_BUILTINS and fname in HEADER_BUILTINS[hdr]:
                        is_known = True
                        break

        if not is_known:
            # Check if it is a standard C library function whose header was not included
            needed_header = None
            if language == "c":
                for hdr, funcs in HEADER_BUILTINS.items():
                    if fname in funcs and (not included_headers or hdr not in included_headers):
                        needed_header = hdr
                        break

            if needed_header:
                msg = f"Unknown function '{fname}'. Did you forget to '#include <{needed_header}>'?"
            else:
                # Check for typos among candidates
                candidates = set(ALL_C_STANDARD_FUNCTIONS)
                if included_headers:
                    for hdr in included_headers:
                        candidates.update(HEADER_BUILTINS.get(hdr, set()))
                if language in ("toy", "python"):
                    candidates.update(TOY_BUILTIN_FUNCTIONS)
                for (s, n), s_obj in symbol_table.items():
                    if s == "global" and s_obj.datatype.startswith("function"):
                        candidates.add(n)

                matches = difflib.get_close_matches(fname, list(candidates), n=1, cutoff=0.55)
                if matches:
                    msg = f"Unknown function '{fname}'. Did you mean '{matches[0]}'?"
                else:
                    msg = f"Unknown function '{fname}'. Function was not declared or defined in this scope"

            errors.append(SemanticError(msg, line_number=expr_line, severity="error", col=expr_col))


def _process_statement(stmt, symbol_table, scope, errors, included_headers=None, language="c"):
    """Processes a single statement dict, updating the symbol table and recording errors."""
    if not stmt or not isinstance(stmt, dict):
        return

    stype = stmt.get("type")
    line = stmt.get("line", 1)
    col = stmt.get("col", None)

    if stype == "Include":
        header = stmt.get("header", "").strip()
        clean_hdr = re.sub(r'[<">]', '', header).strip()
        if included_headers is not None:
            included_headers.add(clean_hdr)
        return

    elif stype == "VarDecl":
        datatype = stmt.get("datatype", "auto")
        name = stmt.get("name")
        init_val = stmt.get("value")

        key = (scope, name)
        if key in symbol_table:
            errors.append(SemanticError(
                f"Redeclaration of variable '{name}' in the same scope '{scope}'",
                line,
                severity="error",
                col=col
            ))

        if init_val:
            _check_expression(init_val, symbol_table, scope, line, errors, included_headers, language)
            symbol_table[key] = Symbol(name, datatype, scope=scope, line=line, initialized=True, col=col)
        else:
            symbol_table[key] = Symbol(name, datatype, scope=scope, line=line, initialized=False, col=col)

    elif stype == "Assign":
        name = stmt.get("name")
        val = stmt.get("value")

        # Check right-hand side first
        _check_expression(val, symbol_table, scope, line, errors, included_headers, language)

        key = (scope, name)
        if key in symbol_table:
            symbol_table[key].initialized = True
        elif ("global", name) in symbol_table:
            symbol_table[("global", name)].initialized = True
        else:
            if language == "c":
                declared_names = [n for (s, n) in symbol_table.keys() if s in (scope, "global")]
                matches = difflib.get_close_matches(name, declared_names, n=1, cutoff=0.6)
                hint = f". Did you mean '{matches[0]}'?" if matches else ""
                errors.append(SemanticError(
                    f"Variable '{name}' used before it was declared or assigned{hint}",
                    line,
                    severity="error",
                    col=col
                ))
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
            _process_statement(body_stmt, symbol_table, func_scope, errors, included_headers, language)

    elif stype == "Return":
        val = stmt.get("value")
        if val:
            _check_expression(val, symbol_table, scope, line, errors, included_headers, language)

    elif stype == "FunctionCall":
        _check_expression(stmt, symbol_table, scope, line, errors, included_headers, language)

    elif stype == "If":
        _check_expression(stmt.get("condition"), symbol_table, scope, line, errors, included_headers, language)
        for s in stmt.get("then_branch", []):
            _process_statement(s, symbol_table, scope, errors, included_headers, language)
        for s in stmt.get("else_branch", []):
            _process_statement(s, symbol_table, scope, errors, included_headers, language)

    elif stype == "BinOp" or stype == "Identifier" or stype == "Number":
        _check_expression(stmt, symbol_table, scope, line, errors, included_headers, language)


def analyze(program, language=None):
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
    included_headers = set()

    lang = language
    if lang is None:
        lang = getattr(program, "language", None)

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

    if lang is None:
        lang = prog_dict.get("language")

    if lang is None:
        # Auto-detect: if any C-specific constructs, it's C, otherwise toy
        has_c = any(
            (isinstance(s, dict) and s.get("type") in ("Include", "FunctionDef")) or
            (isinstance(s, dict) and s.get("type") == "VarDecl" and s.get("datatype") in ("int", "float", "char", "void", "double", "long", "short"))
            for s in statements
        )
        lang = "c" if has_c else "toy"

    lang = str(lang).lower()

    for stmt in statements:
        _process_statement(stmt, symbol_table, scope="global", errors=errors, included_headers=included_headers, language=lang)

    # Entry point validation for C programs
    if lang == "c":
        function_defs = [s for s in statements if isinstance(s, dict) and s.get("type") == "FunctionDef"]
        has_include = any(isinstance(s, dict) and s.get("type") == "Include" for s in statements)

        if function_defs:
            has_main = any(f.get("name") == "main" for f in function_defs)
            if not has_main:
                # Check if any function definition is a typo for 'main'
                main_typo_func = None
                for f in function_defs:
                    fname = f.get("name", "")
                    if fname.lower() in ("ain", "mian", "maim", "mani", "mainn", "mein", "man", "min", "an") or difflib.get_close_matches(fname.lower(), ["main"], cutoff=0.6):
                        main_typo_func = f
                        break

                if main_typo_func:
                    mf_name = main_typo_func.get("name")
                    mf_line = main_typo_func.get("line", 1)
                    mf_col = main_typo_func.get("col", None)
                    errors.append(SemanticError(
                        f"Unknown entry point function '{mf_name}'. C programs require a 'main' function as the entry point. Did you mean 'main'?",
                        line_number=mf_line,
                        severity="error",
                        col=mf_col
                    ))
                else:
                    first_f = function_defs[0]
                    errors.append(SemanticError(
                        "Missing 'main' function. C programs require a 'main' function as the entry point.",
                        line_number=first_f.get("line", 1),
                        severity="error",
                        col=first_f.get("col", None)
                    ))
        elif has_include:
            errors.append(SemanticError(
                "Missing 'main' function. C programs require a 'main' function as the entry point.",
                line_number=1,
                severity="error",
                col=1
            ))

    symbol_table_list = [sym.to_dict() for sym in symbol_table.values()]
    declared_vars = sorted(list({sym.name for sym in symbol_table.values() if not sym.datatype.startswith("function")}))

    return errors, declared_vars, symbol_table_list


if __name__ == "__main__":
    from lexer import Lexer
    from parser import Parser

    c_sample = '''#include <stdio.h>
int main() {
    int total = 3 + 4 * 2;
    rintf("Result = %d\\n", total);
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
