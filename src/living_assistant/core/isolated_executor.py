import subprocess
import json
import tempfile
import sys
import os
from typing import Any

def run_isolated_tool(script_code: str, timeout: float = 120.0) -> dict[str, Any]:
    """
    The Bulletproof Joint: Runs external tool code in a completely isolated subprocess.
    This guarantees that memory leaks, asyncio event loop crashes, and global state 
    corruption in external repos NEVER crash the main Orchestrator.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(script_code)
        temp_path = f.name
        
    try:
        # Run using the same Python executable, but fresh memory space and event loop
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8'
        )
        if result.returncode == 0:
            try:
                # The script must print the final JSON result as the last line
                lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                if not lines:
                    return {"ok": False, "error": "Isolated tool completed but returned no output."}
                last_line = lines[-1]
                return json.loads(last_line)
            except Exception as parse_exc:
                return {
                    "ok": False, 
                    "error": f"Tool output was not valid JSON: {parse_exc}\nStdout:\n{result.stdout}\nStderr:\n{result.stderr}"
                }
        else:
            return {
                "ok": False, 
                "error": f"Isolated tool crashed (exit code {result.returncode}).\nStderr:\n{result.stderr}"
            }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Isolated tool timed out after {timeout} seconds and was forcefully killed."}
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
