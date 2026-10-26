"""
Java Language Compiler Frontend (Educational Java Subset).

Supports:
  - Class declarations: public class Main { ... }
  - Required entry point: public static void main(String[] args)
  - Console I/O: System.out.println(...) and System.out.print(...)
  - Primitive and reference types: int, double, float, boolean, char, String
  - Methods, fields, object instantiation
  - Control flow: if, else, while, for, return
  - Typo diagnostics (System.out.prntln -> println, mian -> main, Stirng -> String)
  - Normalized AST, TAC Quadruples, Assembly, and Safe Execution
"""

import re
import difflib
from typing import Dict, Any, List, Tuple, Optional
from languages.base import BaseCompiler
from tac_vm import TACVirtualMachine
from executor import SafeExecutor
from explainer import generate_explanation


JAVA_KEYWORDS = {
    "public", "private", "protected", "static", "final", "class", "interface",
    "void", "int", "double", "float", "boolean", "char", "String", "new",
    "return", "if", "else", "while", "for", "import", "package", "this",
    "true", "false", "null"
}

JAVA_TYPO_MAP = {
    "println": {"prntln", "printl", "printline", "print_ln"},
    "print": {"prnt", "pritn"},
    "main": {"ain", "mian", "maim", "mani", "mainn"},
    "String": {"Stirng", "string", "Strng", "Sting"},
    "System": {"Systm", "Systen", "system"},
    "public": {"pubic", "publc", "pbulic"},
    "static": {"staitc", "statc", "sttic"},
    "class": {"calss", "clas", "clss"},
    "return": {"eturn", "retun", "retrun"},
}


class JavaCompilerError(Exception):
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


class JavaLexer:
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
                    raise JavaCompilerError(f"Lexical error: Unterminated comment '/*' at line {s_line}, col {s_col}", line=s_line, col=s_col, stage="Lexer")
                continue

            cur_line, cur_col = self.line, self.col

            # Numbers
            if self.current_char.isdigit():
                num_str = ""
                is_flt = False
                while self.current_char is not None and (self.current_char.isdigit() or self.current_char == "."):
                    if self.current_char == ".":
                        if is_flt:
                            raise JavaCompilerError(f"Lexical error: Malformed number '{num_str}.' at line {cur_line}, col {cur_col}", line=cur_line, col=cur_col, stage="Lexer")
                        is_flt = True
                    num_str += self.current_char
                    self.advance()
                tokens.append({"type": "NUMBER", "value": float(num_str) if is_flt else int(num_str), "line": cur_line, "col": cur_col})
                continue

            # Strings
            if self.current_char in ('"', "'"):
                q = self.current_char
                self.advance()
                s_val = ""
                while self.current_char is not None and self.current_char != q:
                    if self.current_char == "\n":
                        raise JavaCompilerError(f"Lexical error: Unterminated string literal at line {cur_line}, col {cur_col}", line=cur_line, col=cur_col, stage="Lexer")
                    if self.current_char == "\\" and self.peek() is not None:
                        self.advance()
                        escapes = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}
                        s_val += escapes.get(self.current_char, self.current_char)
                    else:
                        s_val += self.current_char
                    self.advance()
                if self.current_char != q:
                    raise JavaCompilerError(f"Lexical error: Unterminated string literal at line {cur_line}, col {cur_col}", line=cur_line, col=cur_col, stage="Lexer")
                self.advance()
                tokens.append({"type": "STRING", "value": s_val, "line": cur_line, "col": cur_col})
                continue

            # Identifiers and keywords
            if self.current_char.isalpha() or self.current_char == "_":
                ident = ""
                while self.current_char is not None and (self.current_char.isalnum() or self.current_char == "_"):
                    ident += self.current_char
                    self.advance()
                t_type = "IDENTIFIER"
                if ident in ("int", "double", "float", "boolean", "char", "void", "String"):
                    t_type = "TYPE"
                elif ident in JAVA_KEYWORDS:
                    t_type = ident.upper()
                tokens.append({"type": t_type, "value": ident, "line": cur_line, "col": cur_col})
                continue

            # Two-character operators
            ch2 = self.current_char + (self.peek() or "")
            op2_map = {"==": "EQ", "!=": "NEQ", "<=": "LTE", ">=": "GTE", "++": "INC", "--": "DEC"}
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

            raise JavaCompilerError(f"Lexical error: Unrecognized character {ch!r} at line {cur_line}, col {cur_col}", line=cur_line, col=cur_col, stage="Lexer")

        tokens.append({"type": "EOF", "value": None, "line": self.line, "col": self.col})
        return tokens


class JavaParser:
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
        raise JavaCompilerError(f"Syntax error: expected '{token_type}', got '{c_val}' ({c_type}) at line {c_line}, col {c_col}", line=c_line, col=c_col)

    def parse_program(self) -> Dict[str, Any]:
        statements = []
        while self.cur and self.cur["type"] != "EOF":
            stmt = self.statement()
            if stmt:
                statements.append(stmt)
        return {
            "type": "Program",
            "language": "java",
            "statements": statements
        }

    def statement(self) -> Optional[Dict[str, Any]]:
        if not self.cur or self.cur["type"] == "EOF":
            return None

        line = self.cur["line"]
        col = self.cur["col"]

        # Modifiers: public, private, protected, static, final
        modifiers = []
        while self.cur and self.cur["type"] in ("PUBLIC", "PRIVATE", "PROTECTED", "STATIC", "FINAL"):
            modifiers.append(self.eat(self.cur["type"])["value"])

        if not self.cur:
            return None

        # Typo checks
        if self.cur["type"] == "IDENTIFIER":
            ident_name = str(self.cur["value"])
            for kw, typos in JAVA_TYPO_MAP.items():
                if ident_name != kw and (ident_name in typos or (len(ident_name) >= 3 and difflib.get_close_matches(ident_name, [kw], cutoff=0.7))):
                    raise JavaCompilerError(f"Unknown identifier or keyword '{ident_name}'. Did you mean '{kw}'?", line=line, col=col)

        # class Declaration: [modifiers] class ClassName { ... }
        if self.cur["type"] == "CLASS":
            self.eat("CLASS")
            c_name = self.eat("IDENTIFIER")["value"]
            self.eat("LBRACE")
            members = []
            while self.cur and self.cur["type"] != "RBRACE" and self.cur["type"] != "EOF":
                m = self.statement()
                if m: members.append(m)
            self.eat("RBRACE")
            return {
                "type": "ClassDef",
                "name": c_name,
                "modifiers": modifiers,
                "members": members,
                "line": line,
                "col": col
            }

        # System.out.println(...) or System.out.print(...)
        if self.cur["type"] == "SYSTEM" or (self.cur["type"] == "IDENTIFIER" and self.cur["value"] == "System"):
            self.eat(self.cur["type"])
            self.eat("DOT")
            self.eat("OUT") if self.cur and self.cur["type"] == "OUT" else self.eat("IDENTIFIER")
            self.eat("DOT")
            m_name_tok = self.cur
            m_name = m_name_tok["value"] if m_name_tok else "println"
            self.eat(self.cur["type"])

            # Check println typo
            if m_name in JAVA_TYPO_MAP.get("println", set()):
                raise JavaCompilerError(f"Unknown method 'System.out.{m_name}'. Did you mean 'println'?", line=line, col=col)

            self.eat("LPAREN")
            args = []
            if self.cur and self.cur["type"] != "RPAREN":
                args.append(self.expr())
                while self.cur and self.cur["type"] == "COMMA":
                    self.eat("COMMA")
                    args.append(self.expr())
            self.eat("RPAREN")
            self.eat("SEMICOLON")
            return {
                "type": "FunctionCall",
                "name": f"System.out.{m_name}",
                "args": args,
                "line": line,
                "col": col
            }

        # Method or Field: [modifiers] TYPE IDENTIFIER ( ... ) / (= expr);
        if self.cur["type"] == "TYPE":
            dtype = self.eat("TYPE")["value"]
            # Array bracket check (e.g. String[] or int[])
            if self.cur and self.cur["type"] == "LBRACKET":
                self.eat("LBRACKET"); self.eat("RBRACKET")
                dtype += "[]"

            ident_tok = self.eat("IDENTIFIER")
            ident = ident_tok["value"]

            # Method definition: ( ... ) { ... }
            if self.cur and self.cur["type"] == "LPAREN":
                self.eat("LPAREN")
                params = []
                while self.cur and self.cur["type"] != "RPAREN":
                    p_type = self.eat("TYPE")["value"]
                    if self.cur and self.cur["type"] == "LBRACKET":
                        self.eat("LBRACKET"); self.eat("RBRACKET")
                        p_type += "[]"
                    p_name = self.eat("IDENTIFIER")["value"]
                    params.append({"type": p_type, "name": p_name})
                    if self.cur and self.cur["type"] == "COMMA":
                        self.eat("COMMA")
                self.eat("RPAREN")

                body = []
                if self.cur and self.cur["type"] == "LBRACE":
                    self.eat("LBRACE")
                    while self.cur and self.cur["type"] != "RBRACE" and self.cur["type"] != "EOF":
                        s = self.statement()
                        if s: body.append(s)
                    self.eat("RBRACE")
                return {
                    "type": "FunctionDef",
                    "name": ident,
                    "return_type": dtype,
                    "modifiers": modifiers,
                    "params": params,
                    "body": body,
                    "line": line,
                    "col": ident_tok["col"]
                }

            # Field or local variable: TYPE IDENTIFIER (= expr)?;
            init_val = None
            if self.cur and self.cur["type"] == "ASSIGN":
                self.eat("ASSIGN")
                init_val = self.expr()
            self.eat("SEMICOLON")
            return {
                "type": "VarDecl",
                "datatype": dtype,
                "name": ident,
                "modifiers": modifiers,
                "value": init_val,
                "line": line,
                "col": ident_tok["col"]
            }

        # Return statement
        if self.cur["type"] == "RETURN":
            self.eat("RETURN")
            val = None
            if self.cur and self.cur["type"] != "SEMICOLON":
                val = self.expr()
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

        # Assignment
        if self.cur["type"] == "IDENTIFIER":
            name = self.cur["value"]
            if self.peek() and self.peek()["type"] == "ASSIGN":
                self.eat("IDENTIFIER")
                self.eat("ASSIGN")
                val = self.expr()
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
            raise JavaCompilerError("Syntax error: unexpected end of expression")
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
        raise JavaCompilerError(f"Syntax error: unexpected token '{c_val}' ({c_type}) at line {line}, col {col}", line=line, col=col)


class JavaCompiler(BaseCompiler):
    language_id = "java"
    display_name = "Java (Subset: class Main, public static void main, println)"
    file_extension = ".java"

    def tokenize(self, source: str) -> List[Dict[str, Any]]:
        return JavaLexer(source).tokenize()

    def parse(self, tokens: List[Dict[str, Any]], source: str = "") -> Dict[str, Any]:
        return JavaParser(tokens).parse_program()

    def analyze_semantics(self, ast: Any, source: str = "") -> Tuple[List[Any], List[str], List[Dict[str, Any]]]:
        errors = []
        symbol_table = {}
        declared_vars = set()

        statements = ast.get("statements", []) if isinstance(ast, dict) else []

        # Find classes and their methods
        classes = [s for s in statements if s.get("type") == "ClassDef"]
        if classes:
            has_main = False
            main_typo_found = None
            for cls in classes:
                for m in cls.get("members", []):
                    if m.get("type") == "FunctionDef":
                        fname = m.get("name", "")
                        mods = m.get("modifiers", [])
                        if fname == "main" and "static" in mods:
                            has_main = True
                        elif fname.lower() in JAVA_TYPO_MAP.get("main", set()) or difflib.get_close_matches(fname.lower(), ["main"], cutoff=0.6):
                            main_typo_found = m

            if not has_main:
                if main_typo_found:
                    errors.append({
                        "stage": "Semantic Analyzer",
                        "message": f"Unknown entry point method '{main_typo_found.get('name')}'. Java executable classes require 'public static void main(String[] args)'. Did you mean 'main'?",
                        "line": main_typo_found.get("line", 1),
                        "col": main_typo_found.get("col", 1),
                        "column": main_typo_found.get("col", 1),
                        "severity": "error"
                    })
                else:
                    errors.append({
                        "stage": "Semantic Analyzer",
                        "message": "Missing 'main' method. Java programs require a 'public static void main(String[] args)' entry point inside an enclosing class.",
                        "line": classes[0].get("line", 1),
                        "col": classes[0].get("col", 1),
                        "column": classes[0].get("col", 1),
                        "severity": "error"
                    })

        def walk(stmts: List[Dict[str, Any]], scope: str):
            for s in stmts:
                stype = s.get("type")
                line = s.get("line", 1)
                col = s.get("col", 1)

                if stype == "ClassDef":
                    cname = s.get("name")
                    symbol_table[("global", cname)] = {
                        "name": cname, "type": "class", "scope": "global",
                        "line": line, "col": col, "initialized": True, "status": "Defined"
                    }
                    walk(s.get("members", []), cname)

                elif stype == "FunctionDef":
                    mname = s.get("name")
                    symbol_table[(scope, mname)] = {
                        "name": mname, "type": f"method() -> {s.get('return_type', 'void')}",
                        "scope": scope, "line": line, "col": col, "initialized": True, "status": "Defined"
                    }
                    walk(s.get("body", []), mname)

                elif stype == "VarDecl":
                    name = s.get("name")
                    dtype = s.get("datatype", "auto")
                    symbol_table[(scope, name)] = {
                        "name": name, "type": dtype, "scope": scope,
                        "line": line, "col": col, "initialized": s.get("value") is not None,
                        "status": "Initialized" if s.get("value") is not None else "Declared"
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
            language="java"
        )

    def execute(self, source: str, ir_data: Dict[str, Any]) -> Dict[str, Any]:
        return SafeExecutor.execute("java", source, ir_data)
