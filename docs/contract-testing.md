# Runtime OpenAPI contract testing

## Execution model

Contract tests use `src.contract_settings`, which overwrites unsafe inherited values before loading application
settings. `tests/contract/run_contract.sh` creates a unique SQLite file for every local invocation; CI sets
`CONTRACT_USE_POSTGRES=1` and receives a fresh PostgreSQL service database. The same per-run database is shared by
the migration, seed, server, and generator processes, then the local file is deleted unless
`CONTRACT_PRESERVE_DATABASE=1` is explicitly set.

The previous workflow used `src.test_settings`, whose database is SQLite `:memory:`. Migrations were applied in
the short-lived migration process; the server then opened a different empty in-memory database. PostgreSQL env
variables were ignored. The unit workflow also forced `src.settings`, overriding `pytest.ini` and causing the
email-sender assertion to see `webmaster@localhost`; it now uses `src.test_settings` consistently.

The runtime harness uses local-only email/storage, establishes canonical user/category/brand/product state, and
fails if it cannot create a JWT. A process-wide socket guard is loaded into Django and Schemathesis through
`sitecustomize`; it rejects every non-loopback destination before connection. Explicit local CI service names may
be added with `CONTRACT_ALLOWED_LOCAL_HOSTS`. Preflight rejects non-local DB, SMTP, frontend, and storage endpoints
and populated external credentials. Redirect following remains disabled as a separate defense. OAuth and Stripe
operations are excluded by exactly two reviewed operation IDs because their production boundaries are not
injectable; they remain in inventory and formal schema validation.

## Latest independent local executions

Two corrected runs on 2026-10-04 used Schemathesis 4.1.4, independently created SQLite databases, deterministic
canonical seed data, process-level local-only egress enforcement, two exact external-provider exclusions, and
redirect following disabled.

- 71 operations discovered; 69 selected and all 69 exercised; 2 excluded with CT-019/CT-020.
- Both runs: 890 generated cases; 75 cases found failures; 78 unique check failures; 5 cases skipped.
- Both runs: 2 server errors, 11 response-schema violations, 13 accepted-invalid requests, 19 rejected-valid
  requests, 31 undocumented content types, and 2 undocumented status codes.
- The single unique network error is the intentionally blocked 302 from `GET /api/users/reset-password/` because
  `--max-redirects 0` prevents following the configured frontend URL.
- Both normalized comparisons found 79 known fingerprints, no new fingerprint, and the same 4
  resolved/candidate-for-removal fingerprints. The runtime gate passed in both runs.
- JUnit, full console output, schema, formal-validation log, operation matrix, and normalized JSON are retained in
  `schemathesis-report/` in CI.

The CI gate is green with reviewed debt visible. Schemathesis still exits non-zero for known failures; the runner
does not ignore that output, but requires a JUnit report and performs an exact operation/check/root-cause baseline
comparison. New fingerprints, new 5xx families, an existing cause on a new operation, exclusion expansion,
formal-validation additions, unsafe configuration, or guard/setup failure make the job red. Disappearing known
fingerprints are reported as cleanup candidates.

## Local commands

Use the guarded runner; it owns database and server lifecycle and prints the evidence directory:

```bash
CONTRACT_PYTHON=.venv/bin/python bash tests/contract/run_contract.sh
```

Exact exclusions:

| Finding | Operation | Classification | Reason | Unblocking condition |
|---|---|---|---|---|
| CT-019 | `users_oauth_create` | TEST_DATA_LIMITATION | Requires Google/Facebook provider validation and must not receive real tokens in CI. | Add an injectable local provider boundary. |
| CT-020 | `orders_create_payment_intent_create` | TEST_DATA_LIMITATION | Valid requests call Stripe. | Add an injectable local payment provider boundary. |

`missing_required_header` is deferred because this schema declares no required non-security request headers; it
would not add a contract distinct from the security scheme. `ignored_auth` is deferred from this runtime baseline
because the global valid JWT plus widespread schema/runtime permission mismatch would duplicate the existing
deterministic authorization findings (ND-BE-001/002/008) across many operations rather than isolate a new cause.
It should be enabled in a separately reviewed, operation-scoped authorization gate after those security contracts
are corrected. `unsupported_method`, `use_after_free`, and `ensure_resource_availability` remain deferred because
they require method-aware/stateful setup and would introduce untriaged ordering noise. Response status, content
type, headers, body schema, positive/negative acceptance, and absence of 5xx remain enforced.

## Reviewed baselines

`tests/contract/baselines/runtime_failures.json` keeps exact operation ID + check + RC fingerprints and a registry
of RC-01 through RC-18. Distribution remains Implementation 5, OpenAPI/schema 5, Both 5, Test-data/setup 2, and
Tooling 1. RC-01/02/03/04 link to ND-BE-018/020/021/022. The fresh runs did not reproduce RC-01 or RC-04, so their
four 5xx/content-type fingerprints are reported as resolved candidates rather than silently removed.

ND-BE-022 remains a real backend defect proven by its deterministic regression test. However, neither fresh run
could create the required email/username drift through generated public transitions, so the earlier Schemathesis
observation is now classified as contaminated-state discovery, not independent clean-state discovery.

`tests/contract/baselines/schema_validation.json` separately reviews FSV-001 (`Order.product_count` inferred as
string), FSV-002 (unresolved payment serializer), and FSV-003 (invalid OAuth response property). Formal validation
still exits non-zero, all three known signatures remain visible, and any unrecognized warning/error or replacement
schema-validation exception fails the comparison.

## Schema inventory

- OpenAPI: 3.0.3
- Paths: 33
- Operations: 71
- Component schemas: 274
- Operations with request bodies: 38
- Schema-declared authenticated operations: 66
- Schema-declared public operations: 5
- External-provider exclusions: 2

The schema declares only OAuth, registration, resend activation, token creation, and token refresh public. This
conflicts with current `AllowAny` behavior for cart, orders, payments, and product-image mutations and links to
ND-BE-001, ND-BE-002, and ND-BE-008.

## Contract coverage matrix

`Positive` and `Negative` mean the operation was selected by the generated runtime run. Authenticated CRUD paths
need seeded resource IDs for successful stateful flows, so their response-contract result is partial even though
generated requests execute.

| Endpoint | Method | Schema documented | Tested | Positive | Negative | Auth | Result |
|---|---|---|---|---|---|---|---|
| `/api/audiences/` | GET, POST | YES | YES | YES | YES | JWT | PARTIAL |
| `/api/audiences/{id}/` | GET, PUT, PATCH, DELETE | YES | YES | YES | YES | JWT | STATE_SETUP_REQUIRED |
| `/api/brands/` | GET, POST | YES | YES | YES | YES | JWT | PARTIAL |
| `/api/brands/{id}/` | GET, PUT, PATCH, DELETE | YES | YES | YES | YES | JWT | STATE_SETUP_REQUIRED |
| `/api/carts/` | GET, POST | YES | YES | YES | YES | Schema says JWT; implementation public | FAIL |
| `/api/carts/{id}/` | GET, PUT, PATCH, DELETE | YES | YES | YES | YES | Schema says JWT; implementation public | FAIL |
| `/api/categories/` | GET, POST | YES | YES | YES | YES | JWT | PARTIAL |
| `/api/categories/{id}/` | GET, PUT, PATCH, DELETE | YES | YES | YES | YES | JWT | STATE_SETUP_REQUIRED |
| `/api/game-types/` | GET, POST | YES | YES | YES | YES | JWT | PARTIAL |
| `/api/game-types/{id}/` | GET, PUT, PATCH, DELETE | YES | YES | YES | YES | JWT | STATE_SETUP_REQUIRED |
| `/api/orders/` | GET, POST | YES | YES | YES | YES | Schema says JWT; implementation public | FAIL |
| `/api/orders/create-payment-intent/` | POST | INCOMPLETE | NO | NO | NO | Schema says JWT; implementation public | EXCLUDED_WITH_REASON |
| `/api/photos/` | GET, POST | YES | YES | YES | YES | JWT | PARTIAL |
| `/api/photos/{id}/` | GET, PUT, PATCH, DELETE | YES | YES | YES | YES | JWT | STATE_SETUP_REQUIRED |
| `/api/products/` | GET, POST | YES | YES | YES | YES | JWT mutation | FAIL |
| `/api/products/{id}/` | GET, PUT, PATCH, DELETE | YES | YES | YES | YES | JWT mutation | STATE_SETUP_REQUIRED |
| `/api/products/{product_id}/images/` | POST | YES | YES | YES | YES | Schema says JWT; implementation public | FAIL |
| `/api/products/{product_id}/images/{image_id}/` | DELETE | YES | YES | YES | YES | Schema says JWT; implementation public | FAIL |
| `/api/products/{product_id}/images/order/` | PATCH | YES | YES | YES | YES | Schema says JWT; implementation public | FAIL |
| `/api/reviews/` | GET, POST | YES | YES | YES | YES | JWT | PARTIAL |
| `/api/reviews/{id}/` | GET, PUT, PATCH, DELETE | YES | YES | YES | YES | JWT | STATE_SETUP_REQUIRED |
| `/api/users/` | GET, POST | YES | YES | YES | YES | JWT | PARTIAL |
| `/api/users/{id}/` | GET, PUT, PATCH, DELETE | YES | YES | YES | YES | JWT | STATE_SETUP_REQUIRED |
| `/api/users/activate/{uidb64}/{token}/` | GET | INCOMPLETE | PARTIAL | YES | ERROR | JWT declared | SCHEMA_BLOCKED |
| `/api/users/auth/user-id/` | GET | YES | YES | YES | YES | JWT | PASS |
| `/api/users/forgot-password/` | POST | YES | YES | YES | YES | JWT declared | PARTIAL |
| `/api/users/logout/` | POST | YES | YES | YES | YES | JWT | STATE_SETUP_REQUIRED |
| `/api/users/oauth/` | POST | INVALID RESPONSE SCHEMA | NO | NO | NO | Public | EXCLUDED_WITH_REASON |
| `/api/users/register/` | POST | INCOMPLETE CONSTRAINTS | YES | YES | YES | Public | FAIL |
| `/api/users/resend-activation/` | POST | INCOMPLETE | YES | YES | YES | Public | FAIL |
| `/api/users/reset-password/` | GET, POST | INCOMPLETE | YES | YES | YES | JWT declared | FAIL |
| `/api/users/token/` | POST | INCOMPLETE CONSTRAINTS | YES | YES | YES | Public | FAIL |
| `/api/users/token/refresh/` | POST | INCOMPLETE CONSTRAINTS | YES | YES | YES | Public | FAIL |

## Contract findings

| ID | Type | Endpoint | Generated case | Observed | Contract expectation | Status |
|---|---|---|---|---|---|---|
| CT-001 / ND-BE-019 | SCHEMA_DEFECT | `POST /api/users/oauth/` | Schema validation | `user` response property is an array | Valid Schema Object/reference | CONFIRMED |
| CT-002 | SCHEMA_DEFECT | OAuth/register/token endpoints | Empty strings generated as valid | Implementation returns controlled 400 | Schema must express non-blank/min-length constraints | OPEN |
| CT-003 | SCHEMA_DEFECT | `POST /api/orders/create-payment-intent/` | Schema generation | Request serializer cannot be resolved | Document request and response schemas | OPEN |
| CT-004 | SCHEMA_DEFECT | `GET /api/orders/` | Schema generation | `product_count` defaults to string | Declare the integer return type | OPEN |
| CT-005 | UNDOCUMENTED_BEHAVIOR | Cart detail mutations | Malformed requests | Custom `{detail: ...}` bodies violate documented standardized error schemas | Runtime error body matches schema | OPEN |
| CT-006 | SCHEMA_DEFECT | Integer detail paths | Negative/non-integer generated IDs | Django URL resolver returns HTML 404 | Path constraints and documented content type match routing | OPEN |
| CT-007 | SCHEMA_DEFECT | Cart/orders/images | Auth inventory | Schema declares JWT while implementation uses `AllowAny` | Security declaration matches runtime | LINKS ND-BE-001/002/008 |
| CT-008 | SCHEMA_DEFECT | `POST /api/products/` | Success metadata | Schema documents 200 | Runtime create contract is 201 | OPEN |
| CT-009 | SCHEMA_DEFECT | `DELETE /api/categories/{id}/` | Success metadata | Schema documents 200 | Runtime delete contract is 204 | OPEN |
| CT-010 / ND-BE-006 | IMPLEMENTATION_DEFECT | `GET /api/products/` | Large generated `limit` | HTTP 500 | Controlled 4xx or capped limit | CONFIRMED |
| CT-011 / ND-BE-017 | IMPLEMENTATION_DEFECT | `POST /api/orders/` | JSON array | HTTP 500 | Controlled 400 | CONFIRMED |
| CT-012 / ND-BE-018 | IMPLEMENTATION_DEFECT | `POST /api/users/resend-activation/` | JSON array | HTTP 500 | Controlled 400 | CONFIRMED |
| CT-013 | UNDOCUMENTED_BEHAVIOR | `GET /api/users/reset-password/` | Missing query parameters | 302 redirect to frontend | Redirect response is explicitly documented and constrained | OPEN |
| CT-014 | TEST_DATA_LIMITATION | Authenticated detail operations | Unknown generated IDs | Mostly 404 responses | Seed-aware/stateful links provide real IDs | STATE_SETUP_REQUIRED |
| CT-015 | TOOLING_LIMITATION | Auth-sensitive operations | Missing-header/unsupported-method checks | Auth and URL routing happen before method/header expectations | These optional checks need operation-aware policy | EXCLUDED_WITH_REASON |
| CT-016 / ND-BE-020 | IMPLEMENTATION_DEFECT | `POST /api/categories/` | A second punctuation-only name derives the same empty slug | HTTP 500; no second row persisted | Controlled 400 validation response | CONFIRMED |
| CT-017 / ND-BE-021 | IMPLEMENTATION_DEFECT | `POST /api/photos/` | Empty object accepted by the write serializer | HTTP 500 on missing `product_id`; no image persisted | Controlled 400 or a read-only endpoint | CONFIRMED |
| CT-018 / ND-BE-022 | IMPLEMENTATION_DEFECT | `POST /api/users/register/` | Email is available but equals an existing username | HTTP 500 uniqueness failure; no new account persisted | Controlled 400 and consistent identity constraints | CONFIRMED |
| CT-019 | TEST_DATA_LIMITATION | `POST /api/users/oauth/` | Runtime generation excluded by exact operation ID | Real tokens would contact Google/Facebook; response schema is still validated separately by CT-001 | Injectable local provider boundary | EXCLUDED_WITH_REASON |
| CT-020 | TEST_DATA_LIMITATION | `POST /api/orders/create-payment-intent/` | Runtime generation excluded by exact operation ID | A valid request would contact Stripe; schema-generation defect is recorded by CT-003 | Injectable local payment-provider boundary | EXCLUDED_WITH_REASON |

Formal `manage.py spectacular --validate` currently fails. Generated runs are still possible, but CI intentionally
fails on the documented contract violations; no blanket `continue-on-error` or response-check suppression is used.
