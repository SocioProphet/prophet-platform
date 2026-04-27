"""Runtime settings for the OSM Map API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Configuration for fixture-backed OSM API mode."""

    gaia_fixture_root: Path
    sherlock_fixture_root: Path
    sociosphere_fixture_root: Path
    host: str = "127.0.0.1"
    port: int = 8088

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            gaia_fixture_root=Path(os.environ.get("GAIA_FIXTURE_ROOT", "")).expanduser(),
            sherlock_fixture_root=Path(os.environ.get("SHERLOCK_FIXTURE_ROOT", "")).expanduser(),
            sociosphere_fixture_root=Path(
                os.environ.get("SOCIOSPHERE_FIXTURE_ROOT", "")
            ).expanduser(),
            host=os.environ.get("OSM_MAP_API_HOST", "127.0.0.1"),
            port=int(os.environ.get("OSM_MAP_API_PORT", "8088")),
        )

    def missing_roots(self) -> list[str]:
        missing: list[str] = []
        if not str(self.gaia_fixture_root) or not self.gaia_fixture_root.exists():
            missing.append("GAIA_FIXTURE_ROOT")
        if not str(self.sherlock_fixture_root) or not self.sherlock_fixture_root.exists():
            missing.append("SHERLOCK_FIXTURE_ROOT")
        if not str(self.sociosphere_fixture_root) or not self.sociosphere_fixture_root.exists():
            missing.append("SOCIOSPHERE_FIXTURE_ROOT")
        return missing
