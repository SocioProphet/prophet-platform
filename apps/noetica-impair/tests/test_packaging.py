"""The build context must contain everything the package metadata references.

Regression: pyproject declared license = { file = "LICENSE" } while the Dockerfile
copied only requirements/pyproject/src, so the image build failed at
`pip install -e .` with "License file does not exist" — after a five-minute CUDA
layer pull, three attempts in.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def copied_paths() -> set[str]:
    df = (ROOT / "Dockerfile").read_text()
    out: set[str] = set()
    for m in re.finditer(r"^COPY\s+(.+?)\s+\S+\s*$", df, re.M):
        for tok in m.group(1).split():
            out.add(tok.strip("./"))
    return out


def test_every_file_pyproject_references_is_copied_into_the_image():
    pp = (ROOT / "pyproject.toml").read_text()
    copied = copied_paths()
    needed = {m.group(2) for m in
              re.finditer(r'(readme|license)\s*=\s*\{?\s*(?:file\s*=\s*)?"([^"]+)"', pp)}
    missing = sorted(f for f in needed if f not in copied)
    assert not missing, (
        f"pyproject references {missing} but the Dockerfile never COPYs them; "
        "`pip install -e .` will fail inside the image"
    )


def test_the_package_source_dir_is_copied():
    assert "src" in copied_paths()


def test_referenced_files_actually_exist_in_the_repo():
    pp = (ROOT / "pyproject.toml").read_text()
    for m in re.finditer(r'(readme|license)\s*=\s*\{?\s*(?:file\s*=\s*)?"([^"]+)"', pp):
        assert (ROOT / m.group(2)).is_file(), f"{m.group(2)} referenced but absent"
