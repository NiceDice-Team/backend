"""Compare formal drf-spectacular validation output with reviewed debt."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text())
    completed = subprocess.run(
        [sys.executable, "manage.py", "spectacular", "--validate"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text(completed.stdout)

    observed = []
    for issue in baseline["issues"]:
        if all(token in completed.stdout for token in issue["required_text"]):
            observed.append(issue["id"])
    known_ids = [issue["id"] for issue in baseline["issues"]]
    resolved = sorted(set(known_ids) - set(observed))

    recognized_lines = {
        line
        for line in completed.stdout.splitlines()
        if ("Warning [" in line and "get_product_count" in line)
        or ("Error [CreatePaymentIntentView]" in line and "unable to guess serializer" in line)
    }
    candidate_lines = {
        line
        for line in completed.stdout.splitlines()
        if "Warning [" in line or "Error [" in line
    }
    new_lines = sorted(candidate_lines - recognized_lines)
    oauth_known = "On instance['properties']['user']" in completed.stdout
    validation_exception = "SchemaValidationError:" in completed.stdout
    if validation_exception and not oauth_known:
        new_lines.append("unreviewed SchemaValidationError")
    if completed.returncode and not validation_exception and not candidate_lines:
        new_lines.append(f"validator exited {completed.returncode} without a recognized issue")

    result = {
        "schema_version": 1,
        "known": sorted(observed),
        "new": sorted(set(new_lines)),
        "resolved": resolved,
        "validator_exit_code": completed.returncode,
        "gate": "PASS" if not new_lines else "FAIL",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
