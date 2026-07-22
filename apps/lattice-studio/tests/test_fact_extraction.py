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


US_STATEMENT_BLOCKS = [
    {"page": 4, "kind": "table",
     "text": "2026 | Percent of total revenue | 2025 | Percent of total revenue\n"
             "Total revenue | 3,088,242 | 100.0 | 2,875,253 | 100.0\n"
             "Net income | $ | 302,824 | 9.8 | % | $ | 386,599 | 13.4 | %"},
    {"page": 6, "kind": "table",
     "text": "Net income | $ | 302,824 | $ | 386,599\n"
             "Diluted | $ | 0.23 | $ | 0.28"},
]
US_SCHEMA = {"table": "financials", "fields": [
    {"name": "revenue", "type": "number", "unit": "USD_k", "labels": ["total revenue"]},
    {"name": "net_income", "type": "number", "unit": "USD_k", "labels": ["net income"]},
    {"name": "eps_diluted", "type": "number", "labels": ["diluted"]},
]}


def test_us_statement_year_headers_and_missing_label_column():
    """SEC statement shape: bare-year headers WITHOUT a label column, % columns interleaved.
    The requested year's column must win — not the % cell, not last year's number."""
    facts = {f["field"]: f for f in
             extract_facts_from_blocks(US_STATEMENT_BLOCKS, US_SCHEMA,
                                       period="CY2026Q1", convention="current-first")}
    assert facts["revenue"]["value"] == 3088242.0        # 2026 column, not 100.0, not 2,875,253
    assert facts["net_income"]["value"] == 302824.0
    # prior year still addressable
    fy25 = {f["field"]: f for f in
            extract_facts_from_blocks(US_STATEMENT_BLOCKS, US_SCHEMA,
                                      period="CY2025Q1", convention="current-first")}
    assert fy25["revenue"]["value"] == 2875253.0


def test_headerless_us_table_current_first_fallback():
    # the EPS sub-table has no year header — the convention decides, and US is current-first
    facts = {f["field"]: f for f in
             extract_facts_from_blocks(US_STATEMENT_BLOCKS, US_SCHEMA,
                                       period="CY2026Q1", convention="current-first")}
    assert facts["eps_diluted"]["value"] == 0.23          # NOT last year's 0.28
    # AU default (current-last) preserved for the AU-shaped pack
    au = {f["field"]: f for f in extract_facts_from_blocks(PACK_BLOCKS, SCHEMA)}
    assert au["revenue"]["value"] == 1204.0


def test_punctuated_and_prose_values_parse_correctly():
    # trailing comma must not reject the value ('was $0.23, a 17.9% decrease…')
    assert _parse_fact_value("$0.23,") == (0.23, None)
    blocks = [{"page": 1, "kind": "text",
               "text": "Diluted earnings per share was $0.23, a 17.9% decrease from $0.28\n\n"
                       "Net income for the first quarter of 2026 was $302.8 million\n\n"
                       "Total revenue increased 7.4% to $3.1 billion"}]
    schema = {"table": "t", "fields": [
        {"name": "eps_diluted", "labels": ["diluted earnings per share"]},
        {"name": "net_income", "unit": "USD_m", "labels": ["net income"]},
        {"name": "revenue", "unit": "USD_bn", "labels": ["total revenue"]},
    ]}
    facts = {f["field"]: f for f in extract_facts_from_blocks(blocks, schema)}
    assert facts["eps_diluted"]["value"] == 0.23     # not the 17.9% decrease
    assert facts["net_income"]["value"] == 302.8     # not the bare year 2026
    assert facts["revenue"]["value"] == 3.1          # not the 7.4% growth rate


def test_piped_tables_inside_text_blocks_beat_prose():
    """Converted documents (HTML→text) carry tables as piped lines inside text blocks —
    the labelled cell must still win at table confidence over any prose mention."""
    blocks = [{"page": 1, "kind": "text",
               "text": "Total revenue increased 7.4% to $3.1 billion\n"
                       "2026 | Percent of total revenue | 2025 | Percent of total revenue\n"
                       "Total revenue | 3,088,242 | 100.0 | 2,875,253 | 100.0"}]
    schema = {"table": "t", "fields": [{"name": "revenue", "unit": "USD_k", "labels": ["total revenue"]}]}
    facts = {f["field"]: f for f in
             extract_facts_from_blocks(blocks, schema, period="CY2026Q1", convention="current-first")}
    assert facts["revenue"]["value"] == 3088242.0
    assert facts["revenue"]["confidence"] >= 0.9     # table confidence, not prose
