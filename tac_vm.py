"""
TAC Virtual Machine & Safe Execution Engine.

Simulates execution of Three-Address Code (TAC) Quadruples in a sandboxed,
safe in-process virtual machine with:
  1. Strict instruction step limit (default 100,000 steps) to prevent infinite loops.
  2. Memory and variable store isolation (no arbitrary OS execution).
  3. Built-in I/O interception: printf, print, println, cout, console.log.
  4. Math library evaluation: sqrt, pow, abs, floor, ceil.
  5. Accurate return codes and execution statistics (steps, runtime ms).
"""

import math
import re
import time
from typing import Dict, Any, List, Optional


class TACVirtualMachine:
    def __init__(self, quadruples: Any = None, max_steps: int = 100000):
        if isinstance(quadruples, dict) and "quadruples" in quadruples:
            self.quadruples = quadruples["quadruples"]
        else:
            self.quadruples = quadruples or []
        self.max_steps = max_steps
        self.output_buffer: List[str] = []
        self.variables: Dict[str, Any] = {}
        self.step_count = 0

    def _resolve_val(self, val: Any) -> Any:
        if val is None or val == "" or val == "-":
            return None
        s = str(val).strip()

        # String literal with quotes
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            # unescape common escapes
            raw = s[1:-1]
            return raw.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r")

        # Integer literal
        try:
            if re.match(r'^-?\d+$', s):
                return int(s)
            if re.match(r'^-?\d+\.\d+$', s):
                return float(s)
        except ValueError:
            pass

        # Boolean literal
        if s.lower() == "true":
            return 1
        if s.lower() == "false":
            return 0

        # Variable lookup
        if s in self.variables:
            return self.variables[s]

        return s

    def run(self, ir_data: Any = None) -> Dict[str, Any]:
        if ir_data is not None:
            if isinstance(ir_data, dict) and "quadruples" in ir_data:
                self.quadruples = ir_data["quadruples"]
            elif isinstance(ir_data, list):
                self.quadruples = ir_data

        start_time = time.perf_counter()
        self.output_buffer = []
        self.variables = {}
        self.step_count = 0

        # Build label index map for jumps & function descriptors
        labels: Dict[str, int] = {}
        func_starts: Dict[str, int] = {}
        func_params: Dict[str, List[str]] = {}
        for idx, q in enumerate(self.quadruples):
            op = q.get("op")
            res = q.get("result")
            arg1 = q.get("arg1")
            arg2 = q.get("arg2")
            if op == "LABEL" and res:
                labels[str(res)] = idx
            elif op == "FUNC_START" and arg1:
                func_starts[str(arg1)] = idx
                if arg2 and str(arg2) not in ("void", "auto", "-"):
                    func_params[str(arg1)] = [p.strip() for p in str(arg2).split(",") if p.strip()]
                else:
                    func_params[str(arg1)] = []

        # Determine entry point:
        # If 'main' function exists, start there; otherwise start at 0
        pc = 0
        if "main" in func_starts:
            pc = func_starts["main"]

        call_stack: List[Dict[str, Any]] = []
        pending_params: List[Any] = []
        exit_code = 0

        while 0 <= pc < len(self.quadruples):
            self.step_count += 1
            if self.step_count > self.max_steps:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                return {
                    "executed": True,
                    "success": False,
                    "output": "".join(self.output_buffer) + f"\n[Runtime Error: Maximum execution step limit ({self.max_steps}) exceeded. Possible infinite loop.]",
                    "exit_code": -1,
                    "steps": self.step_count,
                    "time_ms": round(elapsed_ms, 2),
                    "engine": "tac_vm"
                }

            q = self.quadruples[pc]
            op = q.get("op")
            arg1 = q.get("arg1")
            arg2 = q.get("arg2")
            res = q.get("result")

            if op in ("INCLUDE", "LABEL", "FORMAL_PARAM"):
                pc += 1
                continue

            elif op == "FUNC_START":
                if not call_stack and str(arg1) != "main":
                    depth = 1
                    scan_pc = pc + 1
                    while scan_pc < len(self.quadruples):
                        q_scan = self.quadruples[scan_pc]
                        if q_scan.get("op") == "FUNC_START":
                            depth += 1
                        elif q_scan.get("op") == "FUNC_END":
                            depth -= 1
                            if depth == 0:
                                pc = scan_pc + 1
                                break
                        scan_pc += 1
                    continue
                pc += 1
                continue

            elif op == "FUNC_END":
                if call_stack:
                    frame = call_stack.pop()
                    pc = frame["return_pc"]
                    continue
                else:
                    pc += 1
                    break

            elif op == "=":
                val = self._resolve_val(arg1)
                if res and res != "-":
                    self.variables[str(res)] = val
                pc += 1

            elif op in ("+", "-", "*", "/", "%"):
                v1 = self._resolve_val(arg1)
                v2 = self._resolve_val(arg2)
                try:
                    num1 = float(v1) if isinstance(v1, (int, float)) or (isinstance(v1, str) and v1.replace('.','',1).isdigit()) else 0
                    num2 = float(v2) if isinstance(v2, (int, float)) or (isinstance(v2, str) and v2.replace('.','',1).isdigit()) else 0
                    if op == "+":
                        if isinstance(v1, str) or isinstance(v2, str):
                            calc = str(v1) + str(v2)
                        elif isinstance(v1, int) and isinstance(v2, int):
                            calc = int(num1) + int(num2)
                        else:
                            calc = num1 + num2
                    elif op == "-":
                        calc = (int(num1) - int(num2)) if (isinstance(v1, int) and isinstance(v2, int)) else (num1 - num2)
                    elif op == "*":
                        calc = (int(num1) * int(num2)) if (isinstance(v1, int) and isinstance(v2, int)) else (num1 * num2)
                    elif op == "/":
                        if num2 == 0:
                            calc = 0
                            self.output_buffer.append("[Runtime Warning: Division by zero]\n")
                        else:
                            calc = (int(num1) // int(num2)) if (isinstance(v1, int) and isinstance(v2, int)) else (num1 / num2)
                    elif op == "%":
                        calc = int(num1) % int(num2) if num2 != 0 else 0
                    if res and res != "-":
                        self.variables[str(res)] = calc
                except Exception:
                    if res and res != "-":
                        self.variables[str(res)] = 0
                pc += 1

            elif op in ("==", "!=", "<", ">", "<=", ">="):
                v1 = self._resolve_val(arg1)
                v2 = self._resolve_val(arg2)
                try:
                    num1 = float(v1) if isinstance(v1, (int, float)) else 0
                    num2 = float(v2) if isinstance(v2, (int, float)) else 0
                    cond_map = {
                        "==": num1 == num2,
                        "!=": num1 != num2,
                        "<": num1 < num2,
                        ">": num1 > num2,
                        "<=": num1 <= num2,
                        ">=": num1 >= num2,
                    }
                    b_res = 1 if cond_map.get(op, False) else 0
                    if res and res != "-":
                        self.variables[str(res)] = b_res
                except Exception:
                    if res and res != "-":
                        self.variables[str(res)] = 0
                pc += 1

            elif op == "UNARY_MINUS":
                v1 = self._resolve_val(arg1)
                try:
                    val = -v1 if isinstance(v1, (int, float)) else -float(v1)
                    if res and res != "-":
                        self.variables[str(res)] = val
                except Exception:
                    pass
                pc += 1

            elif op == "UNARY_PLUS":
                v1 = self._resolve_val(arg1)
                if res and res != "-":
                    self.variables[str(res)] = v1
                pc += 1

            elif op == "PARAM":
                val = self._resolve_val(arg1)
                pending_params.append(val)
                pc += 1

            elif op == "CALL":
                fname = str(arg1)
                call_res = 0

                # 1. Standard Output handlers: printf, print, println, cout, console.log
                if fname in ("printf", "print", "println", "System.out.println", "System.out.print", "console.log", "cout", "cout_print"):
                    if fname == "printf" and pending_params:
                        fmt_str = str(pending_params[0])
                        args = pending_params[1:]
                        try:
                            # Replace standard C format specifiers %d, %i, %f, %s
                            parts = re.split(r'(%[0-9]*\.?[0-9]*[difsuoxXfeEgGaAcsp%])', fmt_str)
                            out_chunks = []
                            arg_idx = 0
                            for part in parts:
                                if part == "%%":
                                    out_chunks.append("%")
                                elif part.startswith("%") and len(part) > 1 and arg_idx < len(args):
                                    a_val = args[arg_idx]
                                    arg_idx += 1
                                    spec = part[-1]
                                    if spec in "difu":
                                        out_chunks.append(str(int(float(a_val))))
                                    elif spec in "feEgGaA":
                                        out_chunks.append(f"{float(a_val):.6f}".rstrip('0').rstrip('.'))
                                    else:
                                        out_chunks.append(str(a_val))
                                else:
                                    out_chunks.append(part)
                            self.output_buffer.append("".join(out_chunks))
                        except Exception:
                            self.output_buffer.append(fmt_str + " " + " ".join(str(a) for a in args) + "\n")
                    elif fname in ("println", "System.out.println"):
                        msg = " ".join(str(p) for p in pending_params)
                        self.output_buffer.append(msg + "\n")
                    elif fname in ("print", "System.out.print"):
                        msg = " ".join(str(p) for p in pending_params)
                        self.output_buffer.append(msg)
                    elif fname == "console.log":
                        msg = " ".join(str(p) for p in pending_params)
                        self.output_buffer.append(msg + "\n")
                    elif fname in ("cout", "cout_print"):
                        chunks = []
                        for p in pending_params:
                            p_str = str(p)
                            if p in ("endl", "\\n", "\n") or p_str.strip() in ("\\n", r"\n", "\n", "endl"):
                                chunks.append("\n")
                            else:
                                chunks.append(p_str)
                        self.output_buffer.append("".join(chunks))
                    call_res = len(pending_params)

                # 2. Standard Math functions
                elif fname in ("sqrt", "pow", "abs", "floor", "ceil", "sin", "cos", "tan", "log"):
                    args = [float(p) for p in pending_params if isinstance(p, (int, float))]
                    if fname == "sqrt" and args:
                        call_res = math.sqrt(args[0]) if args[0] >= 0 else 0
                    elif fname == "pow" and len(args) >= 2:
                        call_res = math.pow(args[0], args[1])
                    elif fname == "abs" and args:
                        call_res = abs(args[0])
                    elif fname == "floor" and args:
                        call_res = math.floor(args[0])
                    elif fname == "ceil" and args:
                        call_res = math.ceil(args[0])

                # 3. User-defined function call in quadruples
                call_target = fname if fname in func_starts else (fname.split(".", 1)[-1] if "." in fname and fname.split(".", 1)[-1] in func_starts else None)
                if call_target:
                    call_stack.append({
                        "return_pc": pc + 1,
                        "dest": res,
                        "fname": call_target
                    })
                    pnames = func_params.get(call_target, [])
                    for i, val in enumerate(pending_params):
                        if i < len(pnames):
                            self.variables[pnames[i]] = val
                    pc = func_starts[call_target] + 1
                    pending_params = []
                    continue

                if res and res != "-":
                    self.variables[str(res)] = call_res
                pending_params = []
                pc += 1

            elif op == "RETURN":
                val = self._resolve_val(arg1) if (arg1 and arg1 != "-") else 0
                exit_code = int(val) if isinstance(val, (int, float)) else 0
                if call_stack:
                    frame = call_stack.pop()
                    dest = frame.get("dest")
                    if dest and dest != "-":
                        self.variables[str(dest)] = val
                    pc = frame["return_pc"]
                    continue
                else:
                    break

            elif op == "IF_FALSE":
                cond_val = self._resolve_val(arg1)
                is_false = False
                if cond_val is None or cond_val == 0 or cond_val == "0" or cond_val is False:
                    is_false = True
                if is_false and res and str(res) in labels:
                    pc = labels[str(res)]
                else:
                    pc += 1

            elif op == "GOTO":
                if res and str(res) in labels:
                    pc = labels[str(res)]
                else:
                    pc += 1

            else:
                pc += 1

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        output_str = "".join(self.output_buffer)
        if not output_str:
            output_str = f"[Program exited with status code {exit_code}]"

        return {
            "executed": True,
            "success": True,
            "output": output_str,
            "exit_code": exit_code,
            "steps": self.step_count,
            "time_ms": round(elapsed_ms, 2),
            "engine": "tac_vm"
        }
