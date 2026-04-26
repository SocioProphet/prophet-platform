from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "render_search_orchestrator_image_patch.py"
SPEC = importlib.util.spec_from_file_location("render_search_orchestrator_image_patch", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

IMAGE = MODULE.IMAGE
main = MODULE.main


def test_image_patch_renderer_writes_pinned_image(tmp_path, monkeypatch) -> None:
    digest = "sha256:" + ("a" * 64)
    lock_path = tmp_path / "lock.json"
    output_path = tmp_path / "patch.yaml"
    lock_path.write_text(
        json.dumps(
            {
                "image": IMAGE,
                "digest": digest,
                "pinned_ref": IMAGE + "@" + digest,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.argv", ["tool", "--image-lock", str(lock_path), "--output", str(output_path)])
    assert main() == 0
    rendered = output_path.read_text(encoding="utf-8")
    assert "image: " + IMAGE + "@" + digest in rendered
    assert "name: search-orchestrator" in rendered
