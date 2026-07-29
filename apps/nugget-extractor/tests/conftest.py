"""Shared fixtures: a minimal hand-built PDF, so the PDF text-layer path is exercised
with a REAL PDF and no extra dependency (reportlab et al. are not runtime pins and must
not become test-only ones — the closure in requirements.txt is the closure)."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[list[str]]) -> bytes:
    """A minimal, uncompressed PDF 1.4 with a Helvetica text layer. `pages` is a list of
    pages, each a list of lines. An empty line list yields a page with NO text layer —
    which is what a scan looks like to pypdf, and what OcrRequired is raised for."""
    objs: list[str] = []
    n = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objs.append("<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>")
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, lines in enumerate(pages):
        content_no = 5 + 2 * i
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_no} 0 R >>")
        body = ("BT /F1 12 Tf 72 720 Td 14 TL\n"
                + "\n".join(f"({_escape(l)}) Tj T*" for l in lines) + "\nET")
        objs.append(f"<< /Length {len(body)} >>\nstream\n{body}\nendstream")
    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(buf.tell())
        buf.write(f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1"))
    xref = buf.tell()
    buf.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        buf.write(f"{off:010d} 00000 n \n".encode())
    buf.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
              f"startxref\n{xref}\n%%EOF\n".encode())
    return buf.getvalue()


@pytest.fixture
def pdf_bytes() -> bytes:
    return make_pdf([["Network sales grew 22.6% to AUD 1,138.9 million.",
                      "Comparable sales growth was 9.4 per cent."],
                     ["Store rollout continued across 2025."]])


@pytest.fixture
def scanned_pdf_bytes() -> bytes:
    """Pages, no text layer — a scan."""
    return make_pdf([[], []])
