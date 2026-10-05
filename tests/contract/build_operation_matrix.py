"""Build a machine-readable operation inventory from schema and JUnit."""

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    schema = yaml.safe_load(args.schema.read_text())
    baseline = json.loads(args.baseline.read_text())
    excluded = set(baseline["excluded_operations"])
    by_route = {
        (method.upper(), path): operation["operationId"]
        for path, item in schema["paths"].items()
        for method, operation in item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }
    exercised = set()
    for testcase in ET.parse(args.junit).getroot().iter("testcase"):
        match = re.match(r"([A-Z]+) (/.+)", testcase.get("name", ""))
        if match and match.groups() in by_route:
            exercised.add(by_route[match.groups()])
    rows = []
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation_id = operation["operationId"]
            rows.append({
                "operation_id": operation_id,
                "method": method.upper(),
                "path": path,
                "excluded": operation_id in excluded,
                "exercised": operation_id in exercised,
            })
    operation_ids = {row["operation_id"] for row in rows}
    uncovered = sorted(
        row["operation_id"]
        for row in rows
        if not row["exercised"] and not row["excluded"]
    )
    missing_exclusions = sorted(excluded - operation_ids)
    result = {
        "schema_version": 1,
        "discovered": len(rows),
        "exercised": sum(row["exercised"] for row in rows),
        "excluded": sorted(excluded),
        "uncovered": uncovered,
        "missing_exclusions": missing_exclusions,
        "gate": "PASS" if not uncovered and not missing_exclusions else "FAIL",
        "operations": rows,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "discovered", "exercised", "excluded", "uncovered",
        "missing_exclusions", "gate",
    )}, sort_keys=True))
    return 0 if result["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
