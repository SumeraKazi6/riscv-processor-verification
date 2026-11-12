"""Console and JSON report serialization."""
import json
from pathlib import Path

def print_summary(summary):
    cov=summary["coverage"]
    print("Verification Summary\n--------------------")
    print(f"Tests:              {summary['tests_run']:,}")
    print(f"Passed:             {summary['passed']:,}")
    print(f"Failed:             {summary['failed']:,}")
    print(f"Instructions gen.:  {summary['total_instructions_generated']:,}")
    print(f"Instructions exec.: {summary['total_instructions_executed']:,}")
    print(f"Coverage:           {cov['instruction_coverage_percent']:.1f}% ({cov['covered_instructions']}/{cov['supported_instructions']})")
    print(f"Seed:               {summary['seed']}")
    print(f"Execution time:     {summary['elapsed_seconds']:.3f}s")
    if summary["failures"]:
        print("\nFailures:")
        for failure in summary["failures"]:
            print(f"Test {failure['test_id']} (seed {failure['seed']}):")
            for ins in failure["program"]: print(f"  {ins}")
            for mismatch in failure["mismatches"]: print(f"  {mismatch}")

def write_json(summary, path):
    output=Path(path); output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return output
