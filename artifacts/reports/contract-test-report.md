# Contract test report

Revision: `1f0510b96ca39cbba792f7a0922e07ee64e3b096`

Status: **PASS WITH KNOWN DEFECTS**

| Collected | Passed | Failed | Skipped | Warnings | Duration | Findings |
|---:|---:|---:|---:|---:|---:|---:|
| 6 | 6 | 0 | 0 | 0 | 0.578s | 23 |

## Findings

- `APP-01` [Major] Fix inconsistent password-reset payload and serializer token field
- `APP-03` [Major] Return controlled validation response for product limit above 100
- `APP-04` [Major] Remove server-managed fields from category create requirements
- `APP-07` [Major] Return HTTP 400 for non-object resend-activation payloads
- `APP-08` [Major] Validate empty and colliding derived category slugs
- `APP-09` [Major] Validate product ownership before generic photo creation
- `APP-10` [Major] Validate registration email against username uniqueness collisions
- `SEC-01` [Critical] Require authenticated ownership for all cart operations
- `SEC-02` [Critical] Require authenticated ownership for order history and checkout
- `SEC-03` [Critical] Protect product-image upload, reorder and delete with authorization
- `SCH-01` [Major] Declare Order.product_count as integer in OpenAPI
- `SCH-02` [Major] Document payment-intent request and response serializers
- `SCH-03` [Major] Replace invalid OAuth user response array with an OpenAPI schema
- `SCH-04` [Major] Align cart success and validation-error response schemas
- `SCH-05` [Major] Correct category image and product response schemas
- `SCH-06` [Major] Add missing runtime validation constraints to OpenAPI request schemas
- `SCH-07` [Major] Document actual API statuses, redirects and typed-path error content
- `RC-13` [Minor] prove with a normal client payload
- `RC-14` [Minor] isolate throttle state
- `RC-17` [Minor] add stateful prerequisites
- `CT-019` [Minor] add local OAuth provider boundary
- `CT-020` [Minor] add local payment provider boundary
- `DEFERRED_CHECKS` [Minor] add operation-scoped/stateful check plan

## Evidence

- `junit.xml`
- `schemathesis-output.txt`
- `normalized-failures.json`
- `operation-matrix.json`
- `schema-validation.json`
- `schema-validation.log`
- `docs/contract-bug-report.md`
- `artifacts/contract-bug-report.json`
