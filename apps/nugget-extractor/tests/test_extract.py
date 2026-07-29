"""Extraction: spans must be EXACT offsets into the hashed source text, and a document
this service cannot honestly read must be refused rather than silently emptied."""
from __future__ import annotations

import pytest

from nugget_extractor import contract, extract as ex
from nugget_extractor import nuggets as builder

TEXT = ("Network sales grew 22.6% to $1,138.9 million.\r\n"
        "Comparable sales growth was 9.4 per cent.   \r\n"
        "\r\n\r\n\r\n"
        "Store rollout continued across 2025.")


def test_normalize_is_stated_and_idempotent():
    once = ex.normalize(TEXT)
    assert "\r" not in once
    assert "   \n" not in once            # trailing whitespace stripped per line
    assert "\n\n\n" not in once           # 3+ newlines collapsed to the separator
    assert ex.normalize(once) == once


def test_text_blocks_span_the_source_exactly():
    e = ex.extract(TEXT.encode(), filename="notes.txt")
    assert e.media_type == "text/plain" and e.pages == 1
    assert len(e.blocks) == 2             # two paragraphs
    for b in e.blocks:
        # THE invariant everything downstream rests on.
        assert e.source_text[b.start:b.end] == b.text
        assert b.end - b.start == len(b.text)


def test_markdown_is_sniffed_by_extension_and_kept_verbatim():
    e = ex.extract(b"# Heading\n\nA paragraph with 5.5% in it.", filename="doc.md")
    assert e.media_type == "text/markdown"
    assert e.source_text.startswith("# Heading")
    assert all(e.source_text[b.start:b.end] == b.text for b in e.blocks)


def test_sentence_grain_gives_each_repeated_sentence_its_own_span():
    """A repeated sentence must not collapse onto the first occurrence's offsets."""
    body = b"Sales rose 5%. Sales rose 5%. Costs fell 2%."
    e = ex.extract(body, filename="a.txt", grain="sentence")
    assert len(e.blocks) == 3
    starts = [b.start for b in e.blocks]
    assert starts == sorted(starts) and len(set(starts)) == 3
    assert all(e.source_text[b.start:b.end] == b.text for b in e.blocks)


def test_pdf_text_layer_is_real_with_page_attribution(pdf_bytes):
    e = ex.extract(pdf_bytes, filename="report.pdf")
    assert e.media_type == ex.PDF_MEDIA and e.pages == 2
    assert "Network sales grew 22.6%" in e.source_text
    assert "Store rollout continued" in e.source_text
    assert {b.page for b in e.blocks} == {1, 2}
    for b in e.blocks:
        assert e.source_text[b.start:b.end] == b.text
    # every page-2 block must start after every page-1 block
    p1 = max(b.end for b in e.blocks if b.page == 1)
    assert min(b.start for b in e.blocks if b.page == 2) >= p1


def test_pdf_sniffed_by_magic_bytes_not_by_filename(pdf_bytes):
    assert ex.sniff_media("actually-a-pdf.txt", pdf_bytes) == ex.PDF_MEDIA


def test_scanned_pdf_is_refused_not_silently_empty(scanned_pdf_bytes):
    """The OCR gap made honest. This service ships NO OCR; a scan raises, loudly, naming
    the seam — it never returns an empty successful extraction."""
    with pytest.raises(ex.OcrRequired) as e:
        ex.extract(scanned_pdf_bytes, filename="scan.pdf")
    assert "OCR" in str(e.value)


def test_the_only_registered_ocr_backend_refuses():
    assert ex.OCR_BACKEND == "none"
    assert list(ex.OCR_BACKENDS) == ["none"]
    with pytest.raises(ex.OcrRequired):
        ex.OCR_BACKENDS["none"](b"\x89PNG")


def test_unsupported_media_is_refused():
    with pytest.raises(ex.UnsupportedMedia):
        ex.extract(b"\x89PNG\r\n\x1a\n", filename="scan.png", media_type="image/png")


@pytest.mark.parametrize("raw,label", [
    (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", "png"),
    (b"\xff\xd8\xff\xe0\x00\x10JFIF", "jpeg"),
    (b"GIF89a\x01\x00", "gif"),
    (b"PK\x03\x04\x14\x00", "zip/docx"),
    (b"\x1f\x8b\x08\x00", "gzip"),
    (b"II*\x00\x08\x00", "tiff"),
    (b"scan output\x00\x00binary tail", "nul-bearing"),
])
def test_binary_without_a_declared_media_type_is_refused_not_mojibake(raw, label):
    """The silent-wrong case this guards. Sniffed as text and decoded with
    errors="replace", a PNG produces syntactically PERFECT nuggets quoting replacement
    characters — schema-valid, span-exact, and complete nonsense. Refusal is the only
    honest answer, and it must not depend on the caller declaring the type."""
    assert not ex.sniff_media(f"mystery-{label}", raw).startswith("text/")
    with pytest.raises(ex.ExtractError):
        ex.extract(raw, filename=f"mystery-{label}")     # no media_type given


def test_ordinary_text_still_sniffs_as_text():
    assert ex.sniff_media("notes.txt", b"Plain prose with 5% in it.") == "text/plain"
    assert ex.sniff_media("notes.md", b"# Heading\n\nBody.") == "text/markdown"
    assert ex.sniff_media("utf8.txt", "Naïve café — 22.6%".encode()) == "text/plain"


def test_empty_and_whitespace_documents_are_refused():
    with pytest.raises(ex.ExtractError):
        ex.extract(b"", filename="empty.txt")
    with pytest.raises(ex.ExtractError):
        ex.extract(b"   \n\n\t  ", filename="blank.txt")


def test_corrupt_pdf_is_an_honest_error_not_a_crash():
    with pytest.raises(ex.ExtractError):
        ex.extract(b"%PDF-1.4\nnot really a pdf at all", filename="broken.pdf")


# ── extraction → nuggets ──
def test_quantities_normalize_only_what_is_stated():
    e = ex.extract(TEXT.encode(), filename="a.txt")
    found = {p["surface"]: p for _s, _t, p in
             builder.quantities(e.blocks[0].text, e.blocks[0].start)}
    assert found["22.6%"]["kind"] == "percentage"
    assert found["22.6%"]["value"] == 22.6 and found["22.6%"]["unit"] == "percent"
    dollars = found["$1,138.9 million"]
    assert dollars["value"] == 1_138_900_000.0 and dollars["scale"] == "million"
    # A bare "$" is NOT recorded as USD: which dollar it is would be an inference, and
    # this is a `computed` warrant.
    assert dollars["unit"] is None and dollars["currencySymbol"] == "$"
    assert found["9.4 per cent"]["unit"] == "percent"


def test_explicit_iso_code_is_carried_through():
    payloads = [p for _s, _e, p in builder.quantities("Revenue of AUD 1,138.9m.", 0)]
    assert payloads and payloads[0]["unit"] == "AUD"
    assert payloads[0]["value"] == 1_138_900_000.0


def test_bare_numbers_in_prose_are_not_normalized():
    """A year or a count asserts nothing the quote does not already say."""
    assert builder.quantities("Store rollout continued across 2025.", 0) == []
    assert builder.quantities("See page 12 of the report.", 0) == []


def test_build_emits_quotes_and_their_computed_children_in_causal_order():
    e = ex.extract(TEXT.encode(), filename="a.txt")
    out = builder.build(e, doc_ref="urn:srcos:document:t", run_ref="urn:srcos:run:t",
                        clock=lambda: "2026-07-29T00:00:00.000Z", logical_start=0)
    by_id = {n["id"]: n for n in out}
    assert {n["warrant"]["type"] for n in out} == {"direct-quote", "computed"}
    for n in out:
        contract.validate_nugget(n, source_text=e.source_text)
        for ref in n["warrant"]["evidence"]:
            if ref in by_id:
                # a cited parent must never sit AFTER its child on the logical clock
                assert by_id[ref]["logicalTime"] < n["logicalTime"]
    # logical time is dense and monotone across the batch
    assert [n["logicalTime"] for n in out] == list(range(len(out)))


def test_computed_spans_point_at_the_quantity_not_the_whole_paragraph():
    e = ex.extract(TEXT.encode(), filename="a.txt")
    out = builder.build(e, doc_ref="urn:srcos:document:t", run_ref="urn:srcos:run:t",
                        clock=lambda: "2026-07-29T00:00:00.000Z", logical_start=0)
    for n in out:
        if n["warrant"]["type"] != "computed":
            continue
        span = n["sourceRef"]["span"]
        assert e.source_text[span["start"]:span["end"]] == \
            n["canonicalPayload"]["surface"]


def test_nuggets_are_kko_typed():
    e = ex.extract(TEXT.encode(), filename="a.txt")
    out = builder.build(e, doc_ref="urn:srcos:document:t", run_ref="urn:srcos:run:t",
                        clock=lambda: "2026-07-29T00:00:00.000Z", logical_start=0,
                        extra_kko_type_refs=["https://schemas.srcos.ai/ont/ifm/Filing"])
    quotes = [n for n in out if n["warrant"]["type"] == "direct-quote"]
    computed = [n for n in out if n["warrant"]["type"] == "computed"]
    assert all(contract.KKO_WRITTEN_INFO in n["kkoTypeRefs"] for n in quotes)
    assert all(contract.KKO_QUANTITY in n["kkoTypeRefs"] for n in computed)
    assert all("https://schemas.srcos.ai/ont/ifm/Filing" in n["kkoTypeRefs"] for n in out)
