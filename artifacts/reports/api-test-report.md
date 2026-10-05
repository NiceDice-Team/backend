# Api test report

Revision: `1f0510b96ca39cbba792f7a0922e07ee64e3b096`

Status: **PASS WITH KNOWN DEFECTS**

| Collected | Passed | Failed | Skipped | Warnings | Duration | Findings |
|---:|---:|---:|---:|---:|---:|---:|
| 111 | 111 | 0 | 0 | 0 | 0.779s | 17 |

## Findings

- `APP-01` [Major] Fix inconsistent password-reset payload and serializer token field
- `APP-02` [Major] Make registration atomic when activation email delivery fails
- `APP-03` [Major] Return controlled validation response for product limit above 100
- `APP-04` [Major] Remove server-managed fields from category create requirements
- `APP-05` [Major] Make product-image reorder validation and persistence atomic
- `APP-06` [Major] Validate top-level order request type instead of returning 500
- `APP-07` [Major] Return HTTP 400 for non-object resend-activation payloads
- `APP-08` [Major] Validate empty and colliding derived category slugs
- `APP-09` [Major] Validate product ownership before generic photo creation
- `APP-10` [Major] Validate registration email against username uniqueness collisions
- `SEC-01` [Critical] Require authenticated ownership for all cart operations
- `SEC-02` [Critical] Require authenticated ownership for order history and checkout
- `SEC-03` [Critical] Protect product-image upload, reorder and delete with authorization
- `CLR-01` [Major] Enforce agreed cart quantity and stock boundaries
- `CLR-02` [Minor] Define image deletion behavior when storage cleanup fails
- `CLR-03` [Major] Persist immutable order item price and quantity snapshots
- `ND-BE-014` [Minor] User routes load the same code under two module identities

## Evidence

- `api.xml`
