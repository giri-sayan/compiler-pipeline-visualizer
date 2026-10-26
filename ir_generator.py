"""
Intermediate Representation (IR) Generator — Step 4 of the compiler pipeline.

Transforms the high-level Abstract Syntax Tree (AST) into linear Three-Address
Code (TAC) and Quadruples: (Operator, Arg1, Arg2, Result).

Three-Address Code bridges front-end syntax analysis to back-end code generation
by flattening nested expressions, allocating compiler temporaries (t0, t1, ...),
and simplifying control flow into explicit jumps and labels.
"""


class TACInstruction:
    def __init__(self, op, arg1=None, arg2=None, result=None, comment=""):
        self.op = op
        self.arg1 = str(arg1) if arg1 is not None else ""
        self.arg2 = str(arg2) if arg2 is not None else ""
        self.result = str(result) if result is not None else ""
        self.comment = comment

    def to_tac(self):
        """Format as human-readable 3-address code line."""
        if self.op == "INCLUDE":
            return f"INCLUDE {self.arg1}"
        elif self.op == "FUNC_START":
            return f"\n{self.arg1}:"
        elif self.op == "FUNC_END":
            return f"END {self.arg1}\n"
        elif self.op in ("+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">="):
            return f"{self.result} = {self.arg1} {self.op} {self.arg2}"
        elif self.op == "UNARY_MINUS":
            return f"{self.result} = -{self.arg1}"
        elif self.op == "UNARY_PLUS":
            return f"{self.result} = +{self.arg1}"
        elif self.op == "=":
            return f"{self.result} = {self.arg1}"
        elif self.op == "PARAM":
            return f"PARAM {self.arg1}"
        elif self.op == "CALL":
            if self.result:
                return f"{self.result} = CALL {self.arg1}, {self.arg2}"
            return f"CALL {self.arg1}, {self.arg2}"
        elif self.op == "RETURN":
            if self.arg1:
                return f"RETURN {self.arg1}"
            return "RETURN"
        elif self.op == "IF_FALSE":
            return f"IF_FALSE {self.arg1} GOTO {self.result}"
        elif self.op == "GOTO":
            return f"GOTO {self.result}"
        elif self.op == "LABEL":
            return f"{self.result}:"
        else:
            return f"{self.op} {self.arg1} {self.arg2} {self.result}".strip()

    def to_dict(self, index=1):
        return {
            "index": index,
            "tac": self.to_tac().strip(),
            "op": self.op,
            "arg1": self.arg1,
            "arg2": self.arg2,
            "result": self.result,
            "comment": self.comment,
            "quadruple": [self.op, self.arg1 or "-", self.arg2 or "-", self.result or "-"],
        }


class IRGenerator:
    def __init__(self):
        self.instructions = []
        self.temp_count = 0
        self.label_count = 0

    def new_temp(self):
        """Allocate a new compiler temporary register (t0, t1, t2...)."""
        temp = f"t{self.temp_count}"
        self.temp_count += 1
        return temp

    def new_label(self):
        """Allocate a new jump target label (L0, L1, L2...)."""
        label = f"L{self.label_count}"
        self.label_count += 1
        return label

    def emit(self, op, arg1=None, arg2=None, result=None, comment=""):
        instr = TACInstruction(op, arg1, arg2, result, comment)
        self.instructions.append(instr)
        return instr

    def gen_expr(self, node):
        """
        Recursively translates expression node into TAC.
        Returns the variable/constant/temp string representing the result.
        """
        if not node or not isinstance(node, dict):
            return ""

        ntype = node.get("type")

        if ntype == "Number":
            return str(node.get("value"))

        if ntype == "Constant":
            return str(node.get("value"))

        if ntype == "String":
            return repr(node.get("value"))

        if ntype == "Identifier":
            return str(node.get("name"))

        if ntype == "Attribute":
            val = self.gen_expr(node.get("value"))
            return f"{val}.{node.get('attr')}"

        if ntype == "Subscript":
            val = self.gen_expr(node.get("value"))
            sl = self.gen_expr(node.get("slice"))
            return f"{val}[{sl}]"

        if ntype in ("List", "Tuple"):
            items = [self.gen_expr(e) for e in node.get("elements", [])]
            return f"[{', '.join(items)}]"

        if ntype == "Dict":
            return "{...}"

        if ntype == "UnaryOp":
            op = node.get("op")
            operand_val = self.gen_expr(node.get("operand"))
            temp = self.new_temp()
            tac_op = "UNARY_MINUS" if op == "-" else "UNARY_PLUS"
            self.emit(tac_op, operand_val, None, temp, f"Unary {op} on {operand_val}")
            return temp

        if ntype in ("BinOp", "Compare"):
            op = node.get("op", "+")
            left_val = self.gen_expr(node.get("left"))
            right_val = self.gen_expr(node.get("right"))
            temp = self.new_temp()
            comment = f"Compute {left_val} {op} {right_val} -> temporary {temp}"
            self.emit(op, left_val, right_val, temp, comment)
            return temp

        if ntype == "BoolOp":
            op = node.get("op", "and")
            vals = [self.gen_expr(v) for v in node.get("values", [])]
            temp = self.new_temp()
            self.emit(op.upper(), vals[0] if vals else "0", vals[1] if len(vals) > 1 else None, temp, f"BoolOp {op}")
            return temp

        if ntype == "IfExp":
            cond_val = self.gen_expr(node.get("test"))
            true_val = self.gen_expr(node.get("body"))
            temp = self.new_temp()
            self.emit("=", true_val, None, temp, f"Ternary conditional result on {cond_val}")
            return temp

        if ntype == "FunctionCall":
            fname = node.get("name")
            args = node.get("args", [])
            arg_vals = [self.gen_expr(a) for a in args]
            for i, av in enumerate(arg_vals):
                self.emit("PARAM", av, None, None, f"Pass parameter #{i+1} to {fname}")
            temp = self.new_temp()
            self.emit("CALL", fname, len(arg_vals), temp, f"Invoke {fname}() and capture result")
            return temp

        return ""

    def gen_statement(self, stmt):
        """Translate a single AST statement into TAC."""
        if not stmt or not isinstance(stmt, dict):
            return

        stype = stmt.get("type")

        if stype == "Include":
            header = stmt.get("header")
            self.emit("INCLUDE", header, None, None, f"External library header {header}")

        elif stype == "VarDecl":
            name = stmt.get("name")
            dtype = stmt.get("datatype", "int")
            val_node = stmt.get("value")
            if val_node:
                expr_val = self.gen_expr(val_node)
                self.emit("=", expr_val, None, name, f"Initialize declared variable {name} ({dtype})")
            else:
                self.emit("DECL", dtype, None, name, f"Declare uninitialized variable {name} ({dtype})")

        elif stype == "Assign":
            name = stmt.get("name")
            val_node = stmt.get("value")
            expr_val = self.gen_expr(val_node)
            self.emit("=", expr_val, None, name, f"Assign expression result to {name}")

        elif stype == "FunctionDef":
            fname = stmt.get("name")
            ret_type = stmt.get("return_type", "void")
            params = stmt.get("params", [])
            param_names = [p.get("name") if isinstance(p, dict) else str(p) for p in params]
            param_desc = ",".join(param_names) if param_names else ret_type
            self.emit("FUNC_START", fname, param_desc, None, f"Begin function definition {ret_type} {fname}()")

            for p in params:
                pname = p.get("name") if isinstance(p, dict) else str(p)
                self.emit("FORMAL_PARAM", pname, None, None, f"Formal parameter {pname}")

            for s in stmt.get("body", []):
                self.gen_statement(s)

            self.emit("FUNC_END", fname, None, None, f"End of function {fname}")

        elif stype == "Return":
            val_node = stmt.get("value")
            if val_node:
                expr_val = self.gen_expr(val_node)
                self.emit("RETURN", expr_val, None, None, f"Return value {expr_val} to caller")
            else:
                self.emit("RETURN", None, None, None, "Return void to caller")

        elif stype == "FunctionCall":
            fname = stmt.get("name")
            args = stmt.get("args", [])
            arg_vals = [self.gen_expr(a) for a in args]
            for i, av in enumerate(arg_vals):
                self.emit("PARAM", av, None, None, f"Push argument #{i+1} for {fname}")
            self.emit("CALL", fname, len(arg_vals), None, f"Call procedure {fname}")

        elif stype == "If":
            cond_val = self.gen_expr(stmt.get("condition"))
            else_label = self.new_label()
            end_label = self.new_label() if stmt.get("else_branch") else else_label

            self.emit("IF_FALSE", cond_val, None, else_label, f"Jump to {else_label} if condition false")

            for s in stmt.get("then_branch", []):
                self.gen_statement(s)

            if stmt.get("else_branch"):
                self.emit("GOTO", None, None, end_label, f"Skip else branch -> jump to {end_label}")
                self.emit("LABEL", None, None, else_label, f"Else branch entry {else_label}")
                for s in stmt.get("else_branch", []):
                    self.gen_statement(s)
                self.emit("LABEL", None, None, end_label, f"Merge point {end_label}")
            else:
                self.emit("LABEL", None, None, else_label, f"Merge point {else_label}")

        elif stype == "StreamOutput":
            items = stmt.get("items", [])
            for item in items:
                v = self.gen_expr(item)
                self.emit("PARAM", v, None, None, "Stream output operand")
                self.emit("CALL", "cout_print", 1, None, "Stream insertion (cout <<)")

        elif stype == "StreamInput":
            for var in stmt.get("variables", []):
                self.emit("CALL", "cin_read", 0, var, f"Stream extraction (cin >> {var})")

        elif stype == "ClassDef":
            cname = stmt.get("name")
            self.emit("LABEL", None, None, f"class_{cname}", f"Class structure definition: {cname}")
            for m in (stmt.get("members") or stmt.get("body") or []):
                self.gen_statement(m)

        elif stype == "While":
            start_label = self.new_label()
            end_label = self.new_label()
            self.emit("LABEL", None, None, start_label, "While loop condition start")
            cond_val = self.gen_expr(stmt.get("condition"))
            self.emit("IF_FALSE", cond_val, None, end_label, f"Exit while loop if {cond_val} is false")
            for s in (stmt.get("body") or stmt.get("then_branch") or []):
                self.gen_statement(s)
            self.emit("GOTO", None, None, start_label, "Loop back to start")
            self.emit("LABEL", None, None, end_label, "While loop exit")

        elif stype == "For":
            iter_val = self.gen_expr(stmt.get("iter"))
            target_node = stmt.get("target")
            target_name = target_node.get("name", "i") if isinstance(target_node, dict) else "i"
            start_label = self.new_label()
            end_label = self.new_label()
            self.emit("LABEL", None, None, start_label, f"For loop on {iter_val}")
            self.emit("ITER_NEXT", iter_val, None, target_name, f"Fetch next element into {target_name}")
            self.emit("IF_FALSE", target_name, None, end_label, "Exit for loop when iterator exhausted")
            for s in (stmt.get("body") or []):
                self.gen_statement(s)
            self.emit("GOTO", None, None, start_label, "For loop next iteration")
            self.emit("LABEL", None, None, end_label, "For loop exit")

        elif stype == "AugAssign":
            name = stmt.get("name")
            op = stmt.get("op", "+")
            val_node = stmt.get("value")
            expr_val = self.gen_expr(val_node)
            temp = self.new_temp()
            self.emit(op, name, expr_val, temp, f"Augmented {op} on {name}")
            self.emit("=", temp, None, name, f"Assign result back to {name}")

        elif stype in ("Pass", "Break", "Continue", "Import", "ImportFrom"):
            self.emit(stype.upper(), None, None, None, f"Python statement: {stype}")

        elif stype == "NamespaceUse":
            ns = stmt.get("namespace", "std")
            # Namespace import recorded in IR
            pass

        elif stype in ("BinOp", "Identifier", "Number", "String"):
            self.gen_expr(stmt)

    def generate(self, ast):
        """
        Generates TAC and quadruples from AST.
        Returns a dict with structured instructions, quadruples, and raw TAC text.
        """
        self.instructions = []
        self.temp_count = 0
        self.label_count = 0

        if hasattr(ast, "to_dict"):
            ast_dict = ast.to_dict()
        else:
            ast_dict = ast

        statements = []
        if isinstance(ast_dict, dict):
            if ast_dict.get("type") == "Program":
                statements = ast_dict.get("statements", [])
            else:
                statements = [ast_dict]
        elif isinstance(ast_dict, list):
            statements = ast_dict

        for s in statements:
            self.gen_statement(s)

        quadruples = [instr.to_dict(idx + 1) for idx, instr in enumerate(self.instructions)]
        tac_lines = [q["tac"] for q in quadruples if q["tac"]]
        tac_text = "\n".join(tac_lines)

        temporaries = [f"t{i}" for i in range(self.temp_count)]

        return {
            "quadruples": quadruples,
            "tac_text": tac_text,
            "temporaries": temporaries,
            "total_instructions": len(self.instructions),
        }


def generate_ir(ast):
    """Convenience helper function to generate IR."""
    gen = IRGenerator()
    return gen.generate(ast)


if __name__ == "__main__":
    from lexer import Lexer
    from parser import Parser

    c_sample = '''#include <stdio.h>
int main() {
    int total = 3 + 4 * 2;
    printf("Result = %d\\n", total);
    return 0;
}'''

    tokens = Lexer(c_sample).tokenize()
    ast = Parser(tokens).parse_program()
    ir_res = generate_ir(ast)

    print("=== Generated Three-Address Code (TAC) ===")
    print(ir_res["tac_text"])
    print("\n=== Quadruples Table ===")
    for q in ir_res["quadruples"]:
        print(f"[{q['index']:02d}] {q['op']:<10} {q['arg1']:<16} {q['arg2']:<10} -> {q['result']:<8} # {q['comment']}")
