"""Normalize raw Schemathesis JUnit into reviewed root-cause fingerprints."""

import argparse
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import yaml


LABELS = {
    "Server error": "not_a_server_error",
    "Undocumented Content-Type": "content_type_conformance",
    "Response violates schema": "response_schema_conformance",
    "API accepted schema-violating request": "negative_data_rejection",
    "API rejected schema-compliant request": "positive_data_acceptance",
    "Undocumented HTTP status code": "status_code_conformance",
}

ROOTS = {
    "RC-01": ("Implementation", "ND-BE-018"),
    "RC-02": ("Implementation", "ND-BE-020"),
    "RC-03": ("Implementation", "ND-BE-021"),
    "RC-04": ("Implementation", "ND-BE-022"),
    "RC-05": ("Both", None),
    "RC-06": ("Both", None),
    "RC-07": ("Both", None),
    "RC-08": ("OpenAPI/schema", None),
    "RC-09": ("OpenAPI/schema", None),
    "RC-10": ("OpenAPI/schema", "ND-BE-006"),
    "RC-11": ("Both", None),
    "RC-12": ("Both", None),
    "RC-13": ("Tooling", None),
    "RC-14": ("Test-data/setup", None),
    "RC-15": ("OpenAPI/schema", None),
    "RC-16": ("Implementation", "ND-BE-003/ND-BE-004"),
    "RC-17": ("Test-data/setup", None),
    "RC-18": ("OpenAPI/schema", None),
    "RC-UNREVIEWED": ("Unreviewed", None),
}

ROOT_DESCRIPTIONS = {
    "RC-01": "resend activation accepts a non-object body and returns 500/HTML",
    "RC-02": "category slug collision returns 500/HTML",
    "RC-03": "photo creation without product returns 500/HTML",
    "RC-04": "registration identity collision returns 500/HTML",
    "RC-05": "malformed typed path is routed to Django HTML 404",
    "RC-06": "cart success response shape differs from the schema",
    "RC-07": "cart custom error envelope differs from the schema",
    "RC-08": "category blank image value violates URI format",
    "RC-09": "product pagination envelope differs from the schema",
    "RC-10": "product invalid-limit error differs from the schema",
    "RC-11": "product placeholder image differs from the schema",
    "RC-12": "blank or unknown query input is accepted",
    "RC-13": "multipart coercion creates generator false positives",
    "RC-14": "forgot-password throttle state contaminates generated cases",
    "RC-15": "request schema omits implementation constraints",
    "RC-16": "documented reset-password payload is rejected",
    "RC-17": "valid cases lack token, identifier, or uniqueness preconditions",
    "RC-18": "documented statuses and redirect behavior are incomplete",
}


def classify(operation: str, check: str, text: str) -> str:
    if operation == "users_resend_activation_create" and check in {
        "not_a_server_error", "content_type_conformance"
    } and "[500]" in text:
        return "RC-01"
    if operation == "categories_create" and check in {
        "not_a_server_error", "content_type_conformance"
    } and "[500]" in text:
        return "RC-02"
    if operation == "photos_create" and check in {
        "not_a_server_error", "content_type_conformance"
    } and "[500]" in text:
        return "RC-03"
    if operation == "users_register_create" and check in {
        "not_a_server_error", "content_type_conformance"
    } and "[500]" in text:
        return "RC-04"
    if check == "content_type_conformance":
        return "RC-05"
    if check == "response_schema_conformance":
        if operation in {"api_carts_add_item", "api_carts_get_item"} and (
            "required property" in text or "not of type 'integer'" in text
        ):
            return "RC-06"
        if "carts" in operation:
            return "RC-07"
        if operation.startswith("categories_"):
            return "RC-08"
        if operation == "products_list" and "'count' is a required property" in text:
            return "RC-09"
        if operation == "products_list":
            return "RC-10"
        if operation == "products_retrieve":
            return "RC-11"
    if check == "negative_data_rejection":
        if operation == "users_forgot_password_create":
            return "RC-14"
        if operation in {"audiences_create", "brands_create", "game_types_create"}:
            return "RC-13"
        return "RC-12"
    if check == "positive_data_acceptance":
        if operation == "users_forgot_password_create":
            return "RC-14"
        if operation == "users_reset_password_create":
            return "RC-16"
        if operation in {
            "users_activate_retrieve", "users_logout_create",
            "users_resend_activation_create", "api_carts_add_item",
        }:
            return "RC-17"
        return "RC-15"
    if check in {"status_code_conformance", "redirect_blocked"}:
        return "RC-18"
    return "RC-UNREVIEWED"


def operation_map(schema_path: Path) -> dict[tuple[str, str], str]:
    schema = yaml.safe_load(schema_path.read_text())
    return {
        (method.upper(), path): operation["operationId"]
        for path, path_item in schema["paths"].items()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()
    operations = operation_map(args.schema)
    counts: Counter[tuple[str, str, str, str, str]] = Counter()
    junit = ET.parse(args.junit).getroot()

    for testcase in junit.iter("testcase"):
        name = testcase.get("name", "")
        match = re.match(r"([A-Z]+) (/.+)", name)
        if not match:
            continue
        method, path = match.groups()
        operation = operations.get((method, path), "UNKNOWN")
        nodes = list(testcase.findall("failure")) + list(testcase.findall("error"))
        messages = [node.get("message") or node.text or "" for node in nodes]
        if not messages:
            continue
        combined = max(messages, key=len)
        chunks = [chunk for chunk in re.split(r"(?=\d+\. Test Case ID:)", combined) if "Test Case ID:" in chunk]
        if not chunks and "Exceeded 0 redirects" in combined:
            chunks = [combined]
        seen: set[tuple[str, str]] = set()
        for chunk in chunks:
            checks = [value for label, value in LABELS.items() if f"- {label}" in chunk]
            if "Exceeded 0 redirects" in chunk:
                checks.append("redirect_blocked")
            for check in checks:
                case_id = re.search(r"Test Case ID: (\w+)", chunk)
                dedupe = (case_id.group(1) if case_id else "network", check)
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                root = classify(operation, check, chunk)
                counts[(operation, method, path, check, root)] += 1

    fingerprints = sorted(f"{op}|{check}|{root}" for op, _, _, check, root in counts)
    if args.write_baseline:
        roots = {
            root: {
                "description": ROOT_DESCRIPTIONS[root],
                "classification": ROOTS[root][0],
                "nd_be_id": ROOTS[root][1],
            }
            for *_, root in counts
            if root != "RC-UNREVIEWED"
        }
        args.output.write_text(json.dumps({
            "schema_version": 1,
            "reviewed_root_causes": roots,
            "allowed_fingerprints": [f for f in fingerprints if not f.endswith("RC-UNREVIEWED")],
            "excluded_operations": ["users_oauth_create", "orders_create_payment_intent_create"],
        }, indent=2, sort_keys=True) + "\n")
        return 0

    baseline = json.loads(args.baseline.read_text())
    allowed = set(baseline["allowed_fingerprints"])
    rows = []
    for (operation, method, path, check, root), occurrence_count in sorted(counts.items()):
        fingerprint = f"{operation}|{check}|{root}"
        classification, nd_be_id = ROOTS[root]
        rows.append({
            "operation_id": operation, "method": method, "path": path,
            "check": check, "root_cause_id": root, "nd_be_id": nd_be_id,
            "classification": classification,
            "known_or_new": "known" if fingerprint in allowed else "new",
            "occurrence_count": occurrence_count,
        })
    new = sorted(set(fingerprints) - allowed)
    resolved = sorted(allowed - set(fingerprints))
    result = {
        "schema_version": 1,
        "summary": {
            "runtime_root_causes": sorted({row["root_cause_id"] for row in rows}),
            "known_fingerprints": len(set(fingerprints) & allowed),
            "new_fingerprints": new,
            "resolved_fingerprints": resolved,
            "gate": "PASS" if not new else "FAIL",
        },
        "failures": rows,
        "exclusions": baseline["excluded_operations"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["summary"], sort_keys=True))
    return 0 if not new else 1


if __name__ == "__main__":
    raise SystemExit(main())
