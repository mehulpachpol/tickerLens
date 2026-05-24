from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from io import BytesIO

import pymupdf
import pytesseract
from PIL import Image

from tickerlens_api.settings import settings


@dataclass(frozen=True)
class PageText:
    page_num: int
    text: str
    extraction_method: str  # "text" | "ocr"
    checksum: str
    char_count: int


def _normalize_text(text: str) -> str:
    # Keep normalization minimal to preserve traceability while removing common PDF/OCR artifacts.
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _needs_ocr(text: str) -> bool:
    # If a PDF page is scanned, text extraction usually returns empty / near-empty output.
    non_ws = sum(1 for ch in text if not ch.isspace())
    return non_ws < settings.parse_text_min_chars_for_digital


def _ocr_page(page: pymupdf.Page) -> str:
    # Render to an image and OCR using Tesseract.
    pix = page.get_pixmap(dpi=settings.ocr_dpi)
    png_bytes = pix.tobytes("png")
    image = Image.open(BytesIO(png_bytes))
    return pytesseract.image_to_string(image, lang=settings.ocr_language)


def extract_page_texts(pdf_path: str) -> list[PageText]:
    results: list[PageText] = []
    with pymupdf.open(pdf_path) as doc:
        for i in range(doc.page_count):
            page = doc.load_page(i)
            text = page.get_text("text")
            text = _normalize_text(text)
            method = "text"

            if _needs_ocr(text):
                try:
                    text = _normalize_text(_ocr_page(page))
                    method = "ocr"
                except Exception:
                    # If OCR fails, keep whatever we got from normal extraction.
                    method = "text"

            checksum = _sha256_text(text)
            results.append(
                PageText(
                    page_num=i + 1,
                    text=text,
                    extraction_method=method,
                    checksum=checksum,
                    char_count=len(text),
                )
            )
    return results


def download_s3_pdf_to_temp(*, bucket: str, key: str, downloader) -> str:
    """
    Create a temp file path for a PDF and download into it.

    `downloader(bucket, key, path)` is injected to keep S3 logic out of this module.
    """

    _, path = tempfile.mkstemp(prefix="tickerlens-doc-", suffix=os.path.splitext(key)[-1] or ".pdf")
    try:
        downloader(bucket=bucket, key=key, path=path)
        return path
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise

