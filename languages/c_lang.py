"""
C Language Compiler Frontend (C99 Educational Subset).
"""

from typing import Dict, Any, List, Tuple
from languages.base import BaseCompiler
from lexer import Lexer, LexerError
from parser import Parser, ParserError
import semantic
from ir_generator import generate_ir
from codegen import generate_code
from explainer import generate_explanation
from executor import SafeExecutor


class CCompiler(BaseCompiler):
    language_id = "c"
    display_name = "C (Subset: #include, main, types, printf)"
    file_extension = ".c"

    def tokenize(self, source: str) -> List[Any]:
        lexer = Lexer(source, language="c")
        return lexer.tokenize()

    def parse(self, tokens: List[Any], source: str = "") -> Any:
        parser = Parser(tokens, language="c")
        return parser.parse_program()

    def analyze_semantics(self, ast: Any, source: str = "") -> Tuple[List[Any], List[str], List[Dict[str, Any]]]:
        return semantic.analyze(ast, language="c")

    def generate_ir(self, ast: Any) -> Dict[str, Any]:
        return generate_ir(ast)

    def generate_assembly(self, ir_data: Dict[str, Any]) -> Dict[str, str]:
        return generate_code(ir_data)

    def generate_explanation(self, tokens: List[Any], ast: Any, semantic_info: Dict[str, Any],
                             ir_data: Dict[str, Any], assembly_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Take a slice of tokens to avoid huge overhead on 5000 lines
        token_dicts = [t.to_dict() if hasattr(t, "to_dict") else t for t in (tokens[:150] if tokens else [])]
        return generate_explanation(
            tokens=token_dicts,
            ast=ast,
            semantic_info=semantic_info,
            ir_data=ir_data,
            assembly_data=assembly_data,
            language="c"
        )

    def execute(self, source: str, ir_data: Dict[str, Any]) -> Dict[str, Any]:
        return SafeExecutor.execute("c", source, ir_data)
