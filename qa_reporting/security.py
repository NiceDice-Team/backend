"""Normalize security scanner output and evaluate the backend security gate."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse, urlunparse

from .core import SCHEMA_VERSION, repository_identity


SECURITY_CHECKS = ("sast", "sca", "secrets", "container", "config", "dast")
SCANNERS = {
    "sast": "bandit",
    "sca": "pip-audit",
    "secrets": "gitleaks",
    "container": "trivy",
    "config": "django-check",
    "dast": "zap",
}
SECURITY_TYPES = {
    "sast": "SAST_FINDING",
    "sca": "DEPENDENCY_VULNERABILITY",
    "secrets": "SECRET_EXPOSURE",
    "container": "CONTAINER_VULNERABILITY",
    "config": "SECURITY_MISCONFIGURATION",
    "dast": "DAST_FINDING",
}
RISK_LEVELS = ("Critical", "High", "Medium", "Low", "Informational")


def _safe_text(value: Any, limit: int = 500) -> str:
    """Return report-safe single-line metadata, never raw scanner evidence."""
    text = re.sub(r"[\r\n\t]+", " ", str(value or "")).strip()
    text = re.sub(r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    return text[:limit]


def _severity(value: Any, *, default: str = "Medium") -> str:
    mapped = {
        "critical": "Critical", "high": "High", "medium": "Medium",
        "moderate": "Medium", "low": "Low", "info": "Informational",
        "informational": "Informational", "0": "Informational", "1": "Low",
        "2": "Medium", "3": "High", "4": "Critical",
    }
    return mapped.get(str(value or "").strip().lower(), default)


def stable_fingerprint(scanner: str, *parts: Any) -> str:
    normalized = "|".join(_safe_text(part).lower() for part in parts)
    return f"{scanner}:{hashlib.sha256(normalized.encode()).hexdigest()[:24]}"


def load_baseline(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path or not path.exists():
        return {}
    payload = json.loads(path.read_text())
    required = {"fingerprint", "scanner", "rule_id", "reason", "review_status"}
    result = {}
    for entry in payload.get("findings", []):
        missing = required - entry.keys()
        if missing:
            raise ValueError(f"security baseline entry is incomplete: {sorted(missing)}")
        result[entry["fingerprint"]] = entry
    return result


def _common_finding(
    *, check: str, rule_id: str, title: str, severity: str,
    component: str, fingerprint: str, baseline: dict[str, dict[str, Any]],
    confidence: str | None = None, cwe: str | None = None,
    line: int | None = None, details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reviewed = baseline.get(fingerprint)
    known = reviewed is not None
    finding_id = reviewed.get("finding_id") if reviewed else f"{SCANNERS[check].upper()}-{fingerprint.rsplit(':', 1)[-1][:10]}"
    return {
        "finding_id": finding_id,
        "title": _safe_text(title),
        "severity": severity,
        "type": SECURITY_TYPES[check],
        "area": "Security",
        "layer_detected": check,
        "endpoint_or_component": _safe_text(component),
        "status": "KNOWN" if known else "NEW",
        "known_or_new": "known" if known else "new",
        "nd_be_id": reviewed.get("nd_be_id") if reviewed else None,
        "rc_id": None,
        "fsv_id": None,
        "reproducible": "yes",
        "test_ids": [],
        "evidence": [f"artifacts/security/{SCANNERS[check]}.json"],
        "ticket_ready": bool(reviewed and reviewed.get("ticket_ready")),
        "requires_clarification": not bool(reviewed),
        "scanner": SCANNERS[check],
        "rule_id": _safe_text(rule_id),
        "confidence": _safe_text(confidence) if confidence else None,
        "cwe": _safe_text(cwe) if cwe else None,
        "file": _safe_text(component),
        "line": line,
        "fingerprint": fingerprint,
        "suppression_reason": reviewed.get("reason") if reviewed else None,
        "security_details": details or {},
    }


def parse_bandit(payload: dict[str, Any], baseline: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for item in payload.get("results", []):
        rule = str(item.get("test_id", "BANDIT"))
        filename = str(item.get("filename", "unknown"))
        line = int(item.get("line_number", 0) or 0) or None
        fingerprint = stable_fingerprint("bandit", rule, filename, line)
        findings.append(_common_finding(
            check="sast", rule_id=rule, title=item.get("issue_text", rule),
            severity=_severity(item.get("issue_severity")), component=filename,
            fingerprint=fingerprint, baseline=baseline,
            confidence=str(item.get("issue_confidence", "")),
            cwe=(item.get("issue_cwe") or {}).get("id"), line=line,
        ))
    return findings


def parse_pip_audit(payload: dict[str, Any] | list[Any], baseline: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    dependencies = payload.get("dependencies", []) if isinstance(payload, dict) else payload
    findings = []
    for dependency in dependencies:
        package = dependency.get("name", "unknown")
        version = dependency.get("version", "unknown")
        for vulnerability in dependency.get("vulns", []):
            vuln_id = vulnerability.get("id", "UNKNOWN")
            aliases = vulnerability.get("aliases", [])
            fingerprint = stable_fingerprint("pip-audit", package, version, vuln_id)
            findings.append(_common_finding(
                check="sca", rule_id=vuln_id,
                title=f"{package} {version} is affected by {vuln_id}",
                severity=_severity(vulnerability.get("severity")), component=package,
                fingerprint=fingerprint, baseline=baseline,
                cwe=next((alias for alias in aliases if str(alias).startswith("CWE-")), None),
                details={
                    "package": package, "installed_version": version,
                    "affected_range": _safe_text(vulnerability.get("description")),
                    "fixed_versions": vulnerability.get("fix_versions", []),
                    "aliases": aliases, "dependency_kind": "unknown",
                },
            ))
    return findings


def parse_gitleaks(payload: list[dict[str, Any]], baseline: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for item in payload:
        rule = str(item.get("RuleID", "secret"))
        filename = str(item.get("File", "unknown"))
        line = int(item.get("StartLine", 0) or 0) or None
        fingerprint = item.get("Fingerprint") or stable_fingerprint("gitleaks", rule, filename, line)
        findings.append(_common_finding(
            check="secrets", rule_id=rule, title=f"Potential secret detected by {rule}",
            severity="Critical", component=filename, fingerprint=fingerprint,
            baseline=baseline, line=line,
            details={"commit": _safe_text(item.get("Commit"), 40)},
        ))
    return findings


def parse_trivy(payload: dict[str, Any], baseline: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for result in payload.get("Results", []):
        target = result.get("Target", "repository")
        for item in result.get("Vulnerabilities") or []:
            vuln_id = item.get("VulnerabilityID", "UNKNOWN")
            package = item.get("PkgName", "unknown")
            fingerprint = stable_fingerprint("trivy", target, package, item.get("InstalledVersion"), vuln_id)
            findings.append(_common_finding(
                check="container", rule_id=vuln_id, title=item.get("Title") or f"{package}: {vuln_id}",
                severity=_severity(item.get("Severity")), component=f"{target}:{package}",
                fingerprint=fingerprint, baseline=baseline,
                details={"class": "package_vulnerability", "installed_version": item.get("InstalledVersion"),
                         "fixed_version": item.get("FixedVersion")},
            ))
        for item in result.get("Misconfigurations") or []:
            rule = item.get("ID", "MISCONFIG")
            fingerprint = stable_fingerprint("trivy", target, rule, item.get("CauseMetadata", {}).get("StartLine"))
            finding = _common_finding(
                check="container", rule_id=rule, title=item.get("Title", rule),
                severity=_severity(item.get("Severity")), component=target,
                fingerprint=fingerprint, baseline=baseline,
                cwe=item.get("CauseMetadata", {}).get("Provider"),
                line=item.get("CauseMetadata", {}).get("StartLine"),
                details={"class": "misconfiguration"},
            )
            finding["type"] = "SECURITY_MISCONFIGURATION"
            findings.append(finding)
    return findings


def parse_django_check(text: str, baseline: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    pattern = re.compile(r"(?m)^.*?\((security\.[WE]\d+)\)\s*(.*)$")
    for match in pattern.finditer(text):
        rule = match.group(1)
        fingerprint = stable_fingerprint("django-check", rule)
        findings.append(_common_finding(
            check="config", rule_id=rule, title=match.group(2) or rule,
            severity="High" if rule in {"security.W009", "security.W018"} else "Medium",
            component="src.settings", fingerprint=fingerprint, baseline=baseline,
            confidence="High", details={"classification": "deployment-dependent"},
        ))
    return findings


def _safe_url_metadata(value: str) -> str:
    parsed = urlparse(value)
    query_keys = sorted({key for key, _ in parse_qsl(parsed.query, keep_blank_values=True)})
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "&".join(query_keys), ""))


def parse_zap(payload: dict[str, Any], baseline: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for site in payload.get("site", []):
        for alert in site.get("alerts", []):
            plugin = str(alert.get("pluginid", alert.get("alertRef", "ZAP")))
            title = str(alert.get("alert", plugin))
            key = (plugin, title)
            item = grouped.setdefault(key, {"alert": alert, "instances": []})
            item["instances"].extend(alert.get("instances") or [{"uri": site.get("@name", "local-target")}])
    findings = []
    for (plugin, title), item in grouped.items():
        alert = item["alert"]
        instances = [
            {"method": _safe_text(instance.get("method")),
             "endpoint": _safe_url_metadata(str(instance.get("uri", "")))}
            for instance in item["instances"]
        ]
        first = instances[0] if instances else {"method": "", "endpoint": "local-target"}
        fingerprint = stable_fingerprint("zap", plugin, title)
        finding = _common_finding(
            check="dast", rule_id=plugin, title=title,
            severity=_severity(alert.get("riskcode") or alert.get("riskdesc", "").split()[0]),
            component=f"{first['method']} {first['endpoint']} ({len(instances)} instances)".strip(),
            fingerprint=fingerprint, baseline=baseline, confidence=alert.get("confidence"),
            cwe=alert.get("cweid"),
            details={"instances": instances, "instance_count": len(instances), "alert_ref": alert.get("alertRef")},
        )
        if plugin == "10116":
            finding["type"] = "TOOLING_LIMITATION"
            finding["area"] = "Security tooling"
        findings.append(finding)
    return findings


def _is_blocking(check: str, finding: dict[str, Any]) -> bool:
    if finding["known_or_new"] != "new":
        return False
    severity = finding["severity"]
    if check == "secrets":
        return True
    if severity == "Critical":
        return True
    if check == "sast":
        return severity == "High" and str(finding.get("confidence", "")).lower() == "high"
    return severity == "High" if check in {"sca", "container", "dast"} else False


def security_report(
    check: str, findings: list[dict[str, Any]], *, version: str | None,
    duration: float, exit_code: int, scope: str, exclusions: list[str] | None = None,
    network_safety: str = "NOT_APPLICABLE", execution_error: str | None = None,
) -> dict[str, Any]:
    if check not in SECURITY_CHECKS:
        raise ValueError(f"unsupported security check: {check}")
    blocking = [finding["finding_id"] for finding in findings if _is_blocking(check, finding)]
    failed = bool(execution_error) or network_safety == "FAILED" or bool(blocking)
    status = "FAIL" if failed else ("PASS WITH KNOWN FINDINGS" if findings else "PASS")
    return {
        "report_schema_version": SCHEMA_VERSION,
        "check": check,
        "scanner": SCANNERS[check],
        "scanner_version": version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **repository_identity(),
        "scope": scope,
        "execution": {
            "duration_seconds": round(duration, 3), "exit_code": exit_code,
            "status": status, "error": _safe_text(execution_error) if execution_error else None,
        },
        "findings": findings,
        "counts": {risk: sum(f["severity"] == risk for f in findings) for risk in RISK_LEVELS},
        "known": sum(f["known_or_new"] == "known" for f in findings),
        "new": sum(f["known_or_new"] == "new" for f in findings),
        "blocking_findings": blocking,
        "exclusions": exclusions or [],
        "network_safety": network_safety,
        "raw_evidence": {
            "sast": "artifacts/security/bandit.json",
            "sca": "artifacts/security/pip-audit.json",
            "secrets": "artifacts/security/gitleaks.json",
            "container": "artifacts/security/trivy.json",
            "config": "artifacts/security/django-check.txt",
            "dast": "artifacts/security/zap.json",
        }[check],
    }


def validate_security_report(report: dict[str, Any]) -> None:
    required = {"report_schema_version", "check", "scanner", "timestamp", "repository", "branch",
                "commit_sha", "scope", "execution", "findings", "counts", "known", "new",
                "blocking_findings", "exclusions", "network_safety", "raw_evidence"}
    missing = required - report.keys()
    if missing or report.get("check") not in SECURITY_CHECKS:
        raise ValueError(f"invalid security report; missing={sorted(missing)}")
    if report["execution"].get("status") not in {"PASS", "PASS WITH KNOWN FINDINGS", "FAIL", "NOT_RUN"}:
        raise ValueError("invalid security report status")


def aggregate_security(reports: list[dict[str, Any]]) -> dict[str, Any]:
    by_check = {}
    for report in reports:
        validate_security_report(report)
        by_check[report["check"]] = report
    missing = [check for check in SECURITY_CHECKS if check not in by_check]
    findings: dict[str, dict[str, Any]] = {}
    for report in by_check.values():
        for finding in report["findings"]:
            key = finding.get("nd_be_id") or finding["fingerprint"]
            if key not in findings:
                findings[key] = {**finding, "detected_by": [report["scanner"]]}
            elif report["scanner"] not in findings[key]["detected_by"]:
                findings[key]["detected_by"].append(report["scanner"])
    unique = list(findings.values())
    failed = bool(missing) or any(report["execution"]["status"] == "FAIL" for report in by_check.values())
    status = "FAIL" if failed else ("PASS WITH KNOWN FINDINGS" if unique else "PASS")
    identity = next(iter(by_check.values()), repository_identity())
    return {
        "report_schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repository": identity["repository"], "branch": identity["branch"], "commit_sha": identity["commit_sha"],
        "status": status, "checks": [by_check[c] for c in SECURITY_CHECKS if c in by_check],
        "missing_checks": missing, "findings": unique,
        "counts": {risk: sum(f["severity"] == risk for f in unique) for risk in RISK_LEVELS},
        "known": sum(f["known_or_new"] == "known" for f in unique),
        "new": sum(f["known_or_new"] == "new" for f in unique),
        "blocking_findings": sorted({item for report in by_check.values() for item in report["blocking_findings"]}),
        "network_safety": "FAILED" if any(r["network_safety"] == "FAILED" for r in by_check.values()) else "PASSED",
    }


def render_security_report(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['scanner']} security report", "", f"Status: **{report['execution']['status']}**", "",
        "| Critical | High | Medium | Low | Informational | Known | New |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        f"| {report['counts']['Critical']} | {report['counts']['High']} | {report['counts']['Medium']} | "
        f"{report['counts']['Low']} | {report['counts']['Informational']} | {report['known']} | {report['new']} |",
        "", "## Findings", "",
    ]
    lines.extend(
        f"- `{finding['finding_id']}` [{finding['severity']}] {finding['title']} — `{finding['endpoint_or_component']}`"
        for finding in report["findings"]
    )
    if not report["findings"]:
        lines.append("No findings.")
    lines.extend(["", "Raw evidence is retained as an artifact; secret values and response bodies are omitted here."])
    return "\n".join(lines) + "\n"


def render_security_summary(summary: dict[str, Any]) -> str:
    lines = ["# Backend security summary", "", f"Status: **{summary['status']}**", "",
             "| Check | Critical | High | Medium | Low | New | Status |",
             "|---|---:|---:|---:|---:|---:|---|"]
    for report in summary["checks"]:
        counts = report["counts"]
        lines.append(f"| {report['check'].title()} | {counts['Critical']} | {counts['High']} | "
                     f"{counts['Medium']} | {counts['Low']} | {report['new']} | {report['execution']['status']} |")
    if summary["missing_checks"]:
        lines.extend(["", f"Missing mandatory checks: {', '.join(summary['missing_checks'])}"])
    return "\n".join(lines) + "\n"


PARSERS = {
    "sast": parse_bandit,
    "sca": parse_pip_audit,
    "secrets": parse_gitleaks,
    "container": parse_trivy,
    "config": parse_django_check,
    "dast": parse_zap,
}
