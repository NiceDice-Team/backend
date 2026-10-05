# Unified backend QA reporting

## Architecture

Every test layer emits one JSON report using `docs/qa-report-schema.json` and one compact Markdown rendering.
`qa_reporting` parses pytest JUnit, enriches it with reviewed findings, and aggregates reports without changing
application behavior.

```text
Unit / Component / API pytest JUnit ─┐
Contract pytest + Schemathesis ──────┼─> normalized layer reports
Integration report contract ─────────┘              │
                                                    v
                              security-summary.json ─┤
                                                    v
                               qa-summary.json / qa-summary.md
                                                    │
                                      one updated PR dashboard comment
```

Layer artifacts live in `artifacts/reports/`:

- `unit-test-report.{json,md}`
- `component-test-report.{json,md}`
- `api-test-report.{json,md}`
- `contract-test-report.{json,md}`
- `integration-test-report.{json,md}`
- `qa-summary.{json,md}`
- `sast-report.{json,md}`, `sca-report.{json,md}`, and `secrets-report.{json,md}`
- `container-security-report.{json,md}`, `config-security-report.{json,md}`, and `dast-report.{json,md}`
- `security-summary.{json,md}`

The detailed Contract ticket report remains in `docs/contract-bug-report.md` and
`artifacts/contract-bug-report.json`; it is an input to the normalized Contract report rather than a parallel
finding registry. Raw Schemathesis evidence remains described by `docs/contract-testing.md`.

## Common model and layer ownership

Reports contain repository/revision identity, environment and tool versions, execution counts and duration,
optional coverage, normalized findings, known/new/blocked state, exclusions, metrics and evidence paths. Fields
that do not apply use `null` or `not_applicable`. The aggregate also records the complete pytest result and the
secondary `bug` marker result without treating `bug` as a sixth primary layer.

- Unit owns isolated product/service/provider logic and unit-level testability limitations.
- Component owns serializer, persistence and component/service-boundary evidence.
- API owns endpoint behavior, authorization, boundary and state verification; its matrix remains
  `docs/negative-testing-matrix.md`.
- Contract owns OpenAPI validation, Schemathesis operation coverage, fingerprints, root causes and exclusions.
- Integration currently reports `NOT_IMPLEMENTED`; it defines future PostgreSQL, Mailcatcher, S3-compatible,
  provider-fake, container-health and cross-component reporting fields without fabricating results.

## Finding identity and deduplication

Aggregation uses the first available stable key in this order: ND-BE ID, FSV ID, stable finding ID, then a
normalized endpoint/root/type fingerprint. Titles are never deduplication keys. The aggregate keeps one finding
and adds `detected_by` for every contributing layer.

Supported types and statuses are constrained by the JSON schema and runtime validator. Malformed reports fail
aggregation rather than silently producing an incomplete dashboard.

Security scanner ownership, baseline policy, ZAP allowlisting, and local reproduction are documented in
`docs/security-testing.md`. Scanner alerts are normalized into the same finding model; an ND-BE mapping can join
scanner and API/Contract evidence, while CWE equality alone cannot.

## Overall status

- `FAIL`: a required layer failed/did not run, a new unreviewed Contract/formal issue exists, or a new
  Critical/Major finding exists.
- `PASS WITH KNOWN FINDINGS`: all required test and security gates pass with no new blocker, but reviewed active
  findings remain.
- `PASS`: all required gates pass and no active known finding remains.

Pytest green alone is therefore insufficient for an overall `PASS`.

## GitHub PR behavior and safety

The unified workflow runs test jobs, uploads their reports, then executes aggregation with `if: always()`. Report
generation never masks an upstream test failure. The PR body contains the stable marker
`<!-- nicedice-backend-qa-summary -->`; the workflow updates only the matching `github-actions[bot]` comment and
creates it only when absent. Human comments are never modified.

The workflow requests only `contents: read` and `pull-requests: write`. Commenting runs only for same-repository
pull requests. Fork pull requests still run tests and upload artifacts with the read-only token, then log an
explicit skip reason; no secrets are provided to fork code.

## Local reproduction

Generate all available reports, including a fresh guarded Contract run:

```bash
QA_PYTHON=.venv/bin/python bash scripts/generate_qa_reports.sh
```

This command never publishes a PR comment. Reports and raw evidence must not contain credentials, JWTs or
environment dumps.
