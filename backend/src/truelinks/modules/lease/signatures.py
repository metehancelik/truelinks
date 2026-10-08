"""Signatures on a scanned lease, checked by looking at the page.

OCR reads letters; a handwritten signature is not letters, so the text of a
scan cannot say whether a party signed. For scanned leases the vision model
looks at the signature page instead. Its answer is a judgement on an image,
which code cannot verify, so it always goes to a person as UNVERIFIED.
"""

from dataclasses import replace

from pydantic import BaseModel, Field

from truelinks.modules.lease.verification import FieldStatus, VerifiedField
from truelinks.platform.llm.types import (
    LLMImage,
    LLMProvider,
    StructuredRequest,
    StructuredResult,
)

LEASE_SIGNATURES_TASK = "lease.signatures"

SYSTEM_PROMPT = """\
You look at the signature page of a scanned lease and say whether each party signed it.

Rules:
- A party has signed when there is a handwritten signature, initials, a typed /s/ mark or a \
company stamp on or next to that party's signature line.
- An empty line, a printed name alone, or a blank box is not a signature.
- If the page has no signature line for a party, that party has not signed.
- Describe in one sentence what you see on each party's line.
"""


class SignatureCheck(BaseModel):
    landlord_signed: bool
    tenant_signed: bool
    explanation: str = Field(description="What is on each party's signature line, one sentence")


async def check_signatures(
    llm: LLMProvider, signature_page: LLMImage
) -> StructuredResult[SignatureCheck]:
    return await llm.generate_structured(
        StructuredRequest(
            task=LEASE_SIGNATURES_TASK,
            system=SYSTEM_PROMPT,
            prompt="This is the last page of the lease. Has each party signed it?",
            schema=SignatureCheck,
            images=[signature_page],
        )
    )


def apply_signatures(fields: list[VerifiedField], check: SignatureCheck) -> list[VerifiedField]:
    """Replace what the text said about the signatures with what the page shows."""
    seen = {"landlord_signed": check.landlord_signed, "tenant_signed": check.tenant_signed}
    return [
        replace(
            field,
            value=seen[field.name],
            status=FieldStatus.UNVERIFIED,
            issue=None,
            explanation=(
                f"Read from the scanned signature page: {check.explanation} "
                "Check the page before accepting."
            ),
        )
        if field.name in seen
        else field
        for field in fields
    ]
