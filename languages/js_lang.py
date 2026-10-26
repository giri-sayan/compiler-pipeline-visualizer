"""
JavaScript Language Compiler Frontend (ES6+ Subset).

Supports:
  - Variable declarations: let, const, var
  - Functions: function name(params) { ... }
  - Console I/O: console.log(...)
  - Control flow: if, else, while, for, return
  - Expressions, comparisons (===, !==, ==, !=), arithmetic
  - Typo diagnostics (conosle -> console, retrun -> return)
  - Normalized AST, TAC Quadruples, Assembly, and Safe Execution
"""

import re
import difflib
from typing import Dict, Any, List, Tuple, Optional
from languages.base import BaseCompiler
from tac_vm import TACVirtualMachine
from executor import SafeExecutor
from explainer import generate_explanation


JS_KEYWORDS = {
    "let", "const", "var", "function", "return", "if", "else", "while", "for",
    "console", "log", "true", "false", "null", "undefined"
}

JS_TYPO_MAP = {
    "console": {"conosle", "consol", "consoel"},
    "log": {"lg", "loo"},
    "function": {"funtion", "func", "fucntion", "functin"},
    "return": {"eturn", "retun", "retrun"},
}


class JSCompilerError(Exception):
    def __init__(self, message: str, line: int = 1, col: int = 1, stage: str = "Parser"):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        self.column = col
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


class JSLexer:
    def __init__(self, text: str):
        self.text = text or ""
        self.pos = 0
        self.line = 1
        self.col = 1
        self.current_char = self.text[self.pos] if len(self.text) > 0 else None

    def advance(self):
        if self.current_char == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        self.pos += 1
        self.current_char = self.text[self.pos] if self.pos < len(self.text) else None

    def peek(self, offset: int = 1):
        pos = self.pos + offset
        return self.text[pos] if pos < len(self.text) else None

    def tokenize(self) -> List[Dict[str, Any]]:
        tokens = []
        while self.current_char is not None:
            if self.current_char.isspace():
                self.advance()
                continue

            # Comments
            if self.current_char == "/" and self.peek() == "/":
                while self.current_char is not None and self.current_char != "\n":
                    self.advance()
                continue
            if self.current_char == "/" and self.peek() == "*":
                s_line, s_col = self.line, self.col
                self.advance(); self.advance()
                closed = False
                while self.current_char is not None:
                    if self.current_char == "*" and self.peek() == "/":
                        self.advance(); self.advance()
                        closed = True
                        break
                    self.advance()
                if not closed:
                    raise JSCompilerError(f"Lexical error: Unterminated comment '/*' at line {s_line}, col {s_col}", line=s_line, col=s_col, stage="Lexer")
                continue

            cur_line, cur_col = self.line, self.col

            # Numbers
            if self.current_char.isdigit():
                num_str = ""
                is_flt = False
                while self.current_char is not None and (self.current_char.isdigit() or self.current_char == "."):
                    if self.current_char == ".":
                        if is_flt:
                            raise JSCompilerError(f"Lexical error: Malformed number '{num_str}.' at line {cur_line}, col {cur_col}", line=cur_line, col=cur_col, stage="Lexer")
                        is_flt = True
                    num_str += self.current_char
                    self.advance()
                tokens.append({"type": "NUMBER", "value": float(num_str) if is_flt else int(num_str), "line": cur_line, "col": cur_col})
                continue

            # Strings
            if self.current_char in ('"', "'", "`"):
                q = self.current_char
                self.advance()
                s_val = ""
                while self.current_char is not None and self.current_char != q:
                    if self.current_char == "\n" and q != "`":
                        raise JSCompilerError(f"Lexical error: Unterminated string literal at line {cur_line}, col {cur_col}", line=cur_line, col=cur_col, stage="Lexer")
                    if self.current_char == "\\" and self.peek() is not None:
                        self.advance()
                        escapes = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}
                        s_val += escapes.get(self.current_char, self.current_char)
                    else:
                        s_val += self.current_char
                    self.advance()
                if self.current_char != q:
                    raise JSCompilerError(f"Lexical error: Unterminated string literal at line {cur_line}, col {cur_col}", line=cur_line, col=cur_col, stage="Lexer")
                self.advance()
                tokens.append({"type": "STRING", "value": s_val, "line": cur_line, "col": cur_col})
                continue

            # Identifiers and keywords
            if self.current_char.isalpha() or self.current_char in ("_", "$"):
                ident = ""
                while self.current_char is not None and (self.current_char.isalnum() or self.current_char in ("_", "$")):
                    ident += self.current_char
                    self.advance()
                t_type = "IDENTIFIER"
                if ident in ("let", "const", "var"):
                    t_type = "DECL_KW"
                elif ident in JS_KEYWORDS:
                    t_type = ident.upper()
                tokens.append({"type": t_type, "value": ident, "line": cur_line, "col": cur_col})
                continue

            # Multi-char operators (===, !==, ==, !=, <=, >=, =>)
            ch3 = self.current_char + (self.peek(1) or "") + (self.peek(2) or "")
            if ch3 in ("===", "!=="):
                self.advance(); self.advance(); self.advance()
                tokens.append({"type": "EQ" if ch3 == "===" else "NEQ", "value": ch3, "line": cur_line, "col": cur_col})
                continue

            ch2 = self.current_char + (self.peek(1) or "")
            op2_map = {"==": "EQ", "!=": "NEQ", "<=": "LTE", ">=": "GTE", "=>": "ARROW"}
            if ch2 in op2_map:
                self.advance(); self.advance()
                tokens.append({"type": op2_map[ch2], "value": ch2, "line": cur_line, "col": cur_col})
                continue

            # Single characters
            ch = self.current_char
            self.advance()
            s_map = {
                "+": "PLUS", "-": "MINUS", "*": "MUL", "/": "DIV", "%": "MOD",
                "=": "ASSIGN", "<": "LT", ">": "GT", "(": "LPAREN", ")": "RPAREN",
                "{": "LBRACE", "}": "RBRACE", "[": "LBRACKET", "]": "RBRACKET",
                ";": "SEMICOLON", ",": "COMMA", ".": "DOT"
            }
            if ch in s_map:
                tokens.append({"type": s_map[ch], "value": ch, "line": cur_line, "col": cur_col})
                continue

            raise JSCompilerError(f"Lexical error: Unrecognized character {ch!r} at line {cur_line}, col {cur_col}", line=cur_line, col=cur_col, stage="Lexer")

        tokens.append({"type": "EOF", "value": None, "line": self.line, "col": self.col})
        return tokens


class JSParser:
    def __init__(self, tokens: List[Dict[str, Any]]):
        self.tokens = tokens or []
        self.pos = 0
        self.cur = self.tokens[self.pos] if len(self.tokens) > 0 else None

    def peek(self, offset: int = 1) -> Optional[Dict[str, Any]]:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else None

    def eat(self, token_type: str) -> Dict[str, Any]:
        if self.cur and self.cur["type"] == token_type:
            tok = self.cur
            self.pos += 1
            self.cur = self.tokens[self.pos] if self.pos < len(self.tokens) else None
            return tok
        c_type = self.cur["type"] if self.cur else "EOF"
        c_val = self.cur["value"] if self.cur else ""
        c_line = self.cur["line"] if self.cur else 1
        c_col = self.cur["col"] if self.cur else 1
        raise JSCompilerError(f"Syntax error: expected '{token_type}', got '{c_val}' ({c_type}) at line {c_line}, col {c_col}", line=c_line, col=c_col)

    def parse_program(self) -> Dict[str, Any]:
        statements = []
        while self.cur and self.cur["type"] != "EOF":
            stmt = self.statement()
            if stmt:
                statements.append(stmt)
        return {
            "type": "Program",
            "language": "js",
            "statements": statements
        }

    def statement(self) -> Optional[Dict[str, Any]]:
        if not self.cur or self.cur["type"] == "EOF":
            return None

        line = self.cur["line"]
        col = self.cur["col"]

        # Typo check
        if self.cur["type"] == "IDENTIFIER":
            ident_name = str(self.cur["value"])
            for kw, typos in JS_TYPO_MAP.items():
                if ident_name != kw and (ident_name in typos or (len(ident_name) >= 3 and difflib.get_close_matches(ident_name, [kw], cutoff=0.7))):
                    raise JSCompilerError(f"Unknown keyword or identifier '{ident_name}'. Did you mean '{kw}'?", line=line, col=col)

        # console.log(...)
        if self.cur["type"] == "CONSOLE":
            self.eat("CONSOLE")
            self.eat("DOT")
            m_tok = self.cur
            m_name = m_tok["value"] if m_tok else "log"
            self.eat(self.cur["type"])
            self.eat("LPAREN")
            args = []
            if self.cur and self.cur["type"] != "RPAREN":
                args.append(self.expr())
                while self.cur and self.cur["type"] == "COMMA":
                    self.eat("COMMA")
                    args.append(self.expr())
            self.eat("RPAREN")
            if self.cur and self.cur["type"] == "SEMICOLON":
                self.eat("SEMICOLON")
            return {
                "type": "FunctionCall",
                "name": f"console.{m_name}",
                "args": args,
                "line": line,
                "col": col
            }

        # let / const / var variable declaration: let x = 5;
        if self.cur["type"] == "DECL_KW":
            kw = self.eat("DECL_KW")["value"]
            ident_tok = self.eat("IDENTIFIER")
            name = ident_tok["value"]
            init_val = None
            if self.cur and self.cur["type"] == "ASSIGN":
                self.eat("ASSIGN")
                init_val = self.expr()
            if self.cur and self.cur["type"] == "SEMICOLON":
                self.eat("SEMICOLON")
            return {
                "type": "VarDecl",
                "datatype": kw,
                "name": name,
                "value": init_val,
                "line": line,
                "col": ident_tok["col"]
            }

        # Function definition: function add(a, b) { ... }
        if self.cur["type"] == "FUNCTION":
            self.eat("FUNCTION")
            fname = self.eat("IDENTIFIER")["value"]
            self.eat("LPAREN")
            params = []
            while self.cur and self.cur["type"] != "RPAREN":
                p_name = self.eat("IDENTIFIER")["value"]
                params.append({"type": "auto", "name": p_name})
                if self.cur and self.cur["type"] == "COMMA":
                    self.eat("COMMA")
            self.eat("RPAREN")
            self.eat("LBRACE")
            body = []
            while self.cur and self.cur["type"] != "RBRACE" and self.cur["type"] != "EOF":
                s = self.statement()
                if s: body.append(s)
            self.eat("RBRACE")
            return {
                "type": "FunctionDef",
                "name": fname,
                "return_type": "auto",
                "params": params,
                "body": body,
                "line": line,
                "col": col
            }

        # Return statement
        if self.cur["type"] == "RETURN":
            self.eat("RETURN")
            val = None
            if self.cur and self.cur["type"] not in ("SEMICOLON", "RBRACE", "EOF"):
                val = self.expr()
            if self.cur and self.cur["type"] == "SEMICOLON":
                self.eat("SEMICOLON")
            return {"type": "Return", "value": val, "line": line, "col": col}

        # If statement
        if self.cur["type"] == "IF":
            self.eat("IF")
            self.eat("LPAREN")
            cond = self.expr()
            self.eat("RPAREN")
            then_body = []
            if self.cur and self.cur["type"] == "LBRACE":
                self.eat("LBRACE")
                while self.cur and self.cur["type"] != "RBRACE" and self.cur["type"] != "EOF":
                    s = self.statement()
                    if s: then_body.append(s)
                self.eat("RBRACE")
            else:
                s = self.statement()
                if s: then_body.append(s)

            else_body = []
            if self.cur and self.cur["type"] == "ELSE":
                self.eat("ELSE")
                if self.cur and self.cur["type"] == "LBRACE":
                    self.eat("LBRACE")
                    while self.cur and self.cur["type"] != "RBRACE" and self.cur["type"] != "EOF":
                        s = self.statement()
                        if s: else_body.append(s)
                    self.eat("RBRACE")
                else:
                    s = self.statement()
                    if s: else_body.append(s)
            return {"type": "If", "condition": cond, "then_branch": then_body, "else_branch": else_body, "line": line, "col": col}

        # Assignment: x = expr;
        if self.cur["type"] == "IDENTIFIER" and self.peek() and self.peek()["type"] == "ASSIGN":
            name = self.eat("IDENTIFIER")["value"]
            self.eat("ASSIGN")
            val = self.expr()
            if self.cur and self.cur["type"] == "SEMICOLON":
                self.eat("SEMICOLON")
            return {"type": "Assign", "name": name, "value": val, "line": line, "col": col}

        expr = self.expr()
        if self.cur and self.cur["type"] == "SEMICOLON":
            self.eat("SEMICOLON")
        return expr

    def expr(self) -> Dict[str, Any]:
        return self.add_expr()

    def add_expr(self) -> Dict[str, Any]:
        node = self.term()
        while self.cur and self.cur["type"] in ("PLUS", "MINUS", "EQ", "NEQ", "LT", "GT", "LTE", "GTE"):
            op = self.cur["value"]
            line = self.cur["line"]
            col = self.cur["col"]
            self.eat(self.cur["type"])
            right = self.term()
            node = {"type": "BinOp", "op": op, "left": node, "right": right, "line": line, "col": col}
        return node

    def term(self) -> Dict[str, Any]:
        node = self.factor()
        while self.cur and self.cur["type"] in ("MUL", "DIV", "MOD"):
            op = self.cur["value"]
            line = self.cur["line"]
            col = self.cur["col"]
            self.eat(self.cur["type"])
            right = self.factor()
            node = {"type": "BinOp", "op": op, "left": node, "right": right, "line": line, "col": col}
        return node

    def factor(self) -> Dict[str, Any]:
        if not self.cur:
            raise JSCompilerError("Syntax error: unexpected end of expression")
        line = self.cur["line"]
        col = self.cur["col"]

        if self.cur["type"] == "NUMBER":
            val = self.eat("NUMBER")["value"]
            return {"type": "Number", "value": val, "line": line, "col": col}
        if self.cur["type"] in ("TRUE", "FALSE"):
            val = 1 if self.cur["type"] == "TRUE" else 0
            self.eat(self.cur["type"])
            return {"type": "Number", "value": val, "line": line, "col": col}
        if self.cur["type"] == "STRING":
            val = self.eat("STRING")["value"]
            return {"type": "String", "value": val, "line": line, "col": col}
        if self.cur["type"] == "IDENTIFIER":
            name = self.eat("IDENTIFIER")["value"]
            if self.cur and self.cur["type"] == "LPAREN":
                self.eat("LPAREN")
                args = []
                while self.cur and self.cur["type"] != "RPAREN":
                    args.append(self.expr())
                    if self.cur and self.cur["type"] == "COMMA":
                        self.eat("COMMA")
                self.eat("RPAREN")
                return {"type": "FunctionCall", "name": name, "args": args, "line": line, "col": col}
            return {"type": "Identifier", "name": name, "line": line, "col": col}
        if self.cur["type"] == "LPAREN":
            self.eat("LPAREN")
            node = self.expr()
            self.eat("RPAREN")
            return node

        c_type = self.cur["type"]
        c_val = self.cur["value"]
        raise JSCompilerError(f"Syntax error: unexpected token '{c_val}' ({c_type}) at line {line}, col {col}", line=line, col=col)


class JSCompiler(BaseCompiler):
    language_id = "js"
    display_name = "JavaScript (Subset: let/const, functions, console.log)"
    file_extension = ".js"

    def tokenize(self, source: str) -> List[Dict[str, Any]]:
        return JSLexer(source).tokenize()

    def parse(self, tokens: List[Dict[str, Any]], source: str = "") -> Dict[str, Any]:
        return JSParser(tokens).parse_program()

    def analyze_semantics(self, ast: Any, source: str = "") -> Tuple[List[Any], List[str], List[Dict[str, Any]]]:
        errors = []
        symbol_table = {}
        declared_vars = set()

        statements = ast.get("statements", []) if isinstance(ast, dict) else []

        def walk(stmts: List[Dict[str, Any]], scope: str):
            for s in stmts:
                stype = s.get("type")
                line = s.get("line", 1)
                col = s.get("col", 1)

                if stype == "VarDecl":
                    name = s.get("name")
                    symbol_table[(scope, name)] = {
                        "name": name, "type": s.get("datatype", "let"), "scope": scope,
                        "line": line, "col": col, "initialized": s.get("value") is not None,
                        "status": "Initialized" if s.get("value") is not None else "Declared"
                    }
                    declared_vars.add(name)

                elif stype == "FunctionDef":
                    fname = s.get("name")
                    symbol_table[(scope, fname)] = {
                        "name": fname, "type": "function()", "scope": scope,
                        "line": line, "col": col, "initialized": True, "status": "Defined"
                    }
                    for p in s.get("params", []):
                        pname = p.get("name")
                        if pname:
                            symbol_table[(fname, pname)] = {
                                "name": pname, "type": "param", "scope": fname,
                                "line": line, "col": col, "initialized": True, "status": "Parameter"
                            }
                            declared_vars.add(pname)
                    walk(s.get("body", []), fname)

                elif stype == "Assign":
                    name = s.get("name")
                    if (scope, name) not in symbol_table and ("global", name) not in symbol_table:
                        symbol_table[(scope, name)] = {
                            "name": name, "type": "auto", "scope": scope,
                            "line": line, "col": col, "initialized": True, "status": "Assigned"
                        }
                    declared_vars.add(name)

        walk(statements, "global")
        return errors, sorted(list(declared_vars)), list(symbol_table.values())

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
            language="js"
        )

    def execute(self, source: str, ir_data: Dict[str, Any]) -> Dict[str, Any]:
        return SafeExecutor.execute("js", source, ir_data)
