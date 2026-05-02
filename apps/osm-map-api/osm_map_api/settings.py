"""Runtime settings for the OSM Map API."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _split_csv(value: str) -> tuple[str, ...]:
    """Parse comma-separated environment values into a stable tuple."""

    return tuple(part.strip() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    """Configuration for fixture-backed OSM API mode."""

    gaia_fixture_root: Path
    sherlock_fixture_root: Path
    sociosphere_fixture_root: Path
    gaia_layer_catalog_root: Path | None = None
    host: str = "127.0.0.1"
    port: int = 8088
    cors_allowed_origins: tuple[str, ...] = field(default_factory=tuple)
    cors_allow_credentials: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            gaia_fixture_root=Path(os.environ.get("GAIA_FIXTURE_ROOT", "")).expanduser(),
            sherlock_fixture_root=Path(os.environ.get("SHERLOCK_FIXTURE_ROOT", "")).expanduser(),
            sociosphere_fixture_root=Path(
                os.environ.get("SOCIOSPHERE_FIXTURE_ROOT", "")
            ).expanduser(),
            gaia_layer_catalog_root=Path(
                os.environ.get("GAIA_LAYER_CATALOG_ROOT", str(Path(__file__).resolve().parents[1]))
            ).expanduser(),
            host=os.environ.get("OSM_MAP_API_HOST", "127.0.0.1"),
            port=int(os.environ.get("OSM_MAP_API_PORT", "8088")),
            cors_allowed_origins=_split_csv(
                os.environ.get("OSM_MAP_API_CORS_ALLOWED_ORIGINS", "")
            ),
            cors_allow_credentials=os.environ.get(
                "OSM_MAP_API_CORS_ALLOW_CREDENTIALS", "false"
            ).lower()
            in {"1", "true", "yes"},
        )

    def missing_roots(self) -> list[str]:
        missing: list[str] = []
        if not str(self.gaia_fixture_root) or not self.gaia_fixture_root.exists():
            missing.append("GAIA_FIXTURE_ROOT")
        if not str(self.sherlock_fixture_root) or not self.sherlock_fixture_root.exists():
            missing.append("SHERLOCK_FIXTURE_ROOT")
        if not str(self.sociosphere_fixture_root) or not self.sociosphere_fixture_root.exists():
            missing.append("SOCIOSPHERE_FIXTURE_ROOT")
        if self.gaia_layer_catalog_root is None or not self.gaia_layer_catalog_root.exists():
            missing.append("GAIA_LAYER_CATALOG_ROOT")
        return missing
