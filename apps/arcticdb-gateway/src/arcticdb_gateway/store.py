"""Embedded ArcticDB (LMDB) behind a small, deterministic gateway surface.

Why a gateway at all: ArcticDB is an embedded library, not a server. The tritfabric atoms
catalog (fabric/docs/atoms-catalog.md section 3.3) deploys it as "gateway Deployment wrapping
embedded ArcticDB" so the rest of the platform talks HTTP contracts, never links the library.
LMDB is strictly single-writer — the Deployment must run with one replica (values file pairs
persistence with replicaCount: 1 + Recreate).

LICENSE (verified 2026-07-28, PyPI + LICENSE.txt at tag v4.4.3):
  arcticdb 4.4.3 was released 2024-06-19 under BSL 1.1 whose Change Date is "two years as of
  the release date of the respective version" with Change License = Apache License 2.0.
  2024-06-19 + 2 years = 2026-06-19, which has passed — this pinned version is Apache 2.0 today.
  Do NOT bump this pin to a version less than two years old without a licensing decision.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


class SymbolNotFound(KeyError):
    """Library or symbol (or requested version) does not exist."""


class BadRequest(ValueError):
    """Payload is structurally invalid (mismatched column lengths, empty data...)."""


class GatewayStore:
    """Lazily-initialised Arctic handle + the three gateway operations (write/read/versions)."""

    def __init__(self, uri: str) -> None:
        self.uri = uri
        self._arctic: Any = None

    # -- lifecycle -----------------------------------------------------------------
    @property
    def arctic(self) -> Any:
        """Open LMDB on first use, not at import — the module stays importable without /data."""
        if self._arctic is None:
            from arcticdb import Arctic  # deferred: keeps import cheap for tooling/tests

            self._arctic = Arctic(self.uri)
        return self._arctic

    def ping(self) -> dict[str, Any]:
        """Force backend init so the readiness probe proves LMDB actually opens (a green
        /healthz over a broken store would be a silent failure)."""
        return {"libraries": len(self.arctic.list_libraries())}

    # -- helpers -------------------------------------------------------------------
    def _library(self, name: str, create: bool) -> Any:
        if create:
            return self.arctic.get_library(name, create_if_missing=True)
        if name not in self.arctic.list_libraries():
            raise SymbolNotFound(f"library {name!r} does not exist")
        return self.arctic.get_library(name)

    @staticmethod
    def _frame(data: dict[str, list[Any]], index: list[Any] | None) -> pd.DataFrame:
        if not data:
            raise BadRequest("data must contain at least one column")
        lengths = {len(v) for v in data.values()}
        if len(lengths) != 1:
            raise BadRequest(f"columns have mismatched lengths: { {k: len(v) for k, v in data.items()} }")
        (n,) = lengths
        if index is not None:
            if len(index) != n:
                raise BadRequest(f"index length {len(index)} != column length {n}")
            try:
                idx = pd.to_datetime(index)
            except (ValueError, TypeError) as e:
                raise BadRequest(f"index is not parseable as timestamps: {e}") from e
            return pd.DataFrame(data, index=idx)
        return pd.DataFrame(data)

    @staticmethod
    def _index_out(df: pd.DataFrame) -> list[Any]:
        if isinstance(df.index, pd.DatetimeIndex):
            return [ts.isoformat() for ts in df.index]
        return [i.item() if hasattr(i, "item") else i for i in df.index]

    # -- operations ----------------------------------------------------------------
    def write(
        self,
        library: str,
        symbol: str,
        data: dict[str, list[Any]],
        index: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
        prune_previous: bool = False,
    ) -> dict[str, Any]:
        df = self._frame(data, index)
        lib = self._library(library, create=True)
        item = lib.write(symbol, df, metadata=metadata, prune_previous_versions=prune_previous)
        return {
            "library": library,
            "symbol": symbol,
            "version": int(item.version),
            "rows": int(df.shape[0]),
            "columns": list(df.columns),
        }

    def read(self, library: str, symbol: str, as_of: int | None = None) -> dict[str, Any]:
        lib = self._library(library, create=False)
        if not lib.has_symbol(symbol):
            raise SymbolNotFound(f"symbol {symbol!r} not found in library {library!r}")
        try:
            item = lib.read(symbol, as_of=as_of)
        except Exception as e:  # arcticdb raises NoSuchVersionException for a bad as_of
            if "NoSuchVersion" in type(e).__name__ or "NoDataFound" in type(e).__name__:
                raise SymbolNotFound(f"version {as_of!r} of {symbol!r} not found: {e}") from e
            raise
        df = item.data
        return {
            "library": library,
            "symbol": symbol,
            "version": int(item.version),
            "index": self._index_out(df),
            "data": {c: [v.item() if hasattr(v, "item") else v for v in df[c].tolist()] for c in df.columns},
            "metadata": item.metadata,
        }

    def versions(self, library: str, symbol: str | None = None) -> list[dict[str, Any]]:
        lib = self._library(library, create=False)
        out = []
        for key, info in lib.list_versions(symbol).items():
            out.append(
                {
                    "symbol": key.symbol,
                    "version": int(key.version),
                    "date": info.date.isoformat() if getattr(info, "date", None) is not None else None,
                    "deleted": bool(getattr(info, "deleted", False)),
                    "snapshots": list(getattr(info, "snapshots", []) or []),
                }
            )
        out.sort(key=lambda r: (r["symbol"], -r["version"]))
        return out
