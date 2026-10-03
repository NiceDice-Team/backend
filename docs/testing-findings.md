# Backend testing findings

These findings describe the current canonical implementation. The coverage work does not change production behavior.

| Severity | Type | Area | Finding | Test evidence |
|---|---|---|---|---|
| Critical | SECURITY_CONCERN | Cart | Cart endpoints use `AllowAny` and trust a caller-supplied user ID. Anonymous clients can create and mutate another user's cart when IDs are known. | `tests/api/test_cart_api.py` |
| Critical | SECURITY_CONCERN | Orders | Order creation uses `AllowAny` and a caller-supplied user ID, allowing unauthenticated cart consumption and order creation for another user. | `tests/api/test_orders_payments_api.py` |
| Major | DEFECT_CANDIDATE | Password reset | The POST view shadows the imported reset serializer with an email-only serializer. The documented `uid`/`token`/`new_password` payload is rejected and the password is unchanged. | `test_reset_password_post_does_not_implement_documented_token_payload` |
| Major | DEFECT_CANDIDATE | Password reset | The otherwise unused serializer declares `access_token` but reads `attrs['token']`; a valid-looking payload cannot satisfy both names. | Source inspection: `users/interfaces/serializers.py` |
| Major | DEFECT_CANDIDATE | Product pagination | `limit > 100` assigns to DRF's read-only `request.query_params` property and returns HTTP 500. | `test_product_list_caps_large_limit` |
| Major | DEFECT_CANDIDATE | Categories | The create serializer requires client-supplied `id`, `creationAt`, and `updatedAt`, so the documented create payload returns HTTP 400. | `TestCategoryViews.test_category_create_view` |
| Major | SECURITY_CONCERN | Product images | Upload, reorder, and delete endpoints use `AllowAny`. | `tests/api/test_product_images_api.py` and source inspection |
| Major | AMBIGUOUS_CONTRACT | Cart | Quantity zero and quantities greater than product stock are accepted. | `test_cart_currently_allows_zero_and_over_stock_quantities` |
| Major | TESTABILITY_LIMITATION | Checkout | Total calculation, cart consumption, and persistence are embedded in the API view without an atomic service boundary. | `tests/api/test_orders_payments_api.py` |
| Major | MISSING_REQUIREMENT | Orders | Checkout populates the product M2M relation but does not create `OrderItem` price/quantity snapshots. | `test_order_from_multiple_cart_items_persists_total_and_consumes_only_user_cart` plus source inspection |
| Major | MISSING_REQUIREMENT | Discounts | `discount` has no explicit 0–100 validation or canonical discounted-price calculation. | Model/serializer inspection |
| Minor | AMBIGUOUS_CONTRACT | Image deletion | Metadata is deleted even when storage cleanup raises an exception. | Product image delete view inspection |
| Minor | TESTABILITY_LIMITATION | Storage | The production storage class hard-codes bucket/CDN identity and has no configurable local endpoint. | `src/s3.py` inspection |

