"""Command-line entry points for local and CI QA report generation."""

import argparse
import json
from pathlib import Path

from .core import (
    aggregate_reports, apply_contract_evidence, apply_coverage, base_report,
    findings_for_layer, integration_report, parse_junit, render_pr_summary,
    validate_report, write_json_and_markdown,
)
from .security import (
    PARSERS, SECURITY_CHECKS, aggregate_security, load_baseline,
    render_security_report, render_security_summary, security_report,
    validate_security_report,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    layer = sub.add_parser("layer")
    layer.add_argument("--layer", choices=("unit", "component", "api", "contract"), required=True)
    layer.add_argument("--junit", type=Path, required=True)
    layer.add_argument("--bug-report", type=Path, default=Path("artifacts/contract-bug-report.json"))
    layer.add_argument("--coverage", type=Path)
    layer.add_argument("--full-junit", type=Path)
    layer.add_argument("--bug-junit", type=Path)
    layer.add_argument("--contract-evidence", type=Path)
    layer.add_argument("--output-dir", type=Path, default=Path("artifacts/reports"))

    integration = sub.add_parser("integration")
    integration.add_argument("--output-dir", type=Path, default=Path("artifacts/reports"))

    aggregate = sub.add_parser("aggregate")
    aggregate.add_argument("--reports-dir", type=Path, default=Path("artifacts/reports"))

    security = sub.add_parser("security")
    security.add_argument("--check", choices=SECURITY_CHECKS, required=True)
    security.add_argument("--input", type=Path, required=True)
    security.add_argument("--baseline", type=Path, default=Path("docs/security-baseline.json"))
    security.add_argument("--version")
    security.add_argument("--duration", type=float, default=0.0)
    security.add_argument("--exit-code", type=int, default=0)
    security.add_argument("--scope", required=True)
    security.add_argument("--network-safety", choices=("PASSED", "FAILED", "NOT_APPLICABLE"), default="NOT_APPLICABLE")
    security.add_argument("--execution-error")
    security.add_argument("--output-dir", type=Path, default=Path("artifacts/reports"))

    security_aggregate = sub.add_parser("security-aggregate")
    security_aggregate.add_argument("--reports-dir", type=Path, default=Path("artifacts/reports"))

    args = parser.parse_args()
    if args.command == "layer":
        execution = parse_junit(args.junit)
        findings = findings_for_layer(args.layer, args.bug_report)
        report = base_report(args.layer, execution, findings)
        apply_coverage(report, args.coverage)
        if args.full_junit:
            report["details"]["overall_pytest"] = {
                key: value for key, value in parse_junit(args.full_junit).items() if key != "tests"
            }
        if args.bug_junit:
            report["details"]["bug_characterization"] = {
                key: value for key, value in parse_junit(args.bug_junit).items() if key != "tests"
            }
        report["evidence_artifacts"] = [args.junit.name]
        if args.layer == "api":
            report["details"]["negative_testing_matrix"] = "docs/negative-testing-matrix.md"
            report["details"]["ambiguous_or_blocked_scenarios"] = sorted(
                finding["finding_id"]
                for finding in findings
                if finding["requires_clarification"] or finding["status"] == "BLOCKED"
            )
        if args.layer == "contract":
            if not args.contract_evidence:
                parser.error("contract layer requires --contract-evidence")
            apply_contract_evidence(report, args.contract_evidence)
        write_json_and_markdown(
            report,
            args.output_dir / f"{args.layer}-test-report.json",
            args.output_dir / f"{args.layer}-test-report.md",
        )
        return 0
    if args.command == "integration":
        report = integration_report()
        write_json_and_markdown(
            report,
            args.output_dir / "integration-test-report.json",
            args.output_dir / "integration-test-report.md",
        )
        return 0

    if args.command == "security":
        baseline = load_baseline(args.baseline)
        if args.check == "config":
            payload = args.input.read_text()
        else:
            payload = json.loads(args.input.read_text())
        findings = PARSERS[args.check](payload, baseline)
        report = security_report(
            args.check, findings, version=args.version, duration=args.duration,
            exit_code=args.exit_code, scope=args.scope,
            network_safety=args.network_safety, execution_error=args.execution_error,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        stem = {
            "sast": "sast-report", "sca": "sca-report", "secrets": "secrets-report",
            "container": "container-security-report", "config": "config-security-report",
            "dast": "dast-report",
        }[args.check]
        (args.output_dir / f"{stem}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        (args.output_dir / f"{stem}.md").write_text(render_security_report(report))
        return 1 if report["execution"]["status"] == "FAIL" else 0

    if args.command == "security-aggregate":
        reports = []
        for stem in ("sast-report", "sca-report", "secrets-report", "container-security-report", "config-security-report", "dast-report"):
            path = args.reports_dir / f"{stem}.json"
            if path.exists():
                report = json.loads(path.read_text())
                validate_security_report(report)
                reports.append(report)
        summary = aggregate_security(reports)
        (args.reports_dir / "security-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        (args.reports_dir / "security-summary.md").write_text(render_security_summary(summary))
        return 1 if summary["status"] == "FAIL" else 0

    reports = []
    for layer_name in ("unit", "component", "api", "contract", "integration"):
        path = args.reports_dir / f"{layer_name}-test-report.json"
        if path.exists():
            report = json.loads(path.read_text())
            validate_report(report)
            reports.append(report)
    security_path = args.reports_dir / "security-summary.json"
    security_summary = json.loads(security_path.read_text()) if security_path.exists() else None
    summary = aggregate_reports(reports, security_summary)
    (args.reports_dir / "qa-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (args.reports_dir / "qa-summary.md").write_text(render_pr_summary(summary))
    return 1 if summary["overall_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
