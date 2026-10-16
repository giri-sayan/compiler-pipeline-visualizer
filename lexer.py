"""
Lexer (Tokenizer) — Step 1 of the compiler pipeline.

Converts raw source code into a stream of tokens with exact line and column
tracking. Supports C (with #include, types, functions, comments), Toy Mini-Lang,
and Python-like syntax.
"""

# ---- Token Types ----
PREPROCESSOR = "PREPROCESSOR"
TYPE         = "TYPE"
IDENTIFIER   = "IDENTIFIER"
NUMBER       = "NUMBER"
STRING       = "STRING"

# Operators
PLUS         = "PLUS"
MINUS        = "MINUS"
MUL          = "MUL"
DIV          = "DIV"
MOD          = "MOD"
ASSIGN       = "ASSIGN"
EQ           = "EQ"
NEQ          = "NEQ"
LT           = "LT"
GT           = "GT"
LTE          = "LTE"
GTE          = "GTE"

# Delimiters
LPAREN       = "LPAREN"
RPAREN       = "RPAREN"
LBRACE       = "LBRACE"
RBRACE       = "RBRACE"
LBRACKET     = "LBRACKET"
RBRACKET     = "RBRACKET"
SEMICOLON    = "SEMICOLON"
COMMA        = "COMMA"

# Keywords
IF           = "IF"
ELSE         = "ELSE"
WHILE        = "WHILE"
FOR          = "FOR"
RETURN       = "RETURN"

EOF          = "EOF"

# Keyword mappings
KEYWORDS = {
    "int": TYPE,
    "float": TYPE,
    "char": TYPE,
    "double": TYPE,
    "void": TYPE,
    "const": TYPE,
    "unsigned": TYPE,
    "long": TYPE,
    "short": TYPE,
    "if": IF,
    "else": ELSE,
    "while": WHILE,
    "for": FOR,
    "return": RETURN,
}


class Token:
    def __init__(self, type_, value, line=1, col=1):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, L{self.line}:C{self.col})"

    def to_dict(self):
        return {
            "type": self.type,
            "value": self.value,
            "line": self.line,
            "col": self.col,
        }


class Lexer:
    def __init__(self, text, language="c"):
        self.text = text or ""
        self.language = (language or "c").lower()
        self.pos = 0
        self.line = 1
        self.col = 1
        self.current_char = self.text[self.pos] if len(self.text) > 0 else None

    def advance(self):
        """Advance cursor by 1 character, tracking line and col numbers."""
        if self.current_char == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1

        self.pos += 1
        if self.pos < len(self.text):
            self.current_char = self.text[self.pos]
        else:
            self.current_char = None

    def peek(self, offset=1):
        """Lookahead character without consuming."""
        peek_pos = self.pos + offset
        if peek_pos < len(self.text):
            return self.text[peek_pos]
        return None

    def skip_whitespace(self):
        while self.current_char is not None and self.current_char.isspace():
            self.advance()

    def skip_single_line_comment(self):
        """Skip // or # single line comments."""
        while self.current_char is not None and self.current_char != "\n":
            self.advance()

    def skip_multi_line_comment(self):
        """Skip /* ... */ comments."""
        self.advance()  # consume '*'
        while self.current_char is not None:
            if self.current_char == "*" and self.peek() == "/":
                self.advance()  # '*'
                self.advance()  # '/'
                break
            self.advance()

    def read_preprocessor(self):
        """
        Handles preprocessor directives like:
        #include <stdio.h>
        #include "header.h"
        #define MAX 100
        """
        start_col = self.col
        start_line = self.line
        result = ""
        while self.current_char is not None and self.current_char != "\n":
            result += self.current_char
            self.advance()
        return Token(PREPROCESSOR, result.strip(), line=start_line, col=start_col)

    def number(self):
        """Read an integer or floating-point literal."""
        start_col = self.col
        start_line = self.line
        result = ""
        is_float = False

        while self.current_char is not None and (self.current_char.isdigit() or self.current_char == "."):
            if self.current_char == ".":
                if is_float:
                    break
                is_float = True
            result += self.current_char
            self.advance()

        val = float(result) if is_float else int(result)
        return Token(NUMBER, val, line=start_line, col=start_col)

    def identifier(self):
        """Read identifier or keyword."""
        start_col = self.col
        start_line = self.line
        result = ""
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == "_"):
            result += self.current_char
            self.advance()

        token_type = KEYWORDS.get(result, IDENTIFIER)
        return Token(token_type, result, line=start_line, col=start_col)

    def string(self, quote_char):
        """Read string literal like "hello\\n" or 'a'."""
        start_col = self.col
        start_line = self.line
        self.advance()  # Skip opening quote
        result = ""

        while self.current_char is not None and self.current_char != quote_char:
            if self.current_char == "\\" and self.peek() is not None:
                self.advance()
                escape_map = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'"}
                result += escape_map.get(self.current_char, self.current_char)
            else:
                result += self.current_char
            self.advance()

        if self.current_char == quote_char:
            self.advance()  # Skip closing quote

        return Token(STRING, result, line=start_line, col=start_col)

    def get_next_token(self):
        """Returns the next recognized token."""
        while self.current_char is not None:

            # Whitespace
            if self.current_char.isspace():
                self.skip_whitespace()
                continue

            # C single-line comments //
            if self.current_char == "/" and self.peek() == "/":
                self.skip_single_line_comment()
                continue

            # C multi-line comments /* ... */
            if self.current_char == "/" and self.peek() == "*":
                self.advance()  # consume '/'
                self.skip_multi_line_comment()
                continue

            # Preprocessor directives or python comments starting with #
            if self.current_char == "#":
                # Check if it is a preprocessor directive (#include, #define, etc.)
                rest_of_line = self.text[self.pos:self.text.find("\n", self.pos) if "\n" in self.text[self.pos:] else len(self.text)]
                stripped_directive = rest_of_line.strip()
                if stripped_directive.startswith(("#include", "#define", "#pragma", "#ifdef", "#ifndef", "#endif")):
                    return self.read_preprocessor()
                else:
                    # Generic comment (# in Python)
                    self.skip_single_line_comment()
                    continue

            # Numbers
            if self.current_char.isdigit():
                return self.number()

            # Identifiers and keywords
            if self.current_char.isalpha() or self.current_char == "_":
                return self.identifier()

            # Strings
            if self.current_char in ('"', "'"):
                return self.string(self.current_char)

            # Two-character operators
            cur_line, cur_col = self.line, self.col
            if self.current_char == "=" and self.peek() == "=":
                self.advance(); self.advance()
                return Token(EQ, "==", line=cur_line, col=cur_col)

            if self.current_char == "!" and self.peek() == "=":
                self.advance(); self.advance()
                return Token(NEQ, "!=", line=cur_line, col=cur_col)

            if self.current_char == "<" and self.peek() == "=":
                self.advance(); self.advance()
                return Token(LTE, "<=", line=cur_line, col=cur_col)

            if self.current_char == ">" and self.peek() == "=":
                self.advance(); self.advance()
                return Token(GTE, ">=", line=cur_line, col=cur_col)

            # Single-character tokens
            ch = self.current_char
            self.advance()

            single_char_tokens = {
                "+": (PLUS, "+"),
                "-": (MINUS, "-"),
                "*": (MUL, "*"),
                "/": (DIV, "/"),
                "%": (MOD, "%"),
                "=": (ASSIGN, "="),
                "<": (LT, "<"),
                ">": (GT, ">"),
                "(": (LPAREN, "("),
                ")": (RPAREN, ")"),
                "{": (LBRACE, "{"),
                "}": (RBRACE, "}"),
                "[": (LBRACKET, "["),
                "]": (RBRACKET, "]"),
                ";": (SEMICOLON, ";"),
                ",": (COMMA, ","),
            }

            if ch in single_char_tokens:
                token_type, token_val = single_char_tokens[ch]
                return Token(token_type, token_val, line=cur_line, col=cur_col)

            raise Exception(f"Lexical error: Unrecognized character {ch!r} at line {cur_line}, col {cur_col}")

        return Token(EOF, None, line=self.line, col=self.col)

    def tokenize(self):
        """Tokenize entire input string into a list of tokens."""
        tokens = []
        while True:
            tok = self.get_next_token()
            tokens.append(tok)
            if tok.type == EOF:
                break
        return tokens


if __name__ == "__main__":
    c_sample = '''#include <stdio.h>
// calculate sum
int main() {
    int total = 3 + 4 * 2;
    printf("Result = %d\\n", total);
    return 0;
}'''

    print("Testing C lexer with #include:")
    lexer = Lexer(c_sample)
    for t in lexer.tokenize():
        print(" ", t)