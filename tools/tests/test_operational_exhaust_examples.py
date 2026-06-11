import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_operational_exhaust_examples_validate():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate_operational_exhaust_examples.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
