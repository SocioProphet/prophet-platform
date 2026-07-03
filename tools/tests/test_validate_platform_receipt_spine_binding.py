from pathlib import Path
import subprocess
import sys


def test_validate_platform_receipt_spine_binding() -> None:
    repo = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "tools/validate_platform_receipt_spine_binding.py"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK: validated platform receipt-spine binding" in result.stdout
