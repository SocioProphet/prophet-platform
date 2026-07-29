"""Extraction → nuggets. The only two warrants this service is entitled to mint.

`direct-quote`  one per spanned block, text CUT from the source (never retyped), so the
                exactness invariant is true by construction rather than by inspection.
`computed`      one per quantity recognised inside a quote, carrying the deterministic
                normalization of that quantity and CITING the quote nugget as evidence.
                This is the production IFM lineage the contract generalizes: document →
                typed value, with the value's warrant naming the span it came from.

What this service does NOT mint, and why:
  `inferred`        it runs no inference engine. `contract.build_inferred` exists for
                    producers that do; nothing here calls it.
  `model-generated` it calls no model. `contract.build_model_generated` exists, requires
                    a conditioning window, and is exercised by the tests — so the
                    "unwarranted content still names its source" rule is executable
                    rather than aspirational.

QUANTITY NORMALIZATION (regime `nugget-extractor/quantity@v1`) is deliberately narrow —
it computes what is stated and refuses to infer what is not:
  "22.6%"             → 22.6 percent
  "AUD 1,138.9m"      → 1138900000.0 AUD
  "$1,138.9 million"  → 1138900000.0, unit UNSTATED, currencySymbol "$"
A bare "$" is NOT recorded as USD. Deciding which dollar a document means is an
inference about the document, and this is a `computed` warrant: it may only carry what
deterministic computation over the cited span supports. Mislabelling it would be exactly
the laundering the contract forbids, one warrant class down.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Iterable

from . import contract
from .extract import Extraction

REGIME = "nugget-extractor/quantity@v1"

# Scale words → multiplier. Bare "b" is billion in every financial register we ingest;
# bare "t" is NOT included (too often "tonnes").
_SCALES: dict[str, float] = {
    "thousand": 1e3, "k": 1e3,
    "million": 1e6, "m": 1e6, "mn": 1e6,
    "billion": 1e9, "bn": 1e9, "b": 1e9,
    "trillion": 1e12, "tn": 1e12,
}
_ISO = ("AUD", "USD", "EUR", "GBP", "NZD", "CAD", "JPY", "CHF", "CNY", "SGD", "HKD")

_QUANTITY = re.compile(
    r"(?P<iso>\b(?:" + "|".join(_ISO) + r")\b\s*)?"          # explicit ISO code
    r"(?P<symbol>(?:A\$|US\$|NZ\$|C\$|HK\$|S\$|[$£€¥]))?\s*"  # or a currency symbol
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"    # 1,138.9 | 1138.9 | 22
    r"\s*(?P<scale>thousand|million|billion|trillion|mn|bn|tn|[kmb])?"
    r"\s*(?P<pct>%|per\s?cent(?:age)?|percent)?",
    re.IGNORECASE)


def _normalize_quantity(m: re.Match[str]) -> dict[str, Any] | None:
    """One regex match → a canonicalPayload, or None when there is nothing computed.

    A bare integer with no unit, scale, symbol or percent sign is a number in prose (a
    year, a count, a page reference). Normalizing it would produce a nugget that asserts
    nothing the quote does not already say, so it is skipped."""
    iso = (m.group("iso") or "").strip().upper() or None
    symbol = m.group("symbol") or None
    scale_raw = (m.group("scale") or "").lower() or None
    pct = m.group("pct")
    if not (iso or symbol or scale_raw or pct):
        return None
    try:
        value = float(m.group("num").replace(",", ""))
    except ValueError:  # pragma: no cover — the regex cannot produce this
        return None
    scale_word = None
    if scale_raw:
        mult = _SCALES.get(scale_raw)
        if mult is None:
            return None
        value *= mult
        scale_word = {1e3: "thousand", 1e6: "million", 1e9: "billion",
                      1e12: "trillion"}[mult]
    if pct:
        kind, unit = "percentage", "percent"
    elif iso or symbol:
        kind, unit = "currency", iso
    else:
        kind, unit = "number", None
    return {"normalizationRegime": REGIME, "kind": kind, "value": value, "unit": unit,
            "currencySymbol": symbol, "scale": scale_word, "surface": m.group(0).strip()}


def _statement(payload: dict[str, Any]) -> str:
    unit = payload["unit"]
    tail = f" {unit}" if unit else ""
    note = "" if (unit or payload["kind"] != "currency") else \
        f' (currency symbol "{payload["currencySymbol"]}" — code not stated in the source)'
    return (f'Normalized quantity: {payload["value"]:g}{tail}'
            f'{note} (from "{payload["surface"]}").')


def quantities(text: str, offset: int) -> list[tuple[int, int, dict[str, Any]]]:
    """(absolute start, absolute end, canonicalPayload) for each quantity in `text`.
    `offset` is where `text` starts in the source, so spans stay source-absolute."""
    found = []
    for m in _QUANTITY.finditer(text):
        payload = _normalize_quantity(m)
        if payload is None:
            continue
        # Trim the match back to its own surface: the regex tolerates whitespace between
        # parts, so the raw match can carry a trailing space the surface does not.
        raw = m.group(0)
        lead = len(raw) - len(raw.lstrip())
        found.append((offset + m.start() + lead,
                      offset + m.start() + lead + len(raw.strip()), payload))
    return found


def build(extraction: Extraction, *, doc_ref: str, run_ref: str,
          clock: Callable[[], str], logical_start: int,
          policy_labels: Iterable[str] = (),
          extra_kko_type_refs: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Extraction → nuggets, in emission order.

    Order matters and is not cosmetic: a `computed` nugget cites the `direct-quote` it was
    derived from, and the envelope's logical clock must never let a cited parent sit AFTER
    its child (the causal-ordering invariant the shared time vocabulary carries). Each
    quote is therefore emitted immediately before the quantities computed from it, and
    logicalTime increments once per nugget in that same order.

    Nothing is validated here — building and gating are separate on purpose. The emitter
    validates every nugget against the vendored schema before a single graph write, so
    there is exactly ONE fail-closed gate and it sits in front of the door."""
    src, h = extraction.source_text, contract.content_hash(extraction.source_text)
    labels = list(policy_labels)
    quote_types = [contract.KKO_WRITTEN_INFO, *extra_kko_type_refs]
    computed_types = [contract.KKO_QUANTITY, *extra_kko_type_refs]

    out: list[dict[str, Any]] = []
    logical = logical_start
    for block in extraction.blocks:
        quote = contract.build_direct_quote(
            doc_ref=doc_ref, source_text=src, src_hash=h, start=block.start,
            end=block.end, page=block.page, ordinal=len(out), wall_time=clock(),
            logical_time=logical, run_ref=run_ref, kko_type_refs=quote_types,
            policy_labels=labels)
        out.append(quote)
        logical += 1
        for start, end, payload in quantities(block.text, block.start):
            out.append(contract.build_computed(
                doc_ref=doc_ref, src_hash=h, start=start, end=end, page=block.page,
                ordinal=len(out), text=_statement(payload), wall_time=clock(),
                logical_time=logical, evidence=[quote["id"]], canonical_payload=payload,
                kko_type_refs=computed_types, policy_labels=labels))
            logical += 1
    return out


__all__ = ["REGIME", "build", "quantities"]
