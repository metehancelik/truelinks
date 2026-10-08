"""Run the lease agent on every evaluation case and score it.

uv run python scripts/run_evals.py                  # the model in .env
uv run python scripts/run_evals.py --stub           # canned answers: checks the harness only
uv run python scripts/run_evals.py --case problems  # one case
uv run python scripts/run_evals.py --out report.json
"""

import argparse
import asyncio
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from truelinks.evals.lease import CaseResult, load_cases, run_case, summarise
from truelinks.modules.lease.demo import register_demo_leases
from truelinks.modules.lease.rules import load_ruleset
from truelinks.modules.unit.records import load_units
from truelinks.platform.llm.config import LLMSettings
from truelinks.platform.llm.openai_compatible import OpenAICompatibleProvider
from truelinks.platform.llm.stub import StubProvider
from truelinks.platform.llm.types import LLMProvider

ROOT = Path(__file__).parents[2]
CASES = ROOT / "evals" / "leases" / "cases.json"


def print_case(result: CaseResult) -> None:
    print(f"\n{result.case.name}  ({result.case.tests})")
    if result.error:
        print(f"  ERROR {result.error}")
        return
    right = sum(f.correct for f in result.fields)
    print(
        f"  fields {right}/{len(result.fields)} right, "
        f"rules {len(result.rules) - len(result.rules_wrong)}/{len(result.rules)} right, "
        f"{result.seconds:.0f}s, {result.tokens} tokens"
    )
    for f in result.trusted_but_wrong:
        print(f"  TRUSTED BUT WRONG  {f.name}: got {f.actual!r}, expected {f.expected!r}")
    for f in result.flagged_and_wrong:
        print(f"  caught             {f.name}: got {f.actual!r}, expected {f.expected!r}")
    for f in result.flagged_but_right:
        print(f"  flagged but right  {f.name} ({f.status})")
    for rule in result.rules_wrong:
        expected, got = result.rules[rule]
        print(f"  rule {rule}: got {got}, expected {expected}")


async def main(stub: bool, only: str | None, out: Path | None) -> None:
    llm: LLMProvider = (
        register_demo_leases(StubProvider()) if stub else OpenAICompatibleProvider(LLMSettings())
    )
    ruleset = load_ruleset(ROOT / "data" / "owner_ruleset.json")
    units = load_units(ROOT / "data" / "units.json")

    cases = [c for c in load_cases(CASES) if only in (None, c.name)]
    if stub:
        cases = [c for c in cases if c.name in ("clean", "problems")]
    if shutil.which("tesseract") is None:
        skipped = [c.name for c in cases if c.needs_ocr]
        cases = [c for c in cases if not c.needs_ocr]
        if skipped:
            print(f"Skipped (Tesseract not installed): {', '.join(skipped)}")

    results: list[CaseResult] = []
    for case in cases:
        result = await run_case(llm, case, ROOT, ruleset, units)
        print_case(result)
        results.append(result)

    summary = summarise(results)
    print("\nSUMMARY")
    print(f"  fields right       {summary.correct}/{summary.fields}")
    print(f"  trusted but wrong  {summary.trusted_but_wrong}   <- must be 0")
    print(f"  wrong and caught   {summary.flagged_and_wrong}")
    print(f"  flagged but right  {summary.flagged_but_right}   (review load)")
    print(f"  rules right        {summary.rules_correct}/{summary.rules}")
    print(f"  seconds per lease  {summary.seconds_per_lease}")
    if summary.errors:
        print(f"  errors             {summary.errors}")

    if out:
        report = {
            "summary": asdict(summary),
            "cases": [
                {
                    "name": r.case.name,
                    "error": r.error,
                    "seconds": r.seconds,
                    "tokens": r.tokens,
                    "fields": [
                        {
                            "name": f.name,
                            "expected": f.expected,
                            "actual": str(f.actual) if f.actual is not None else None,
                            "status": f.status,
                            "correct": f.correct,
                        }
                        for f in r.fields
                    ],
                    "rules": {k: {"expected": e, "got": g} for k, (e, g) in r.rules.items()},
                }
                for r in results
            ],
        }
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nReport written to {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--stub", action="store_true", help="canned answers, no model")
    parser.add_argument("--case", help="run one case by name")
    parser.add_argument("--out", type=Path, help="write a JSON report here")
    args = parser.parse_args()
    asyncio.run(main(args.stub, args.case, args.out))
