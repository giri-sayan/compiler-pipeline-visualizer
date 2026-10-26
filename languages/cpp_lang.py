"""
C++ Language Compiler Frontend (Educational Modern C++ Subset).

Supports:
  - #include <iostream>, <vector>, <string>, <cmath>
  - using namespace std;
  - Stream I/O: cout << ... << endl; and cin >> var;
  - Classes: class Name { public: ... private: ... };
  - Member methods, fields, and constructors
  - Object instantiation and member access
  - Entry point validation (int main() required)
  - Full semantic checking with C++ typo suggestions (coutt -> cout, ednl -> endl)
  - TAC IR, Assembly code generation, and Safe Execution
"""

import re
import difflib
from typing import Dict, Any, List, Tuple, Optional
from languages.base import BaseCompiler
from tac_vm import TACVirtualMachine
from executor import SafeExecutor
from explainer import generate_explanation


CPP_KEYWORDS = {
    "class", "public", "private", "protected", "namespace", "using", "std",
    "cout", "cin", "endl", "new", "delete", "auto", "bool", "true", "false",
    "const", "int", "float", "double", "char", "void", "string",
    "if", "else", "while", "for", "return"
}

CPP_TYPO_MAP = {
    "cout": {"coutt", "cot", "cuot", "count_out"},
    "cin": {"cinn", "cn"},
    "endl": {"ednl", "endll", "end"},
    "main": {"ain", "mian", "maim", "mani", "mainn", "mein"},
    "class": {"calss", "clas", "clss"},
    "public": {"pubic", "publc"},
    "private": {"privat", "privte"},
    "return": {"eturn", "retun", "retrun", "reurn"},
}


class CPPCompilerError(Exception):
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


class CPPLexer:
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
                    raise CPPCompilerError(f"Lexical error: Unterminated multi-line comment '/*' at line {s_line}, col {s_col}", line=s_line, col=s_col, stage="Lexer")
                continue

            # Preprocessor #include
            if self.current_char == "#":
                s_line, s_col = self.line, self.col
                rest = ""
                while self.current_char is not None and self.current_char != "\n":
                    rest += self.current_char
                    self.advance()
                tokens.append({"type": "PREPROCESSOR", "value": rest.strip(), "line": s_line, "col": s_col})
                continue

            cur_line, cur_col = self.line, self.col

            # Numbers
            if self.current_char.isdigit():
                num_str = ""
                is_flt = False
                while self.current_char is not None and (self.current_char.isdigit() or self.current_char == "."):
                    if self.current_char == ".":
                        if is_flt:
                            raise CPPCompilerError(f"Lexical error: Malformed numeric literal '{num_str}.' at line {cur_line}, col {cur_col}", line=cur_line, col=cur_col, stage="Lexer")
                        is_flt = True
                    num_str += self.current_char
                    self.advance()
                # Invalid suffix check
                if self.current_char is not None and (self.current_char.isalpha() or self.current_char == "_"):
                    bad = ""
                    while self.current_char is not None and (self.current_char.isalnum() or self.current_char == "_"):
                        bad += self.current_char
                        self.advance()
                    raise CPPCompilerError(f"Lexical error: Malformed numeric literal '{num_str}{bad}' at line {cur_line}, col {cur_col}", line=cur_line, col=cur_col, stage="Lexer")
                tokens.append({"type": "NUMBER", "value": float(num_str) if is_flt else int(num_str), "line": cur_line, "col": cur_col})
                continue

            # Identifiers and Keywords
            if self.current_char.isalpha() or self.current_char == "_":
                ident = ""
                while self.current_char is not None and (self.current_char.isalnum() or self.current_char == "_"):
                    ident += self.current_char
                    self.advance()
                t_type = "IDENTIFIER"
                if ident in ("int", "float", "double", "char", "void", "bool", "string", "auto"):
                    t_type = "TYPE"
                elif ident in CPP_KEYWORDS:
                    t_type = ident.upper()
                tokens.append({"type": t_type, "value": ident, "line": cur_line, "col": cur_col})
                continue

            # Strings
            if self.current_char in ('"', "'"):
                q = self.current_char
                self.advance()
                s_val = ""
                while self.current_char is not None and self.current_char != q:
                    if self.current_char == "\n":
                        raise CPPCompilerError(f"Lexical error: Unterminated string literal at line {cur_line}, col {cur_col}", line=cur_line, col=cur_col, stage="Lexer")
                    if self.current_char == "\\" and self.peek() is not None:
                        self.advance()
                        escapes = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}
                        s_val += escapes.get(self.current_char, self.current_char)
                    else:
                        s_val += self.current_char
                    self.advance()
                if self.current_char != q:
                    raise CPPCompilerError(f"Lexical error: Unterminated string literal at line {cur_line}, col {cur_col}", line=cur_line, col=cur_col, stage="Lexer")
                self.advance()
                tokens.append({"type": "STRING", "value": s_val, "line": cur_line, "col": cur_col})
                continue

            # Two-character operators (<<, >>, ::, ==, !=, <=, >=)
            ch2 = self.current_char + (self.peek() or "")
            op2_map = {
                "<<": "STREAM_OUT", ">>": "STREAM_IN", "::": "SCOPE",
                "==": "EQ", "!=": "NEQ", "<=": "LTE", ">=": "GTE"
            }
            if ch2 in op2_map:
                self.advance(); self.advance()
                tokens.append({"type": op2_map[ch2], "value": ch2, "line": cur_line, "col": cur_col})
                continue

            # Single-character tokens
            ch = self.current_char
            self.advance()
            s_map = {
                "+": "PLUS", "-": "MINUS", "*": "MUL", "/": "DIV", "%": "MOD",
                "=": "ASSIGN", "<": "LT", ">": "GT", "(": "LPAREN", ")": "RPAREN",
                "{": "LBRACE", "}": "RBRACE", "[": "LBRACKET", "]": "RBRACKET",
                ";": "SEMICOLON", ",": "COMMA", ":": "COLON", ".": "DOT", "&": "AMP"
            }
            if ch in s_map:
                tokens.append({"type": s_map[ch], "value": ch, "line": cur_line, "col": cur_col})
                continue

            raise CPPCompilerError(f"Lexical error: Unrecognized character {ch!r} at line {cur_line}, col {cur_col}", line=cur_line, col=cur_col, stage="Lexer")

        tokens.append({"type": "EOF", "value": None, "line": self.line, "col": self.col})
        return tokens


class CPPParser:
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
        raise CPPCompilerError(f"Syntax error: expected '{token_type}', got '{c_val}' ({c_type}) at line {c_line}, col {c_col}", line=c_line, col=c_col)

    def parse_program(self) -> Dict[str, Any]:
        statements = []
        while self.cur and self.cur["type"] != "EOF":
            stmt = self.statement()
            if stmt:
                statements.append(stmt)
        return {
            "type": "Program",
            "language": "cpp",
            "statements": statements
        }

    def statement(self) -> Optional[Dict[str, Any]]:
        if not self.cur or self.cur["type"] == "EOF":
            return None

        line = self.cur["line"]
        col = self.cur["col"]

        # Preprocessor: #include <iostream>
        if self.cur["type"] == "PREPROCESSOR":
            val = self.cur["value"]
            self.eat("PREPROCESSOR")
            hdr = val.replace("#include", "").strip() if "#include" in val else val
            return {"type": "Include", "header": hdr, "line": line, "col": col}

        # using namespace std;
        if self.cur["type"] == "USING":
            self.eat("USING")
            if self.cur and self.cur["type"] == "NAMESPACE":
                self.eat("NAMESPACE")
            ns_name = self.cur["value"] if self.cur else "std"
            self.eat(self.cur["type"])
            self.eat("SEMICOLON")
            return {"type": "NamespaceUse", "namespace": ns_name, "line": line, "col": col}

        # Typo checks for cout, cin, class, return
        if self.cur["type"] == "IDENTIFIER":
            ident_name = str(self.cur["value"]).lower()
            for kw, typos in CPP_TYPO_MAP.items():
                if ident_name != kw and (ident_name in typos or (len(ident_name) >= 3 and difflib.get_close_matches(ident_name, [kw], cutoff=0.7))):
                    raise CPPCompilerError(f"Unknown keyword or statement '{self.cur['value']}'. Did you mean '{kw}'?", line=line, col=col)

        # cout << expr << ... << endl;
        if self.cur["type"] == "COUT":
            self.eat("COUT")
            items = []
            while self.cur and self.cur["type"] == "STREAM_OUT":
                self.eat("STREAM_OUT")
                if self.cur and self.cur["type"] == "ENDL":
                    self.eat("ENDL")
                    items.append({"type": "String", "value": "\n", "line": line, "col": col})
                else:
                    items.append(self.expr())
            self.eat("SEMICOLON")
            return {"type": "StreamOutput", "stream": "cout", "items": items, "line": line, "col": col}

        # cin >> var;
        if self.cur["type"] == "CIN":
            self.eat("CIN")
            items = []
            while self.cur and self.cur["type"] == "STREAM_IN":
                self.eat("STREAM_IN")
                var_tok = self.eat("IDENTIFIER")
                items.append(var_tok["value"])
            self.eat("SEMICOLON")
            return {"type": "StreamInput", "stream": "cin", "variables": items, "line": line, "col": col}

        # class ClassName { public: ... private: ... };
        if self.cur["type"] == "CLASS":
            self.eat("CLASS")
            name_tok = self.eat("IDENTIFIER")
            c_name = name_tok["value"]
            self.eat("LBRACE")
            members = []
            current_access = "private"
            while self.cur and self.cur["type"] != "RBRACE" and self.cur["type"] != "EOF":
                if self.cur["type"] in ("PUBLIC", "PRIVATE", "PROTECTED"):
                    current_access = self.cur["value"]
                    self.eat(self.cur["type"])
                    self.eat("COLON")
                    continue
                m_stmt = self.statement()
                if m_stmt:
                    m_stmt["access"] = current_access
                    members.append(m_stmt)
            self.eat("RBRACE")
            if self.cur and self.cur["type"] == "SEMICOLON":
                self.eat("SEMICOLON")
            return {"type": "ClassDef", "name": c_name, "members": members, "line": line, "col": col}

        # Type declaration or function: TYPE IDENTIFIER
        if self.cur["type"] == "TYPE":
            dtype = self.eat("TYPE")["value"]
            # optional reference or pointer (int&, int*)
            is_ref = False
            if self.cur and self.cur["type"] in ("AMP", "MUL"):
                is_ref = True
                self.eat(self.cur["type"])
            ident = self.eat("IDENTIFIER")["value"]

            # Function definition: TYPE IDENTIFIER ( ... ) { ... }
            if self.cur and self.cur["type"] == "LPAREN":
                self.eat("LPAREN")
                params = []
                while self.cur and self.cur["type"] != "RPAREN":
                    p_type = self.eat("TYPE")["value"]
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
                return {"type": "FunctionDef", "return_type": dtype, "name": ident, "params": params, "body": body, "line": line, "col": col}

            # Variable declaration: TYPE IDENTIFIER (= expr)?;
            init_val = None
            if self.cur and self.cur["type"] == "ASSIGN":
                self.eat("ASSIGN")
                init_val = self.expr()
            self.eat("SEMICOLON")
            return {"type": "VarDecl", "datatype": dtype, "name": ident, "is_reference": is_ref, "value": init_val, "line": line, "col": col}

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

        # Assignment: IDENTIFIER = expr; or object member r.width = 10;
        if self.cur["type"] == "IDENTIFIER":
            name = self.cur["value"]
            next_t = self.peek()
            if next_t and next_t["type"] == "DOT":
                self.eat("IDENTIFIER")
                self.eat("DOT")
                member = self.eat("IDENTIFIER")["value"]
                self.eat("ASSIGN")
                val = self.expr()
                self.eat("SEMICOLON")
                return {"type": "Assign", "name": f"{name}.{member}", "value": val, "line": line, "col": col}

            if next_t and next_t["type"] == "ASSIGN":
                self.eat("IDENTIFIER")
                self.eat("ASSIGN")
                val = self.expr()
                self.eat("SEMICOLON")
                return {"type": "Assign", "name": name, "value": val, "line": line, "col": col}

        # Standalone expression
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
            raise CPPCompilerError("Syntax error: unexpected end of expression")
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
            while self.cur and self.cur["type"] == "DOT":
                self.eat("DOT")
                member = self.eat("IDENTIFIER")["value"]
                name = f"{name}.{member}"
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
        raise CPPCompilerError(f"Syntax error: unexpected token '{c_val}' ({c_type}) in expression at line {line}, col {col}", line=line, col=col)


class CPPCompiler(BaseCompiler):
    language_id = "cpp"
    display_name = "C++ (Subset: <iostream>, cout, classes, main)"
    file_extension = ".cpp"

    def tokenize(self, source: str) -> List[Dict[str, Any]]:
        return CPPLexer(source).tokenize()

    def parse(self, tokens: List[Dict[str, Any]], source: str = "") -> Dict[str, Any]:
        return CPPParser(tokens).parse_program()

    def analyze_semantics(self, ast: Any, source: str = "") -> Tuple[List[Any], List[str], List[Dict[str, Any]]]:
        errors = []
        symbol_table = {}
        declared_vars = set()

        statements = ast.get("statements", []) if isinstance(ast, dict) else []

        # 1. Entry point check: C++ programs with functions MUST define int main()
        function_defs = [s for s in statements if s.get("type") == "FunctionDef"]
        if function_defs:
            has_main = any(f.get("name") == "main" for f in function_defs)
            if not has_main:
                # Typo check for main
                main_typo = next((f for f in function_defs if f.get("name", "").lower() in CPP_TYPO_MAP.get("main", set()) or difflib.get_close_matches(f.get("name", "").lower(), ["main"], cutoff=0.6)), None)
                if main_typo:
                    errors.append({
                        "stage": "Semantic Analyzer",
                        "message": f"Unknown entry point function '{main_typo.get('name')}'. C++ programs require a 'main' function as the entry point. Did you mean 'main'?",
                        "line": main_typo.get("line", 1),
                        "col": main_typo.get("col", 1),
                        "column": main_typo.get("col", 1),
                        "severity": "error"
                    })
                else:
                    errors.append({
                        "stage": "Semantic Analyzer",
                        "message": "Missing 'main' function. C++ programs require a 'main' function as the entry point.",
                        "line": function_defs[0].get("line", 1),
                        "col": function_defs[0].get("col", 1),
                        "column": function_defs[0].get("col", 1),
                        "severity": "error"
                    })

        def walk(stmts: List[Dict[str, Any]], scope: str):
            for s in stmts:
                stype = s.get("type")
                line = s.get("line", 1)
                col = s.get("col", 1)

                if stype == "VarDecl":
                    name = s.get("name")
                    dtype = s.get("datatype", "auto")
                    symbol_table[(scope, name)] = {
                        "name": name, "type": dtype, "scope": scope,
                        "line": line, "col": col, "initialized": s.get("value") is not None,
                        "status": "Initialized" if s.get("value") is not None else "Declared"
                    }
                    declared_vars.add(name)

                elif stype == "ClassDef":
                    cname = s.get("name")
                    symbol_table[("global", cname)] = {
                        "name": cname, "type": "class", "scope": "global",
                        "line": line, "col": col, "initialized": True, "status": "Defined"
                    }
                    walk(s.get("members", []), cname)

                elif stype == "FunctionDef":
                    fname = s.get("name")
                    symbol_table[(scope, fname)] = {
                        "name": fname, "type": f"function() -> {s.get('return_type', 'void')}",
                        "scope": scope, "line": line, "col": col, "initialized": True, "status": "Defined"
                    }
                    walk(s.get("body", []), fname)

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
            language="cpp"
        )

    def execute(self, source: str, ir_data: Dict[str, Any]) -> Dict[str, Any]:
        return SafeExecutor.execute("cpp", source, ir_data)
