"""
Parser — Step 2 of the compiler pipeline.

Takes the list of tokens from the lexer and builds an AST (Abstract
Syntax Tree): a tree structure that captures operator precedence and
program structure.

Grammar we're implementing (standard arithmetic + assignment):

    statement  : IDENTIFIER ASSIGN expr
               | expr

    expr       : term ((PLUS | MINUS) term)*
    term       : factor ((MUL | DIV) factor)*
    factor     : NUMBER
               | IDENTIFIER
               | LPAREN expr RPAREN

This precedence chain (expr -> term -> factor) is *how* '*' and '/'
end up nested deeper in the tree than '+' and '-' automatically.
"""

from lexer import Lexer, NUMBER, IDENTIFIER, PLUS, MINUS, MUL, DIV, LPAREN, RPAREN, ASSIGN, EOF


# ---- AST Node types ----
# Each node is just a small object describing one piece of structure.

class NumberNode:
    def __init__(self, value):
        self.value = value

    def to_dict(self):
        return {"type": "Number", "value": self.value}


class IdentifierNode:
    def __init__(self, name):
        self.name = name

    def to_dict(self):
        return {"type": "Identifier", "name": self.name}


class BinOpNode:
    """A binary operation, e.g. left + right."""
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

    def to_dict(self):
        return {
            "type": "BinOp",
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }


class AssignNode:
    """e.g. x = 10"""
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def to_dict(self):
        return {
            "type": "Assign",
            "name": self.name,
            "value": self.value.to_dict(),
        }


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.current_token = self.tokens[self.pos]

    def error(self, expected):
        raise Exception(
            f"Parse error: expected {expected}, got {self.current_token} at position {self.pos}"
        )

    def eat(self, token_type):
        """Consume the current token if it matches, else error."""
        if self.current_token.type == token_type:
            self.pos += 1
            if self.pos < len(self.tokens):
                self.current_token = self.tokens[self.pos]
        else:
            self.error(token_type)

    def factor(self):
        """factor : NUMBER | IDENTIFIER | LPAREN expr RPAREN"""
        tok = self.current_token

        if tok.type == NUMBER:
            self.eat(NUMBER)
            return NumberNode(tok.value)

        if tok.type == IDENTIFIER:
            self.eat(IDENTIFIER)
            return IdentifierNode(tok.value)

        if tok.type == LPAREN:
            self.eat(LPAREN)
            node = self.expr()
            self.eat(RPAREN)
            return node

        self.error("NUMBER, IDENTIFIER or (")

    def term(self):
        """term : factor ((MUL | DIV) factor)*"""
        node = self.factor()
        while self.current_token.type in (MUL, DIV):
            op_tok = self.current_token
            self.eat(op_tok.type)
            right = self.factor()
            node = BinOpNode(node, op_tok.value, right)
        return node

    def expr(self):
        """expr : term ((PLUS | MINUS) term)*"""
        node = self.term()
        while self.current_token.type in (PLUS, MINUS):
            op_tok = self.current_token
            self.eat(op_tok.type)
            right = self.term()
            node = BinOpNode(node, op_tok.value, right)
        return node

    def statement(self):
        """statement : IDENTIFIER ASSIGN expr | expr"""
        if self.current_token.type == IDENTIFIER and self.tokens[self.pos + 1].type == ASSIGN:
            name = self.current_token.value
            self.eat(IDENTIFIER)
            self.eat(ASSIGN)
            value = self.expr()
            return AssignNode(name, value)
        return self.expr()

    def parse(self):
        node = self.statement()
        if self.current_token.type != EOF:
            self.error("EOF")
        return node


def print_tree(node, indent=0):
    """Pretty-print an AST node dict for terminal viewing."""
    d = node.to_dict() if hasattr(node, "to_dict") else node
    pad = "  " * indent
    if d["type"] == "Number":
        print(f"{pad}Number({d['value']})")
    elif d["type"] == "Identifier":
        print(f"{pad}Identifier({d['name']})")
    elif d["type"] == "BinOp":
        print(f"{pad}BinOp({d['op']})")
        print_tree(d["left"], indent + 1)
        print_tree(d["right"], indent + 1)
    elif d["type"] == "Assign":
        print(f"{pad}Assign({d['name']})")
        print_tree(d["value"], indent + 1)


# ---- Quick manual test ----
if __name__ == "__main__":
    test_inputs = [
        "2 + 3 * 4",
        "x = 10",
        "(1 + 2) * 3",
    ]

    for src in test_inputs:
        print(f"\nSource: {src}")
        lexer = Lexer(src)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        tree = parser.parse()
        print_tree(tree)