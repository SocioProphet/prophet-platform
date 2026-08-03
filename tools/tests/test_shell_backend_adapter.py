import sys, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def test_adapters_valid_and_parity():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "validate_shell_backend_adapter.py")],
                       text=True, capture_output=True)
    assert r.returncode == 0, r.stderr + r.stdout
    assert "op-parity" in r.stdout

if __name__ == "__main__":
    import pytest; sys.exit(pytest.main([__file__, "-q"]))
