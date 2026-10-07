from io import BytesIO

from pypdf import PdfReader


class UnreadableDocumentError(ValueError):
    """The upload has no text the agent can read."""


def read_document(filename: str, content: bytes) -> str:
    """Return the text of an uploaded lease (PDF with a text layer, or plain text)."""
    if filename.lower().endswith(".pdf"):
        pages = PdfReader(BytesIO(content)).pages
        text = "\n".join(page.extract_text() or "" for page in pages)
    else:
        text = content.decode("utf-8", errors="replace")

    if not text.strip():
        # A scanned PDF is images only. OCR or the vision model is the next step.
        raise UnreadableDocumentError(
            f"{filename} contains no text. Scanned documents are not supported yet."
        )
    return text
