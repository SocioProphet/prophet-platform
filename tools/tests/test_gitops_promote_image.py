from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "gitops_promote_image.py"
spec = importlib.util.spec_from_file_location("gitops_promote_image", MODULE_PATH)
promote = importlib.util.module_from_spec(spec)
sys.modules["gitops_promote_image"] = promote
spec.loader.exec_module(promote)

GOOD_DIGEST = "sha256:" + "a" * 64
ALL_REQUIRED = {
    "require_digest": True,
    "require_signature_state": True,
    "require_sbom": True,
    "require_provenance": True,
}
FULL_VERIFICATION = {"digest_pinned": True, "signed": True, "sbom": True, "provenance": True}


class CheckPromotionTests(unittest.TestCase):
    def test_all_requirements_met_passes(self):
        self.assertEqual(promote.check_promotion(ALL_REQUIRED, FULL_VERIFICATION, GOOD_DIGEST), [])

    def test_missing_signature_is_refused(self):
        v = {**FULL_VERIFICATION, "signed": False}
        errors = promote.check_promotion(ALL_REQUIRED, v, GOOD_DIGEST)
        self.assertTrue(any("require_signature_state" in e for e in errors))

    def test_missing_sbom_and_provenance_both_reported(self):
        v = {**FULL_VERIFICATION, "sbom": False, "provenance": False}
        errors = promote.check_promotion(ALL_REQUIRED, v, GOOD_DIGEST)
        self.assertTrue(any("require_sbom" in e for e in errors))
        self.assertTrue(any("require_provenance" in e for e in errors))

    def test_unpinned_digest_refused_even_if_signed(self):
        errors = promote.check_promotion(ALL_REQUIRED, FULL_VERIFICATION, "hellgraph-service:latest")
        self.assertTrue(any("pinned" in e for e in errors))

    def test_relaxed_profile_only_enforces_declared_requirements(self):
        relaxed = {"require_digest": True}  # sbom/provenance/signature not required here
        v = {"digest_pinned": True, "signed": False, "sbom": False, "provenance": False}
        self.assertEqual(promote.check_promotion(relaxed, v, GOOD_DIGEST), [])


class ApplyDigestTests(unittest.TestCase):
    def test_apply_digest_pins_into_values(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            vf = Path(d) / "hellgraph-service.yaml"
            vf.write_text("image:\n  repository: hellgraph-service\nservice:\n  port: 8080\n", encoding="utf-8")
            promote.apply_digest(vf, GOOD_DIGEST, "prod", tag="abc123")
            out = yaml.safe_load(vf.read_text(encoding="utf-8"))
            self.assertEqual(out["image"]["digest"], GOOD_DIGEST)
            self.assertEqual(out["image"]["tag"], "abc123")
            self.assertEqual(out["image"]["channel"], "prod")
            self.assertEqual(out["image"]["repository"], "hellgraph-service")  # preserved
            self.assertEqual(out["service"]["port"], 8080)                      # untouched


if __name__ == "__main__":
    unittest.main()
