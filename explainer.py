"""
Explainer — Step 6 of the compiler pipeline.

Generates comprehensive, pedagogical explanations of the transformations occurring
at every stage of the compilation pipeline. Bridges theory to practice so students
and instructors can inspect exactly why each decision was made.
"""


def generate_explanation(tokens, ast, semantic_info, ir_data, assembly_data, language="c"):
    """
    Constructs stage-by-stage educational explanations for the visualizer.
    """
    explanations = []

    # 1. Lexical Analysis explanation
    num_tokens = len(tokens) if tokens else 0
    token_types = {}
    has_preprocessor = False
    for t in (tokens or []):
        ttype = t.get("type") if isinstance(t, dict) else getattr(t, "type", "UNKNOWN")
        token_types[ttype] = token_types.get(ttype, 0) + 1
        if ttype == "PREPROCESSOR":
            has_preprocessor = True

    lexer_summary = [
        f"The Lexer scanned the input text and extracted {num_tokens} tokens.",
        f"Tokens found: {', '.join(f'{count}x {t}' for t, count in token_types.items() if t != 'EOF')}.",
    ]
    if has_preprocessor:
        lexer_summary.append("Preprocessor directive(s) such as '#include' were detected and tokenized without lexer error.")
    lexer_summary.append("Insignificant whitespace and comments were safely stripped during this phase.")

    explanations.append({
        "stage": 1,
        "name": "Lexical Analysis (Scanner)",
        "badge": "Source -> Tokens",
        "description": "Transforms unstructured character streams into categorized lexical units.",
        "points": lexer_summary,
        "takeaway": "The lexer verifies that the character alphabet is valid, but has no knowledge of grammar, operator precedence, or variable declarations."
    })

    # 2. Syntax Analysis explanation
    ast_dict = ast.to_dict() if hasattr(ast, "to_dict") else (ast or {})
    statements = ast_dict.get("statements", []) if ast_dict.get("type") == "Program" else [ast_dict]
    num_stmts = len(statements)

    parser_summary = [
        f"The recursive-descent Parser verified grammar rules and constructed an Abstract Syntax Tree (AST) containing {num_stmts} top-level node(s).",
        "Operator precedence was enforced hierarchically: multiplicative operations (*, /, %) evaluate before additive operations (+, -).",
        "Higher-precedence operations appear deeper in the tree, guaranteeing mathematically correct evaluation order without needing explicit parentheses at runtime."
    ]

    explanations.append({
        "stage": 2,
        "name": "Syntax Analysis (Parser)",
        "badge": "Tokens -> AST",
        "description": "Constructs a hierarchical syntax tree enforcing language grammar and operator precedence.",
        "points": parser_summary,
        "takeaway": "The parser validates grammatical structure, but does not verify whether variables were declared before use or whether types match."
    })

    # 3. Semantic Analysis explanation
    errors = semantic_info.get("errors", [])
    symbol_table = semantic_info.get("symbol_table", [])
    declared_vars = semantic_info.get("declared_vars", [])

    semantic_summary = [
        f"The Semantic Analyzer inspected the AST and populated a Symbol Table with {len(symbol_table)} entry/entries.",
        f"Tracked variables: {', '.join(declared_vars) if declared_vars else 'none'}.",
    ]
    if not errors:
        semantic_summary.append("[PASS] Validation passed: All referenced variables were properly declared and initialized before use.")
    else:
        semantic_summary.append(f"⚠ Detected {len(errors)} semantic issue(s): {errors[0].get('message', '')}")

    explanations.append({
        "stage": 3,
        "name": "Semantic Analysis (Type & Scope Checker)",
        "badge": "AST -> Symbol Table & Diagnostics",
        "description": "Enforces context-sensitive rules that cannot be captured by context-free grammar.",
        "points": semantic_summary,
        "takeaway": "Semantic analysis connects names to declarations, prevents uninitialized variable access, and ensures type soundness before code generation."
    })

    # 4. Intermediate Code Generation explanation
    quads = ir_data.get("quadruples", [])
    temps = ir_data.get("temporaries", [])

    ir_summary = [
        f"The IR Generator linearized the nested AST tree into {len(quads)} Three-Address Code (TAC) instructions.",
        f"Allocated {len(temps)} compiler temporary register(s) ({', '.join(temps) if temps else 'none'}) to hold intermediate sub-expression results.",
        "Each TAC statement contains at most three addresses (two operands and one destination), flattening tree recursion into sequential steps.",
        "Quadruples explicitly store (Operator, Arg1, Arg2, Result), enabling machine-independent compiler optimizations (such as dead-code elimination and constant folding)."
    ]

    explanations.append({
        "stage": 4,
        "name": "Intermediate Code Generation (IR / 3-Address Code)",
        "badge": "AST -> Three-Address Code (TAC)",
        "description": "Bridges frontend language syntax to backend hardware instructions via a uniform, machine-independent representation.",
        "points": ir_summary,
        "takeaway": "By targeting an Intermediate Representation first, compilers avoid having to write a separate code generator for every source language and CPU architecture."
    })

    # 5. Target Code Generation explanation
    asm_summary = [
        "The Code Generator lowered the Three-Address Code into concrete hardware assembly instructions.",
        "Created function prologue and epilogue, managing the base pointer (%rbp) and stack pointer (%rsp).",
        "Mapped compiler temporaries and local variables to stack memory displacements (-4(%rbp), -8(%rbp), -12(%rbp)).",
        "Prepared system registers according to calling conventions (%rdi, %rsi for function arguments, %eax for return value)."
    ]

    explanations.append({
        "stage": 5,
        "name": "Target Code Generation (Assembly Code)",
        "badge": "IR -> Machine Assembly",
        "description": "Translates machine-independent IR into target architecture assembly code (x86-64 / RISC).",
        "points": asm_summary,
        "takeaway": "The final stage handles hardware realities: fixed register sets, stack layout conventions, and machine instruction formats."
    })

    return explanations


if __name__ == "__main__":
    from lexer import Lexer
    from parser import Parser
    from semantic import analyze
    from ir_generator import generate_ir
    from codegen import generate_code

    src = '''#include <stdio.h>
int main() {
    int total = 3 + 4 * 2;
    printf("Result = %d\\n", total);
    return 0;
}'''

    tokens = Lexer(src).tokenize()
    token_dicts = [t.to_dict() for t in tokens]
    ast = Parser(tokens).parse_program()
    errs, declared, syms = analyze(ast)
    ir = generate_ir(ast)
    target = generate_code(ir)

    exp = generate_explanation(token_dicts, ast, {"errors": errs, "declared_vars": declared, "symbol_table": syms}, ir, target)
    for e in exp:
        print(f"\n[{e['stage']}] {e['name']} ({e['badge']}):")
        for p in e["points"]:
            print("  *", p)
