"""
Target Code Generator — Step 5 of the compiler pipeline.

Translates Three-Address Code (TAC) into:
  1. Standard x86-64 Assembly (AT&T / Gas format) with stack-frame management
     and Linux/System V calling conventions.
  2. Educational Virtual Assembly (LOAD, STORE, ADD, MUL, RET) for beginner
     pedagogical clarity.

Includes explanatory comments on every instruction showing register allocation,
stack displacement, and calling conventions.
"""


class CodeGenerator:
    def __init__(self, ir_data):
        self.ir = ir_data or {}
        self.quadruples = self.ir.get("quadruples", [])
        self.string_literals = {}
        self.string_counter = 0

    def _collect_strings(self):
        """Scans quadruples to extract string constants for .rodata section."""
        for q in self.quadruples:
            for arg in (q.get("arg1"), q.get("arg2")):
                if arg and (arg.startswith('"') or arg.startswith("'")) and len(arg) >= 2:
                    raw_val = arg[1:-1]
                    if raw_val not in self.string_literals:
                        label = f".LC{self.string_counter}"
                        self.string_counter += 1
                        self.string_literals[raw_val] = label

    @staticmethod
    def _is_literal(val):
        """Check if an operand is a numeric literal (positive or negative integer)."""
        if val is None:
            return False
        s = str(val).strip()
        if s.isdigit():
            return True
        if s.startswith("-") and len(s) > 1 and s[1:].isdigit():
            return True
        return False

    def generate_x86_64(self):
        """Generates standard x86-64 assembly."""
        self._collect_strings()
        lines = []

        lines.append("\t.file\t\"source.c\"")
        lines.append("\t# Target Architecture: x86-64 (GNU Assembler / Linux System V AMD64 ABI)")
        lines.append("\t# Generated from Three-Address Code (TAC)")
        lines.append("\t.text")

        # Read-only data section for string constants
        if self.string_literals:
            lines.append("\t.section\t.rodata")
            for text_val, label in self.string_literals.items():
                escaped = text_val.replace("\n", "\\n").replace("\t", "\\t")
                lines.append(f"{label}:")
                lines.append(f"\t.string\t\"{escaped}\"")
            lines.append("\t.text")

        # Stack offset tracker for local variables & temporaries
        stack_offsets = {}
        current_offset = 0

        def get_offset(var_name):
            nonlocal current_offset
            if var_name not in stack_offsets:
                current_offset += 4
                stack_offsets[var_name] = current_offset
            return stack_offsets[var_name]

        # Pre-scan quadruples to allocate all stack offsets and compute total frame size
        for q in self.quadruples:
            q_op = q.get("op")
            for key in ("arg1", "arg2", "result"):
                v = q.get(key)
                if not v or self._is_literal(v) or v.startswith('"') or v.startswith("'"):
                    continue
                if q_op in ("LABEL", "GOTO", "FUNC_START", "FUNC_END", "INCLUDE"):
                    continue
                if q_op == "IF_FALSE" and key == "result":
                    continue
                if q_op == "CALL" and key in ("arg1", "arg2"):
                    continue
                get_offset(v)

        total_frame_bytes = max(32, ((current_offset + 15) // 16) * 16)

        in_function = False
        current_func_name = ""
        pending_params = []

        for q in self.quadruples:
            op = q.get("op")
            arg1 = q.get("arg1", "")
            arg2 = q.get("arg2", "")
            res = q.get("result", "")

            if op == "INCLUDE":
                lines.append(f"\t# Direct inclusion of header: {arg1}")

            elif op == "FUNC_START":
                in_function = True
                current_func_name = arg1
                lines.append(f"\t.globl\t{current_func_name}")
                lines.append(f"\t.type\t{current_func_name}, @function")
                lines.append(f"{current_func_name}:")
                lines.append("\tpushq\t%rbp                 # Save old base pointer")
                lines.append("\tmovq\t%rsp, %rbp           # Set up current stack frame")
                lines.append(f"\tsubq\t${total_frame_bytes}, %rsp             # Reserve {total_frame_bytes} bytes (16-byte aligned)")

            elif op == "FUNC_END":
                if in_function:
                    lines.append(f"\t# End of {current_func_name}")
                in_function = False

            elif op in ("+", "-", "*", "/", "%"):
                # Load arg1 into %eax
                if self._is_literal(arg1):
                    lines.append(f"\tmovl\t${arg1}, %eax             # Load constant {arg1} into %eax")
                else:
                    lines.append(f"\tmovl\t-{get_offset(arg1)}(%rbp), %eax  # Load {arg1} from stack")

                # Perform op with arg2
                if op == "+":
                    if self._is_literal(arg2):
                        lines.append(f"\taddl\t${arg2}, %eax             # Add literal {arg2}")
                    else:
                        lines.append(f"\taddl\t-{get_offset(arg2)}(%rbp), %eax  # Add {arg2}")
                elif op == "-":
                    if self._is_literal(arg2):
                        lines.append(f"\tsubl\t${arg2}, %eax             # Subtract literal {arg2}")
                    else:
                        lines.append(f"\tsubl\t-{get_offset(arg2)}(%rbp), %eax  # Subtract {arg2}")
                elif op == "*":
                    if self._is_literal(arg2):
                        lines.append(f"\timull\t${arg2}, %eax            # Multiply by literal {arg2}")
                    else:
                        lines.append(f"\timull\t-{get_offset(arg2)}(%rbp), %eax # Multiply by {arg2}")
                elif op in ("/", "%"):
                    lines.append("\tcltd                          # Sign-extend %eax into %edx:%eax")
                    if self._is_literal(arg2):
                        lines.append(f"\tmovl\t${arg2}, %ecx")
                        lines.append("\tidivl\t%ecx")
                    else:
                        lines.append(f"\tidivl\t-{get_offset(arg2)}(%rbp)")
                    if op == "%":
                        lines.append("\tmovl\t%edx, %eax             # Modulo remainder is in %edx")

                # Store result temporary
                lines.append(f"\tmovl\t%eax, -{get_offset(res)}(%rbp)  # Store result into {res}")

            elif op in ("==", "!=", "<", ">", "<=", ">="):
                # Load arg1 into %eax
                if self._is_literal(arg1):
                    lines.append(f"\tmovl\t${arg1}, %eax             # Load constant {arg1} into %eax")
                else:
                    lines.append(f"\tmovl\t-{get_offset(arg1)}(%rbp), %eax  # Load {arg1} from stack")

                # Compare %eax with arg2 (in AT&T syntax: cmpl S, D computes D - S = %eax - arg2)
                if self._is_literal(arg2):
                    lines.append(f"\tcmpl\t${arg2}, %eax             # Compare {arg1} with constant {arg2}")
                else:
                    lines.append(f"\tcmpl\t-{get_offset(arg2)}(%rbp), %eax  # Compare {arg1} with {arg2}")

                set_inst = {
                    "==": "sete",
                    "!=": "setne",
                    "<":  "setl",
                    "<=": "setle",
                    ">":  "setg",
                    ">=": "setge",
                }[op]

                lines.append(f"\t{set_inst}\t%al                        # Set byte if condition ({op}) holds")
                lines.append("\tmovzbl\t%al, %eax                    # Zero-extend boolean result to 32-bit")
                lines.append(f"\tmovl\t%eax, -{get_offset(res)}(%rbp)  # Store comparison result into {res}")

            elif op in ("UNARY_MINUS", "UNARY_PLUS"):
                if self._is_literal(arg1):
                    lines.append(f"\tmovl\t${arg1}, %eax             # Load constant {arg1}")
                else:
                    lines.append(f"\tmovl\t-{get_offset(arg1)}(%rbp), %eax  # Load {arg1} from stack")
                if op == "UNARY_MINUS":
                    lines.append("\tnegl\t%eax                         # Negate %eax")
                lines.append(f"\tmovl\t%eax, -{get_offset(res)}(%rbp)  # Store unary result into {res}")

            elif op == "=":
                if self._is_literal(arg1):
                    lines.append(f"\tmovl\t${arg1}, -{get_offset(res)}(%rbp) # Assign {res} = {arg1}")
                else:
                    lines.append(f"\tmovl\t-{get_offset(arg1)}(%rbp), %eax  # Load {arg1}")
                    lines.append(f"\tmovl\t%eax, -{get_offset(res)}(%rbp)  # Store into {res}")

            elif op == "PARAM":
                pending_params.append(arg1)

            elif op == "CALL":
                # System V AMD64 ABI registers: %rdi, %rsi, %rdx, %rcx, %r8, %r9
                reg_map_64 = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
                reg_map_32 = ["%edi", "%esi", "%edx", "%ecx", "%r8d", "%r9d"]

                for i, p in enumerate(pending_params[:6]):
                    clean_str = p[1:-1] if (p.startswith('"') or p.startswith("'")) and len(p) >= 2 else None
                    if clean_str in self.string_literals:
                        lbl = self.string_literals[clean_str]
                        lines.append(f"\tleaq\t{lbl}(%rip), {reg_map_64[i]}      # Arg #{i+1}: string {lbl}")
                    elif self._is_literal(p):
                        lines.append(f"\tmovl\t${p}, {reg_map_32[i]}             # Arg #{i+1}: literal {p}")
                    else:
                        lines.append(f"\tmovl\t-{get_offset(p)}(%rbp), {reg_map_32[i]}  # Arg #{i+1}: variable {p}")

                lines.append("\tmovl\t$0, %eax               # 0 vector registers used for variadic call")
                lines.append(f"\tcall\t{arg1}@PLT            # Call {arg1}()")
                if res:
                    lines.append(f"\tmovl\t%eax, -{get_offset(res)}(%rbp)  # Capture return value in {res}")
                pending_params = []

            elif op == "RETURN":
                if self._is_literal(arg1):
                    lines.append(f"\tmovl\t${arg1}, %eax             # Set return register %eax = {arg1}")
                elif arg1:
                    lines.append(f"\tmovl\t-{get_offset(arg1)}(%rbp), %eax  # Load return value {arg1} into %eax")
                else:
                    lines.append("\tmovl\t$0, %eax               # Return 0")
                lines.append("\tleave                        # Epilogue: mov %rbp, %rsp; pop %rbp")
                lines.append("\tret                          # Return to caller")

            elif op == "LABEL":
                lines.append(f"{res}:")
            elif op == "GOTO":
                lines.append(f"\tjmp\t{res}")
            elif op == "IF_FALSE":
                if self._is_literal(arg1):
                    if int(arg1) == 0:
                        lines.append(f"\tjmp\t{res}")
                else:
                    lines.append(f"\tcmpl\t$0, -{get_offset(arg1)}(%rbp)")
                    lines.append(f"\tje\t{res}")

        # If no explicit return was encountered at end of main
        if in_function:
            lines.append("\tmovl\t$0, %eax               # Default return 0")
            lines.append("\tleave")
            lines.append("\tret")

        return "\n".join(lines)

    def generate_educational_asm(self):
        """
        Generates simplified educational pseudo-assembly instructions
        (LOAD, STORE, ADD, MUL, CALL, RET).
        """
        lines = []
        lines.append("; ==========================================================================")
        lines.append("; Educational Target Pseudo-Assembly (Virtual 4-Register RISC Architecture)")
        lines.append("; NOTE: For conceptual teaching of register allocation, LOAD/STORE, and ALU.")
        lines.append("; ==========================================================================")
        lines.append("")

        reg_idx = 0
        def next_reg():
            nonlocal reg_idx
            r = f"R{reg_idx % 4}"
            reg_idx += 1
            return r

        for q in self.quadruples:
            op = q.get("op")
            arg1 = q.get("arg1", "")
            arg2 = q.get("arg2", "")
            res = q.get("result", "")

            if op == "INCLUDE":
                lines.append(f"; [Header] {arg1}")
            elif op == "FUNC_START":
                lines.append(f"\n{arg1}:")
                lines.append(f"  ENTER_FRAME                 ; Allocate activation record")
            elif op == "FUNC_END":
                lines.append(f"  LEAVE_FRAME                 ; Restore caller activation record\n")
            elif op in ("+", "-", "*", "/", "%"):
                r1 = next_reg()
                r2 = next_reg()
                dest = "R0"
                op_name = {"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV", "%": "MOD"}[op]

                load_cmd1 = "LOAD_CONST" if self._is_literal(arg1) else "LOAD"
                load_cmd2 = "LOAD_CONST" if self._is_literal(arg2) else "LOAD"

                lines.append(f"  {load_cmd1:<11} {r1}, {arg1:<12} ; Load operand 1")
                lines.append(f"  {load_cmd2:<11} {r2}, {arg2:<12} ; Load operand 2")
                lines.append(f"  {op_name:<11} {dest}, {r1}, {r2}       ; {dest} = {r1} {op} {r2}")
                lines.append(f"  STORE       [{res}], {dest}       ; Save to temporary {res}")
            elif op in ("==", "!=", "<", ">", "<=", ">="):
                r1 = next_reg()
                r2 = next_reg()
                dest = "R0"
                op_name = {
                    "==": "CMP_EQ",
                    "!=": "CMP_NE",
                    "<":  "CMP_LT",
                    ">":  "CMP_GT",
                    "<=": "CMP_LE",
                    ">=": "CMP_GE",
                }[op]
                load_cmd1 = "LOAD_CONST" if self._is_literal(arg1) else "LOAD"
                load_cmd2 = "LOAD_CONST" if self._is_literal(arg2) else "LOAD"
                lines.append(f"  {load_cmd1:<11} {r1}, {arg1:<12} ; Load operand 1")
                lines.append(f"  {load_cmd2:<11} {r2}, {arg2:<12} ; Load operand 2")
                lines.append(f"  {op_name:<11} {dest}, {r1}, {r2}       ; Test condition: {r1} {op} {r2}")
                lines.append(f"  STORE       [{res}], {dest}       ; Save boolean result to {res}")
            elif op in ("UNARY_MINUS", "UNARY_PLUS"):
                r1 = next_reg()
                dest = "R0"
                load_cmd = "LOAD_CONST" if self._is_literal(arg1) else "LOAD"
                lines.append(f"  {load_cmd:<11} {r1}, {arg1:<12} ; Load operand")
                if op == "UNARY_MINUS":
                    lines.append(f"  NEG         {dest}, {r1}             ; Negate value")
                else:
                    lines.append(f"  MOV         {dest}, {r1}             ; Move value")
                lines.append(f"  STORE       [{res}], {dest}       ; Save to {res}")
            elif op == "=":
                r = next_reg()
                load_cmd = "LOAD_CONST" if self._is_literal(arg1) else "LOAD"
                lines.append(f"  {load_cmd:<11} {r}, {arg1:<12} ; Load value")
                lines.append(f"  STORE       [{res}], {r}          ; {res} = {r}")
            elif op == "PARAM":
                lines.append(f"  PUSH_ARG    {arg1:<16} ; Pass argument")
            elif op == "CALL":
                lines.append(f"  CALL        {arg1}, {arg2:<10} ; Execute procedure")
            elif op == "RETURN":
                load_cmd = "LOAD_CONST" if self._is_literal(arg1) else "LOAD"
                if arg1:
                    lines.append(f"  {load_cmd:<11} R0, {arg1:<12} ; Place return value in register R0")
                lines.append(f"  RET                         ; Return control to caller")
            elif op == "LABEL":
                lines.append(f"{res}:")
            elif op == "GOTO":
                lines.append(f"  JUMP        {res}")
            elif op == "IF_FALSE":
                lines.append(f"  BR_FALSE    {arg1}, {res}")

        return "\n".join(lines)

    def generate(self):
        return {
            "x86_64": self.generate_x86_64(),
            "educational": self.generate_educational_asm(),
        }


def generate_code(ir_data):
    """Helper function to generate target code."""
    cg = CodeGenerator(ir_data)
    return cg.generate()


if __name__ == "__main__":
    from lexer import Lexer
    from parser import Parser
    from ir_generator import generate_ir

    c_sample = '''#include <stdio.h>
int main() {
    int total = 3 + 4 * 2;
    printf("Result = %d\\n", total);
    return 0;
}'''

    tokens = Lexer(c_sample).tokenize()
    ast = Parser(tokens).parse_program()
    ir = generate_ir(ast)
    target = generate_code(ir)

    print("=== x86-64 Target Assembly ===")
    print(target["x86_64"])
    print("\n=== Educational RISC Pseudo-Assembly ===")
    print(target["educational"])
