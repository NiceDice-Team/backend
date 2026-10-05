# Backend static and dynamic security gate

## Pre-change inventory

The repository was inspected before adding scanners. Existing API and Contract tests characterize three confirmed
authorization defects (`ND-BE-001`, `ND-BE-002`, and `ND-BE-008`), but none of the scanner capabilities below
was integrated into CI, normalized reports, or the PR dashboard.

| Capability | Existing | Tool before change | CI | Blocking | Report | PR summary |
|---|---|---|---|---|---|---|
| SAST | No | None | No | No | No | No |
| SCA | No | None | No | No | No | No |
| Secret scan | No | None | No | No | No | No |
| Container scan | No | None | No | No | No | No |
| Config scan | No | None | No | No | No | No |
| Django security check | No | None | No | No | No | No |
| DAST | No | None | No | No | No | No |

Dockerfiles, Compose files, `requirements*.txt`, Django settings, all workflows, existing artifacts, and the
Contract egress guard were included in the inventory. There was no scanner configuration hidden elsewhere.

## Implemented architecture and ownership

- Bandit 1.8.6 owns Python SAST. It scans production source and explicitly excludes migrations, local settings,
  in-source legacy test suites, and the test-data loader. These exclusions are scope decisions, not silent rule
  suppressions.
- pip-audit 2.9.0 owns Python dependency/SCA evidence. The repository has no lock file, so the result applies to
  packages resolved at scan time; direct/transitive ownership and reproducibility remain evidence gaps.
- Gitleaks 8.24.2 owns repository/history secret detection and always uses redaction. Reports never include a
  secret value and discovered credentials are never validated.
- Trivy owns filesystem dependency and Docker/Compose misconfiguration evidence. pip-audit remains the primary
  Python SCA source; cross-tool fingerprints prevent duplicate bug counts.
- `manage.py check --deploy` runs under fail-closed local Contract settings. Reviewed test-environment and
  deployment-dependent warnings remain visible in `docs/security-baseline.json`.
- OWASP ZAP 2.16.1 runs `zap-api-scan.py` in safe (`-S`) OpenAPI mode against a disposable local backend. No
  active attack scan is enabled for pull requests.

Each check is an independent CI job. It uploads raw evidence plus normalized JSON/Markdown. Aggregation runs
with `if: always()` and fails if a mandatory report is missing, a scanner fails, ZAP escapes its allowlist, or a
new blocking finding appears. Reporting cannot turn a failed scanner green.

## Gate policy

Immediate failure:

- any detected secret;
- new Critical finding;
- new High-severity, High-confidence Bandit finding;
- new High/Critical SCA, Trivy, or ZAP finding;
- scanner execution failure or missing mandatory report;
- any ZAP evidence URL outside loopback or the explicit `host.docker.internal` bridge.

Medium, Low, Informational, and low-confidence findings remain visible and require review. Reviewed non-Critical
debt produces `PASS WITH KNOWN FINDINGS`. Critical findings are never automatically baselined. Every baseline
entry records the stable fingerprint, scanner, rule, review state, and reason; baselining changes classification,
not evidence visibility.

Cross-tool deduplication prefers an existing `ND-BE-*` application identity when a reviewed mapping exists,
then uses the scanner fingerprint. A shared CWE alone is never sufficient to merge findings.

## ZAP scope and network safety

PR DAST imports the locally generated OpenAPI document and performs safe/passive API scanning. Public operations
are covered; deterministic authenticated setup is not yet implemented, so authenticated authorization behavior
continues to be owned by API regression tests. External OAuth, Stripe, CDN/storage, frontend redirects, external
images, and arbitrary discovered hosts are excluded.

`scripts/run_zap_local.sh` rejects non-local targets before starting ZAP. The post-scan verifier inspects every
site and instance URL in raw ZAP JSON and requires an exact allowlisted origin (scheme, host, and port). A
non-allowlisted URL fails the gate and is reported only as scheme/host/port.
Raw response bodies are not copied into normalized or PR reports.

## Local reproduction

Use a disposable environment and install the pinned Python tools:

```bash
python -m pip install -r requirements-dev.txt
bash scripts/run_security_check.sh sast
bash scripts/run_security_check.sh sca
bash scripts/run_security_check.sh secrets
bash scripts/run_security_check.sh container
bash scripts/run_security_check.sh config
```

Gitleaks and Trivy use a local binary when available, otherwise their pinned container image. Their public rule
and vulnerability databases are infrastructure dependencies, not application targets.

For DAST, start a disposable backend with `src.contract_settings`, a local SQLite/PostgreSQL database, empty
provider credentials, and only local URLs. Then run:

```bash
ZAP_TARGET=http://host.docker.internal:8000/api/schema/ \
  bash scripts/run_zap_local.sh
python -m qa_reporting.cli security-aggregate
python -m qa_reporting.cli aggregate
```

Never point `ZAP_TARGET` at staging or production. The script rejects it even if a user supplies such a URL.

## Evidence

Raw scanner output is written beneath `artifacts/security/`; normalized reports are written beneath
`artifacts/reports/`. Raw Gitleaks evidence is redacted. Markdown and the PR comment contain metadata only.
`security-summary.json` feeds `qa-summary.json`, and one bot comment with the stable QA marker is updated.

Known limitations are explicit: dependency inputs are not locked; image vulnerability scanning requires a built
image and is reserved for the deeper scheduled/manual gate; authenticated ZAP coverage is not yet implemented;
and deployment-owned TLS/proxy behavior cannot be confirmed from this repository alone.
