"""
Toy Mini-Language Compiler Frontend.
"""

from typing import Dict, Any, List, Tuple
from languages.base import BaseCompiler
from lexer import Lexer
from parser import Parser
import semantic
from ir_generator import generate_ir
from codegen import generate_code
from explainer import generate_explanation
from executor import SafeExecutor


class ToyCompiler(BaseCompiler):
    language_id = "toy"
    display_name = "Toy Mini-Lang (x = 5, y = x + 2)"
    file_extension = ".toy"

    def tokenize(self, source: str) -> List[Any]:
        lexer = Lexer(source, language="toy")
        return lexer.tokenize()

    def parse(self, tokens: List[Any], source: str = "") -> Any:
        parser = Parser(tokens, language="toy")
        return parser.parse_program()

    def analyze_semantics(self, ast: Any, source: str = "") -> Tuple[List[Any], List[str], List[Dict[str, Any]]]:
        return semantic.analyze(ast, language="toy")

    def generate_ir(self, ast: Any) -> Dict[str, Any]:
        return generate_ir(ast)

    def generate_assembly(self, ir_data: Dict[str, Any]) -> Dict[str, str]:
        return generate_code(ir_data)

    def generate_explanation(self, tokens: List[Any], ast: Any, semantic_info: Dict[str, Any],
                             ir_data: Dict[str, Any], assembly_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        token_dicts = [t.to_dict() if hasattr(t, "to_dict") else t for t in (tokens[:150] if tokens else [])]
        return generate_explanation(
            tokens=token_dicts,
            ast=ast,
            semantic_info=semantic_info,
            ir_data=ir_data,
            assembly_data=assembly_data,
            language="toy"
        )

    def execute(self, source: str, ir_data: Dict[str, Any]) -> Dict[str, Any]:
        return SafeExecutor.execute("toy", source, ir_data)
