"""The provider-leakage check's allow-list must let a domain term through WITHOUT opening a
hole for a real provider identifier on the same line (#1046)."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("vnpl", ROOT / "tools" / "validate_no_provider_leakage.py")
vnpl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vnpl)

GOOGLE = re.compile(r'"google_')


def test_google_ai_domain_token_is_allowed():
    # `google_ai` is an AI engine an AI-visibility probe targets, not a GCP resource.
    assert vnpl._match_is_only_allowed(GOOGLE, '"engine": "google_ai"') is True


def test_a_real_google_resource_alongside_still_fails():
    # The allow-list must not become a smuggling channel: a genuine terraform resource on
    # the same line as an allowed token is still a leak.
    line = '{"engine":"google_ai","bucket":"google_storage_bucket"}'
    assert vnpl._match_is_only_allowed(GOOGLE, line) is False


def test_unrelated_provider_tokens_are_untouched_by_the_allowlist():
    assert vnpl._match_is_only_allowed(re.compile(r'"aws_'), '"x":"aws_s3_bucket"') is False


def test_the_repo_currently_has_no_provider_leakage():
    # The check runs clean on the tree — google_ai in the web-intel contracts is allowed,
    # everything else is genuinely provider-neutral.
    vnpl.ERRORS.clear()
    for scan_dir in vnpl.CANONICAL_DIRS:
        if scan_dir.exists():
            for p in sorted(scan_dir.rglob("*")):
                if p.is_file():
                    vnpl.check_file(p)
    assert vnpl.ERRORS == [], f"unexpected provider leakage: {vnpl.ERRORS[:3]}"
