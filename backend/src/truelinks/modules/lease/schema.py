"""What the model returns when it reads a lease."""

from datetime import date
from typing import Literal, cast

from pydantic import BaseModel, Field

type PaymentFrequency = Literal["monthly", "quarterly", "semi-annual", "annual", "other"]
type FieldValue = str | int | float | bool | date


class Extracted[T](BaseModel):
    """One lease field: the value the model read and the text it read it from.

    Both are null when the lease does not say. The model never reports its own
    confidence; whether a field can be trusted is computed afterwards from the
    quote (see `verification`).
    """

    value: T | None
    quote: str | None = Field(
        description="Verbatim text copied from the lease that states this value. No paraphrasing."
    )


class LeaseExtraction(BaseModel):
    landlord_name: Extracted[str] = Field(description="Full legal name of the landlord / lessor")
    tenant_name: Extracted[str] = Field(description="Full legal name of the tenant / lessee")
    landlord_signed: Extracted[bool] = Field(
        description="Whether the lease shows the landlord's signature"
    )
    tenant_signed: Extracted[bool] = Field(
        description="Whether the lease shows the tenant's signature"
    )

    unit_reference: Extracted[str] = Field(
        description="The leased unit exactly as the lease names it, including building"
    )

    commencement_date: Extracted[date] = Field(
        description="Date the lease term starts, as an ISO date YYYY-MM-DD"
    )
    expiry_date: Extracted[date] = Field(
        description="Date the lease term ends, as an ISO date YYYY-MM-DD"
    )
    term_months: Extracted[int] = Field(
        description=(
            "Length of the term in months, as the lease states it. "
            "Do not calculate it from the dates."
        )
    )

    monthly_rent: Extracted[float] = Field(
        description="Rent per month as a plain number, only if the lease states a monthly figure"
    )
    annual_rent: Extracted[float] = Field(
        description="Rent per year as a plain number, only if the lease states an annual figure"
    )
    currency: Extracted[str] = Field(description="Three-letter currency code of the rent, e.g. QAR")
    payment_frequency: Extracted[PaymentFrequency] = Field(description="How often rent is paid")
    deposit_amount: Extracted[float] = Field(description="Security deposit as a plain number")

    escalation_clause: Extracted[str] = Field(
        description="How future rent increases are determined, in one sentence"
    )
    renewal_terms: Extracted[str] = Field(description="How the lease renews, in one sentence")
    termination_terms: Extracted[str] = Field(
        description="How either party may end the lease early, in one sentence"
    )


def parse_field_value(name: str, raw: object) -> FieldValue | None:
    """Turn a stored or human-entered JSON value into the field's own type.

    A corrected date arrives as text and a rent may arrive as "9500"; the
    field's declared type decides, exactly as it does for the model's answer.
    """
    extracted = cast(type[Extracted[FieldValue]], LeaseExtraction.model_fields[name].annotation)
    return extracted.model_validate({"value": raw, "quote": None}).value


def to_json_value(value: FieldValue | None) -> str | int | float | bool | None:
    return value.isoformat() if isinstance(value, date) else value
