"""Run extraction and verification on one lease file and print the result.

uv run python scripts/extract_lease.py ../samples/leases/01-clean-mc-b-1204.txt
"""

import asyncio
import sys
from pathlib import Path

from truelinks.modules.lease.extraction import extract_lease
from truelinks.modules.lease.verification import verify_extraction
from truelinks.platform.llm.config import LLMSettings
from truelinks.platform.llm.openai_compatible import OpenAICompatibleProvider


async def main(path: Path) -> None:
    lease_text = path.read_text(encoding="utf-8")
    llm = OpenAICompatibleProvider(LLMSettings())

    result = await extract_lease(llm, lease_text)

    for field in verify_extraction(result.data, lease_text):
        issue = field.issue or ""
        print(f"{field.name:<20} {field.status:<11} {issue:<22} {field.value!s:.70}")

    seconds = result.duration_ms / 1000
    print(
        f"\n{result.model}: {seconds:.1f}s, "
        f"{result.input_tokens} tokens in, {result.output_tokens} out"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(Path(sys.argv[1])))
