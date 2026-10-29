import json
import subprocess
import sys
from pathlib import Path


def test_demo_uses_two_stdio_processes() -> None:
    script = Path(__file__).parents[1] / "examples" / "demo_ocr.py"
    completed = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60, check=True)
    result = json.loads(completed.stdout)
    assert result["status"] == "passed"
    assert result["clients"] == "2 MCP stdio subprocesses"
    assert result["checkpoint_version"] == 3
    assert result["evidence_status"] == "unverified"
