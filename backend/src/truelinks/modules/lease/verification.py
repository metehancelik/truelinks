"""Layers 1 and 2 of verification: deterministic checks on each extracted field.

Layer 1: the quote exists in the document.
Layer 2: the value is what the quote says.

Whether the quote is about the right thing is a question of meaning and is
left to the evaluator (layer 3).
"""

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from truelinks.modules.lease.schema import Extracted, FieldValue, LeaseExtraction


class FieldStatus(StrEnum):
    """Computed trust in one extracted field. Never reported by the model."""

    VERIFIED = "VERIFIED"  # the quote is in the document and agrees with the value
    UNVERIFIED = "UNVERIFIED"  # there is a value, but its source could not be confirmed
    MISSING = "MISSING"  # the model found no value in the lease


class VerificationIssue(StrEnum):
    """Why a field is UNVERIFIED."""

    # Found by code (layers 1 and 2).
    NO_QUOTE = "NO_QUOTE"  # a value without a quote
    QUOTE_NOT_IN_DOCUMENT = "QUOTE_NOT_IN_DOCUMENT"  # possibly invented
    VALUE_NOT_IN_QUOTE = "VALUE_NOT_IN_QUOTE"  # possibly misread

    # Raised by the evaluator (layer 3).
    WRONG_SOURCE = "WRONG_SOURCE"  # the quote is about a different field
    CONTRADICTION = "CONTRADICTION"  # the lease states conflicting values
    IMPLAUSIBLE = "IMPLAUSIBLE"  # the value looks wrong on its face


@dataclass(frozen=True)
class VerifiedField:
    name: str
    value: FieldValue | None
    quote: str | None
    status: FieldStatus
    issue: VerificationIssue | None = None
    # The evaluator's one-sentence reason, when it raised the issue.
    explanation: str | None = None


# Free-text fields whose value should appear word for word in the quote.
# Other text fields (summaries, codes) are interpretations of the quote.
LITERAL_FIELDS = frozenset({"landlord_name", "tenant_name", "unit_reference"})


def verify_extraction(extraction: LeaseExtraction, document_text: str) -> list[VerifiedField]:
    document = _normalize(document_text)
    return [
        _verify_field(name, getattr(extraction, name), document)
        for name in LeaseExtraction.model_fields
    ]


def _verify_field(name: str, field: Extracted[FieldValue], document: str) -> VerifiedField:
    value, quote = field.value, field.quote

    if value is None:
        return VerifiedField(name, None, quote, FieldStatus.MISSING)

    if not quote or not quote.strip():
        issue = VerificationIssue.NO_QUOTE
    elif _normalize(quote) not in document:
        issue = VerificationIssue.QUOTE_NOT_IN_DOCUMENT
    elif not _quote_supports_value(name, value, quote):
        issue = VerificationIssue.VALUE_NOT_IN_QUOTE
    else:
        return VerifiedField(name, value, quote, FieldStatus.VERIFIED)

    return VerifiedField(name, value, quote, FieldStatus.UNVERIFIED, issue)


def _quote_supports_value(name: str, value: FieldValue, quote: str) -> bool:
    match value:
        case bool():  # before int: bool is a subclass of int
            return True
        case int() | float():
            return float(value) in _numbers_in(quote)
        case date():
            return _quote_states_date(quote, value)
        case str() if name in LITERAL_FIELDS:
            return _normalize(value) in _normalize(quote)
        case str():
            return True


_TYPOGRAPHIC = str.maketrans(
    {
        "\N{LEFT SINGLE QUOTATION MARK}": "'",
        "\N{RIGHT SINGLE QUOTATION MARK}": "'",
        "\N{LEFT DOUBLE QUOTATION MARK}": '"',
        "\N{RIGHT DOUBLE QUOTATION MARK}": '"',
        "\N{EN DASH}": "-",
        "\N{EM DASH}": "-",
    }
)


def _normalize(text: str) -> str:
    """Flatten case, whitespace and typographic punctuation.

    PDF text and model output never match byte for byte; this makes them
    comparable without accepting different wording.
    """
    return " ".join(text.translate(_TYPOGRAPHIC).split()).lower()


def _numbers_in(text: str) -> list[float]:
    """'QAR 9,500.00 per month' -> [9500.0]"""
    return [float(match.replace(",", "")) for match in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]


_MONTH_NAMES = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)  # fmt: skip


def _quote_states_date(quote: str, expected: date) -> bool:
    """True when the quote names the same year, month and day in any common form.

    Accepts "1 January 2027", "Jan 1, 2027" and "01/01/2027".
    """
    text = _normalize(quote)
    numbers = _numbers_in(text)
    month_name = _MONTH_NAMES[expected.month - 1]

    has_month_name = month_name in text or re.search(rf"\b{month_name[:3]}\b", text) is not None
    # A numeric date carries the month as a number, in addition to the day.
    needed = 2 if expected.day == expected.month else 1
    has_month_number = numbers.count(expected.month) >= needed

    return (
        expected.year in numbers
        and expected.day in numbers
        and (has_month_name or has_month_number)
    )
