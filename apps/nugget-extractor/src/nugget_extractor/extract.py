"""Document bytes → one normalized source text + spanned blocks. No model, no guessing.

THE EXTRACTION GRAIN. Every span this module reports is a character offset into ONE
normalized source text, and that same text is what `contract.content_hash` hashes — so a
nugget's (contentHash, start, end) triple is checkable by anyone who can re-derive the
text, and offsets can never silently drift (contract §1).

Normalization is deterministic and stated, because the hash is over its OUTPUT, not over
the raw bytes:
  1. decode UTF-8 (errors="replace" — a decode failure must not be silent data loss),
  2. CRLF / CR → LF,
  3. strip trailing whitespace per line,
  4. collapse 3+ consecutive newlines to exactly 2 (paragraph separator),
  5. strip leading/trailing whitespace of the whole document.
The raw-byte sha256 is reported alongside, so the chain document-bytes → normalized-text
→ span is complete; the graph's document node carries both.

WHAT IS REAL HERE
  text/plain, text/markdown       real — decode + normalize.
  application/pdf (text layer)    real — pypdf per-page extract_text(), pages joined by
                                  the paragraph separator, page boundaries tracked so
                                  every block reports its 1-based page.

WHAT IS DEFERRED, AND WHY — OCR (scanned / image-only documents)
  NOT IMPLEMENTED. This service ships NO OCR and does not pretend to: a PDF whose pages
  carry no text layer raises `OcrRequired`, which the server answers as an explicit 422
  naming the gap, and /healthz counts it (`ocr_required`). It is never a silently empty
  extraction and never a stub that looks like OCR.
  Why deferred rather than pinned: every credible engine (tesseract + langpacks,
  PaddleOCR, RapidOCR) adds 300 MB–1.5 GB of native binaries, model weights and apt
  layers to a 130 MB python:3.11-slim image, and the weights would have to be vendored
  and digest-pinned to keep the build hermetic and the estate's no-CDN rule. That is a
  deliberate, sized decision — not this service's first commit.
  The seam is one function: `OCR_BACKENDS` maps a backend name to a callable
  `(bytes) -> str`. It contains exactly one entry today, "none", which raises. Setting
  OCR_BACKEND to anything unregistered fails LOUDLY at import (`UnsupportedOcrBackend`),
  so a deployment cannot believe it has OCR when it does not. Adding one is: pin the
  dependency, register the callable, size the image, extend this docstring.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
from dataclasses import dataclass
from typing import Callable

TEXT_MEDIA = ("text/plain", "text/markdown", "text/x-markdown")
PDF_MEDIA = "application/pdf"

PARAGRAPH_SEP = "\n\n"
# Sentence boundary: a ., ! or ? followed by whitespace. Deliberately simple and
# language-agnostic; the fallback grain is the paragraph, and a mis-split only changes
# where a quote ends, never whether it is verbatim (the span is still cut from source).
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_TRAILING_WS = re.compile(r"[ \t]+$", re.MULTILINE)
_MANY_NEWLINES = re.compile(r"\n{3,}")
# A paragraph is a run of non-blank lines: normalization has already made the blank line
# THE separator, so this needs no lookahead games.
_PARAGRAPH = re.compile(r"[^\n]+(?:\n[^\n]+)*")


class ExtractError(ValueError):
    """The document cannot be turned into text. Honest error, never a crash, never an
    empty success."""


class UnsupportedMedia(ExtractError):
    pass


class OcrRequired(ExtractError):
    """A PDF with pages but no text layer — a scan. This service ships no OCR (see the
    module docstring); the document is REJECTED, loudly, and counted."""


class UnsupportedOcrBackend(RuntimeError):
    """OCR_BACKEND names a backend that does not exist. Fails at import, not at the first
    scanned page, so no deployment can believe it has OCR that it does not have."""


def _no_ocr(_raw: bytes) -> str:
    raise OcrRequired(
        "this document needs OCR (no text layer) and nugget-extractor ships no OCR "
        "backend; OCR_BACKEND=none. See extract.py OCR_BACKENDS for the seam.")


# The seam. name -> (bytes) -> extracted text. One entry today, and it refuses.
OCR_BACKENDS: dict[str, Callable[[bytes], str]] = {"none": _no_ocr}
OCR_BACKEND = os.getenv("OCR_BACKEND", "none")
if OCR_BACKEND not in OCR_BACKENDS:
    raise UnsupportedOcrBackend(
        f"OCR_BACKEND={OCR_BACKEND!r} is not implemented. Registered backends: "
        f"{sorted(OCR_BACKENDS)}. nugget-extractor ships NO OCR — do not configure one "
        "until a real backend is pinned in requirements.txt and registered here.")


@dataclass(frozen=True)
class Block:
    """One spanned unit of the normalized source text. `text` is redundant with
    source_text[start:end] and kept only for readability — the emitter always re-cuts
    from the source, so a divergence here can never become a false quote."""
    start: int
    end: int
    page: int
    text: str


@dataclass(frozen=True)
class Extraction:
    source_text: str
    raw_sha256: str
    media_type: str
    pages: int
    blocks: list[Block]


# Magic bytes for binary formats this service cannot read. Sniffing MUST recognise these
# rather than fall through to text/plain: a PNG decoded with errors="replace" yields
# mojibake that extracts cleanly into perfectly well-formed nuggets quoting garbage — a
# silent-wrong result, which is worse than a refusal.
_BINARY_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"), (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
    (b"II*\x00", "image/tiff"), (b"MM\x00*", "image/tiff"),
    (b"RIFF", "application/octet-stream"),      # webp/wav/avi container
    (b"PK\x03\x04", "application/zip"),         # docx/pptx/xlsx and friends
    (b"\x1f\x8b", "application/gzip"),
    (b"%!PS", "application/postscript"),
    (b"\x7fELF", "application/octet-stream"),
)


def sniff_media(filename: str, raw: bytes) -> str:
    """Magic bytes first (filenames lie), extension as the tiebreak — same order the
    compute-gateway ingest adapter uses, so the two agree on what a document is.

    Unlike that adapter, an UNRECOGNISED binary must not fall through to text/plain here:
    this service's output is quoted text, and decoding arbitrary bytes with
    errors="replace" would mint syntactically perfect nuggets quoting replacement
    characters. So anything holding a NUL byte — which valid UTF-8 text never does
    outside deliberate embedding — is declared binary and refused."""
    if raw[:5] == b"%PDF-":
        return PDF_MEDIA
    for magic, media in _BINARY_MAGIC:
        if raw.startswith(magic):
            return media
    if b"\x00" in raw[:8192]:
        return "application/octet-stream"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("md", "markdown"):
        return "text/markdown"
    return "text/plain"


def normalize(text: str) -> str:
    """The 5 stated steps. Idempotent: normalize(normalize(x)) == normalize(x)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_WS.sub("", text)
    text = _MANY_NEWLINES.sub(PARAGRAPH_SEP, text)
    return text.strip()


def _pdf_pages(raw: bytes) -> list[str]:
    from pypdf import PdfReader  # lazy: only the PDF path needs it
    try:
        reader = PdfReader(io.BytesIO(raw))
        return [(page.extract_text() or "") for page in reader.pages]
    except OcrRequired:
        raise
    except Exception as e:  # noqa: BLE001 — a corrupt PDF is an honest error, not a 500
        raise ExtractError(f"pdf parse failed: {e}") from e


def _trim(text: str, start: int) -> tuple[int, int]:
    """(absolute start, absolute end) of `text` with surrounding whitespace trimmed."""
    lead = len(text) - len(text.lstrip())
    return start + lead, start + len(text.rstrip())


def _sentence_spans(para: str) -> list[tuple[int, int]]:
    """Sentence spans RELATIVE to `para`, taken from match positions — never from
    `.find()`, so a sentence repeated in the same paragraph gets its own span instead of
    collapsing onto the first occurrence."""
    spans, pos = [], 0
    for m in _SENTENCE_END.finditer(para):
        if para[pos:m.start()].strip():
            spans.append(_trim(para[pos:m.start()], pos))
        pos = m.end()
    if para[pos:].strip():
        spans.append(_trim(para[pos:], pos))
    return spans


def _blocks(source_text: str, page_bounds: list[tuple[int, int, int]],
            grain: str) -> list[Block]:
    """Cut the normalized text into spanned blocks, offsets exact by construction.

    A paragraph is a run of non-blank lines (normalization has already made the blank
    line THE separator). Sentence grain splits each paragraph further. Every span is an
    absolute offset into `source_text`, taken from regex match positions."""
    out: list[Block] = []
    for m in _PARAGRAPH.finditer(source_text):
        p_start, para = m.start(), m.group()
        pairs = ([(p_start + a, p_start + b) for a, b in _sentence_spans(para)]
                 if grain == "sentence" else [_trim(para, p_start)])
        for start, end in pairs:
            if end > start:
                out.append(Block(start, end, _page_of(start, page_bounds),
                                 source_text[start:end]))
    return out


def _page_of(offset: int, page_bounds: list[tuple[int, int, int]]) -> int:
    for page, start, end in page_bounds:
        if start <= offset < end:
            return page
    return page_bounds[-1][0] if page_bounds else 1


def extract(raw: bytes, *, filename: str = "", media_type: str | None = None,
            grain: str = "paragraph") -> Extraction:
    """Document bytes → normalized source text + spanned blocks.

    Raises UnsupportedMedia for anything that is not text/markdown/PDF, OcrRequired for a
    PDF with pages but no text layer, ExtractError for a corrupt or empty document.
    Never returns a successful-looking empty extraction."""
    if not raw:
        raise ExtractError("empty document")
    media = media_type or sniff_media(filename, raw)
    raw_sha = hashlib.sha256(raw).hexdigest()

    if media == PDF_MEDIA:
        pages = _pdf_pages(raw)
        if not pages:
            raise ExtractError("pdf has no pages")
        if not any(p.strip() for p in pages):
            # A scan. The seam is called so a future registered backend takes over here
            # and nowhere else; today it raises OcrRequired.
            OCR_BACKENDS[OCR_BACKEND](raw)
            raise OcrRequired("pdf has pages but no text layer")  # pragma: no cover
        # Join the pages that carry text, tracking each one's half-open char range in the
        # joined text so every block can report its 1-based page. Empty pages are skipped
        # (joining them would inject separator runs the normalizer just collapsed) but
        # still counted in `pages` — the page NUMBERS stay the document's own.
        parts: list[str] = []
        page_bounds: list[tuple[int, int, int]] = []
        cursor = 0
        for pno, page_text in enumerate(pages, 1):
            piece = normalize(page_text)
            if not piece:
                continue
            if parts:
                cursor += len(PARAGRAPH_SEP)
            parts.append(piece)
            page_bounds.append((pno, cursor, cursor + len(piece) + len(PARAGRAPH_SEP)))
            cursor += len(piece)
        source_text = PARAGRAPH_SEP.join(parts)
        n_pages = len(pages)
    elif media in TEXT_MEDIA or media.startswith("text/"):
        source_text = normalize(raw.decode("utf-8", errors="replace"))
        page_bounds = [(1, 0, len(source_text) + 1)]
        n_pages = 1
    else:
        raise UnsupportedMedia(
            f"unsupported media type {media!r}; nugget-extractor handles "
            f"{PDF_MEDIA} (text layer) and text/* — image formats need OCR, which this "
            "service does not ship (see extract.py OCR_BACKENDS)")

    if not source_text.strip():
        raise ExtractError("document normalized to empty text")
    blocks = _blocks(source_text, page_bounds, grain)
    if not blocks:
        raise ExtractError("no extractable blocks")
    return Extraction(source_text=source_text, raw_sha256=raw_sha, media_type=media,
                      pages=n_pages, blocks=blocks)


__all__ = ["Block", "Extraction", "ExtractError", "OcrRequired", "UnsupportedMedia",
           "UnsupportedOcrBackend", "OCR_BACKEND", "OCR_BACKENDS", "PDF_MEDIA",
           "TEXT_MEDIA", "extract", "normalize", "sniff_media"]
