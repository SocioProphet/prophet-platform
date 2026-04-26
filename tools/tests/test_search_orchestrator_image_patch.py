from __future__ import annotations

import json

from tools.render_search_orchestrator_image_patch import IMAGE, main


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
