"""The 'sense' edge — map an estate exchange (exchange-envelope.v0) to a percolation trigger, so
materialisation is AUTOMATIC. An exchange references the assets it touched (asset_refs / content_refs);
those are the change seeds whose downstream closure hellgraph re-materialises. Tenant-isolated: an
exchange in one tenant only percolates that tenant's catalog objects, so a cross-tenant event can't
trigger another's rebuild. This closes the loop end to end:

    exchange (sense)  ->  percolate (plan)  ->  scoped upsert (actuate)  ->  receipt (record)
"""
from __future__ import annotations

from typing import List, Mapping

from tools.hellgraph_percolation.percolation import Catalog, PercolationResult, Writer, percolate


def changed_from_exchange(envelope: Mapping) -> List[str]:
    """The catalog ids an exchange touched: its asset_refs then content_refs, de-duplicated."""
    out: List[str] = []
    for ref in list(envelope.get("asset_refs", ())) + list(envelope.get("content_refs", ())):
        if ref not in out:
            out.append(ref)
    return out


def sense(envelope: Mapping, catalog: Catalog, *, writer: Writer, now: str) -> PercolationResult:
    """Percolate the change an exchange announces. Only catalog objects in the exchange's own tenant
    are seeded (isolation); references to uncataloged assets are ignored (fail-safe)."""
    tenant = envelope.get("tenant_id")
    changed = [
        c for c in changed_from_exchange(envelope)
        if c in catalog.objects and catalog.objects[c].tenant_id == tenant
    ]
    return percolate(catalog, changed, writer=writer, now=now)
