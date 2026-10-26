"""
Base Compiler Interface and Pipeline Dispatcher for Language Frontends.
"""

from typing import Dict, Any, List, Tuple, Optional
from collections import defaultdict
import re


def make_diagnostic(stage: str, err: Any, default_line: Optional[int] = None, default_col: Optional[int] = None, severity: str = "error") -> Dict[str, Any]:
    line = None
    col = None
    msg = None
    err_stage = stage
    err_severity = severity

    if isinstance(err, dict):
        line = err.get("line") or err.get("line_number") or err.get("lineno")
        col = err.get("col") or err.get("column") or err.get("offset")
        msg = err.get("message") or err.get("error") or str(err)
        err_stage = err.get("stage", stage)
        err_severity = err.get("severity", severity)
    elif hasattr(err, "to_dict") and callable(err.to_dict):
        try:
            d = err.to_dict()
            if isinstance(d, dict):
                line = d.get("line") or d.get("line_number") or d.get("lineno")
                col = d.get("col") or d.get("column") or d.get("offset")
                msg = d.get("message") or d.get("error")
                err_stage = d.get("stage", stage)
                err_severity = d.get("severity", severity)
        except Exception:
            pass

    if line is None:
        line = (
            getattr(err, "line", None)
            or getattr(err, "line_number", None)
            or getattr(err, "lineno", None)
            or default_line
        )
    if col is None:
        col = (
            getattr(err, "col", None)
            or getattr(err, "column", None)
            or getattr(err, "offset", None)
            or default_col
        )
    if msg is None:
        msg = getattr(err, "message", None) or getattr(err, "msg", None) or str(err)
    if hasattr(err, "stage"):
        err_stage = getattr(err, "stage", stage)
    if hasattr(err, "severity"):
        err_severity = getattr(err, "severity", severity)

    # Check for line/col embedded in message if still None
    if line is None:
        m_line = re.search(r'\b(?:line|L)\s*[:#]?\s*(\d+)', str(msg), re.IGNORECASE)
        if m_line:
            try:
                line = int(m_line.group(1))
            except ValueError:
                pass

    if col is None:
        m_col = re.search(r'\b(?:col(?:umn)?|offset|pos(?:ition)?)\s*[:#]?\s*(\d+)', str(msg), re.IGNORECASE)
        if m_col:
            try:
                col = int(m_col.group(1))
            except ValueError:
                pass

    return {
        "stage": err_stage,
        "message": msg,
        "line": line if line is not None else 1,
        "col": col if col is not None else 1,
        "column": col if col is not None else 1,
        "severity": err_severity
    }


class BaseCompiler:
    language_id: str = "base"
    display_name: str = "Base Language"
    file_extension: str = ".txt"

    def tokenize(self, source: str) -> List[Any]:
        """Convert source code into a list of Token objects or dicts."""
        raise NotImplementedError

    def parse(self, tokens: List[Any], source: str = "") -> Any:
        """Parse token stream into a normalized Abstract Syntax Tree (AST)."""
        raise NotImplementedError

    def analyze_semantics(self, ast: Any, source: str = "") -> Tuple[List[Any], List[str], List[Dict[str, Any]]]:
        """
        Validate semantic rules, construct Symbol Table.
        Returns: (errors, declared_vars, symbol_table)
        """
        raise NotImplementedError

    def generate_ir(self, ast: Any) -> Dict[str, Any]:
        """Convert AST into linear Three-Address Code (TAC) and quadruples."""
        raise NotImplementedError

    def generate_assembly(self, ir_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate x86-64 and Educational RISC assembly from IR."""
        raise NotImplementedError

    def generate_explanation(self, tokens: List[Any], ast: Any, semantic_info: Dict[str, Any],
                             ir_data: Dict[str, Any], assembly_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate pedagogical step-by-step walkthrough."""
        raise NotImplementedError

    def execute(self, source: str, ir_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute or simulate execution of the program safely."""
        raise NotImplementedError

    def compile(self, source: str) -> Dict[str, Any]:
        """
        Executes the full compilation pipeline with strict stage validation,
        high-speed linear token grouping, precise diagnostics, and execution dispatch.
        """
        if not source.strip():
            return {
                "success": False,
                "pipeline_success": False,
                "syntax_valid": False,
                "semantic_valid": False,
                "has_semantic_errors": False,
                "error": "Source code cannot be empty",
                "diagnostics": [{
                    "stage": "Source",
                    "message": "Source code cannot be empty",
                    "line": 1,
                    "col": 1,
                    "column": 1,
                    "severity": "error"
                }],
                "stages": {
                    "source": "failed",
                    "tokens": "blocked",
                    "ast": "blocked",
                    "semantic": "blocked",
                    "ir": "blocked",
                    "asm": "blocked",
                    "explain": "blocked",
                },
                "status_code": 400
            }

        raw_lines = source.split("\n")
        if len(raw_lines) > 10000:
            return {
                "success": False,
                "pipeline_success": False,
                "syntax_valid": False,
                "semantic_valid": False,
                "has_semantic_errors": False,
                "error": f"Source document exceeds maximum limit of 10,000 lines (current: {len(raw_lines)} lines)",
                "diagnostics": [{
                    "stage": "Source",
                    "message": f"Source document exceeds maximum limit of 10,000 lines (current: {len(raw_lines)} lines)",
                    "line": 10001,
                    "col": 1,
                    "column": 1,
                    "severity": "error"
                }],
                "stages": {
                    "source": "failed",
                    "tokens": "blocked",
                    "ast": "blocked",
                    "semantic": "blocked",
                    "ir": "blocked",
                    "asm": "blocked",
                    "explain": "blocked",
                },
                "status_code": 400
            }

        # 1. Lexical Analysis
        try:
            tokens = self.tokenize(source)
            tokens_list = [t.to_dict() if hasattr(t, "to_dict") else t for t in tokens]
        except Exception as e:
            diag = make_diagnostic("Lexer", e)
            partial_tokens = [t.to_dict() if hasattr(t, "to_dict") else t for t in getattr(self, "tokens_so_far", [])]
            return {
                "success": False,
                "pipeline_success": True,
                "syntax_valid": False,
                "semantic_valid": False,
                "has_semantic_errors": False,
                "stage": "Lexer",
                "error": str(e),
                "diagnostics": [diag],
                "stages": {
                    "source": "passed",
                    "tokens": "failed",
                    "ast": "blocked",
                    "semantic": "blocked",
                    "ir": "blocked",
                    "asm": "blocked",
                    "explain": "blocked",
                },
                "tokens": partial_tokens,
                "lines": [{"line": diag.get("line") or 1, "source": source, "error": str(e)}],
                "status_code": 200
            }

        # Fast O(N) grouping of tokens by line for UI line breakdown
        tokens_by_line = defaultdict(list)
        for t in tokens_list:
            if t.get("type") != "EOF":
                tokens_by_line[t.get("line", 1)].append(t)

        line_results = []
        for i, line in enumerate(raw_lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            line_results.append({
                "line": i,
                "source": stripped,
                "tokens": tokens_by_line.get(i, [])
            })

        # 2. Syntax Analysis (AST)
        try:
            ast = self.parse(tokens, source=source)
            ast_dict = ast.to_dict() if hasattr(ast, "to_dict") else ast
        except Exception as e:
            diag = make_diagnostic("Parser", e)
            return {
                "success": False,
                "pipeline_success": True,
                "syntax_valid": False,
                "semantic_valid": False,
                "has_semantic_errors": False,
                "stage": "Parser",
                "error": str(e),
                "diagnostics": [diag],
                "stages": {
                    "source": "passed",
                    "tokens": "passed",
                    "ast": "failed",
                    "semantic": "blocked",
                    "ir": "blocked",
                    "asm": "blocked",
                    "explain": "blocked",
                },
                "tokens": tokens_list,
                "lines": [{"line": diag.get("line") or 1, "source": source, "error": str(e)}],
                "status_code": 200
            }

        # 3. Semantic Analysis & Symbol Table
        try:
            semantic_errors, declared_vars, symbol_table = self.analyze_semantics(ast, source=source)
        except Exception as e:
            diag = make_diagnostic("Semantic Analyzer", e)
            return {
                "success": False,
                "pipeline_success": True,
                "syntax_valid": True,
                "semantic_valid": False,
                "has_semantic_errors": True,
                "stage": "Semantic Analyzer",
                "error": f"Semantic analysis error: {e}",
                "diagnostics": [diag],
                "stages": {
                    "source": "passed",
                    "tokens": "passed",
                    "ast": "passed",
                    "semantic": "failed",
                    "ir": "blocked",
                    "asm": "blocked",
                    "explain": "blocked",
                },
                "tokens": tokens_list,
                "ast": ast_dict,
                "lines": line_results,
                "status_code": 200
            }

        semantic_diagnostics = [e.to_dict() if hasattr(e, "to_dict") else e for e in semantic_errors]
        has_semantic_errors = any(
            (e.severity if hasattr(e, "severity") else e.get("severity", "error")) == "error"
            for e in semantic_errors
        )
        semantic_valid = len(semantic_errors) == 0

        if has_semantic_errors:
            first_err = next(
                (e for e in semantic_diagnostics if e.get("severity") == "error"),
                semantic_diagnostics[0] if semantic_diagnostics else {"message": "Semantic analysis failed"}
            )
            return {
                "success": False,
                "pipeline_success": True,
                "syntax_valid": True,
                "semantic_valid": False,
                "has_semantic_errors": True,
                "stage": "Semantic Analyzer",
                "error": first_err.get("message", "Semantic analysis failed"),
                "diagnostics": semantic_diagnostics,
                "stages": {
                    "source": "passed",
                    "tokens": "passed",
                    "ast": "passed",
                    "semantic": "failed",
                    "ir": "blocked",
                    "asm": "blocked",
                    "explain": "blocked",
                },
                "language": self.language_id,
                "lines": line_results,
                "tokens": tokens_list,
                "ast": ast_dict,
                "semantic_errors": semantic_diagnostics,
                "declared_vars": declared_vars,
                "symbol_table": symbol_table,
                "status_code": 200
            }

        # 4. Intermediate Representation (Three-Address Code & Quadruples)
        try:
            ir_data = self.generate_ir(ast)
        except Exception as e:
            diag = make_diagnostic("IR Generator", e)
            return {
                "success": False,
                "pipeline_success": False,
                "stage": "IR Generator",
                "error": f"IR generation error: {e}",
                "diagnostics": [diag],
                "stages": {
                    "source": "passed",
                    "tokens": "passed",
                    "ast": "passed",
                    "semantic": "passed",
                    "ir": "failed",
                    "asm": "blocked",
                    "explain": "blocked",
                },
                "tokens": tokens_list,
                "ast": ast_dict,
                "lines": line_results,
                "status_code": 200
            }

        # 5. Target Code Generation
        try:
            assembly_data = self.generate_assembly(ir_data)
        except Exception as e:
            diag = make_diagnostic("Code Generator", e)
            return {
                "success": False,
                "pipeline_success": False,
                "stage": "Code Generator",
                "error": f"Code generation error: {e}",
                "diagnostics": [diag],
                "stages": {
                    "source": "passed",
                    "tokens": "passed",
                    "ast": "passed",
                    "semantic": "passed",
                    "ir": "passed",
                    "asm": "failed",
                    "explain": "blocked",
                },
                "tokens": tokens_list,
                "ast": ast_dict,
                "ir": ir_data,
                "lines": line_results,
                "status_code": 200
            }

        # 6. Guided Educational Explanation
        try:
            semantic_info = {
                "errors": semantic_diagnostics,
                "declared_vars": declared_vars,
                "symbol_table": symbol_table,
            }
            explanation = self.generate_explanation(tokens, ast, semantic_info, ir_data, assembly_data)
        except Exception:
            explanation = []

        # 7. Safe Program Execution
        try:
            exec_result = self.execute(source, ir_data)
        except Exception as e:
            exec_result = {
                "executed": False,
                "output": f"Execution error: {e}",
                "exit_code": -1,
                "engine": "none",
                "time_ms": 0.0,
                "error": str(e)
            }

        semantic_stage_status = "warning" if len(semantic_errors) > 0 else "passed"
        stages_status = {
            "source": "passed",
            "tokens": "passed",
            "ast": "passed",
            "semantic": semantic_stage_status,
            "ir": "passed",
            "asm": "passed",
            "explain": "passed",
        }

        return {
            "success": True,
            "pipeline_success": True,
            "syntax_valid": True,
            "semantic_valid": len(semantic_errors) == 0,
            "has_semantic_errors": False,
            "diagnostics": semantic_diagnostics,
            "stages": stages_status,
            "language": self.language_id,
            "lines": line_results,
            "tokens": tokens_list,
            "ast": ast_dict,
            "semantic_errors": semantic_diagnostics,
            "declared_vars": declared_vars,
            "symbol_table": symbol_table,
            "ir": ir_data,
            "assembly": assembly_data,
            "explanation": explanation,
            "execution": exec_result,
            "status_code": 200
        }
