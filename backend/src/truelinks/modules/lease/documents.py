"""Turn an uploaded lease into the text the agent reads and quotes from."""

import time
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from pathlib import Path
from typing import cast

# Neither library ships complete type hints; their calls are kept in _page_text.
import pypdfium2 as pdfium  # pyright: ignore[reportMissingTypeStubs]
import pytesseract  # pyright: ignore[reportMissingTypeStubs]
from PIL.Image import Image
from pypdf import PdfReader

# Tesseract reads best at around 300 DPI; PDF pages are measured at 72.
OCR_SCALE = 300 / 72
# The signature page is shown to the vision model; it needs less detail than OCR.
SIGNATURE_PAGE_SCALE = 150 / 72
MAX_OCR_PAGES = 20


class UnreadableDocumentError(ValueError):
    """The upload has no text the agent can read."""


class ReadMethod(StrEnum):
    TEXT = "text"  # plain text file
    PDF_TEXT = "pdf_text"  # the PDF's own text layer
    OCR = "ocr"  # a scanned PDF, read by Tesseract


@dataclass(frozen=True)
class Document:
    text: str
    method: ReadMethod
    duration_ms: int
    # A scan's last page as PNG: the vision model checks the signatures on it.
    signature_page: bytes | None = None


def read_document(filename: str, content: bytes) -> Document:
    """Return the text of an uploaded lease, falling back to OCR for scanned PDFs.

    The text returned here is what every quote is checked against, so OCR
    mistakes are visible: a quote can only be as good as this text.
    """
    started = time.perf_counter()
    signature_page = None

    if not filename.lower().endswith(".pdf"):
        text, method = content.decode("utf-8", errors="replace"), ReadMethod.TEXT
    else:
        text, method = _pdf_text_layer(content), ReadMethod.PDF_TEXT
        if not text.strip():
            text, signature_page = _ocr(filename, content)
            method = ReadMethod.OCR

    if not text.strip():
        raise UnreadableDocumentError(f"{filename} contains no readable text.")
    duration_ms = round((time.perf_counter() - started) * 1000)
    return Document(text, method, duration_ms, signature_page)


def _pdf_text_layer(content: bytes) -> str:
    pages = PdfReader(BytesIO(content)).pages
    return "\n".join(page.extract_text() or "" for page in pages)


def _ocr(filename: str, content: bytes) -> tuple[str, bytes]:
    """The text of every page, and the last page as an image for the signature check."""
    pdf = pdfium.PdfDocument(content)
    if len(pdf) > MAX_OCR_PAGES:
        raise UnreadableDocumentError(
            f"{filename} is a scanned document of {len(pdf)} pages; "
            f"OCR is limited to {MAX_OCR_PAGES}."
        )
    try:
        text = "\n".join(_page_text(page) for page in pdf)
        return text, _page_png(pdf[len(pdf) - 1])
    except pytesseract.TesseractNotFoundError as error:
        raise UnreadableDocumentError(
            f"{filename} is a scanned document and OCR is not installed on this server."
        ) from error
    finally:
        pdf.close()


def _page_text(page: pdfium.PdfPage) -> str:
    text = pytesseract.image_to_string(_render(page, OCR_SCALE))  # pyright: ignore[reportUnknownMemberType]
    return str(text)


def _page_png(page: pdfium.PdfPage) -> bytes:
    buffer = BytesIO()
    _render(page, SIGNATURE_PAGE_SCALE).save(buffer, format="PNG")
    return buffer.getvalue()


def _render(page: pdfium.PdfPage, scale: float) -> Image:
    bitmap = page.render(scale=scale)  # pyright: ignore[reportArgumentType, reportUnknownMemberType, reportUnknownVariableType]
    return cast(Image, bitmap.to_pil())  # pyright: ignore[reportUnknownMemberType]


def signature_page_path(uploads_dir: Path, lease_id: str) -> Path:
    return uploads_dir / f"lease-{lease_id}-signature-page.png"
