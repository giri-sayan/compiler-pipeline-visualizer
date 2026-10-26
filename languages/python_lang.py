"""
Python Language Compiler Frontend.

Uses Python's genuine standard library `ast` and `tokenize` modules to provide:
  - Exact token stream with line and column tracking.
  - Normalized AST tree matching compiler visualizer conventions.
  - True Python semantic analysis with scope checking, symbol tables, and typo diagnostics (e.g. pirnt -> print).
  - Intermediate Representation (TAC Quadruples) and Assembly code generation.
  - Safe sandboxed runtime execution.
"""

import ast as py_ast
import io
import difflib
import tokenize as py_tokenize
from typing import Dict, Any, List, Tuple, Optional
from languages.base import BaseCompiler
from tac_vm import TACVirtualMachine
from executor import SafeExecutor
from explainer import generate_explanation


PYTHON_BUILTINS = {
    "print", "len", "range", "input", "int", "float", "str", "bool",
    "list", "dict", "set", "tuple", "abs", "max", "min", "sum",
    "enumerate", "zip", "open", "round", "sorted", "reversed", "isinstance", "type"
}


class PythonCompilerError(Exception):
    def __init__(self, message: str, line: int = 1, col: int = 1, stage: str = "Parser"):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        self.stage = stage
        self.severity = "error"

    def to_dict(self):
        return {
            "stage": self.stage,
            "message": self.message,
            "line": self.line,
            "col": self.col,
            "column": self.col,
            "severity": self.severity
        }


class PythonCompiler(BaseCompiler):
    language_id = "python"
    display_name = "Python (Subset: def, print, control flow, types)"
    file_extension = ".py"

    def tokenize(self, source: str) -> List[Dict[str, Any]]:
        tokens = []
        try:
            reader = io.StringIO(source).readline
            for tok in py_tokenize.generate_tokens(reader):
                tok_type_name = py_tokenize.tok_name.get(tok.type, "TOKEN")
                # Normalize token names
                val = tok.string
                norm_type = "IDENTIFIER"

                if tok_type_name == "NUMBER":
                    norm_type = "NUMBER"
                    val = float(val) if "." in val else int(val)
                elif tok_type_name == "STRING":
                    norm_type = "STRING"
                    # strip quotes for value
                    val = val[1:-1] if len(val) >= 2 and val[0] in ('"', "'") else val
                elif tok_type_name == "NAME":
                    if val in ("def", "return", "if", "elif", "else", "while", "for", "in", "import", "from", "as", "class", "pass", "break", "continue"):
                        norm_type = val.upper()
                    elif val in ("True", "False", "None"):
                        norm_type = "BOOLEAN"
                    else:
                        norm_type = "IDENTIFIER"
                elif tok_type_name == "OP":
                    op_map = {
                        "+": "PLUS", "-": "MINUS", "*": "MUL", "/": "DIV", "%": "MOD",
                        "=": "ASSIGN", "==": "EQ", "!=": "NEQ", "<": "LT", ">": "GT",
                        "<=": "LTE", ">=": "GTE", "(": "LPAREN", ")": "RPAREN",
                        ":": "COLON", ",": "COMMA", "[": "LBRACKET", "]": "RBRACKET",
                        "{": "LBRACE", "}": "RBRACE"
                    }
                    norm_type = op_map.get(val, "OPERATOR")
                elif tok_type_name in ("NEWLINE", "NL", "INDENT", "DEDENT"):
                    norm_type = tok_type_name
                elif tok_type_name == "COMMENT":
                    continue  # skip comments in token stream display
                elif tok_type_name == "ENDMARKER":
                    norm_type = "EOF"
                    val = None

                tokens.append({
                    "type": norm_type,
                    "value": val,
                    "line": tok.start[0],
                    "col": tok.start[1] + 1
                })
        except Exception as e:
            # Fallback if tokenize fails
            m_line = getattr(e, "lineno", 1) if hasattr(e, "lineno") else 1
            m_col = getattr(e, "offset", 1) if hasattr(e, "offset") else 1
            raise PythonCompilerError(f"Lexical error: {e}", line=m_line, col=m_col, stage="Lexer")

        return tokens

    def parse(self, tokens: List[Any], source: str = "") -> Dict[str, Any]:
        try:
            tree = py_ast.parse(source)
            return self._convert_ast(tree)
        except SyntaxError as e:
            line = e.lineno or 1
            col = e.offset or 1
            msg = e.msg or "Invalid Python syntax"
            raise PythonCompilerError(f"Syntax error: {msg} at line {line}, col {col}", line=line, col=col, stage="Parser")
        except Exception as e:
            e_line = getattr(e, "lineno", None) or getattr(e, "line", None) or getattr(e, "line_number", None)
            e_col = getattr(e, "offset", None) or getattr(e, "col", None) or getattr(e, "column", None)
            if e_line is None:
                m = re.search(r'\b(?:line|L)\s*[:#]?\s*(\d+)', str(e), re.IGNORECASE)
                if m:
                    e_line = int(m.group(1))
            if e_col is None:
                m_c = re.search(r'\b(?:col(?:umn)?|offset)\s*[:#]?\s*(\d+)', str(e), re.IGNORECASE)
                if m_c:
                    e_col = int(m_c.group(1))
            raise PythonCompilerError(f"Syntax error: {e}", line=e_line or 1, col=e_col or 1, stage="Parser")

    def _get_call_name(self, node: Any) -> str:
        if isinstance(node, py_ast.Name):
            return node.id
        elif isinstance(node, py_ast.Attribute):
            return f"{self._get_call_name(node.value)}.{node.attr}"
        return "func"

    def _format_type_annotation(self, node: Any) -> str:
        if isinstance(node, py_ast.Name):
            return node.id
        elif isinstance(node, py_ast.Constant):
            return str(node.value)
        elif isinstance(node, py_ast.Subscript):
            val = self._format_type_annotation(node.value)
            sl = self._format_type_annotation(node.slice)
            return f"{val}[{sl}]"
        elif isinstance(node, py_ast.Attribute):
            return f"{self._format_type_annotation(node.value)}.{node.attr}"
        return "auto"

    def _convert_ast(self, node: Any) -> Dict[str, Any]:
        """Convert standard Python AST to normalized, fully recursive visualizer AST."""
        if node is None:
            return None

        if isinstance(node, py_ast.Module):
            stmts = [self._convert_ast(s) for s in node.body]
            statements = [s for s in stmts if s is not None]
            children = [{"node": s, "badge": f"stmt {i + 1}"} for i, s in enumerate(statements)]
            return {
                "type": "Program",
                "language": "python",
                "statements": statements,
                "children": children
            }

        line = getattr(node, "lineno", 1)
        col = getattr(node, "col_offset", 0) + 1

        if isinstance(node, py_ast.ClassDef):
            bases = [self._convert_ast(b) for b in node.bases]
            members = [self._convert_ast(s) for s in node.body if s is not None]
            children = []
            for b in bases:
                if b:
                    children.append({"badge": "base", "node": b})
            for m in members:
                if m:
                    children.append({"badge": "member", "node": m})
            return {
                "type": "ClassDef",
                "name": node.name,
                "bases": bases,
                "members": members,
                "body": members,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, (py_ast.FunctionDef, py_ast.AsyncFunctionDef)):
            type_name = "AsyncFunctionDef" if isinstance(node, py_ast.AsyncFunctionDef) else "FunctionDef"
            params = []
            children = []
            for a in node.args.args:
                p_line = getattr(a, "lineno", line)
                p_col = getattr(a, "col_offset", col - 1) + 1
                p = {"type": "Param", "name": a.arg, "line": p_line, "col": p_col}
                params.append(p)
                children.append({"badge": "param", "node": p})
            if node.args.vararg:
                p = {"type": "Param", "name": f"*{node.args.vararg.arg}", "line": line, "col": col}
                params.append(p)
                children.append({"badge": "vararg", "node": p})
            if node.args.kwarg:
                p = {"type": "Param", "name": f"**{node.args.kwarg.arg}", "line": line, "col": col}
                params.append(p)
                children.append({"badge": "kwarg", "node": p})
            body = [self._convert_ast(s) for s in node.body if s is not None]
            for s in body:
                children.append({"badge": "body", "node": s})
            return {
                "type": type_name,
                "name": node.name,
                "return_type": "auto",
                "params": params,
                "body": body,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Assign):
            targets = [self._convert_ast(t) for t in node.targets]
            target_name = node.targets[0].id if (len(node.targets) == 1 and isinstance(node.targets[0], py_ast.Name)) else "target"
            val = self._convert_ast(node.value)
            children = []
            if len(targets) > 1:
                for t in targets:
                    if t:
                        children.append({"badge": "target", "node": t})
            elif len(targets) == 1 and not isinstance(node.targets[0], py_ast.Name):
                children.append({"badge": "target", "node": targets[0]})
            if val:
                children.append({"badge": "val", "node": val})
            return {
                "type": "Assign",
                "name": target_name,
                "targets": targets,
                "value": val,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.AugAssign):
            op_map = {
                py_ast.Add: "+", py_ast.Sub: "-", py_ast.Mult: "*", py_ast.Div: "/",
                py_ast.FloorDiv: "//", py_ast.Mod: "%", py_ast.Pow: "**",
                py_ast.LShift: "<<", py_ast.RShift: ">>", py_ast.BitOr: "|",
                py_ast.BitXor: "^", py_ast.BitAnd: "&"
            }
            op_str = op_map.get(type(node.op), "+")
            target = self._convert_ast(node.target)
            target_name = node.target.id if isinstance(node.target, py_ast.Name) else "target"
            val = self._convert_ast(node.value)
            children = []
            if not isinstance(node.target, py_ast.Name) and target:
                children.append({"badge": "target", "node": target})
            if val:
                children.append({"badge": "val", "node": val})
            return {
                "type": "AugAssign",
                "name": target_name,
                "op": op_str,
                "target": target,
                "value": val,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.AnnAssign):
            target_name = node.target.id if isinstance(node.target, py_ast.Name) else "target"
            dtype = self._format_type_annotation(node.annotation)
            val = self._convert_ast(node.value) if node.value else None
            children = []
            if val:
                children.append({"badge": "val", "node": val})
            return {
                "type": "VarDecl",
                "name": target_name,
                "datatype": dtype,
                "value": val,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Return):
            val = self._convert_ast(node.value) if node.value else None
            children = [{"badge": "val", "node": val}] if val else []
            return {
                "type": "Return",
                "value": val,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.If):
            cond = self._convert_ast(node.test)
            then_branch = [self._convert_ast(s) for s in node.body if s is not None]
            else_branch = [self._convert_ast(s) for s in node.orelse if s is not None]
            children = []
            if cond:
                children.append({"badge": "test", "node": cond})
            for s in then_branch:
                children.append({"badge": "then", "node": s})
            for s in else_branch:
                children.append({"badge": "else", "node": s})
            return {
                "type": "If",
                "condition": cond,
                "then_branch": then_branch,
                "else_branch": else_branch,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.While):
            cond = self._convert_ast(node.test)
            body = [self._convert_ast(s) for s in node.body if s is not None]
            orelse = [self._convert_ast(s) for s in node.orelse if s is not None]
            children = []
            if cond:
                children.append({"badge": "test", "node": cond})
            for s in body:
                children.append({"badge": "body", "node": s})
            for s in orelse:
                children.append({"badge": "else", "node": s})
            return {
                "type": "While",
                "loop_type": "while",
                "condition": cond,
                "body": body,
                "then_branch": body,
                "else_branch": orelse,
                "orelse": orelse,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.For):
            target = self._convert_ast(node.target)
            iter_node = self._convert_ast(node.iter)
            body = [self._convert_ast(s) for s in node.body if s is not None]
            orelse = [self._convert_ast(s) for s in node.orelse if s is not None]
            children = []
            if target:
                children.append({"badge": "target", "node": target})
            if iter_node:
                children.append({"badge": "iter", "node": iter_node})
            for s in body:
                children.append({"badge": "body", "node": s})
            for s in orelse:
                children.append({"badge": "else", "node": s})
            return {
                "type": "For",
                "loop_type": "for",
                "target": target,
                "iter": iter_node,
                "body": body,
                "orelse": orelse,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Expr):
            return self._convert_ast(node.value)

        elif isinstance(node, py_ast.Call):
            fname = self._get_call_name(node.func)
            func_node = self._convert_ast(node.func) if not isinstance(node.func, py_ast.Name) else None
            args = [self._convert_ast(a) for a in node.args if a is not None]
            keywords = []
            for kw in node.keywords:
                val = self._convert_ast(kw.value)
                kw_node = {
                    "type": "Keyword",
                    "arg": kw.arg or "**",
                    "value": val,
                    "children": [{"badge": "val", "node": val}] if val else [],
                    "line": line,
                    "col": col
                }
                keywords.append(kw_node)
            children = []
            if func_node:
                children.append({"badge": "func", "node": func_node})
            for i, a in enumerate(args):
                children.append({"badge": f"arg {i + 1}", "node": a})
            for k in keywords:
                children.append({"badge": f"kw:{k['arg']}", "node": k})
            return {
                "type": "FunctionCall",
                "name": fname,
                "func": func_node,
                "args": args,
                "keywords": keywords,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.BinOp):
            op_map = {
                py_ast.Add: "+", py_ast.Sub: "-", py_ast.Mult: "*",
                py_ast.Div: "/", py_ast.FloorDiv: "//", py_ast.Mod: "%", py_ast.Pow: "**",
                py_ast.LShift: "<<", py_ast.RShift: ">>", py_ast.BitOr: "|",
                py_ast.BitXor: "^", py_ast.BitAnd: "&"
            }
            op_symbol = op_map.get(type(node.op), "+")
            left = self._convert_ast(node.left)
            right = self._convert_ast(node.right)
            children = []
            if left:
                children.append({"badge": "Left", "node": left})
            if right:
                children.append({"badge": "Right", "node": right})
            return {
                "type": "BinOp",
                "op": op_symbol,
                "left": left,
                "right": right,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.UnaryOp):
            op_symbol = "-" if isinstance(node.op, py_ast.USub) else ("not" if isinstance(node.op, py_ast.Not) else ("~" if isinstance(node.op, py_ast.Invert) else "+"))
            operand = self._convert_ast(node.operand)
            children = [{"badge": "operand", "node": operand}] if operand else []
            return {
                "type": "UnaryOp",
                "operand": operand,
                "op": op_symbol,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Compare):
            op_map = {
                py_ast.Eq: "==", py_ast.NotEq: "!=", py_ast.Lt: "<",
                py_ast.LtE: "<=", py_ast.Gt: ">", py_ast.GtE: ">=",
                py_ast.Is: "is", py_ast.IsNot: "is not",
                py_ast.In: "in", py_ast.NotIn: "not in"
            }
            left = self._convert_ast(node.left)
            op_sym = op_map.get(type(node.ops[0]), "==") if node.ops else "=="
            right = self._convert_ast(node.comparators[0]) if node.comparators else None
            children = []
            if left:
                children.append({"badge": "Left", "node": left})
            if right:
                children.append({"badge": "Right", "node": right})
            for i in range(1, len(node.comparators)):
                op_i = op_map.get(type(node.ops[i]), "==") if i < len(node.ops) else "=="
                comp_i = self._convert_ast(node.comparators[i])
                if comp_i:
                    children.append({"badge": op_i, "node": comp_i})
            return {
                "type": "BinOp",
                "op": op_sym,
                "left": left,
                "right": right,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.BoolOp):
            op_str = "and" if isinstance(node.op, py_ast.And) else "or"
            values = [self._convert_ast(v) for v in node.values if v is not None]
            children = [{"badge": f"val {i + 1}", "node": v} for i, v in enumerate(values)]
            return {
                "type": "BoolOp",
                "op": op_str,
                "values": values,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.IfExp):
            test = self._convert_ast(node.test)
            body = self._convert_ast(node.body)
            orelse = self._convert_ast(node.orelse)
            children = []
            if test:
                children.append({"badge": "test", "node": test})
            if body:
                children.append({"badge": "true", "node": body})
            if orelse:
                children.append({"badge": "false", "node": orelse})
            return {
                "type": "IfExp",
                "test": test,
                "body": body,
                "orelse": orelse,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.List):
            elements = [self._convert_ast(e) for e in node.elts if e is not None]
            children = [{"badge": f"[{i}]", "node": e} for i, e in enumerate(elements)]
            return {
                "type": "List",
                "elements": elements,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Tuple):
            elements = [self._convert_ast(e) for e in node.elts if e is not None]
            children = [{"badge": f"({i})", "node": e} for i, e in enumerate(elements)]
            return {
                "type": "Tuple",
                "elements": elements,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Set):
            elements = [self._convert_ast(e) for e in node.elts if e is not None]
            children = [{"badge": "item", "node": e} for e in elements]
            return {
                "type": "Set",
                "elements": elements,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Dict):
            entries = []
            children = []
            for k, v in zip(node.keys, node.values):
                k_node = self._convert_ast(k) if k else {"type": "Identifier", "name": "**", "line": line, "col": col}
                v_node = self._convert_ast(v)
                entry = {
                    "type": "DictEntry",
                    "key": k_node,
                    "value": v_node,
                    "children": [{"badge": "key", "node": k_node}, {"badge": "val", "node": v_node}],
                    "line": getattr(k, "lineno", line) if k else line,
                    "col": getattr(k, "col_offset", col - 1) + 1 if k else col
                }
                entries.append(entry)
                children.append({"badge": "pair", "node": entry})
            return {
                "type": "Dict",
                "entries": entries,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Subscript):
            val = self._convert_ast(node.value)
            sl = self._convert_ast(node.slice)
            children = []
            if val:
                children.append({"badge": "val", "node": val})
            if sl:
                children.append({"badge": "slice", "node": sl})
            return {
                "type": "Subscript",
                "value": val,
                "slice": sl,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Slice):
            lower = self._convert_ast(node.lower) if node.lower else None
            upper = self._convert_ast(node.upper) if node.upper else None
            step = self._convert_ast(node.step) if node.step else None
            children = []
            if lower:
                children.append({"badge": "start", "node": lower})
            if upper:
                children.append({"badge": "stop", "node": upper})
            if step:
                children.append({"badge": "step", "node": step})
            return {
                "type": "Slice",
                "lower": lower,
                "upper": upper,
                "step": step,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Attribute):
            val = self._convert_ast(node.value)
            children = [{"badge": "obj", "node": val}] if val else []
            return {
                "type": "Attribute",
                "value": val,
                "attr": node.attr,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Import):
            names = [a.name for a in node.names]
            return {
                "type": "Import",
                "names": names,
                "children": [],
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.ImportFrom):
            names = [a.name for a in node.names]
            return {
                "type": "ImportFrom",
                "module": node.module or "",
                "names": names,
                "children": [],
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Pass):
            return {"type": "Pass", "children": [], "line": line, "col": col}

        elif isinstance(node, py_ast.Break):
            return {"type": "Break", "children": [], "line": line, "col": col}

        elif isinstance(node, py_ast.Continue):
            return {"type": "Continue", "children": [], "line": line, "col": col}

        elif isinstance(node, (py_ast.ListComp, py_ast.SetComp, py_ast.DictComp, py_ast.GeneratorExp)):
            elt = self._convert_ast(getattr(node, "elt", None) or getattr(node, "key", None))
            children = []
            if elt:
                children.append({"badge": "elt", "node": elt})
            for gen in node.generators:
                tgt = self._convert_ast(gen.target)
                it = self._convert_ast(gen.iter)
                if tgt:
                    children.append({"badge": "for", "node": tgt})
                if it:
                    children.append({"badge": "in", "node": it})
            return {
                "type": type(node).__name__,
                "children": children,
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Name):
            return {
                "type": "Identifier",
                "name": node.id,
                "children": [],
                "line": line,
                "col": col
            }

        elif isinstance(node, py_ast.Constant):
            if isinstance(node.value, bool):
                return {"type": "Constant", "value": node.value, "children": [], "line": line, "col": col}
            elif isinstance(node.value, (int, float)):
                return {"type": "Number", "value": node.value, "children": [], "line": line, "col": col}
            elif isinstance(node.value, str):
                return {"type": "String", "value": node.value, "children": [], "line": line, "col": col}
            elif node.value is None:
                return {"type": "Constant", "value": "None", "children": [], "line": line, "col": col}
            return {"type": "Constant", "value": str(node.value), "children": [], "line": line, "col": col}

        # Generic fallback for any other AST node
        children = []
        for field, value in py_ast.iter_fields(node):
            if isinstance(value, py_ast.AST):
                c = self._convert_ast(value)
                if c:
                    children.append({"badge": field, "node": c})
            elif isinstance(value, list):
                for idx, item in enumerate(value):
                    if isinstance(item, py_ast.AST):
                        c = self._convert_ast(item)
                        if c:
                            children.append({"badge": f"{field}[{idx}]", "node": c})
        return {
            "type": type(node).__name__,
            "name": type(node).__name__,
            "children": children,
            "line": line,
            "col": col
        }

    def analyze_semantics(self, ast: Any, source: str = "") -> Tuple[List[Any], List[str], List[Dict[str, Any]]]:
        errors = []
        symbol_table: Dict[Tuple[str, str], Dict[str, Any]] = {}
        declared_vars_set = set()

        statements = ast.get("statements", []) if isinstance(ast, dict) else []

        def check_expr(expr: Dict[str, Any], scope: str):
            if not expr or not isinstance(expr, dict):
                return
            etype = expr.get("type")
            line = expr.get("line", 1)
            col = expr.get("col", 1)

            if etype == "Identifier":
                name = expr.get("name")
                if name in PYTHON_BUILTINS or name in ("True", "False", "None", "self", "cls"):
                    return
                # Check if defined in current scope or global
                if (scope, name) not in symbol_table and ("global", name) not in symbol_table:
                    candidates = list(PYTHON_BUILTINS) + [n for (s, n) in symbol_table.keys()]
                    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=0.6)
                    hint = f". Did you mean '{matches[0]}'?" if matches else ""
                    errors.append({
                        "stage": "Semantic Analyzer",
                        "message": f"NameError: name '{name}' is not defined{hint}",
                        "line": line,
                        "col": col,
                        "column": col,
                        "severity": "error"
                    })

            elif etype == "BinOp":
                check_expr(expr.get("left"), scope)
                check_expr(expr.get("right"), scope)

            elif etype == "UnaryOp":
                check_expr(expr.get("operand"), scope)

            elif etype == "BoolOp":
                for v in expr.get("values", []):
                    check_expr(v, scope)

            elif etype == "IfExp":
                check_expr(expr.get("test"), scope)
                check_expr(expr.get("body"), scope)
                check_expr(expr.get("orelse"), scope)

            elif etype == "Attribute":
                check_expr(expr.get("value"), scope)

            elif etype == "Subscript":
                check_expr(expr.get("value"), scope)
                check_expr(expr.get("slice"), scope)

            elif etype in ("List", "Tuple", "Set"):
                for el in expr.get("elements", []):
                    check_expr(el, scope)

            elif etype == "Dict":
                for entry in expr.get("entries", []):
                    check_expr(entry.get("key"), scope)
                    check_expr(entry.get("value"), scope)

            elif etype == "DictEntry":
                check_expr(expr.get("key"), scope)
                check_expr(expr.get("value"), scope)

            elif etype == "FunctionCall":
                fname = expr.get("name")
                for a in expr.get("args", []):
                    check_expr(a, scope)
                for kw in expr.get("keywords", []):
                    check_expr(kw.get("value"), scope)
                if expr.get("func"):
                    check_expr(expr.get("func"), scope)
                elif fname not in PYTHON_BUILTINS and ("global", fname) not in symbol_table and (scope, fname) not in symbol_table:
                    if "." in str(fname):
                        base_obj = str(fname).split(".")[0]
                        if base_obj not in symbol_table and ("global", base_obj) not in symbol_table and base_obj not in PYTHON_BUILTINS:
                            pass
                    else:
                        candidates = list(PYTHON_BUILTINS) + [n for (s, n) in symbol_table.keys() if s == "global"]
                        matches = difflib.get_close_matches(fname, candidates, n=1, cutoff=0.55)
                        hint = f". Did you mean '{matches[0]}'?" if matches else ""
                        errors.append({
                            "stage": "Semantic Analyzer",
                            "message": f"NameError: name '{fname}' is not defined{hint}",
                            "line": line,
                            "col": col,
                            "column": col,
                            "severity": "error"
                        })

        def walk_statements(stmts: List[Dict[str, Any]], scope: str):
            for s in stmts:
                if not s or not isinstance(s, dict):
                    continue
                stype = s.get("type")
                line = s.get("line", 1)
                col = s.get("col", 1)

                if stype == "Assign":
                    check_expr(s.get("value"), scope)
                    name = s.get("name")
                    if name and name != "target":
                        symbol_table[(scope, name)] = {
                            "name": name,
                            "type": "auto",
                            "scope": scope,
                            "line": line,
                            "col": col,
                            "initialized": True,
                            "status": "Assigned"
                        }
                        declared_vars_set.add(name)

                elif stype == "AugAssign":
                    check_expr(s.get("value"), scope)
                    name = s.get("name")
                    if name and name != "target":
                        symbol_table[(scope, name)] = {
                            "name": name,
                            "type": "auto",
                            "scope": scope,
                            "line": line,
                            "col": col,
                            "initialized": True,
                            "status": "Assigned"
                        }
                        declared_vars_set.add(name)

                elif stype == "VarDecl":
                    check_expr(s.get("value"), scope)
                    name = s.get("name")
                    dtype = s.get("datatype", "auto")
                    symbol_table[(scope, name)] = {
                        "name": name,
                        "type": dtype,
                        "scope": scope,
                        "line": line,
                        "col": col,
                        "initialized": True,
                        "status": "Declared"
                    }
                    declared_vars_set.add(name)

                elif stype in ("FunctionDef", "AsyncFunctionDef"):
                    fname = s.get("name")
                    symbol_table[(scope, fname)] = {
                        "name": fname,
                        "type": "function() -> auto",
                        "scope": scope,
                        "line": line,
                        "col": col,
                        "initialized": True,
                        "status": "Defined"
                    }
                    if scope != "global":
                        symbol_table[("global", fname)] = symbol_table[(scope, fname)]
                    for p in s.get("params", []):
                        pname = p.get("name")
                        if pname and not pname.startswith("*"):
                            symbol_table[(fname, pname)] = {
                                "name": pname,
                                "type": "param",
                                "scope": fname,
                                "line": line,
                                "col": col,
                                "initialized": True,
                                "status": "Parameter"
                            }
                            declared_vars_set.add(pname)
                    walk_statements(s.get("body", []), fname)

                elif stype == "ClassDef":
                    cname = s.get("name")
                    symbol_table[("global", cname)] = {
                        "name": cname,
                        "type": "class",
                        "scope": "global",
                        "line": line,
                        "col": col,
                        "initialized": True,
                        "status": "Defined"
                    }
                    declared_vars_set.add(cname)
                    walk_statements(s.get("members", []) or s.get("body", []), cname)

                elif stype == "If":
                    check_expr(s.get("condition"), scope)
                    walk_statements(s.get("then_branch", []), scope)
                    walk_statements(s.get("else_branch", []), scope)

                elif stype == "While":
                    check_expr(s.get("condition"), scope)
                    walk_statements(s.get("body", []) or s.get("then_branch", []), scope)
                    walk_statements(s.get("orelse", []) or s.get("else_branch", []), scope)

                elif stype == "For":
                    check_expr(s.get("iter"), scope)
                    target = s.get("target")
                    if isinstance(target, dict) and target.get("name"):
                        tname = target.get("name")
                        symbol_table[(scope, tname)] = {
                            "name": tname,
                            "type": "auto",
                            "scope": scope,
                            "line": line,
                            "col": col,
                            "initialized": True,
                            "status": "Iterator"
                        }
                        declared_vars_set.add(tname)
                    walk_statements(s.get("body", []), scope)
                    walk_statements(s.get("orelse", []), scope)

                elif stype == "Return":
                    check_expr(s.get("value"), scope)

                elif stype == "FunctionCall":
                    check_expr(s, scope)

                elif stype in ("Import", "ImportFrom"):
                    for nm in s.get("names", []):
                        symbol_table[("global", nm)] = {
                            "name": nm,
                            "type": "module/symbol",
                            "scope": "global",
                            "line": line,
                            "col": col,
                            "initialized": True,
                            "status": "Imported"
                        }
                        declared_vars_set.add(nm)

        walk_statements(statements, "global")
        symbol_table_list = list(symbol_table.values())
        return errors, sorted(list(declared_vars_set)), symbol_table_list

    def generate_ir(self, ast: Any) -> Dict[str, Any]:
        from ir_generator import generate_ir
        return generate_ir(ast)

    def generate_assembly(self, ir_data: Dict[str, Any]) -> Dict[str, str]:
        from codegen import generate_code
        return generate_code(ir_data)

    def generate_explanation(self, tokens: List[Any], ast: Any, semantic_info: Dict[str, Any],
                             ir_data: Dict[str, Any], assembly_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        token_dicts = [t if isinstance(t, dict) else t.to_dict() for t in (tokens[:150] if tokens else [])]
        return generate_explanation(
            tokens=token_dicts,
            ast=ast,
            semantic_info=semantic_info,
            ir_data=ir_data,
            assembly_data=assembly_data,
            language="python"
        )

    def execute(self, source: str, ir_data: Dict[str, Any]) -> Dict[str, Any]:
        return SafeExecutor.execute("python", source, ir_data, prefer_native=True)
