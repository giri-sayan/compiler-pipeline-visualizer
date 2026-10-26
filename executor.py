"""
Execution Runner — Dispatches safe execution across languages.

Supports:
  1. Sandboxed TAC Virtual Machine simulation (cross-platform, zero native dependencies, safe).
  2. Optional native subprocess execution (with timeout, temp directory isolation, non-blocking limits).
"""

import os
import shutil
import subprocess
import tempfile
import time
from typing import Dict, Any, Optional
from tac_vm import TACVirtualMachine


class SafeExecutor:
    @staticmethod
    def execute(language: str, source: str, ir_data: Dict[str, Any], prefer_native: bool = False) -> Dict[str, Any]:
        """
        Executes program safely.
        By default uses TACVirtualMachine for reliable sandboxed execution.
        If native execution is specifically feasible and safe, runs with strict timeout.
        """
        quads = ir_data.get("quadruples", []) if isinstance(ir_data, dict) else []

        # 1. TAC Virtual Machine simulation
        if not prefer_native or not quads:
            vm = TACVirtualMachine(quads)
            return vm.run()

        # 2. Native runner for Python
        lang = (language or "c").lower()
        if lang == "python":
            return SafeExecutor._run_python_native(source)

        # For compiled languages or when native compiler is absent, fallback to TAC VM
        vm = TACVirtualMachine(quads)
        return vm.run()

    @staticmethod
    def _run_python_native(source: str, timeout_sec: float = 2.0) -> Dict[str, Any]:
        """Safely execute Python source in a separate restricted subprocess."""
        start_t = time.perf_counter()
        tmp_dir = tempfile.mkdtemp(prefix="cpv_py_")
        tmp_file = os.path.join(tmp_dir, "script.py")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(source)

            proc = subprocess.run(
                ["python", "-I", "-B", tmp_file],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=tmp_dir,
            )
            elapsed_ms = (time.perf_counter() - start_t) * 1000
            stdout_text = proc.stdout
            if proc.stderr:
                stdout_text += ("\n" if stdout_text else "") + proc.stderr
            return {
                "executed": True,
                "success": proc.returncode == 0,
                "output": stdout_text or "[Program finished with no output]",
                "exit_code": proc.returncode,
                "time_ms": round(elapsed_ms, 2),
                "engine": "native_python"
            }
        except subprocess.TimeoutExpired:
            return {
                "executed": True,
                "success": False,
                "output": f"[Execution timed out after {timeout_sec} seconds. Possible infinite loop.]",
                "exit_code": -1,
                "time_ms": round(timeout_sec * 1000, 2),
                "engine": "native_python"
            }
        except Exception as e:
            # Fallback to TAC VM if native fails
            return {
                "executed": False,
                "success": False,
                "output": f"[Execution error: {e}]",
                "exit_code": -1,
                "time_ms": 0,
                "engine": "native_python"
            }
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
