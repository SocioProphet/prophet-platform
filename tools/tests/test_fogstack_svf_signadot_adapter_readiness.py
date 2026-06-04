from __future__ import annotations

import subprocess
import sys


def test_fogstack_svf_signadot_adapter_readiness_validator_passes() -> None:
    proc = subprocess.run(
        [sys.executable, "tools/validate_fogstack_svf_signadot_adapter_readiness.py"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "PASS: Fog Stack SVF Signadot adapter readiness" in proc.stdout
    assert '"passed": true' in proc.stdout
    assert "Validator does not call Signadot" in proc.stdout
    assert "Validator does not certify production readiness or vendor parity" in proc.stdout
