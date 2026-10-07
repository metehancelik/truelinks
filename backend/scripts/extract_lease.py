"""Run the lease agent on one file and print each step's result.

uv run python scripts/extract_lease.py ../samples/leases/01-clean-mc-b-1204.txt
"""

import asyncio
import sys
from pathlib import Path

from truelinks.modules.lease.pipeline import analyse_lease
from truelinks.modules.lease.rules import load_ruleset
from truelinks.modules.unit.records import load_units
from truelinks.platform.llm.config import LLMSettings
from truelinks.platform.llm.openai_compatible import OpenAICompatibleProvider

DATA = Path(__file__).parents[2] / "data"


async def main(path: Path) -> None:
    llm = OpenAICompatibleProvider(LLMSettings())
    analysis = await analyse_lease(
        llm,
        path.read_text(encoding="utf-8"),
        load_ruleset(DATA / "owner_ruleset.json"),
        load_units(DATA / "units.json"),
    )

    print("FIELDS")
    for field in analysis.fields:
        issue = field.issue or ""
        print(f"  {field.name:<20} {field.status:<11} {issue:<22} {field.value!s:.60}")
        if field.explanation:
            print(f"  {'':<20} {field.explanation}")

    print("\nRULES")
    for result in analysis.rules:
        print(f"  {result.rule.id}  {result.outcome:<17} {result.reason}")

    print("\nTRACE")
    for step in analysis.trace:
        tokens = f"{step.input_tokens} in, {step.output_tokens} out" if step.model else ""
        seconds = step.duration_ms / 1000
        print(f"  {step.name:<8} {step.model or 'code':<14} {seconds:>6.1f}s  {tokens}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(Path(sys.argv[1])))
