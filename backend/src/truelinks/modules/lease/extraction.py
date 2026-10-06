from truelinks.modules.lease.schema import LeaseExtraction
from truelinks.platform.llm.types import LLMProvider, StructuredRequest, StructuredResult

LEASE_EXTRACT_TASK = "lease.extract"

SYSTEM_PROMPT = """\
You read a residential lease and fill in a structured record.

Rules:
- Use only what the lease text states. If the lease does not state a field, set its value and \
quote to null. Never guess.
- Never calculate or derive a value. Report figures and dates exactly as the lease gives them.
- For every value, "quote" is the shortest passage from the lease that states it: at most one \
sentence, copied character for character. Do not paraphrase, shorten with "...", or join separate \
passages.
- The quote must be about that field. A deposit amount is not evidence for the rent, even if the \
numbers are equal.
- Write date values in ISO format (YYYY-MM-DD). The quote keeps the lease's own wording.
- A party has signed when its signature line carries a mark such as "/s/ Name", "Signed: Name" \
or "[signature]": value true, quote that line. A blank signature line is false. Use null only \
when the lease has no signature line for that party.
"""


async def extract_lease(llm: LLMProvider, lease_text: str) -> StructuredResult[LeaseExtraction]:
    """Step 1 of the lease pipeline: the model reads, it does not judge."""
    return await llm.generate_structured(
        StructuredRequest(
            task=LEASE_EXTRACT_TASK,
            system=SYSTEM_PROMPT,
            prompt=f"<lease>\n{lease_text}\n</lease>",
            schema=LeaseExtraction,
        )
    )
