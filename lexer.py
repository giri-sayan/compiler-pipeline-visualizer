"""
Lexer (Tokenizer) — Step 1 of the compiler pipeline.

Takes a source code string and breaks it into a list of tokens.
A token is just a small piece with a TYPE and a VALUE, e.g.
    "3"   -> (NUMBER, 3)
    "+"   -> (PLUS, '+')
    "x"   -> (IDENTIFIER, 'x')

Supports for now: numbers, + - * / ( ), identifiers (variable names),
'=' for assignment, and 'if' as a keyword. That's enough to look like
a real (tiny) language without being overwhelming.
"""

# ---- Token types ----
NUMBER      = "NUMBER"
IDENTIFIER  = "IDENTIFIER"
PLUS        = "PLUS"
MINUS       = "MINUS"
MUL         = "MUL"
DIV         = "DIV"
LPAREN      = "LPAREN"
RPAREN      = "RPAREN"
ASSIGN      = "ASSIGN"
IF          = "IF"
EOF         = "EOF"

KEYWORDS = {"if": IF}


class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f"Token({self.type}, {self.value!r})"

    def to_dict(self):
        # Used later when we send tokens to the frontend as JSON
        return {"type": self.type, "value": self.value}


class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.current_char = self.text[self.pos] if self.text else None

    def advance(self):
        """Move to the next character."""
        self.pos += 1
        if self.pos < len(self.text):
            self.current_char = self.text[self.pos]
        else:
            self.current_char = None

    def skip_whitespace(self):
        while self.current_char is not None and self.current_char.isspace():
            self.advance()

    def number(self):
        """Read a full multi-digit number, e.g. '123'."""
        result = ""
        while self.current_char is not None and self.current_char.isdigit():
            result += self.current_char
            self.advance()
        return Token(NUMBER, int(result))

    def identifier(self):
        """Read a full identifier or keyword, e.g. 'x' or 'if'."""
        result = ""
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == "_"):
            result += self.current_char
            self.advance()
        token_type = KEYWORDS.get(result, IDENTIFIER)
        return Token(token_type, result)

    def get_next_token(self):
        """The main function: returns the next token each time it's called."""
        while self.current_char is not None:

            if self.current_char.isspace():
                self.skip_whitespace()
                continue

            if self.current_char.isdigit():
                return self.number()

            if self.current_char.isalpha() or self.current_char == "_":
                return self.identifier()

            if self.current_char == "+":
                self.advance()
                return Token(PLUS, "+")

            if self.current_char == "-":
                self.advance()
                return Token(MINUS, "-")

            if self.current_char == "*":
                self.advance()
                return Token(MUL, "*")

            if self.current_char == "/":
                self.advance()
                return Token(DIV, "/")

            if self.current_char == "(":
                self.advance()
                return Token(LPAREN, "(")

            if self.current_char == ")":
                self.advance()
                return Token(RPAREN, ")")

            if self.current_char == "=":
                self.advance()
                return Token(ASSIGN, "=")

            raise Exception(f"Unrecognized character: {self.current_char!r} at position {self.pos}")

        return Token(EOF, None)

    def tokenize(self):
        """Convenience: get ALL tokens at once as a list (used for testing/printing)."""
        tokens = []
        while True:
            tok = self.get_next_token()
            tokens.append(tok)
            if tok.type == EOF:
                break
        return tokens


# ---- Quick manual test ----
if __name__ == "__main__":
    test_inputs = [
        "2 + 3 * 4",
        "x = 10",
        "if x = 1",
        "(1 + 2) * 3",
    ]

    for src in test_inputs:
        print(f"\nSource: {src}")
        lexer = Lexer(src)
        for tok in lexer.tokenize():
            print("  ", tok)