import re
from typing import Dict, Any, Optional, List


class DiagnosticParser:
    """Extracts structured diagnostic signals from test outputs, traces, and compiler errors."""

    @staticmethod
    def extract_failure_details(stdout: str, stderr: str) -> Dict[str, Any]:
        combined = f"{stdout}\n{stderr}"
        failing_file = None
        line_number = None
        error_type = "UnknownError"
        error_message = ""

        # Pattern 1: Python tracebacks: File "path/to/file.py", line 42, in ...
        tb_match = re.search(r'File "([^"]+)", line (\d+)(?:, in (\w+))?', combined)
        if tb_match:
            failing_file = tb_match.group(1)
            line_number = int(tb_match.group(2))

        # Pattern 2: Pytest assertion or syntax error: E   assert 2 == 5 or AssertionError
        err_match = re.search(r"E\s+([A-Za-z0-9_]+Error:.*)", combined)
        if err_match:
            error_message = err_match.group(1).strip()
        else:
            # Fallback assertion failure
            assert_match = re.search(r"E\s+(assert.*)", combined)
            if assert_match:
                error_message = assert_match.group(1).strip()
                error_type = "AssertionError"

        # Pattern 3: Node / Jest / Mocha errors
        node_match = re.search(r"at (?:.+ \()?([^:)]+):(\d+):(\d+)\)?", combined)
        if not failing_file and node_match:
            failing_file = node_match.group(1)
            line_number = int(node_match.group(2))

        if not error_message and ("FAILED" in combined or "Error:" in combined):
            # Grab last 5 lines as fallback summary
            lines = [l.strip() for l in combined.splitlines() if l.strip()]
            error_message = "\n".join(lines[-5:]) if lines else "Test command exited with failure"

        return {
            "failing_file": failing_file,
            "line_number": line_number,
            "error_type": error_type,
            "error_message": error_message,
            "raw_snippet": combined[-2000:] if len(combined) > 2000 else combined,
        }
