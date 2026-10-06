"""Run the lease pipeline on one file and print each step's result.

uv run python scripts/extract_lease.py ../samples/leases/01-clean-mc-b-1204.txt
"""

import asyncio
import sys
from pathlib import Path

from truelinks.modules.lease.extraction import extract_lease
from truelinks.modules.lease.rules import evaluate_rules, load_ruleset
from truelinks.modules.lease.verification import verify_extraction
from truelinks.modules.unit.records import load_units
from truelinks.platform.llm.config import LLMSettings
from truelinks.platform.llm.openai_compatible import OpenAICompatibleProvider

DATA = Path(__file__).parents[2] / "data"


async def main(path: Path) -> None:
    lease_text = path.read_text(encoding="utf-8")
    llm = OpenAICompatibleProvider(LLMSettings())

    result = await extract_lease(llm, lease_text)
    fields = verify_extraction(result.data, lease_text)

    print("FIELDS")
    for field in fields:
        issue = field.issue or ""
        print(f"  {field.name:<20} {field.status:<11} {issue:<22} {field.value!s:.60}")

    print("\nRULES")
    ruleset = load_ruleset(DATA / "owner_ruleset.json")
    units = load_units(DATA / "units.json")
    for outcome in evaluate_rules(ruleset, fields, units):
        print(f"  {outcome.rule.id}  {outcome.outcome:<17} {outcome.reason}")

    seconds = result.duration_ms / 1000
    print(
        f"\n{result.model}: {seconds:.1f}s, "
        f"{result.input_tokens} tokens in, {result.output_tokens} out"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(Path(sys.argv[1])))
