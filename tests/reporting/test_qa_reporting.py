import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from jsonschema import validate as validate_json_schema

from qa_reporting.core import (
    COMMENT_MARKER,
    ReportValidationError,
    aggregate_reports,
    base_report,
    finding_key,
    integration_report,
    parse_junit,
    render_pr_summary,
    validate_report,
)


pytestmark = pytest.mark.unit


def execution(*, failed=0):
    return {
        "duration_seconds": 1.5,
        "collected": 2,
        "passed": 2 - failed,
        "failed": failed,
        "skipped": 0,
        "warnings": 0,
        "tests": [],
    }


def finding(*, finding_id="APP-01", nd_be_id="ND-BE-003", severity="Major", known="known"):
    return {
        "finding_id": finding_id,
        "title": "Example finding",
        "severity": severity,
        "type": "APPLICATION_DEFECT",
        "area": "Users",
        "layer_detected": "api",
        "endpoint_or_component": "POST /api/users/reset-password/",
        "status": "CONFIRMED",
        "known_or_new": known,
        "nd_be_id": nd_be_id,
        "rc_id": "RC-16",
        "fsv_id": None,
        "reproducible": "yes",
        "test_ids": ["test_reset"],
        "evidence": ["junit.xml"],
        "ticket_ready": True,
        "requires_clarification": False,
    }


def report(layer, findings=None, failed=0):
    value = base_report(layer, execution(failed=failed), findings or [])
    value["repository"] = "github.com/nicedice-team/backend"
    value["branch"] = "qa/reporting"
    value["commit_sha"] = "a" * 40
    value["coverage"] = "not_applicable"
    if layer == "contract":
        value["metrics"] = {
            "operations_discovered": 71, "operations_exercised": 69,
            "operations_excluded": 2, "generated_cases": 890,
            "known_fingerprints": 79, "new_fingerprints": 0,
            "root_cause_clusters": 16,
        }
    return value


def all_reports(findings=None):
    reports = [report(layer, findings if layer == "api" else []) for layer in ("unit", "component", "api", "contract")]
    reports.append(integration_report())
    return reports


def test_parse_junit_counts_observable_results(tmp_path):
    suite = ET.Element("testsuite", tests="3", failures="1", errors="0", skipped="1", time="2.25")
    ET.SubElement(suite, "testcase", classname="tests.unit.test_example", name="test_pass")
    ET.ElementTree(suite).write(tmp_path / "junit.xml")

    parsed = parse_junit(tmp_path / "junit.xml")

    assert parsed | {"tests": []} == {
        "duration_seconds": 2.25, "collected": 3, "passed": 1,
        "failed": 1, "skipped": 1, "warnings": 0, "tests": [],
    }
    assert parsed["tests"][0]["name"] == "test_pass"


def test_common_layer_report_validates():
    validate_report(report("unit", [finding()]))


def test_common_layer_report_matches_published_json_schema():
    schema = json.loads((Path(__file__).parents[2] / "docs/qa-report-schema.json").read_text())

    validate_json_schema(instance=report("unit", [finding()]), schema=schema)


def test_malformed_layer_report_is_rejected():
    malformed = report("api")
    malformed.pop("execution")

    with pytest.raises(ReportValidationError, match="missing fields"):
        validate_report(malformed)


def test_finding_schema_rejects_unknown_type():
    invalid = finding()
    invalid["type"] = "MADE_UP"

    with pytest.raises(ReportValidationError, match="unsupported finding type"):
        validate_report(report("api", [invalid]))


def test_nd_be_cross_layer_findings_are_deduplicated():
    api_finding = finding()
    contract_finding = {**finding(finding_id="CONTRACT-ALIAS"), "layer_detected": "contract"}
    reports = all_reports()
    reports[2]["findings"] = [api_finding]
    reports[3]["findings"] = [contract_finding]

    summary = aggregate_reports(reports)

    assert summary["raw_finding_references"] == 2
    assert summary["unique_findings"] == 1
    assert summary["findings"][0]["detected_by"] == ["api", "contract"]
    assert finding_key(api_finding) == "ND-BE-003"


def test_severity_and_known_counts_render_from_unique_findings():
    reports = all_reports([
        finding(severity="Critical"),
        finding(finding_id="APP-02", nd_be_id="ND-BE-005", severity="Major"),
    ])
    reports[2]["known_defects_reproduced"] = ["APP-01", "APP-02"]
    summary = aggregate_reports(reports)

    rendered = render_pr_summary(summary)

    assert "- Critical: 1" in rendered
    assert "- Major: 1" in rendered
    assert "- Known defects reproduced: 2" in rendered


def test_missing_required_layer_makes_aggregate_fail():
    summary = aggregate_reports([report("unit"), report("component"), report("contract"), integration_report()])

    assert summary["overall_status"] == "FAIL"
    api = next(layer for layer in summary["layers"] if layer["layer"] == "api")
    assert api["execution"]["status"] == "NOT_RUN"


def test_failed_layer_makes_aggregate_fail():
    reports = all_reports()
    reports[2] = report("api", failed=1)

    assert aggregate_reports(reports)["overall_status"] == "FAIL"


def test_known_active_finding_produces_pass_with_known_defects():
    assert aggregate_reports(all_reports([finding()]))["overall_status"] == "PASS WITH KNOWN DEFECTS"


def test_new_major_finding_makes_aggregate_fail():
    new = finding(known="new")
    new["status"] = "NEW"

    assert aggregate_reports(all_reports([new]))["overall_status"] == "FAIL"


def test_clean_required_layers_pass_and_integration_is_not_implemented():
    summary = aggregate_reports(all_reports())

    assert summary["overall_status"] == "PASS"
    assert summary["quality_metrics"]["integration"] == "NOT_IMPLEMENTED"


def test_aggregate_preserves_full_pytest_and_bug_characterization_metrics():
    reports = all_reports()
    reports[0]["details"]["overall_pytest"] = {"passed": 191, "failed": 0}
    reports[0]["details"]["bug_characterization"] = {"passed": 18, "failed": 0}

    summary = aggregate_reports(reports)

    assert summary["quality_metrics"]["overall_pytest"] == {"passed": 191, "failed": 0}
    assert summary["quality_metrics"]["bug_characterization"] == {"passed": 18, "failed": 0}


def test_pr_markdown_has_stable_marker_and_is_concise():
    rendered = render_pr_summary(aggregate_reports(all_reports([finding()])))

    assert rendered.startswith(COMMENT_MARKER)
    assert "## NiceDice Backend — QA & Security Summary" in rendered
    assert "No new blocking findings." in rendered
    assert len(rendered.splitlines()) <= 100
