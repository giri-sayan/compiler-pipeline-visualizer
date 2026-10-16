"""
Parser — Step 2 of the compiler pipeline.

Constructs an Abstract Syntax Tree (AST) using a hand-written recursive-descent
parser. Supports C programs (with #include, types, functions, return, printf,
semicolons), Toy Mini-Lang statements, and expressions.
"""

from lexer import (
    PREPROCESSOR, TYPE, IDENTIFIER, NUMBER, STRING,
    PLUS, MINUS, MUL, DIV, MOD, ASSIGN,
    EQ, NEQ, LT, GT, LTE, GTE,
    LPAREN, RPAREN, LBRACE, RBRACE, SEMICOLON, COMMA,
    IF, ELSE, WHILE, FOR, RETURN, EOF
)


# ---- AST Node Classes ----

class ASTNode:
    def to_dict(self):
        raise NotImplementedError


class NumberNode(ASTNode):
    def __init__(self, value, line=1):
        self.value = value
        self.line = line

    def to_dict(self):
        return {"type": "Number", "value": self.value, "line": self.line}


class StringNode(ASTNode):
    def __init__(self, value, line=1):
        self.value = value
        self.line = line

    def to_dict(self):
        return {"type": "String", "value": self.value, "line": self.line}


class IdentifierNode(ASTNode):
    def __init__(self, name, line=1):
        self.name = name
        self.line = line

    def to_dict(self):
        return {"type": "Identifier", "name": self.name, "line": self.line}


class BinOpNode(ASTNode):
    def __init__(self, left, op, right, line=1):
        self.left = left
        self.op = op
        self.right = right
        self.line = line

    def to_dict(self):
        return {
            "type": "BinOp",
            "op": self.op,
            "left": self.left.to_dict() if hasattr(self.left, "to_dict") else self.left,
            "right": self.right.to_dict() if hasattr(self.right, "to_dict") else self.right,
            "line": self.line,
        }


class UnaryOpNode(ASTNode):
    def __init__(self, op, operand, line=1):
        self.op = op
        self.operand = operand
        self.line = line

    def to_dict(self):
        return {
            "type": "UnaryOp",
            "op": self.op,
            "operand": self.operand.to_dict() if hasattr(self.operand, "to_dict") else self.operand,
            "line": self.line,
        }


class AssignNode(ASTNode):
    def __init__(self, name, value, line=1):
        self.name = name
        self.value = value
        self.line = line

    def to_dict(self):
        return {
            "type": "Assign",
            "name": self.name,
            "value": self.value.to_dict() if hasattr(self.value, "to_dict") else self.value,
            "line": self.line,
        }


class VarDeclNode(ASTNode):
    def __init__(self, datatype, name, value=None, line=1):
        self.datatype = datatype
        self.name = name
        self.value = value
        self.line = line

    def to_dict(self):
        return {
            "type": "VarDecl",
            "datatype": self.datatype,
            "name": self.name,
            "value": self.value.to_dict() if self.value and hasattr(self.value, "to_dict") else None,
            "line": self.line,
        }


class IncludeNode(ASTNode):
    def __init__(self, header, line=1):
        self.header = header
        self.line = line

    def to_dict(self):
        return {"type": "Include", "header": self.header, "line": self.line}


class FunctionCallNode(ASTNode):
    def __init__(self, name, args=None, line=1):
        self.name = name
        self.args = args or []
        self.line = line

    def to_dict(self):
        return {
            "type": "FunctionCall",
            "name": self.name,
            "args": [a.to_dict() if hasattr(a, "to_dict") else a for a in self.args],
            "line": self.line,
        }


class FunctionDefNode(ASTNode):
    def __init__(self, return_type, name, params=None, body=None, line=1):
        self.return_type = return_type
        self.name = name
        self.params = params or []
        self.body = body or []
        self.line = line

    def to_dict(self):
        return {
            "type": "FunctionDef",
            "return_type": self.return_type,
            "name": self.name,
            "params": self.params,
            "body": [s.to_dict() if hasattr(s, "to_dict") else s for s in self.body],
            "line": self.line,
        }


class ReturnNode(ASTNode):
    def __init__(self, value=None, line=1):
        self.value = value
        self.line = line

    def to_dict(self):
        return {
            "type": "Return",
            "value": self.value.to_dict() if self.value and hasattr(self.value, "to_dict") else None,
            "line": self.line,
        }


class IfNode(ASTNode):
    def __init__(self, condition, then_branch=None, else_branch=None, line=1):
        self.condition = condition
        self.then_branch = then_branch or []
        self.else_branch = else_branch or []
        self.line = line

    def to_dict(self):
        return {
            "type": "If",
            "condition": self.condition.to_dict() if hasattr(self.condition, "to_dict") else self.condition,
            "then_branch": [s.to_dict() if hasattr(s, "to_dict") else s for s in self.then_branch],
            "else_branch": [s.to_dict() if hasattr(s, "to_dict") else s for s in self.else_branch],
            "line": self.line,
        }


class ProgramNode(ASTNode):
    def __init__(self, statements=None):
        self.statements = statements or []

    def to_dict(self):
        return {
            "type": "Program",
            "statements": [s.to_dict() if hasattr(s, "to_dict") else s for s in self.statements],
        }


# ---- Parser Class ----

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens or []
        self.pos = 0
        self.current_token = self.tokens[self.pos] if len(self.tokens) > 0 else None

    def error(self, expected):
        token_info = f"'{self.current_token.value}' ({self.current_token.type})" if self.current_token else "EOF"
        line = self.current_token.line if self.current_token else "?"
        col = self.current_token.col if self.current_token else "?"
        raise Exception(f"Syntax error: expected {expected}, got {token_info} at line {line}, col {col}")

    def peek(self, offset=1):
        pos = self.pos + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return None

    def eat(self, token_type):
        """Consume current token if it matches expected type."""
        if self.current_token and self.current_token.type == token_type:
            tok = self.current_token
            self.pos += 1
            if self.pos < len(self.tokens):
                self.current_token = self.tokens[self.pos]
            else:
                self.current_token = None
            return tok
        self.error(token_type)

    def factor(self):
        """
        factor : NUMBER | STRING | IDENTIFIER (LPAREN arg_list? RPAREN)? | LPAREN expr RPAREN | (PLUS | MINUS) factor
        """
        tok = self.current_token
        if tok is None:
            self.error("expression factor")

        line = tok.line

        # Unary operators + and -
        if tok.type in (PLUS, MINUS):
            op_tok = self.eat(tok.type)
            operand = self.factor()
            return UnaryOpNode(op_tok.value, operand, line=line)

        # Number literal
        if tok.type == NUMBER:
            self.eat(NUMBER)
            return NumberNode(tok.value, line=line)

        # String literal
        if tok.type == STRING:
            self.eat(STRING)
            return StringNode(tok.value, line=line)

        # Identifier or function call
        if tok.type == IDENTIFIER:
            name = tok.value
            self.eat(IDENTIFIER)
            # Function call e.g. printf(...)
            if self.current_token and self.current_token.type == LPAREN:
                self.eat(LPAREN)
                args = []
                if self.current_token and self.current_token.type != RPAREN:
                    args.append(self.expr())
                    while self.current_token and self.current_token.type == COMMA:
                        self.eat(COMMA)
                        args.append(self.expr())
                self.eat(RPAREN)
                return FunctionCallNode(name, args, line=line)
            return IdentifierNode(name, line=line)

        # Parenthesized expression
        if tok.type == LPAREN:
            self.eat(LPAREN)
            node = self.expr()
            self.eat(RPAREN)
            return node

        self.error("number, string, identifier, or '('")

    def term(self):
        """term : factor ((MUL | DIV | MOD) factor)*"""
        node = self.factor()
        while self.current_token and self.current_token.type in (MUL, DIV, MOD):
            op_tok = self.eat(self.current_token.type)
            right = self.factor()
            node = BinOpNode(node, op_tok.value, right, line=op_tok.line)
        return node

    def add_expr(self):
        """add_expr : term ((PLUS | MINUS) term)*"""
        node = self.term()
        while self.current_token and self.current_token.type in (PLUS, MINUS):
            op_tok = self.eat(self.current_token.type)
            right = self.term()
            node = BinOpNode(node, op_tok.value, right, line=op_tok.line)
        return node

    def relational_expr(self):
        """relational_expr : add_expr ((LT | GT | LTE | GTE) add_expr)*"""
        node = self.add_expr()
        while self.current_token and self.current_token.type in (LT, GT, LTE, GTE):
            op_tok = self.eat(self.current_token.type)
            right = self.add_expr()
            node = BinOpNode(node, op_tok.value, right, line=op_tok.line)
        return node

    def expr(self):
        """expr : relational_expr ((EQ | NEQ) relational_expr)*"""
        node = self.relational_expr()
        while self.current_token and self.current_token.type in (EQ, NEQ):
            op_tok = self.eat(self.current_token.type)
            right = self.relational_expr()
            node = BinOpNode(node, op_tok.value, right, line=op_tok.line)
        return node

    def statement(self):
        """
        Parses a single statement or directive:
          - Preprocessor: #include <stdio.h>
          - Function definition: int main() { ... }
          - Variable declaration: int x = 5;
          - Assignment: x = 10;
          - Return: return 0;
          - If: if (cond) { ... }
          - Expression or call: printf(...);
        """
        tok = self.current_token
        if tok is None:
            return None

        line = tok.line

        # 1. Preprocessor directive (#include, #define)
        if tok.type == PREPROCESSOR:
            directive_text = tok.value
            self.eat(PREPROCESSOR)
            header = directive_text
            # Extract header name e.g. <stdio.h>
            if "#include" in directive_text:
                parts = directive_text.split(None, 1)
                if len(parts) > 1:
                    header = parts[1].strip()
            return IncludeNode(header, line=line)

        # 2. Type declaration or Function definition
        if tok.type == TYPE:
            dtype_tok = self.eat(TYPE)
            ident_tok = self.eat(IDENTIFIER)

            # Check if this is a function definition: TYPE IDENTIFIER LPAREN
            if self.current_token and self.current_token.type == LPAREN:
                self.eat(LPAREN)
                params = []
                while self.current_token and self.current_token.type != RPAREN:
                    if self.current_token.type == TYPE:
                        p_type = self.eat(TYPE).value
                        p_name = self.eat(IDENTIFIER).value if self.current_token and self.current_token.type == IDENTIFIER else ""
                        params.append({"type": p_type, "name": p_name})
                    if self.current_token and self.current_token.type == COMMA:
                        self.eat(COMMA)
                self.eat(RPAREN)

                # Function body in { ... }
                body = []
                if self.current_token and self.current_token.type == LBRACE:
                    self.eat(LBRACE)
                    while self.current_token and self.current_token.type != RBRACE and self.current_token.type != EOF:
                        stmt = self.statement()
                        if stmt:
                            body.append(stmt)
                    if self.current_token and self.current_token.type == RBRACE:
                        self.eat(RBRACE)
                return FunctionDefNode(dtype_tok.value, ident_tok.value, params=params, body=body, line=line)

            # Otherwise, variable declaration: TYPE IDENTIFIER (= expr)? ;?
            init_val = None
            if self.current_token and self.current_token.type == ASSIGN:
                self.eat(ASSIGN)
                init_val = self.expr()

            if self.current_token and self.current_token.type == SEMICOLON:
                self.eat(SEMICOLON)

            return VarDeclNode(dtype_tok.value, ident_tok.value, init_val, line=line)

        # 3. Return statement: return expr?;
        if tok.type == RETURN:
            self.eat(RETURN)
            val = None
            if self.current_token and self.current_token.type not in (SEMICOLON, RBRACE, EOF):
                val = self.expr()
            if self.current_token and self.current_token.type == SEMICOLON:
                self.eat(SEMICOLON)
            return ReturnNode(val, line=line)

        # 4. If statement: if (expr) { ... } (else { ... })?
        if tok.type == IF:
            self.eat(IF)
            if self.current_token and self.current_token.type == LPAREN:
                self.eat(LPAREN)
                cond = self.expr()
                self.eat(RPAREN)
            else:
                cond = self.expr()

            then_body = []
            if self.current_token and self.current_token.type == LBRACE:
                self.eat(LBRACE)
                while self.current_token and self.current_token.type != RBRACE and self.current_token.type != EOF:
                    s = self.statement()
                    if s: then_body.append(s)
                self.eat(RBRACE)
            else:
                s = self.statement()
                if s: then_body.append(s)

            else_body = []
            if self.current_token and self.current_token.type == ELSE:
                self.eat(ELSE)
                if self.current_token and self.current_token.type == LBRACE:
                    self.eat(LBRACE)
                    while self.current_token and self.current_token.type != RBRACE and self.current_token.type != EOF:
                        s = self.statement()
                        if s: else_body.append(s)
                    self.eat(RBRACE)
                else:
                    s = self.statement()
                    if s: else_body.append(s)

            return IfNode(cond, then_body, else_body, line=line)

        # 5. Assignment without type: IDENTIFIER = expr
        next_tok = self.peek()
        if tok.type == IDENTIFIER and next_tok and next_tok.type == ASSIGN:
            name = tok.value
            self.eat(IDENTIFIER)
            self.eat(ASSIGN)
            val = self.expr()
            if self.current_token and self.current_token.type == SEMICOLON:
                self.eat(SEMICOLON)
            return AssignNode(name, val, line=line)

        # 6. Expression or standalone call: printf(...) or 3 + 4;
        expr_node = self.expr()
        if self.current_token and self.current_token.type == SEMICOLON:
            self.eat(SEMICOLON)
        return expr_node

    def parse_program(self):
        """Parse all tokens into a ProgramNode."""
        statements = []
        while self.current_token and self.current_token.type != EOF:
            stmt = self.statement()
            if stmt:
                statements.append(stmt)
        return ProgramNode(statements)

    def parse(self):
        """
        Convenience method: if whole program has 1 expression/assignment statement,
        returns that single AST node for backward compatibility; otherwise returns ProgramNode.
        """
        prog = self.parse_program()
        if len(prog.statements) == 1 and isinstance(prog.statements[0], (AssignNode, BinOpNode, NumberNode, IdentifierNode)):
            return prog.statements[0]
        return prog


def print_tree(node, indent=0):
    """Pretty-print an AST node for console inspection."""
    d = node.to_dict() if hasattr(node, "to_dict") else node
    pad = "  " * indent
    ntype = d.get("type", "Unknown")

    if ntype == "Program":
        print(f"{pad}Program")
        for s in d.get("statements", []):
            print_tree(s, indent + 1)
    elif ntype == "Include":
        print(f"{pad}Include({d.get('header')})")
    elif ntype == "FunctionDef":
        print(f"{pad}FunctionDef: {d.get('return_type')} {d.get('name')}()")
        for s in d.get("body", []):
            print_tree(s, indent + 1)
    elif ntype == "VarDecl":
        print(f"{pad}VarDecl: {d.get('datatype')} {d.get('name')}")
        if d.get("value"):
            print_tree(d["value"], indent + 1)
    elif ntype == "Assign":
        print(f"{pad}Assign({d.get('name')})")
        print_tree(d.get("value"), indent + 1)
    elif ntype == "BinOp":
        print(f"{pad}BinOp({d.get('op')})")
        print_tree(d.get("left"), indent + 1)
        print_tree(d.get("right"), indent + 1)
    elif ntype == "Number":
        print(f"{pad}Number({d.get('value')})")
    elif ntype == "Identifier":
        print(f"{pad}Identifier({d.get('name')})")
    elif ntype == "String":
        print(f"{pad}String({d.get('value')!r})")
    elif ntype == "Return":
        print(f"{pad}Return")
        if d.get("value"):
            print_tree(d["value"], indent + 1)
    elif ntype == "FunctionCall":
        print(f"{pad}Call: {d.get('name')}()")
        for arg in d.get("args", []):
            print_tree(arg, indent + 1)
    else:
        print(f"{pad}{ntype}")


if __name__ == "__main__":
    from lexer import Lexer

    c_sample = '''#include <stdio.h>

int main() {
    int total = 3 + 4 * 2;
    printf("Result = %d\\n", total);
    return 0;
}'''

    tokens = Lexer(c_sample).tokenize()
    parser = Parser(tokens)
    tree = parser.parse()
    print("Parsed AST:")
    print_tree(tree)