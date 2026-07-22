"""Fact-mode extraction (IFM stage 03): {blocks, target_schema} → {facts[]} — the contract
the compute-gateway extraction adapter speaks. Deterministic, span-preserving, and it never
fabricates: a field the document doesn't state yields NO fact (the warrant machinery depends
on that honesty)."""
from fastapi.testclient import TestClient

from lattice_studio.server import _parse_fact_value, app, extract_facts_from_blocks

client = TestClient(app)

SCHEMA = {"table": "financials", "fields": [
    {"name": "revenue", "type": "number", "unit": "AUD"},
    {"name": "net_profit", "type": "number"},
    {"name": "gross_margin", "type": "number"},
    {"name": "npat", "type": "number", "labels": ["net profit after tax"]},
    {"name": "ebitda", "type": "number"},          # deliberately absent from the pack
]}

PACK_BLOCKS = [
    {"page": 1, "kind": "text", "text": "GYG FY26 Results"},
    {"page": 2, "kind": "table", "text": "Metric | FY25 | FY26\nRevenue | $1,050m | $1,204m\n"
                                         "Net profit | $9m | ($14m)\nGross margin | 61% | 63%"},
    {"page": 3, "kind": "text", "text": "Net profit after tax of $12m reflects expansion costs.\n\n"
                                        "Revenue rose strongly across all regions."},
]


def test_value_parser_handles_finance_notation():
    assert _parse_fact_value("$1,204m") == (1204.0, "m")
    assert _parse_fact_value("($14m)") == (-14.0, "m")          # accounting negative
    assert _parse_fact_value("63%") == (63.0, "%")
    assert _parse_fact_value("2.5bn") == (2.5, "bn")
    assert _parse_fact_value("$500 ") == (500.0, None)
    assert _parse_fact_value("FY26") is None                    # year token is not a value
    assert _parse_fact_value("no numbers here") is None


def test_period_column_selection_never_trades_on_last_years_number():
    fy26 = {f["field"]: f for f in extract_facts_from_blocks(PACK_BLOCKS, SCHEMA, period="FY26")}
    assert fy26["revenue"]["value"] == 1204.0                   # header-matched column
    assert fy26["net_profit"]["value"] == -14.0                 # accounting negative, right period
    fy25 = {f["field"]: f for f in extract_facts_from_blocks(PACK_BLOCKS, SCHEMA, period="FY25")}
    assert fy25["revenue"]["value"] == 1050.0 and fy25["gross_margin"]["value"] == 61.0
    # no period → rightmost (current-period convention)
    noper = {f["field"]: f for f in extract_facts_from_blocks(PACK_BLOCKS, SCHEMA)}
    assert noper["revenue"]["value"] == 1204.0


def test_table_rows_beat_prose_and_spans_are_kept():
    facts = {f["field"]: f for f in extract_facts_from_blocks(PACK_BLOCKS, SCHEMA, period="FY26")}
    assert facts["revenue"]["confidence"] >= 0.9 and facts["revenue"]["page"] == 2
    assert facts["revenue"]["source_span"].startswith("p2/tbl")
    assert facts["revenue"]["verbatim"] is True
    # percent field carries its detected unit
    assert facts["gross_margin"]["unit"] == "%"


def test_schema_aliases_reach_prose_facts():
    facts = {f["field"]: f for f in extract_facts_from_blocks(PACK_BLOCKS, SCHEMA)}
    # 'npat' has no table row — found via its alias in prose, at prose confidence
    assert facts["npat"]["value"] == 12.0 and facts["npat"]["confidence"] == 0.6
    assert facts["npat"]["source_span"].startswith("p3/txt")


def test_absent_fields_are_never_fabricated():
    facts = {f["field"]: f for f in extract_facts_from_blocks(PACK_BLOCKS, SCHEMA)}
    assert "ebitda" not in facts                                # absent means absent
    assert extract_facts_from_blocks([], SCHEMA) == []          # no blocks, no facts


def test_extract_facts_endpoint_serves_gateway_contract():
    r = client.post("/api/studio/extract-facts",
                    json={"project": "demo", "blocks": PACK_BLOCKS, "target_schema": SCHEMA})
    assert r.status_code == 200
    b = r.json()
    assert b["fields_requested"] == 5 and b["fields_found"] == 4
    assert all({"field", "value", "page", "source_span", "confidence"} <= set(f) for f in b["facts"])
