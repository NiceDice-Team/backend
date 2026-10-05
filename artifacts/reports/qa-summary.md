<!-- nicedice-backend-qa-summary -->
## NiceDice Backend — QA & Security Summary

Revision: `20ccda5ec8bd`
Overall: **PASS WITH KNOWN FINDINGS**

| Layer | Passed | Failed | Findings | New | Known | Status |
|---|---:|---:|---:|---:|---:|---|
| Unit | 61 | 0 | 1 | 0 | 1 | PASS WITH KNOWN DEFECTS |
| Component | 28 | 0 | 3 | 0 | 3 | PASS WITH KNOWN DEFECTS |
| Api | 111 | 0 | 17 | 0 | 17 | PASS WITH KNOWN DEFECTS |
| Contract | 6 | 0 | 23 | 0 | 23 | PASS WITH KNOWN DEFECTS |
| Integration | 0 | 0 | 0 | 0 | 0 | NOT_IMPLEMENTED |

### Coverage

- Overall pytest: 206 passed, 0 failed
- Bug characterization: 18 passed, 0 failed
- Production line coverage: 86%
- Contract operations: 69 / 71
- Schemathesis cases: 880
- Integration: NOT_IMPLEMENTED

### Findings

- Critical: 3
- Major: 21
- Minor: 9
- High: 2
- Medium: 6
- Low: 6
- Informational: 3
- New findings: 7
- Known defects reproduced: 20
- Ready-to-file tickets: 20
- Needs clarification: 11

### New / Blocking Findings

No new blocking findings.

### Contract

- Known fingerprints: 77
- New fingerprints: 0
- Root-cause clusters: 15
- Excluded operations: 2

### Static Security

| Check | Critical | High | Medium | Low | New | Status |
|---|---:|---:|---:|---:|---:|---|
| Sast | 0 | 0 | 0 | 0 | 0 | PASS |
| Sca | 0 | 0 | 0 | 0 | 0 | PASS |
| Secrets | 0 | 0 | 0 | 0 | 0 | PASS |
| Container | 0 | 0 | 0 | 1 | 1 | PASS WITH KNOWN FINDINGS |
| Config | 0 | 2 | 4 | 0 | 0 | PASS WITH KNOWN FINDINGS |

### Dynamic Security

- ZAP endpoints/surface scanned: OpenAPI public surface; safe/passive API scan; authentication not configured
- High: 0
- Medium: 2
- Low: 5
- New: 6
- Status: PASS WITH KNOWN FINDINGS

### Security Gate

- Status: PASS WITH KNOWN FINDINGS
- Known scanner findings: 10
- New security findings: 7
- New blocking security findings: 0
- Ticket-ready security findings: 3

### Safety

- External non-local application targets contacted: NO
- Production application diff from test work: EMPTY

### Detailed Evidence

See uploaded CI artifacts: QA/security summaries, normalized reports, raw scanner evidence, JUnit, coverage, and Contract evidence.
