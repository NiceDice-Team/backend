import json
import subprocess
import sys
from pathlib import Path

import pytest

from qa_reporting.core import aggregate_reports, render_pr_summary
from qa_reporting.security import (
    aggregate_security, parse_bandit, parse_django_check, parse_gitleaks,
    parse_pip_audit, parse_trivy, parse_zap, security_report,
    stable_fingerprint, validate_security_report,
)
from tests.reporting.test_qa_reporting import all_reports


pytestmark = pytest.mark.unit


def make_report(check, findings=(), *, error=None, network="NOT_APPLICABLE"):
    return security_report(
        check, list(findings), version="test", duration=0.1, exit_code=1 if error else 0,
        scope="local test scope", execution_error=error, network_safety=network,
    )


def test_bandit_normalization_redacts_and_high_confidence_high_is_blocking():
    payload = {"results": [{
        "test_id": "B105", "filename": "src/settings.py", "line_number": 1,
        "issue_text": "hardcoded password=super-secret", "issue_severity": "HIGH",
        "issue_confidence": "HIGH", "issue_cwe": {"id": 259},
    }]}
    findings = parse_bandit(payload, {})
    report = make_report("sast", findings)

    assert findings[0]["title"] == "hardcoded password=[REDACTED]"
    assert findings[0]["cwe"] == "259"
    assert report["execution"]["status"] == "FAIL"
    assert report["blocking_findings"] == [findings[0]["finding_id"]]


def test_reviewed_baseline_is_visible_known_debt_not_new_blocker():
    fingerprint = stable_fingerprint("bandit", "B101", "src/example.py", 2)
    baseline = {fingerprint: {"fingerprint": fingerprint, "finding_id": "SEC-SAST-001", "reason": "reviewed"}}
    findings = parse_bandit({"results": [{
        "test_id": "B101", "filename": "src/example.py", "line_number": 2,
        "issue_text": "assert used", "issue_severity": "HIGH", "issue_confidence": "HIGH",
    }]}, baseline)

    report = make_report("sast", findings)

    assert report["execution"]["status"] == "PASS WITH KNOWN FINDINGS"
    assert findings[0]["known_or_new"] == "known"
    assert findings[0]["suppression_reason"] == "reviewed"


def test_pip_audit_keeps_package_fix_and_vulnerability_metadata():
    findings = parse_pip_audit({"dependencies": [{
        "name": "demo", "version": "1.0", "vulns": [{
            "id": "PYSEC-1", "fix_versions": ["1.1"], "aliases": ["CWE-79"],
            "description": "affected before 1.1",
        }],
    }]}, {})

    assert findings[0]["security_details"]["fixed_versions"] == ["1.1"]
    assert findings[0]["security_details"]["installed_version"] == "1.0"
    assert findings[0]["cwe"] == "CWE-79"


def test_secret_report_never_contains_secret_value():
    findings = parse_gitleaks([{
        "RuleID": "generic-api-key", "File": "dev.env", "StartLine": 2,
        "Fingerprint": "safe-fingerprint", "Secret": "must-not-appear",
    }], {})

    serialized = json.dumps(findings)
    assert "must-not-appear" not in serialized
    assert findings[0]["severity"] == "Critical"
    assert make_report("secrets", findings)["execution"]["status"] == "FAIL"


def test_trivy_separates_vulnerability_and_misconfiguration():
    payload = {"Results": [{
        "Target": "Dockerfile", "Vulnerabilities": [{
            "VulnerabilityID": "CVE-1", "PkgName": "lib", "InstalledVersion": "1", "Severity": "LOW",
        }], "Misconfigurations": [{
            "ID": "DS001", "Title": "Runs as root", "Severity": "HIGH",
            "CauseMetadata": {"StartLine": 1},
        }],
    }]}
    findings = parse_trivy(payload, {})

    assert {finding["type"] for finding in findings} == {"CONTAINER_VULNERABILITY", "SECURITY_MISCONFIGURATION"}
    assert {finding["security_details"]["class"] for finding in findings} == {"package_vulnerability", "misconfiguration"}


def test_django_deploy_check_parses_only_safe_warning_metadata():
    findings = parse_django_check(
        "WARNINGS:\n?: (security.W004) You have not set SECURE_HSTS_SECONDS. (security.W004)\n", {}
    )

    assert len(findings) == 1
    assert findings[0]["rule_id"] == "security.W004"
    assert findings[0]["security_details"]["classification"] == "deployment-dependent"


def test_zap_fingerprints_each_endpoint_and_does_not_copy_response_bodies():
    findings = parse_zap({"site": [{"@name": "http://127.0.0.1:8000", "alerts": [{
        "pluginid": "10020", "alert": "Missing anti-clickjacking header", "riskcode": "1",
        "confidence": "2", "cweid": "1021", "evidence": "sensitive-body",
        "instances": [{"uri": "http://127.0.0.1:8000/api/schema/", "method": "GET"}],
    }]}]}, {})

    assert findings[0]["severity"] == "Low"
    assert "sensitive-body" not in json.dumps(findings)
    assert findings[0]["security_details"]["instances"][0]["method"] == "GET"


def test_missing_or_failed_security_check_fails_security_gate():
    partial = aggregate_security([make_report("sast")])
    assert partial["status"] == "FAIL"
    assert "dast" in partial["missing_checks"]

    reports = [make_report(check) for check in ("sast", "sca", "secrets", "container", "config")]
    reports.append(make_report("dast", error="scanner failed"))
    assert aggregate_security(reports)["status"] == "FAIL"


def test_network_escape_fails_gate_even_without_alerts():
    report = make_report("dast", network="FAILED")
    assert report["execution"]["status"] == "FAIL"


def test_zap_evidence_network_verifier_rejects_external_host_without_printing_query(tmp_path):
    report = tmp_path / "zap.json"
    report.write_text(json.dumps({"site": [{"@name": "https://example.com/path?token=secret", "alerts": []}]}))
    script = Path(__file__).parents[2] / "scripts/verify_zap_targets.py"

    result = subprocess.run(
        [sys.executable, str(script), str(report), "--allow-origin", "http://127.0.0.1:8000"],
        text=True, capture_output=True,
    )

    assert result.returncode == 1
    assert "https://example.com:" in result.stdout
    assert "token" not in result.stdout
    assert "secret" not in result.stdout


def test_zap_evidence_network_verifier_accepts_loopback(tmp_path):
    report = tmp_path / "zap.json"
    report.write_text(json.dumps({"site": [{"@name": "http://127.0.0.1:8000", "alerts": []}]}))
    script = Path(__file__).parents[2] / "scripts/verify_zap_targets.py"

    result = subprocess.run(
        [sys.executable, str(script), str(report), "--allow-origin", "http://127.0.0.1:8000"],
        text=True, capture_output=True,
    )

    assert result.returncode == 0
    assert "PASSED" in result.stdout


def test_cross_tool_dedup_uses_application_id_not_cwe():
    first = parse_bandit({"results": [{
        "test_id": "B101", "filename": "src/a.py", "line_number": 1,
        "issue_text": "one", "issue_severity": "LOW", "issue_confidence": "HIGH",
        "issue_cwe": {"id": 1},
    }]}, {})[0]
    second = parse_zap({"site": [{"alerts": [{
        "pluginid": "2", "alert": "two", "riskcode": "1", "cweid": "1",
        "instances": [{"uri": "http://127.0.0.1/a", "method": "GET"}],
    }]}]}, {})[0]
    security = aggregate_security([
        make_report("sast", [first]), make_report("sca"), make_report("secrets"),
        make_report("container"), make_report("config"), make_report("dast", [second]),
    ])
    assert len(security["findings"]) == 2

    first["nd_be_id"] = second["nd_be_id"] = "ND-BE-001"
    security = aggregate_security([
        make_report("sast", [first]), make_report("sca"), make_report("secrets"),
        make_report("container"), make_report("config"), make_report("dast", [second]),
    ])
    assert len(security["findings"]) == 1
    assert security["findings"][0]["detected_by"] == ["bandit", "zap"]


def test_unified_summary_preserves_security_failure_and_renders_compact_tables():
    reports = [make_report(check) for check in ("sast", "sca", "secrets", "container", "config")]
    reports.append(make_report("dast", error="failed"))
    security = aggregate_security(reports)

    summary = aggregate_reports(all_reports(), security)
    rendered = render_pr_summary(summary)

    assert summary["overall_status"] == "FAIL"
    assert "## NiceDice Backend — QA & Security Summary" in rendered
    assert "### Static Security" in rendered
    assert "### Dynamic Security" in rendered
    assert len(rendered.splitlines()) <= 120


def test_valid_security_report_contract():
    validate_security_report(make_report("sast"))
