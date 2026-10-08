import shutil
from io import BytesIO

import pytest
from PIL import Image, ImageDraw, ImageFont

from truelinks.modules.lease.documents import ReadMethod, UnreadableDocumentError, read_document

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="Tesseract is not installed"
)


def scanned_pdf(lines: list[str]) -> bytes:
    """A PDF that is only an image, like a scan: no text layer at all."""
    page = Image.new("RGB", (1240, 1754), "white")  # A4 at 150 DPI
    draw = ImageDraw.Draw(page)
    font = ImageFont.load_default(size=36)
    for row, line in enumerate(lines):
        draw.text((120, 160 + row * 70), line, fill="black", font=font)
    buffer = BytesIO()
    page.save(buffer, format="PDF", resolution=150)
    return buffer.getvalue()


def test_plain_text_is_read_as_it_is() -> None:
    document = read_document("lease.txt", b"TENANT: Sara Haddad")

    assert document.text == "TENANT: Sara Haddad"
    assert document.method is ReadMethod.TEXT
    assert document.signature_page is None


@needs_tesseract
def test_scanned_pdf_is_read_with_ocr() -> None:
    content = scanned_pdf(["TENANT: Lina Farouk", "The annual rent is QAR 84,000."])

    document = read_document("scan.pdf", content)

    assert document.method is ReadMethod.OCR
    assert "Lina Farouk" in document.text
    assert "84,000" in document.text
    assert (document.signature_page or b"").startswith(b"\x89PNG")


@needs_tesseract
def test_blank_scan_is_refused() -> None:
    with pytest.raises(UnreadableDocumentError, match="no readable text"):
        read_document("blank.pdf", scanned_pdf([]))
