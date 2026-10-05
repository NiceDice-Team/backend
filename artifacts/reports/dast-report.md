# zap security report

Status: **PASS WITH KNOWN FINDINGS**

| Critical | High | Medium | Low | Informational | Known | New |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 2 | 5 | 3 | 4 | 6 |

## Findings

- `ZAP-adc5a63973` [Medium] Absence of Anti-CSRF Tokens — `GET http://host.docker.internal:28140/api/schema/ (1 instances)`
- `ZAP-2b56c6382a` [Medium] Content Security Policy (CSP) Header Not Set — `GET http://host.docker.internal:28140/api/schema/ (1 instances)`
- `ZAP-d0c76a56e3` [Low] Permissions Policy Header Not Set — `GET http://host.docker.internal:28140/api/schema/ (1 instances)`
- `ZAP-435a4d39ba` [Low] Private IP Disclosure — `GET http://host.docker.internal:28140/api/schema/ (1 instances)`
- `SEC-DAST-003` [Low] Server Leaks Version Information via "Server" HTTP Response Header Field — `GET http://host.docker.internal:28140/api/schema/ (1 instances)`
- `SEC-DAST-001` [Low] Unexpected Content-Type was returned — `GET http://host.docker.internal:28140/api/schema/ (1 instances)`
- `SEC-TOOL-001` [Low] ZAP is Out of Date — `GET http://host.docker.internal:28140/api/schema/ (1 instances)`
- `SEC-DAST-004` [Informational] A Client Error response code was returned by the server — `GET http://host.docker.internal:28140/api/schema/ (1 instances)`
- `ZAP-2b66671829` [Informational] Modern Web Application — `GET http://host.docker.internal:28140/api/schema/ (1 instances)`
- `ZAP-c8d6d675a0` [Informational] Non-Storable Content — `GET http://host.docker.internal:28140/api/schema/ (1 instances)`

Raw evidence is retained as an artifact; secret values and response bodies are omitted here.
