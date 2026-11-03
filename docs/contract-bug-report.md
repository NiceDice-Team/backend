# NiceDice backend contract bug report

## 1. Executive summary

This report converts the reviewed OpenAPI and Schemathesis evidence into ticket-sized root causes. It does not
count generated examples as independent defects.

> **890 generated cases and 78 unique check failures do not mean 78 product bugs.** The reviewed baseline groups
> runtime evidence into 18 root-cause clusters, of which 16 were observed on each clean run. Related causes are
> further grouped into 24 actionable or clarification-oriented ticket candidates.

| Item | Value |
|---|---|
| Contract run date | 2026-10-04 |
| Backend revision containing the reviewed test foundation | `0e0d43a8a08843c9517414de6af51c7b6a10a29a` |
| Production application revision/context | Parent `1949d6fb65c400cc040c0b38f27697e2ecf17058`; production application diff is empty |
| OpenAPI context | Runtime-generated OpenAPI 3.0.3; 33 paths, 71 operations, 274 component schemas |
| Schemathesis | 4.1.4, deterministic mode, two independently fresh SQLite databases |
| Operations discovered / executed | 71 / 69 |
| Excluded operations | `users_oauth_create` (real OAuth provider boundary); `orders_create_payment_intent_create` (real Stripe boundary) |
| Generated cases | 890 in run A; 890 in run B |
| Failing generated cases | 75 in each run |
| Unique check failures | 78 in each run, plus one intentionally blocked redirect/network error |
| Normalized observed fingerprints | 79 known; 0 new; 4 resolved candidates |
| Root-cause registry / observed | 18 registered / 16 observed on both fresh runs |
| Confirmed application candidates | 10 tickets |
| Confirmed security candidates | 3 tickets |
| Schema/documentation candidates | 7 tickets |
| Needs requirements clarification | 4 findings |
| Technical/setup/tooling only | 6 groups |

The four resolved candidates are the server-error and content-type fingerprints for RC-01/ND-BE-018 and
RC-04/ND-BE-022. Their deterministic regression tests still prove the application defects. Their disappearance
only means the fresh generated runs did not recreate the prerequisite state/input; it does not close the defects.

## 2. Bug candidate summary

| Candidate ID | Severity | Type | Area | Endpoint | Summary | Reproducible | Existing ND-BE | Recommended action |
|---|---|---|---|---|---|---|---|---|
| APP-01 | Major | APPLICATION_DEFECT | Password reset | `POST /api/users/reset-password/` | Documented reset payload is rejected and serializer uses inconsistent token fields | 100% | ND-BE-003/004 | One ticket; align view, serializer and OpenAPI payload |
| APP-02 | Major | APPLICATION_DEFECT | Registration | `POST /api/users/register/` | SMTP failure returns 500 after inactive account persists | 100% with failed mail boundary | ND-BE-005 | Make registration atomic or define retry semantics |
| APP-03 | Major | APPLICATION_DEFECT | Product pagination | `GET /api/products/?limit=101` | Limit above cap returns 500 | 100% | ND-BE-006 | Cap or reject with controlled 4xx |
| APP-04 | Major | APPLICATION_DEFECT | Categories | `POST /api/categories/` | Documented payload requires server-managed fields | 100% | ND-BE-007 | Correct writable serializer fields |
| APP-05 | Major | APPLICATION_DEFECT | Product images | `PATCH /api/products/{id}/images/order/` | Rejected multi-image reorder persists an earlier update | 100% | ND-BE-016 | Wrap validation/update in one transaction |
| APP-06 | Major | APPLICATION_DEFECT | Orders | `POST /api/orders/` | JSON array produces 500 | 100% | ND-BE-017 | Validate top-level body type |
| APP-07 | Major | APPLICATION_DEFECT | Activation | `POST /api/users/resend-activation/` | JSON array produces 500 | 100% regression; not reached in fresh generated run | ND-BE-018 | Validate top-level body type |
| APP-08 | Major | APPLICATION_DEFECT | Categories | `POST /api/categories/` | Derived empty-slug collision produces 500 | 100% | ND-BE-020 | Validate derived slug and return 400 |
| APP-09 | Major | APPLICATION_DEFECT | Photos | `POST /api/photos/` | Empty body reaches database constraint and returns 500 | 100% | ND-BE-021 | Require product or make endpoint read-only |
| APP-10 | Major | APPLICATION_DEFECT | Registration | `POST /api/users/register/` | Email can collide with an existing username and produce 500 | 100% state-dependent regression | ND-BE-022 | Validate both identity constraints |
| SEC-01 | Critical | SECURITY_DEFECT | Cart | `/api/carts/**` | Anonymous caller can manage another user's cart | 100% | ND-BE-001 | Require authentication and server-derived ownership |
| SEC-02 | Critical | SECURITY_DEFECT | Orders/payments | `/api/orders/**` | Anonymous caller can read/create victim orders and consume victim cart | 100% | ND-BE-002 | Require authentication/authorization; audit payment endpoint in same ticket |
| SEC-03 | Critical | SECURITY_DEFECT | Product images | `/api/products/{id}/images/**` | Anonymous upload, reorder and delete are allowed | 100% | ND-BE-008 | Require authorized mutation role |
| SCH-01 | Major | SCHEMA_DOCUMENTATION_DEFECT | Orders | `GET /api/orders/` | `product_count` is generated as string instead of integer | 100% formal validation | — / FSV-001 | Add return type or explicit schema field |
| SCH-02 | Major | SCHEMA_DOCUMENTATION_DEFECT | Payments | `POST /api/orders/create-payment-intent/` | Request/response serializer cannot be resolved | 100% formal validation | — / FSV-002 | Declare request and response schemas |
| SCH-03 | Major | SCHEMA_DOCUMENTATION_DEFECT | OAuth | `POST /api/users/oauth/` | `user` response property is an array, not a Schema Object | 100% | ND-BE-019 / FSV-003 | Replace array with valid object/reference |
| SCH-04 | Major | API_CONTRACT_DEFECT | Cart | `POST/GET/PATCH/DELETE /api/carts/**` | Success and custom error bodies disagree with schema | 100% generated A/B | —; RC-06/07 | Align serializers/error envelope or schema |
| SCH-05 | Major | SCHEMA_DOCUMENTATION_DEFECT | Products/categories | Product envelopes, placeholder image and category image URI disagree with schema | 100% generated A/B | ND-BE-006 linked; RC-08–11 | Correct response schemas; keep implementation defect separate |
| SCH-06 | Major | SCHEMA_DOCUMENTATION_DEFECT | Request validation | Multiple create/token/query schemas omit runtime constraints | 100% generated A/B | —; RC-12/15 | Add required, minLength, non-blank and query constraints |
| SCH-07 | Major | SCHEMA_DOCUMENTATION_DEFECT | Status/routing | 201/204/401/302 and HTML router 404 behavior are incomplete or undocumented | 100% generated A/B | —; RC-05/18 | Document actual statuses/routing or standardize responses |
| CLR-01 | Major | AMBIGUOUS_CONTRACT | Cart | `/api/carts/**` | Zero and over-stock quantities persist | 100% | ND-BE-009 | Product decision before implementation ticket |
| CLR-02 | Minor | AMBIGUOUS_CONTRACT | Image deletion | `DELETE /api/products/{id}/images/{image_id}/` | Metadata is deleted when storage cleanup fails | 100% with failed storage boundary | ND-BE-013 | Decide retry/atomicity policy |
| CLR-03 | Major | MISSING_REQUIREMENT | Orders | `POST /api/orders/` | Order does not retain item price/quantity snapshots | Source/state inspection | ND-BE-011 | Define historical order model requirements |
| CLR-04 | Major | MISSING_REQUIREMENT | Discounts | Product create/update | Values below 0 and above 100 persist | 100% serializer regression | ND-BE-012 | Define range and canonical calculation |

Pure setup and tooling limitations are intentionally excluded from this table and appear in section 5.

## 3. Ticket-ready detail — application defects

### APP-01 / ND-BE-003+004 — Password reset rejects its documented token payload

#### Classification

- Severity: Major
- Priority recommendation: High
- Type: `APPLICATION_DEFECT`
- Area: Users / password reset
- Endpoint and method: `POST /api/users/reset-password/`
- Root cause: the view uses an email-only serializer while the reset serializer declares `access_token` but reads `token`
- Schemathesis check: `positive_data_acceptance`, RC-16

#### Preconditions

An active local user with a valid Django password-reset UID and token.

#### Steps to reproduce

1. Create a user and generate its UID and reset token.
2. Send the documented reset request.
3. Reload the user and verify the password.

#### Request

```http
POST /api/users/reset-password/
Content-Type: application/json
Accept: application/json

{"uid":"<valid-uid>","token":"<valid-token>","new_password":"newpassword123"}
```

#### Actual result

HTTP 400 with `{"error":"This field is required."}`; persisted password is unchanged. Direct serializer use with
`access_token` raises `KeyError('token')`.

#### Expected result

The documented valid token payload resets the password; invalid tokens receive controlled validation errors.

#### Impact and reproducibility

The documented password-reset flow cannot complete. Reproducibility: **100%**.

#### Automated evidence

ND-BE-003/004; RC-16; `test_current_reset_password_defect_rejects_documented_token_payload`;
`test_current_reset_serializer_defect_reads_undeclared_token_field`; operation `users_reset_password_create`;
fingerprint `users_reset_password_create|positive_data_acceptance|RC-16`; JUnit `POST /api/users/reset-password/`.

#### Suggested ticket title

`Fix inconsistent password-reset payload and serializer token field`

### APP-02 / ND-BE-005 — Registration persists account after activation email failure

#### Classification

- Severity: Major
- Priority recommendation: High
- Type: `APPLICATION_DEFECT`
- Area: Registration / email
- Endpoint and method: `POST /api/users/register/`
- Root cause: user persistence occurs before an uncontained SMTP failure
- Schemathesis check: no stable generated fingerprint; deterministic dependency-failure regression

#### Preconditions

Clean database and a local SMTP boundary configured to fail deterministically.

#### Steps to reproduce

1. Configure the local mail sender to raise an SMTP/provider error.
2. Register a new email.
3. Query the user table for that email.

#### Request

```http
POST /api/users/register/
Content-Type: application/json

{"email":"mail-failure@example.com","password":"strongpassword123","first_name":"Mail","last_name":"Failure"}
```

#### Actual result

HTTP 500; an inactive user remains persisted. Retrying encounters an existing identity.

#### Expected result

Registration must be atomic or return a documented recoverable state that permits safe resend/retry.

#### Impact and reproducibility

Users can be locked into a partially registered state. Reproducibility: **100% with the failed local mail boundary**.

#### Automated evidence

ND-BE-005; `test_current_registration_defect_persists_inactive_user_after_email_failure`; no RC or normalized
Schemathesis fingerprint; API regression is the stable evidence.

#### Suggested ticket title

`Make registration atomic when activation email delivery fails`

### APP-03 / ND-BE-006 — Product pagination limit above cap returns HTTP 500

#### Classification

- Severity: Major
- Priority recommendation: High
- Type: `APPLICATION_DEFECT`
- Area: Products / pagination
- Endpoint and method: `GET /api/products/`
- Root cause: code attempts to mutate DRF's read-only `request.query_params`
- Schemathesis check: linked product error-contract evidence under RC-10

#### Preconditions

Backend with at least one product.

#### Steps to reproduce

1. Create or seed a product.
2. Request the product list with `limit=101`.

#### Request

```http
GET /api/products/?limit=101
Accept: application/json
```

#### Actual result

HTTP 500. No persistent state changes.

#### Expected result

Cap the limit or reject it with a documented controlled 4xx response.

#### Impact and reproducibility

Ordinary query input can crash the endpoint. Reproducibility: **100%**.

#### Automated evidence

ND-BE-006; RC-10; `test_current_pagination_defect_returns_500_when_limit_exceeds_cap`; operation
`products_list`; product response-schema fingerprints in `normalized-failures.json`.

#### Suggested ticket title

`Return controlled validation response for product limit above 100`

### APP-04 / ND-BE-007 — Category create rejects documented payload unless server fields are supplied

#### Classification

- Severity: Major
- Priority recommendation: High
- Type: `APPLICATION_DEFECT`
- Area: Categories
- Endpoint and method: `POST /api/categories/`
- Root cause: create serializer treats `id`, `creationAt`, and `updatedAt` as client-required
- Schemathesis check: `positive_data_acceptance`, RC-15 family

#### Preconditions

Authenticated local user.

#### Steps to reproduce

1. Authenticate.
2. Submit the documented writable category fields.
3. Check response and category persistence.

#### Request

```http
POST /api/categories/
Authorization: Bearer <local-test-token>
Content-Type: application/json

{"name":"Created Category","slug":"created-category","description":"Created via API","image":"http://example.test/image.jpg"}
```

#### Actual result

HTTP 400 identifies `id`, `creationAt`, and `updatedAt` as missing; category is not created.

#### Expected result

The documented payload creates the category and server-managed fields are generated by the backend.

#### Impact and reproducibility

Generated and manually written clients cannot use the documented create contract. Reproducibility: **100%**.

#### Automated evidence

ND-BE-007; RC-15 family; `TestCategoryViews.test_current_category_create_defect_rejects_documented_payload`;
operation `categories_create`; check `positive_data_acceptance`.

#### Suggested ticket title

`Remove server-managed fields from category create requirements`

### APP-05 / ND-BE-016 — Failed image reorder leaves partial persisted state

#### Classification

- Severity: Major
- Priority recommendation: High
- Type: `APPLICATION_DEFECT`
- Area: Product images
- Endpoint and method: `PATCH /api/products/{product_id}/images/order/`
- Root cause: updates are applied before all image ownership checks complete
- Schemathesis check: no dedicated generated fingerprint; deterministic atomicity regression

#### Preconditions

One target product with an image at sort 7 and a second product with a foreign image at sort 9.

#### Steps to reproduce

1. Submit a reorder containing the valid target image first and foreign image second.
2. Receive the rejection.
3. Reload both image records.

#### Request

```http
PATCH /api/products/<target-id>/images/order/
Content-Type: application/json

{"images":[{"id":<target-image-id>,"sort":1},{"id":<foreign-image-id>,"sort":2}]}
```

#### Actual result

HTTP 400; target image sort is nevertheless persisted as 1, while the foreign image remains 9.

#### Expected result

A rejected reorder leaves all image ordering unchanged.

#### Impact and reproducibility

Clients receive failure while data is partially mutated. Reproducibility: **100%**.

#### Automated evidence

ND-BE-016; `test_current_reorder_atomicity_defect_persists_earlier_update_before_later_validation_failure`;
no dedicated RC/fingerprint.

#### Suggested ticket title

`Make product-image reorder validation and persistence atomic`

### APP-06 / ND-BE-017 — Non-object order body produces HTTP 500

#### Classification

- Severity: Major
- Priority recommendation: High
- Type: `APPLICATION_DEFECT`
- Area: Orders
- Endpoint and method: `POST /api/orders/`
- Root cause: the view assumes `request.data` implements `.get`
- Schemathesis check: server-error family; deterministic API regression is authoritative

#### Preconditions

Clean local database; no authentication is currently required.

#### Steps to reproduce

1. Send a JSON array as the top-level request body.
2. Verify response and order count.

#### Request

```http
POST /api/orders/
Content-Type: application/json

[null,null]
```

#### Actual result

HTTP 500; no order is persisted.

#### Expected result

Malformed top-level JSON input returns controlled HTTP 400 without persistence.

#### Impact and reproducibility

Untrusted client input can trigger an internal error. Reproducibility: **100%**.

#### Automated evidence

ND-BE-017; `test_current_order_validation_defect_returns_500_for_non_object_json`; operation `orders_create`;
the isolated API regression supplies the stable reproduction; generated discovery did not retain a separate RC.

#### Suggested ticket title

`Validate top-level order request type instead of returning 500`

### APP-07 / ND-BE-018 — Non-object resend-activation body produces HTTP 500

#### Classification

- Severity: Major
- Priority recommendation: High
- Type: `APPLICATION_DEFECT`
- Area: Registration / activation
- Endpoint and method: `POST /api/users/resend-activation/`
- Root cause: the view assumes `request.data` is an object
- Schemathesis check: `not_a_server_error` and `content_type_conformance`, RC-01

#### Preconditions

Clean local database.

#### Steps to reproduce

1. Send a JSON array to resend activation.
2. Verify response and that no user was created.

#### Request

```http
POST /api/users/resend-activation/
Content-Type: application/json

[null,null]
```

#### Actual result

HTTP 500 with HTML error content; no user is persisted.

#### Expected result

Controlled HTTP 400 JSON validation response.

#### Impact and reproducibility

Malformed public input reaches an internal exception. Regression reproducibility: **100%**. RC-01 disappeared in
both fresh generated runs and is a baseline-removal candidate, not evidence that the defect is fixed.

#### Automated evidence

ND-BE-018; RC-01; `test_current_resend_activation_validation_defect_returns_500_for_non_object_json`;
operation `users_resend_activation_create`; fingerprints `...|not_a_server_error|RC-01` and
`...|content_type_conformance|RC-01`; prior JUnit plus current resolved list.

#### Suggested ticket title

`Return HTTP 400 for non-object resend-activation payloads`

### APP-08 / ND-BE-020 — Category derived-slug collision produces HTTP 500

#### Classification

- Severity: Major
- Priority recommendation: High
- Type: `APPLICATION_DEFECT`
- Area: Categories
- Endpoint and method: `POST /api/categories/`
- Root cause: distinct punctuation-only names normalize to the same empty slug without controlled validation
- Schemathesis check: `not_a_server_error`, `content_type_conformance`, RC-02

#### Preconditions

Authenticated local user and existing category `name="[]", slug=""`.

#### Steps to reproduce

1. Create the prerequisite empty-slug category.
2. Submit another punctuation-only name such as `{}`.
3. Inspect response and category rows.

#### Request

```http
POST /api/categories/
Authorization: Bearer <local-test-token>
Content-Type: application/json

{"id":999,"name":"{}","image":"https://example.test/category.png","creationAt":"2026-10-03T00:00:00Z","updatedAt":"2026-10-03T00:00:00Z"}
```

#### Actual result

HTTP 500 with HTML error content; the second category is not persisted.

#### Expected result

Reject an empty or colliding derived slug with controlled HTTP 400 JSON validation.

#### Impact and reproducibility

Schema-valid user input crashes category creation. Reproducibility: **100%**.

#### Automated evidence

ND-BE-020; RC-02; `test_current_category_slug_collision_defect_returns_500_without_persistence`; operation
`categories_create`; fingerprints `categories_create|not_a_server_error|RC-02` and
`categories_create|content_type_conformance|RC-02`; JUnit `POST /api/categories/`.

#### Suggested ticket title

`Validate empty and colliding derived category slugs`

### APP-09 / ND-BE-021 — Generic photo create reaches database constraint without product

#### Classification

- Severity: Major
- Priority recommendation: High
- Type: `APPLICATION_DEFECT`
- Area: Product images / generic photos
- Endpoint and method: `POST /api/photos/`
- Root cause: writable serializer accepts an empty body although `product_id` is required by persistence
- Schemathesis check: `not_a_server_error`, `content_type_conformance`, RC-03

#### Preconditions

Authenticated local user.

#### Steps to reproduce

1. Authenticate.
2. POST an empty JSON object.
3. Verify response and product-image table.

#### Request

```http
POST /api/photos/
Authorization: Bearer <local-test-token>
Content-Type: application/json

{}
```

#### Actual result

HTTP 500 with HTML error content; no image row is persisted.

#### Expected result

Either require a valid product and return HTTP 400 when missing, or make the generic endpoint read-only.

#### Impact and reproducibility

Incomplete user input reaches a database error. Reproducibility: **100%**.

#### Automated evidence

ND-BE-021; RC-03; `test_current_photo_create_defect_returns_500_without_product_image`; operation
`photos_create`; fingerprints `photos_create|not_a_server_error|RC-03` and
`photos_create|content_type_conformance|RC-03`; JUnit `POST /api/photos/`.

#### Suggested ticket title

`Validate product ownership before generic photo creation`

### APP-10 / ND-BE-022 — Registration email can collide with an existing username

#### Classification

- Severity: Major
- Priority recommendation: High
- Type: `APPLICATION_DEFECT`
- Area: Registration / identity
- Endpoint and method: `POST /api/users/register/`
- Root cause: email uniqueness is checked but the same value is persisted into a separately unique username
- Schemathesis check: `not_a_server_error`, `content_type_conformance`, RC-04

#### Preconditions

Existing user with `username=identity-collision@example.com` and a different email.

#### Steps to reproduce

1. Create the prerequisite user identity.
2. Register `identity-collision@example.com` as a new email.
3. Verify response, user rows and mail outbox.

#### Request

```http
POST /api/users/register/
Content-Type: application/json

{"email":"identity-collision@example.com","password":"strongpassword123","first_name":"Signup","last_name":"User"}
```

#### Actual result

HTTP 500; no new email row is persisted and no email is sent.

#### Expected result

Validate every affected uniqueness constraint and return controlled HTTP 400.

#### Impact and reproducibility

A legitimate-looking registration crashes when historical identity fields drift. Reproducibility: **100% with the
prerequisite state**. Fresh Schemathesis runs did not independently create that state, correcting the earlier
discovery provenance.

#### Automated evidence

ND-BE-022; RC-04; `test_current_registration_identity_collision_defect_returns_500_without_new_user`; operation
`users_register_create`; two RC-04 fingerprints are resolved candidates in fresh-run evidence.

#### Suggested ticket title

`Validate registration email against username uniqueness collisions`

## 4. Ticket-ready detail — security defects

### SEC-01 / ND-BE-001 — Anonymous caller can manage another user's cart

#### Classification

- Severity: Critical
- Priority recommendation: Immediate
- Type: `SECURITY_DEFECT`
- Area: Cart authorization
- Endpoint and methods: `/api/carts/` and `/api/carts/{id}/`; POST, GET, PATCH, DELETE
- Root cause: `AllowAny` plus caller-supplied `user`/`user_id`
- Schemathesis check: auth check deferred; schema/runtime security inventory links CT-007

#### Preconditions

A victim user, a product, and knowledge of numeric identifiers. No caller credentials.

#### Steps to reproduce

1. Without `Authorization`, create a cart item using the victim ID.
2. List it with `user_id=<victim-id>`.
3. Update and delete it with the same query parameter.

#### Request

```http
POST /api/carts/
Content-Type: application/json

{"user":<victim-id>,"product":<product-id>,"quantity":1}
```

Then use `GET /api/carts/?user_id=<victim-id>`, `PATCH /api/carts/<item-id>/?user_id=<victim-id>`, and DELETE.

#### Actual result

201, 200, 200 and 204 respectively; victim cart state is created, disclosed, changed and deleted.

#### Expected result

Unauthenticated requests are rejected, and ownership is derived from or authorized against the authenticated user.

#### Impact and reproducibility

Unauthorized read and write access to another user's cart. Reproducibility: **100%**.

#### Automated evidence

ND-BE-001; `test_current_security_defect_allows_anonymous_client_to_manage_victim_cart`; no dedicated RC because
`ignored_auth` is deferred; schema declares JWT while implementation is public.

#### Suggested ticket title

`Require authenticated ownership for all cart operations`

### SEC-02 / ND-BE-002 — Anonymous caller can read and create victim orders

#### Classification

- Severity: Critical
- Priority recommendation: Immediate
- Type: `SECURITY_DEFECT`
- Area: Orders and checkout authorization
- Endpoint and methods: `GET/POST /api/orders/`; payment endpoint requires the same permission audit
- Root cause: `AllowAny` plus caller-supplied `user_id`
- Schemathesis check: auth check deferred; schema/runtime inventory links CT-007

#### Preconditions

A victim user with cart items; no caller credentials.

#### Steps to reproduce

1. Without `Authorization`, submit the victim's `user_id` to order creation.
2. Confirm an order is created and the victim cart is consumed.
3. Query order history using the victim ID.

#### Request

```http
POST /api/orders/
Content-Type: application/json

{"user_id":<victim-id>}
```

```http
GET /api/orders/?user_id=<victim-id>
```

#### Actual result

HTTP 201 creates a pending order and removes the victim's cart items; HTTP 200 discloses order history.

#### Expected result

Both operations require authentication and authorize the target user/cart. The same authorization policy should be
confirmed for `POST /api/orders/create-payment-intent/`.

#### Impact and reproducibility

Unauthorized checkout, destructive cart consumption and order-history disclosure. Reproducibility: **100%**.

#### Automated evidence

ND-BE-002; `test_current_security_defect_allows_anonymous_order_for_victim_and_consumes_victim_cart`;
`test_current_security_defect_allows_anonymous_client_to_read_victim_order_history`; no dedicated auth fingerprint.

#### Suggested ticket title

`Require authenticated ownership for order history and checkout`

### SEC-03 / ND-BE-008 — Anonymous callers can mutate product images

#### Classification

- Severity: Critical
- Priority recommendation: Immediate
- Type: `SECURITY_DEFECT`
- Area: Product image administration
- Endpoint and methods: POST upload, PATCH reorder, DELETE image under `/api/products/{product_id}/images/`
- Root cause: all three mutation views use `AllowAny`
- Schemathesis check: auth check deferred; schema/runtime inventory links CT-007

#### Preconditions

Existing product and image IDs; no caller credentials. Upload regression replaces storage with a local fake.

#### Steps to reproduce

1. Omit `Authorization`.
2. Upload an image, reorder two images, or delete an existing image.
3. Reload product-image records.

#### Request

```http
PATCH /api/products/<product-id>/images/order/
Content-Type: application/json

{"images":[{"id":<first-id>,"sort":20},{"id":<second-id>,"sort":10}]}
```

#### Actual result

Anonymous upload returns 201, reorder returns 200 and persists sort values, and delete returns 204 and removes data.

#### Expected result

Mutations require an authenticated actor with the intended product-management role.

#### Impact and reproducibility

Unauthenticated callers can alter catalog media. Reproducibility: **100%**.

#### Automated evidence

ND-BE-008; three tests named `test_current_security_defect_allows_anonymous_product_image_*`; no dedicated auth
fingerprint because `ignored_auth` is deferred.

#### Suggested ticket title

`Protect product-image upload, reorder and delete with authorization`

## 5. Ticket-ready detail — schema and documentation defects

### SCH-01 / FSV-001 — Order product_count is documented as a string

#### Classification

- Severity: Major; priority recommendation: Medium
- Type: `SCHEMA_DOCUMENTATION_DEFECT`
- Area: Order list response; `GET /api/orders/`
- Root cause: `get_product_count` lacks a resolvable return type/schema annotation
- Schemathesis check: formal drf-spectacular validation

#### Preconditions and steps

Run `DJANGO_SETTINGS_MODULE=src.contract_settings python manage.py spectacular --validate` locally.

#### Request

Inspect the generated `OrderList` schema for `product_count` and compare it with the integer returned by the API.

#### Actual result

Formal warning: unable to resolve `get_product_count`; generated type defaults to string.

#### Expected result

The response schema declares `product_count` as integer.

#### Impact and reproducibility

Generated clients deserialize the field with the wrong type. Reproducibility: **100%**.

#### Automated evidence

FSV-001; no runtime RC or ND-BE ID; formal baseline signature in `schema_validation.json`.

#### Suggested ticket title

`Declare Order.product_count as integer in OpenAPI`

### SCH-02 / FSV-002 — Payment intent endpoint has no resolvable OpenAPI serializer

#### Classification

- Severity: Major; priority recommendation: High
- Type: `SCHEMA_DOCUMENTATION_DEFECT`
- Area: Payments; `POST /api/orders/create-payment-intent/`
- Root cause: APIView exposes no request/response serializer metadata
- Schemathesis check: formal drf-spectacular validation

#### Preconditions and steps

Run formal schema validation and inspect the payment operation.

#### Request

```http
POST /api/orders/create-payment-intent/
Content-Type: application/json

{"amount":2500}
```

#### Actual result

Runtime behavior exists, but formal generation reports `unable to guess serializer` and ignores the view contract;
the runtime operation is excluded because a valid call would reach Stripe.

#### Expected result

OpenAPI documents the integer amount request and success/error response schemas without contacting Stripe.

#### Impact and reproducibility

Generated clients cannot safely call the payment endpoint. Reproducibility: **100% formal validation**.

#### Automated evidence

FSV-002; CT-003/CT-020; no runtime RC; formal baseline and local provider-isolated API tests.

#### Suggested ticket title

`Document payment-intent request and response serializers`

### SCH-03 / ND-BE-019 / FSV-003 — OAuth user response property is invalid OpenAPI

#### Classification

- Severity: Major; priority recommendation: High
- Type: `SCHEMA_DOCUMENTATION_DEFECT`
- Area: OAuth; `POST /api/users/oauth/`
- Root cause: response `properties.user` contains a list of field names instead of a Schema Object/reference
- Schemathesis check: formal validation; runtime excluded from real provider traffic

#### Preconditions and steps

1. Generate or request `/api/schema/`.
2. Inspect `paths./api/users/oauth/.post.responses.200...properties.user`.
3. Run formal validation.

#### Request

```http
GET /api/schema/
Accept: application/json
```

#### Actual result

`user` equals `["id","email","first_name","last_name","date_joined"]`; formal validation raises
`SchemaValidationError`.

#### Expected result

Every response property is a valid Schema Object or `$ref`.

#### Impact and reproducibility

The published schema is invalid and breaks generators. Reproducibility: **100%**.

#### Automated evidence

ND-BE-019; FSV-003; CT-001; `test_current_schema_defect_emits_array_instead_of_oauth_user_schema`; no runtime RC.

#### Suggested ticket title

`Replace invalid OAuth user response array with an OpenAPI schema`

### SCH-04 / RC-06+07 — Cart success and error bodies disagree with OpenAPI

#### Classification

- Severity: Major; priority recommendation: Medium
- Type: `API_CONTRACT_DEFECT`
- Area: Cart; POST and detail operations under `/api/carts/`
- Root cause: response serializers and custom `{detail: ...}` error envelope differ from documented schemas
- Schemathesis check: `response_schema_conformance`

#### Preconditions and steps

1. Seed a user/product/cart item.
2. POST a valid item and GET its detail.
3. Call detail without `user_id`.

#### Request

```http
GET /api/carts/<item-id>/
Accept: application/json
```

#### Actual result

Success may embed a product object where the schema says integer; missing `user_id` returns
`{"detail":"Параметр user_id є обов'язковим."}` outside the documented standardized envelope.

#### Expected result

Implementation and OpenAPI describe the same success and error bodies. Which representation is canonical requires
API-owner confirmation, so this is not labeled solely as an implementation bug.

#### Impact and reproducibility

Generated clients cannot deserialize responses reliably. Reproducibility: **100% in both generated runs**.

#### Automated evidence

RC-06/07; operations `api_carts_add_item`, `api_carts_get_item`, `carts_update`,
`api_carts_update_item`, `api_carts_remove_item`; stable normalized fingerprints and JUnit cart cases; no ND-BE ID.

#### Suggested ticket title

`Align cart success and validation-error response schemas`

### SCH-05 / RC-08–11 — Catalog response schemas disagree with runtime payloads

#### Classification

- Severity: Major; priority recommendation: Medium
- Type: `SCHEMA_DOCUMENTATION_DEFECT`
- Area: Categories and products
- Endpoints: category detail/update and product list/detail
- Root cause: blank image URI, pagination/error envelope and placeholder image fields are modeled incorrectly
- Schemathesis check: `response_schema_conformance`

#### Preconditions and steps

1. Create a category with blank image and a product without images.
2. GET category detail and product detail/list.
3. Compare runtime JSON with `/api/schema/`.

#### Request

```http
GET /api/products/<product-without-images-id>/
Accept: application/json
```

#### Actual result

Runtime placeholder image and product envelopes violate declared schemas; blank category image `""` violates the
declared URI format. Invalid product-limit error codes also differ from the schema.

#### Expected result

Schema describes intentionally returned runtime values, or implementation is changed only where a product contract
explicitly requires it. ND-BE-006's 500 remains a separate application ticket.

#### Impact and reproducibility

Schema-driven validation and generated clients reject valid runtime responses. Reproducibility: **100% A/B**.

#### Automated evidence

RC-08/09/10/11; operations `categories_retrieve`, `categories_partial_update`, `products_list`,
`products_retrieve`; stable normalized fingerprints; placeholder behavior test; ND-BE-006 cross-link.

#### Suggested ticket title

`Correct category image and product response schemas`

### SCH-06 / RC-12+15 — Request schemas omit runtime validation constraints

#### Classification

- Severity: Major; priority recommendation: Medium
- Type: `SCHEMA_DOCUMENTATION_DEFECT`
- Area: Create/token/query operations across the API
- Root cause: required/non-blank/min-length/query constraints are absent or permissive
- Schemathesis checks: `negative_data_rejection`, `positive_data_acceptance`

#### Preconditions and steps

1. Load the runtime schema.
2. Send a schema-compliant empty string or generated multipart payload to an affected create/token operation.
3. Send an unknown or blank query parameter to affected list operations.

#### Request

```http
POST /api/users/token/
Content-Type: application/json

{}
```

#### Actual result

The schema treats inputs as valid that runtime rejects with 400, while blank/unknown query values may be accepted
despite being generated as invalid.

#### Expected result

OpenAPI expresses actual required fields, string lengths, non-blank rules and query policy. Multipart coercion cases
must be excluded from this product ticket and remain tooling-only.

#### Impact and reproducibility

Generated clients accept invalid payloads and generated tests report false contract divergence. Reproducibility:
**100% across both deterministic runs**.

#### Automated evidence

RC-12/15; affected audience/brand/product/review/user/register/token operations; normalized fingerprints; no single
ND-BE ID. RC-13 multipart-only cases are explicitly excluded from this ticket.

#### Suggested ticket title

`Add missing runtime validation constraints to OpenAPI request schemas`

### SCH-07 / RC-05+18 — Status codes, redirects and router 404 content are undocumented

#### Classification

- Severity: Major; priority recommendation: Medium
- Type: `SCHEMA_DOCUMENTATION_DEFECT`
- Area: Cross-cutting HTTP contract
- Endpoints: integer detail paths, product create, category delete, token refresh, reset-password redirect
- Root cause: schema status/content metadata does not cover routing and actual successful/auth responses
- Schemathesis checks: `content_type_conformance`, `status_code_conformance`, `redirect_blocked`

#### Preconditions and steps

1. Request an integer detail route using a malformed path value.
2. Create a product, delete a category, submit an invalid refresh token, and call reset-password GET without query.
3. Compare statuses/content types to schema.

#### Request

```http
GET /api/audiences/not-an-integer/
Accept: application/json
```

#### Actual result

Django routing returns HTML 404 for malformed typed paths. Other runtime cases include 201, 204, 401 and a 302
frontend redirect not fully described by the schema.

#### Expected result

Document actual supported statuses and redirect semantics, constrain path generation, or standardize router errors
as JSON. The reset redirect destination must remain environment-derived.

#### Impact and reproducibility

Generated clients and monitoring cannot rely on status/content contracts. Reproducibility: **100% A/B**.

#### Automated evidence

RC-05/18; CT-006/008/009/013; multiple detail operation fingerprints, category destroy, token refresh and reset GET;
no ND-BE ID.

#### Suggested ticket title

`Document actual API statuses, redirects and typed-path error content`

## 6. Needs product or requirements clarification

These observations have deterministic evidence, but their expected behavior is not defined strongly enough to file
an implementation bug without a product decision.

### CLR-01 / ND-BE-009 — Cart quantity boundaries

- Actual: quantity 0 and quantity 999 against stock 1 are accepted and persisted.
- Reproduction: POST `{"user":<id>,"product":<id>,"quantity":0}`, then PATCH quantity to 999.
- Evidence: `test_cart_currently_allows_zero_and_over_stock_quantities`.
- Expected result: **Requires product/requirements clarification** about zero quantity, stock enforcement and
  reservation semantics.
- Suggested title after clarification: `Enforce agreed cart quantity and stock boundaries`.

### CLR-02 / ND-BE-013 — Image deletion after storage cleanup failure

- Actual: with deterministic storage cleanup failure, DELETE returns 204 and removes database metadata.
- Evidence: `test_ambiguous_current_behavior_deletes_image_metadata_when_storage_cleanup_fails`.
- Expected result: **Requires product/requirements clarification** about metadata atomicity, retry and orphan cleanup.
- Suggested title after clarification: `Define image deletion behavior when storage cleanup fails`.

### CLR-03 / ND-BE-011 — Historical order-item snapshots

- Actual: checkout stores product M2M and aggregate total, but no item price/quantity snapshots.
- Evidence: order security regression plus source/persistence inspection; no dedicated deterministic snapshot test.
- Expected result: **Requires product/requirements clarification** about immutable historical receipts.
- Suggested title after clarification: `Persist immutable order item price and quantity snapshots`.

### CLR-04 / ND-BE-012 — Discount range and calculation

- Actual: `-1.00` and `100.01` validate and persist.
- Evidence: `test_product_serializer_currently_accepts_out_of_range_discount`.
- Expected result: **Requires product/requirements clarification** about 0–100 bounds, precision and displayed price.
- Suggested title after clarification: `Define and enforce product discount semantics`.

## 7. Technical and non-product findings

Each item below is marked **Do not create product bug** until its stated prerequisite is met.

| Finding | Classification | Evidence | Why not a product ticket | Reclassification prerequisite |
|---|---|---|---|---|
| RC-13 multipart coercion | Tooling | Generated audience/brand/game-type cases | **Do not create product bug.** Multipart string coercion can turn generated structures into strings. | Prove the same mismatch with a normal client payload. |
| RC-14 forgot-password throttle contamination | Test data/setup | Repeated generated calls | **Do not create product bug.** Rate-limit state crosses examples by design. | Isolate/reset throttle state or define a rate-limit contract test. |
| RC-17 missing valid IDs/tokens/uniqueness | Test data/setup | Detail/activation/logout generated cases | **Do not create product bug.** Generated examples lack legitimate state transitions. | Add stateful links or deterministic prerequisite factories. |
| CT-019 OAuth runtime exclusion | Testability limitation | Exact exclusion `users_oauth_create` | **Do not create product bug.** Safe execution needs an injectable local provider. | Add a local provider boundary; retain FSV-003 separately. |
| CT-020 Stripe runtime exclusion | Testability limitation | Exact exclusion `orders_create_payment_intent_create` | **Do not create product bug.** Valid runtime traffic would contact Stripe. | Add a local payment provider boundary; retain FSV-002 separately. |
| Deferred checks | Tooling/setup | `ignored_auth`, `missing_required_header`, `unsupported_method`, `use_after_free`, resource availability | **Do not create product bug.** Current global auth and non-stateful generation create duplicate or ordering noise. | Add operation-scoped auth and stateful test plans, then baseline reviewed causes. |

## 8. Jira readiness

### Ready to file now

- Application: APP-01 through APP-10.
- Security: SEC-01 through SEC-03.
- Schema/documentation: SCH-01 through SCH-07.

APP-01 should group ND-BE-003 and ND-BE-004 because both describe the same broken reset flow. SEC-02 should group
order read/create authorization and include an explicit payment authorization audit. SCH-05 should cross-link, not
duplicate, the ND-BE-006 implementation ticket.

### Needs product clarification

- CLR-01 cart quantities.
- CLR-02 storage-cleanup deletion semantics.
- CLR-03 historical order snapshots.
- CLR-04 discount semantics.

### Schema/documentation tickets

- SCH-01 `Order.product_count` type.
- SCH-02 payment serializer/schema.
- SCH-03 OAuth invalid response schema.
- SCH-04 cart response/error schemas.
- SCH-05 category/product response schemas.
- SCH-06 request constraints.
- SCH-07 statuses, redirects and routing content.

### Test infrastructure only

RC-13, RC-14, RC-17, CT-019, CT-020 and deferred optional checks must not enter the product backlog yet.

## 9. Statistics

```text
Confirmed application defects: 10 ticket candidates
Confirmed security defects: 3 ticket candidates
Schema/documentation defects: 7 ticket candidates
Ambiguous contracts: 2 findings
Missing requirements: 2 findings
Technical/setup/tooling findings: 6 groups
Ready-to-file tickets: 20
Needs-clarification findings: 4
```

Counts are ticket/root-cause based, not generated-example based.

## 10. Traceability and evidence gaps

```text
Schemathesis case
  -> operation/check normalized fingerprint
  -> RC-XX root cause
  -> ND-BE-XXX or FSV-XXX where assigned
  -> APP/SEC/SCH ticket candidate
  -> deterministic regression test where available
```

Examples:

- Category 500: generated case → `categories_create|not_a_server_error|RC-02` → RC-02 → ND-BE-020 → APP-08
  → `test_current_category_slug_collision_defect_returns_500_without_persistence`.
- OAuth schema: formal validator → FSV-003 → ND-BE-019 → SCH-03 →
  `test_current_schema_defect_emits_array_instead_of_oauth_user_schema`.
- Cart authorization: generated auth check is missing/deferred → ND-BE-001 → SEC-01 →
  `test_current_security_defect_allows_anonymous_client_to_manage_victim_cart`.

Candidates without a dedicated isolated regression test are SCH-01, SCH-02, SCH-04, SCH-05, SCH-06, SCH-07 and
CLR-03. SCH candidates have reproducible formal-validation or identical two-run Schemathesis evidence; CLR-03 has
source/persistence inspection only. RC-01 and RC-04 retain deterministic API regressions but were not independently
rediscovered from either clean generated run.

Raw local evidence is retained outside the repository at `/tmp/nicedice-contract-final-a2/` and
`/tmp/nicedice-contract-final-b/`. CI publishes the equivalent `schemathesis-report/` artifact.
