"""
Diff Service — Stage-by-Stage Compiler Pipeline Difference Engine.

Enables 'Diff Mode' (planned feature for Review 2):
Compares two versions of a program side-by-side across all 5 compiler stages:
  1. Source Code Diff
  2. Token Stream Diff
  3. AST Structural Diff
  4. Three-Address Code (IR) Diff
  5. Target Assembly Diff
"""

import difflib
import json
from languages import get_compiler


def _line_diff(text_a, text_b):
    """Computes line-by-line diff between two multi-line texts."""
    lines_a = (text_a or "").splitlines()
    lines_b = (text_b or "").splitlines()
    matcher = difflib.SequenceMatcher(None, lines_a, lines_b)

    diff_entries = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in lines_a[i1:i2]:
                diff_entries.append({"type": "same", "text_a": line, "text_b": line})
        elif tag == "replace":
            chunk_a = lines_a[i1:i2]
            chunk_b = lines_b[j1:j2]
            max_len = max(len(chunk_a), len(chunk_b))
            for k in range(max_len):
                la = chunk_a[k] if k < len(chunk_a) else ""
                lb = chunk_b[k] if k < len(chunk_b) else ""
                diff_entries.append({"type": "modified", "text_a": la, "text_b": lb})
        elif tag == "delete":
            for line in lines_a[i1:i2]:
                diff_entries.append({"type": "removed", "text_a": line, "text_b": ""})
        elif tag == "insert":
            for line in lines_b[j1:j2]:
                diff_entries.append({"type": "added", "text_a": "", "text_b": line})

    return diff_entries


def compile_pipeline(source, language="c"):
    """Runs a full compilation pipeline pass on a source string."""
    compiler = get_compiler(language)
    res = compiler.compile(source)
    if not res.get("success", False):
        diags = res.get("diagnostics") or []
        first_diag = diags[0] if diags else {}
        msg = first_diag.get("message") or res.get("error") or "Compilation failed"
        line = first_diag.get("line") or 1
        raise Exception(f"Line {line}: {msg}")
    return res


def compare_programs(source_a, source_b, language="c"):
    """
    Compares two programs and computes stage-by-stage diffs.
    """
    res_a = compile_pipeline(source_a, language=language)
    res_b = compile_pipeline(source_b, language=language)

    # 1. Source diff
    source_diff = _line_diff(source_a, source_b)

    # 2. Token diff
    tokens_str_a = "\n".join(f"{t['type']}: {t['value']}" for t in res_a["tokens"] if t["type"] != "EOF")
    tokens_str_b = "\n".join(f"{t['type']}: {t['value']}" for t in res_b["tokens"] if t["type"] != "EOF")
    token_diff = _line_diff(tokens_str_a, tokens_str_b)

    # 3. AST JSON diff
    ast_str_a = json.dumps(res_a["ast"], indent=2)
    ast_str_b = json.dumps(res_b["ast"], indent=2)
    ast_diff = _line_diff(ast_str_a, ast_str_b)

    # 4. IR TAC diff
    ir_diff = _line_diff(res_a["ir"]["tac_text"], res_b["ir"]["tac_text"])

    # 5. Assembly diff (educational & x86_64)
    edu_asm_diff = _line_diff(res_a["assembly"]["educational"], res_b["assembly"]["educational"])
    x86_asm_diff = _line_diff(res_a["assembly"]["x86_64"], res_b["assembly"]["x86_64"])

    return {
        "program_a": res_a,
        "program_b": res_b,
        "diffs": {
            "source": source_diff,
            "tokens": token_diff,
            "ast": ast_diff,
            "ir": ir_diff,
            "assembly_edu": edu_asm_diff,
            "assembly_x86": x86_asm_diff,
        }
    }


if __name__ == "__main__":
    src_v1 = "int total = 3 + 4;"
    src_v2 = "int total = 3 + 4 * 2;"

    diff_res = compare_programs(src_v1, src_v2, language="c")
    print("=== IR Diff ===")
    for row in diff_res["diffs"]["ir"]:
        print(f"[{row['type'].upper():<8}] A: {row['text_a']:<25} | B: {row['text_b']}")
