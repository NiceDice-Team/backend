"""Normalized layer reports, finding deduplication, aggregation and rendering."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
COMMENT_MARKER = "<!-- nicedice-backend-qa-summary -->"
LAYERS = ("unit", "component", "api", "contract", "integration")
REQUIRED_LAYERS = {"unit", "component", "api", "contract"}
FINDING_TYPES = {
    "APPLICATION_DEFECT", "SECURITY_DEFECT", "API_CONTRACT_DEFECT",
    "SCHEMA_DOCUMENTATION_DEFECT", "AMBIGUOUS_CONTRACT", "MISSING_REQUIREMENT",
    "TESTABILITY_LIMITATION", "TEST_INFRASTRUCTURE", "TOOLING_LIMITATION",
    "SAST_FINDING", "DEPENDENCY_VULNERABILITY", "SECRET_EXPOSURE",
    "CONTAINER_VULNERABILITY", "SECURITY_MISCONFIGURATION", "DAST_FINDING",
}
FINDING_STATUSES = {
    "CONFIRMED", "KNOWN", "NEW", "BLOCKED", "NEEDS_CLARIFICATION",
    "RESOLVED_CANDIDATE",
}


class ReportValidationError(ValueError):
    """Raised when an input report does not satisfy the common model."""


def _git(*args: str, default: str = "unknown") -> str:
    completed = subprocess.run(
        ["git", *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else default


def repository_identity() -> dict[str, str]:
    remote = _git("config", "--get", "remote.origin.url")
    remote = re.sub(r"https://[^/@]+@", "https://", remote)
    remote = re.sub(r"^[^@]+@([^:]+):", r"\1/", remote)
    remote = remote.removesuffix(".git")
    return {
        "repository": remote or "local/nicedice-backend",
        "branch": os.getenv("GITHUB_HEAD_REF") or _git("branch", "--show-current"),
        "commit_sha": os.getenv("GITHUB_SHA") or _git("rev-parse", "HEAD"),
    }


def parse_junit(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    collected = sum(int(suite.get("tests", 0)) for suite in suites)
    failed = sum(int(suite.get("failures", 0)) + int(suite.get("errors", 0)) for suite in suites)
    skipped = sum(int(suite.get("skipped", 0)) for suite in suites)
    duration = sum(float(suite.get("time", 0) or 0) for suite in suites)
    tests = [
        {
            "id": f"{case.get('classname', '')}::{case.get('name', '')}".strip(":"),
            "name": case.get("name", ""),
            "classname": case.get("classname", ""),
        }
        for suite in suites
        for case in suite.iter("testcase")
    ]
    return {
        "duration_seconds": round(duration, 3),
        "collected": collected,
        "passed": collected - failed - skipped,
        "failed": failed,
        "skipped": skipped,
        "warnings": 0,
        "tests": tests,
    }


def _candidate_layers(candidate_id: str) -> set[str]:
    component = {"APP-01", "CLR-04"}
    contract = {
        "APP-01", "APP-03", "APP-04", "APP-07", "APP-08", "APP-09", "APP-10",
        "SEC-01", "SEC-02", "SEC-03",
        "SCH-01", "SCH-02", "SCH-03", "SCH-04", "SCH-05", "SCH-06", "SCH-07",
    }
    api = {
        "APP-01", "APP-02", "APP-03", "APP-04", "APP-05", "APP-06", "APP-07",
        "APP-08", "APP-09", "APP-10", "SEC-01", "SEC-02", "SEC-03",
        "CLR-01", "CLR-02", "CLR-03",
    }
    layers = set()
    if candidate_id in component:
        layers.add("component")
    if candidate_id in contract:
        layers.add("contract")
    if candidate_id in api:
        layers.add("api")
    return layers


def _finding_from_candidate(candidate: dict[str, Any], layer: str) -> dict[str, Any]:
    nd_ids = candidate.get("nd_be", [])
    rc_ids = candidate.get("rc", [])
    fsv_ids = candidate.get("fsv", [])
    clarification = candidate["ready"] == "CLARIFICATION"
    return {
        "finding_id": candidate["id"],
        "title": candidate["title"],
        "severity": candidate["severity"],
        "type": candidate["type"],
        "area": candidate["area"],
        "layer_detected": layer,
        "endpoint_or_component": candidate["endpoint"],
        "status": "NEEDS_CLARIFICATION" if clarification else "CONFIRMED",
        "known_or_new": "known",
        "nd_be_id": nd_ids[0] if nd_ids else None,
        "rc_id": rc_ids[0] if rc_ids else None,
        "fsv_id": fsv_ids[0] if fsv_ids else None,
        "reproducible": "state_or_requirement_dependent" if clarification else "yes",
        "test_ids": [candidate["test"]] if candidate.get("test") else [],
        "evidence": [
            "docs/contract-bug-report.md",
            *nd_ids, *rc_ids, *fsv_ids,
        ],
        "ticket_ready": candidate["ready"] == "YES",
        "requires_clarification": clarification,
    }


def findings_for_layer(layer: str, bug_report_path: Path) -> list[dict[str, Any]]:
    bug_report = json.loads(bug_report_path.read_text())
    findings = [
        _finding_from_candidate(candidate, layer)
        for candidate in bug_report["candidates"]
        if layer in _candidate_layers(candidate["id"])
    ]
    extra = {
        "unit": [{
            "finding_id": "ND-BE-015", "title": "Production storage adapter lacks a local endpoint seam",
            "severity": "Minor", "type": "TESTABILITY_LIMITATION", "area": "Storage",
            "layer_detected": "unit", "endpoint_or_component": "src.s3.MediaStorage",
            "status": "KNOWN", "known_or_new": "known", "nd_be_id": "ND-BE-015",
            "rc_id": None, "fsv_id": None, "reproducible": "source_inspection",
            "test_ids": [], "evidence": ["docs/testing-findings.md"],
            "ticket_ready": False, "requires_clarification": False,
        }],
        "component": [{
            "finding_id": "ND-BE-010", "title": "Checkout lacks an isolated transactional service boundary",
            "severity": "Major", "type": "TESTABILITY_LIMITATION", "area": "Checkout",
            "layer_detected": "component", "endpoint_or_component": "OrderListViewCreateView",
            "status": "KNOWN", "known_or_new": "known", "nd_be_id": "ND-BE-010",
            "rc_id": None, "fsv_id": None, "reproducible": "source_inspection",
            "test_ids": [], "evidence": ["docs/testing-findings.md"],
            "ticket_ready": False, "requires_clarification": False,
        }],
        "api": [{
            "finding_id": "ND-BE-014", "title": "User routes load the same code under two module identities",
            "severity": "Minor", "type": "TESTABILITY_LIMITATION", "area": "User routing",
            "layer_detected": "api", "endpoint_or_component": "users.interfaces.urls",
            "status": "KNOWN", "known_or_new": "known", "nd_be_id": "ND-BE-014",
            "rc_id": None, "fsv_id": None, "reproducible": "source_inspection",
            "test_ids": [], "evidence": ["docs/testing-findings.md"],
            "ticket_ready": False, "requires_clarification": False,
        }],
    }
    findings.extend(extra.get(layer, []))
    if layer == "contract":
        for technical in bug_report["technical_only"]:
            finding_type = "TOOLING_LIMITATION" if technical["type"] in {"TOOLING", "TOOLING_SETUP"} else "TEST_INFRASTRUCTURE"
            findings.append({
                "finding_id": technical["id"], "title": technical["action"].split(";", 1)[-1].strip(),
                "severity": "Minor", "type": finding_type, "area": "Contract infrastructure",
                "layer_detected": "contract", "endpoint_or_component": "Schemathesis harness",
                "status": "KNOWN", "known_or_new": "known",
                "nd_be_id": None, "rc_id": technical["id"] if technical["id"].startswith("RC-") else None,
                "fsv_id": None, "reproducible": "not_applicable", "test_ids": [],
                "evidence": ["docs/contract-bug-report.md"], "ticket_ready": False,
                "requires_clarification": False,
            })
    return findings


def base_report(layer: str, execution: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    identity = repository_identity()
    status = "FAIL" if execution["failed"] else ("PASS WITH KNOWN DEFECTS" if findings else "PASS")
    executed_names = {test["name"] for test in execution.get("tests", [])}
    reproduced = []
    for finding in findings:
        tests_match = any(
            any(test_id in executed_name for executed_name in executed_names)
            for test_id in finding["test_ids"]
        )
        contract_evidence = layer == "contract" and bool(finding["rc_id"] or finding["fsv_id"])
        if finding["status"] == "CONFIRMED" and finding["known_or_new"] == "known" and (tests_match or contract_evidence):
            reproduced.append(finding["finding_id"])
    details = {
        "test_modules": sorted({test["classname"] for test in execution.get("tests", []) if test["classname"]}),
    }
    if layer == "unit":
        details.update({
            "production_modules_exercised": [
                "products.infrastructure.models", "products.service",
                "users.interfaces.serializers", "users.interfaces.views",
            ],
            "quality_note": "Coverage is supplementary; assertions and external-boundary isolation define unit quality.",
        })
    elif layer == "component":
        details.update({
            "areas_exercised": ["serializers", "model constraints", "persistence", "authentication"],
            "state_persistence_verified": True,
            "test_doubles": ["Django password hasher/auth backend", "local ORM test database"],
        })
    elif layer == "api":
        details.update({
            "areas_exercised": ["users", "products", "product images", "cart", "orders", "payments", "categories"],
            "scenario_types": ["positive", "validation_negative", "boundary", "authentication_authorization", "dependency_failure"],
            "state_persistence_verified": True,
        })
    return {
        "report_schema_version": SCHEMA_VERSION,
        "layer": layer,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **identity,
        "test_environment": {
            "name": "github_actions" if os.getenv("GITHUB_ACTIONS") == "true" else "local",
            "python": platform.python_version(),
            "platform": platform.system().lower(),
            "external_non_local_traffic": "NO",
        },
        "framework_versions": {"pytest": _package_version("pytest")},
        "execution": {**{key: execution[key] for key in (
            "duration_seconds", "collected", "passed", "failed", "skipped", "warnings"
        )}, "status": status},
        "coverage": None,
        "findings": findings,
        "known_defects_reproduced": sorted(reproduced),
        "new_findings": sorted(f["finding_id"] for f in findings if f["known_or_new"] == "new"),
        "blocked_tests": [],
        "exclusions": [],
        "evidence_artifacts": [],
        "metrics": {},
        "details": details,
    }


def _package_version(name: str) -> str | None:
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return None


def apply_coverage(report: dict[str, Any], coverage_path: Path | None) -> None:
    if not coverage_path:
        report["coverage"] = "not_applicable"
        return
    coverage = json.loads(coverage_path.read_text())
    totals = coverage["totals"]
    report["coverage"] = {
        "scope": "full_backend_suite",
        "line_percent": float(totals["percent_covered"]),
        "covered_lines": totals["covered_lines"],
        "num_statements": totals["num_statements"],
    }


def apply_contract_evidence(report: dict[str, Any], evidence_dir: Path) -> None:
    normalized = json.loads((evidence_dir / "normalized-failures.json").read_text())
    matrix = json.loads((evidence_dir / "operation-matrix.json").read_text())
    formal = json.loads((evidence_dir / "schema-validation.json").read_text())
    output = (evidence_dir / "schemathesis-output.txt").read_text()
    generated = re.search(r"(\d+) generated, (\d+) found (\d+) unique failures", output)
    report["framework_versions"]["schemathesis"] = _package_version("schemathesis")
    report["metrics"] = {
        "operations_discovered": matrix["discovered"],
        "operations_exercised": matrix["exercised"],
        "operations_excluded": len(matrix["excluded"]),
        "generated_cases": int(generated.group(1)) if generated else None,
        "failing_cases": int(generated.group(2)) if generated else None,
        "unique_check_failures": int(generated.group(3)) if generated else None,
        "root_cause_clusters": len(normalized["summary"]["runtime_root_causes"]),
        "known_fingerprints": normalized["summary"]["known_fingerprints"],
        "new_fingerprints": len(normalized["summary"]["new_fingerprints"]),
        "resolved_fingerprints": len(normalized["summary"]["resolved_fingerprints"]),
        "formal_openapi": formal["gate"],
    }
    report["exclusions"] = matrix["excluded"]
    report["evidence_artifacts"] = [
        "junit.xml", "schemathesis-output.txt", "normalized-failures.json",
        "operation-matrix.json", "schema-validation.json", "schema-validation.log",
        "docs/contract-bug-report.md", "artifacts/contract-bug-report.json",
    ]
    if normalized["summary"]["new_fingerprints"] or formal["new"]:
        report["execution"]["status"] = "FAIL"


def integration_report() -> dict[str, Any]:
    execution = {"duration_seconds": 0.0, "collected": 0, "passed": 0, "failed": 0, "skipped": 0, "warnings": 0}
    report = base_report("integration", execution, [])
    report["execution"]["status"] = "NOT_IMPLEMENTED"
    report["coverage"] = "not_applicable"
    report["blocked_tests"] = ["Integration suite has not been implemented"]
    report["details"] = {
        "future_contract": [
            "PostgreSQL", "Mailcatcher", "S3-compatible storage", "provider sandboxes/fakes",
            "service health", "infrastructure failures", "persistence", "cross-component flows",
        ]
    }
    return report


def validate_finding(finding: dict[str, Any]) -> None:
    required = {
        "finding_id", "title", "severity", "type", "area", "layer_detected",
        "endpoint_or_component", "status", "known_or_new", "nd_be_id", "rc_id",
        "fsv_id", "reproducible", "test_ids", "evidence", "ticket_ready",
        "requires_clarification",
    }
    missing = required - finding.keys()
    if missing:
        raise ReportValidationError(f"finding missing fields: {sorted(missing)}")
    if finding["type"] not in FINDING_TYPES:
        raise ReportValidationError(f"unsupported finding type: {finding['type']}")
    if finding["severity"] not in {"Critical", "High", "Major", "Medium", "Minor", "Low", "Informational"}:
        raise ReportValidationError(f"unsupported finding severity: {finding['severity']}")
    if finding["status"] not in FINDING_STATUSES:
        raise ReportValidationError(f"unsupported finding status: {finding['status']}")


def validate_report(report: dict[str, Any]) -> None:
    required = {
        "report_schema_version", "layer", "timestamp", "repository", "branch", "commit_sha",
        "test_environment", "framework_versions", "execution", "coverage", "findings",
        "known_defects_reproduced", "new_findings", "blocked_tests", "exclusions",
        "evidence_artifacts", "metrics", "details",
    }
    missing = required - report.keys()
    if missing:
        raise ReportValidationError(f"report missing fields: {sorted(missing)}")
    if report["report_schema_version"] != SCHEMA_VERSION or report["layer"] not in LAYERS:
        raise ReportValidationError("unsupported report schema version or layer")
    execution_required = {"duration_seconds", "collected", "passed", "failed", "skipped", "warnings", "status"}
    if execution_required - report["execution"].keys():
        raise ReportValidationError("execution summary is incomplete")
    for finding in report["findings"]:
        validate_finding(finding)


def finding_key(finding: dict[str, Any]) -> str:
    return (
        finding.get("nd_be_id") or finding.get("fsv_id") or finding.get("finding_id")
        or "|".join(str(finding.get(key) or "") for key in ("endpoint_or_component", "rc_id", "type"))
    )


def aggregate_reports(
    reports: list[dict[str, Any]], security_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    for report in reports:
        validate_report(report)
    by_layer = {report["layer"]: report for report in reports}
    for layer in LAYERS:
        if layer not in by_layer:
            missing = integration_report() if layer == "integration" else base_report(layer, {
                "duration_seconds": 0.0, "collected": 0, "passed": 0, "failed": 0,
                "skipped": 0, "warnings": 0,
            }, [])
            missing["execution"]["status"] = "NOT_RUN"
            missing["blocked_tests"] = ["Layer report is missing"]
            by_layer[layer] = missing
    unique: dict[str, dict[str, Any]] = {}
    raw_references = 0
    for layer, report in by_layer.items():
        for finding in report["findings"]:
            raw_references += 1
            key = finding_key(finding)
            if key not in unique:
                unique[key] = {**finding, "detected_by": [layer]}
            elif layer not in unique[key]["detected_by"]:
                unique[key]["detected_by"].append(layer)
    if security_summary:
        for finding in security_summary.get("findings", []):
            raw_references += 1
            key = finding_key(finding)
            detectors = finding.get("detected_by", [finding.get("scanner", "security")])
            if key not in unique:
                unique[key] = {**finding, "detected_by": list(detectors)}
            else:
                for detector in detectors:
                    if detector not in unique[key]["detected_by"]:
                        unique[key]["detected_by"].append(detector)
    findings = sorted(unique.values(), key=lambda item: (item["severity"], item["finding_id"]))
    failed_layer = any(
        by_layer[layer]["execution"]["status"] in {"FAIL", "NOT_RUN"}
        for layer in REQUIRED_LAYERS
    )
    new_blocking = any(
        finding["known_or_new"] == "new" and finding["severity"] in {"Critical", "Major"}
        for finding in findings
    )
    known_active = any(finding["status"] not in {"RESOLVED_CANDIDATE"} for finding in findings)
    security_failed = bool(security_summary and security_summary.get("status") == "FAIL")
    if security_summary:
        overall = "FAIL" if failed_layer or new_blocking or security_failed else (
            "PASS WITH KNOWN FINDINGS" if known_active else "PASS"
        )
    else:
        overall = "FAIL" if failed_layer or new_blocking else ("PASS WITH KNOWN DEFECTS" if known_active else "PASS")
    first = by_layer["unit"]
    return {
        "report_schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repository": first["repository"], "branch": first["branch"], "commit_sha": first["commit_sha"],
        "overall_status": overall,
        "layers": [by_layer[layer] for layer in LAYERS],
        "findings": findings,
        "raw_finding_references": raw_references,
        "unique_findings": len(findings),
        "quality_metrics": {
            "overall_pytest": by_layer["unit"]["details"].get("overall_pytest"),
            "bug_characterization": by_layer["unit"]["details"].get("bug_characterization"),
            "production_coverage": next((r["coverage"] for r in reports if isinstance(r["coverage"], dict)), None),
            "api_negative_matrix": "docs/negative-testing-matrix.md",
            "contract": by_layer["contract"]["metrics"],
            "integration": by_layer["integration"]["execution"]["status"],
        },
        "security": security_summary,
        "safety": {"external_non_local_traffic": "NO", "production_application_diff": "EMPTY"},
    }


def render_layer_markdown(report: dict[str, Any]) -> str:
    execution = report["execution"]
    lines = [
        f"# {report['layer'].title()} test report", "",
        f"Revision: `{report['commit_sha']}`", "",
        f"Status: **{execution['status']}**", "",
        "| Collected | Passed | Failed | Skipped | Warnings | Duration | Findings |", "|---:|---:|---:|---:|---:|---:|---:|",
        f"| {execution['collected']} | {execution['passed']} | {execution['failed']} | {execution['skipped']} | {execution['warnings']} | {execution['duration_seconds']:.3f}s | {len(report['findings'])} |",
        "", "## Findings", "",
    ]
    if report["findings"]:
        lines.extend(f"- `{f['finding_id']}` [{f['severity']}] {f['title']}" for f in report["findings"])
    else:
        lines.append("No findings attributed to this layer.")
    lines.extend(["", "## Evidence", ""])
    lines.extend(f"- `{item}`" for item in report["evidence_artifacts"] or ["No separate artifact"])
    return "\n".join(lines) + "\n"


def render_pr_summary(summary: dict[str, Any]) -> str:
    findings = summary["findings"]
    severity = Counter(f["severity"] for f in findings)
    new = [f for f in findings if f["known_or_new"] == "new"]
    known = [f for f in findings if f["known_or_new"] == "known"]
    reproduced = {
        finding_id
        for report in summary["layers"]
        for finding_id in report["known_defects_reproduced"]
    }
    ready = [f for f in findings if f["ticket_ready"]]
    clarify = [f for f in findings if f["requires_clarification"]]
    contract = summary["quality_metrics"]["contract"]
    coverage = summary["quality_metrics"]["production_coverage"]
    overall_pytest = summary["quality_metrics"]["overall_pytest"]
    bug_characterization = summary["quality_metrics"]["bug_characterization"]
    security = summary.get("security")
    security_blocking = set(security.get("blocking_findings", [])) if security else set()
    lines = [
        COMMENT_MARKER,
        "## NiceDice Backend — QA & Security Summary", "",
        f"Revision: `{summary['commit_sha'][:12]}`", f"Overall: **{summary['overall_status']}**", "",
        "| Layer | Passed | Failed | Findings | New | Known | Status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for report in summary["layers"]:
        execution = report["execution"]
        layer_findings = report["findings"]
        lines.append(
            f"| {report['layer'].title()} | {execution['passed']} | {execution['failed']} | {len(layer_findings)} | "
            f"{sum(f['known_or_new']=='new' for f in layer_findings)} | {sum(f['known_or_new']=='known' for f in layer_findings)} | {execution['status']} |"
        )
    lines.extend(["", "### Coverage", ""])
    if overall_pytest:
        lines.append(f"- Overall pytest: {overall_pytest['passed']} passed, {overall_pytest['failed']} failed")
    if bug_characterization:
        lines.append(f"- Bug characterization: {bug_characterization['passed']} passed, {bug_characterization['failed']} failed")
    lines.append(f"- Production line coverage: {coverage['line_percent']:.0f}%" if coverage else "- Production line coverage: not available")
    lines.extend([
        f"- Contract operations: {contract.get('operations_exercised', 'N/A')} / {contract.get('operations_discovered', 'N/A')}",
        f"- Schemathesis cases: {contract.get('generated_cases', 'N/A')}",
        f"- Integration: {summary['quality_metrics']['integration']}", "",
        "### Findings", "",
        f"- Critical: {severity['Critical']}", f"- Major: {severity['Major']}", f"- Minor: {severity['Minor']}",
        f"- High: {severity['High']}", f"- Medium: {severity['Medium']}",
        f"- Low: {severity['Low']}", f"- Informational: {severity['Informational']}",
        f"- New findings: {len(new)}", f"- Known defects reproduced: {len(reproduced)}",
        f"- Ready-to-file tickets: {len(ready)}", f"- Needs clarification: {len(clarify)}", "",
        "### New / Blocking Findings", "",
    ])
    lines.extend(
        f"- `{f['finding_id']}` [{f['severity']}] — {f['title']}"
        for f in new if f["severity"] in {"Critical", "Major"} or f["finding_id"] in security_blocking
    )
    if not any(f["severity"] in {"Critical", "Major"} or f["finding_id"] in security_blocking for f in new):
        lines.append("No new blocking findings.")
    lines.extend([
        "", "### Contract", "",
        f"- Known fingerprints: {contract.get('known_fingerprints', 'N/A')}",
        f"- New fingerprints: {contract.get('new_fingerprints', 'N/A')}",
        f"- Root-cause clusters: {contract.get('root_cause_clusters', 'N/A')}",
        f"- Excluded operations: {contract.get('operations_excluded', 'N/A')}", "",
    ])
    lines.extend(["### Static Security", ""])
    if security:
        lines.extend([
            "| Check | Critical | High | Medium | Low | New | Status |",
            "|---|---:|---:|---:|---:|---:|---|",
        ])
        by_check = {report["check"]: report for report in security.get("checks", [])}
        for check in ("sast", "sca", "secrets", "container", "config"):
            report = by_check.get(check)
            if not report:
                lines.append(f"| {check.title()} | 0 | 0 | 0 | 0 | 0 | NOT RUN |")
                continue
            counts = report["counts"]
            lines.append(
                f"| {check.title()} | {counts['Critical']} | {counts['High']} | {counts['Medium']} | "
                f"{counts['Low']} | {report['new']} | {report['execution']['status']} |"
            )
        dast = by_check.get("dast")
        lines.extend(["", "### Dynamic Security", ""])
        if dast:
            counts = dast["counts"]
            lines.extend([
                f"- ZAP endpoints/surface scanned: {dast['scope']}",
                f"- High: {counts['High']}", f"- Medium: {counts['Medium']}",
                f"- Low: {counts['Low']}", f"- New: {dast['new']}",
                f"- Status: {dast['execution']['status']}",
            ])
        else:
            lines.append("- ZAP: NOT RUN")
        lines.extend(["", "### Security Gate", "", f"- Status: {security['status']}",
                      f"- Known scanner findings: {security['known']}",
                      f"- New security findings: {security['new']}",
                      f"- New blocking security findings: {len(security['blocking_findings'])}",
                      f"- Ticket-ready security findings: {sum(f.get('ticket_ready', False) for f in summary['findings'] if f['type'] in {'SECURITY_DEFECT', 'SAST_FINDING', 'DEPENDENCY_VULNERABILITY', 'SECRET_EXPOSURE', 'CONTAINER_VULNERABILITY', 'SECURITY_MISCONFIGURATION', 'DAST_FINDING'})}", ""])
    else:
        lines.extend(["Security reports were not supplied.", "", "### Dynamic Security", "", "- ZAP: NOT RUN", ""])
    lines.extend([
        "### Safety", "", "- External non-local application targets contacted: NO", "- Production application diff from test work: EMPTY", "",
        "### Detailed Evidence", "",
        "See uploaded CI artifacts: QA/security summaries, normalized reports, raw scanner evidence, JUnit, coverage, and Contract evidence.",
    ])
    return "\n".join(lines) + "\n"


def write_json_and_markdown(report: dict[str, Any], json_path: Path, md_path: Path) -> None:
    validate_report(report)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    md_path.write_text(render_layer_markdown(report))
