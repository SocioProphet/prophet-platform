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


def copied_paths(dockerfile: str = "Dockerfile") -> set[str]:
    df = (ROOT / dockerfile).read_text()
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


def test_run_planes_pin_an_immutable_tag_not_latest():
    """A moving tag under imagePullPolicy: IfNotPresent means a node keeps serving a
    cached image and a fix never rolls out — a failure mode this estate has already
    hit. Planes must reference a sha- tag."""
    import re
    for plane in ("gcp_vm.py", "gke.py"):
        src = (ROOT / "src" / "noetica_impair" / "planes" / plane).read_text()
        for m in re.finditer(r"noetica-impair:([A-Za-z0-9._-]+)", src):
            tag = m.group(1)
            assert tag.startswith("sha-"), (
                f"{plane} references noetica-impair:{tag}; pin an immutable sha- tag"
            )


def test_the_cpu_image_copies_everything_pyproject_needs_too():
    """Both Dockerfiles must satisfy the package metadata; the CUDA one already had a
    LICENSE gap that only surfaced inside a GPU image build."""
    import re
    pp = (ROOT / "pyproject.toml").read_text()
    copied = copied_paths("Dockerfile.cpu")
    needed = {m.group(2) for m in
              re.finditer(r'(readme|license)\s*=\s*\{?\s*(?:file\s*=\s*)?"([^"]+)"', pp)}
    missing = sorted(f for f in needed if f not in copied)
    assert not missing, f"Dockerfile.cpu never COPYs {missing}"


def test_the_cpu_image_is_not_cuda_based():
    """The whole reason it exists: the CUDA base is published for amd64 ONLY, so an
    arm64 workstation cannot run the GPU image at all."""
    df = (ROOT / "Dockerfile.cpu").read_text()
    assert "cuda" not in df.split("FROM")[1].split("\n")[0].lower()
    assert "download.pytorch.org/whl/cpu" in df, "must use the CPU wheel index"


def test_both_images_keep_the_offline_invariant():
    """Invariant 0.6: the rig never fetches weights at runtime."""
    for f in ("Dockerfile", "Dockerfile.cpu"):
        df = (ROOT / f).read_text()
        assert "HF_HUB_OFFLINE=1" in df, f"{f} must stay offline"
        assert "TRANSFORMERS_OFFLINE=1" in df
