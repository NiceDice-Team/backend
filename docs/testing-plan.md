# Coverage Report And Test Plan

## Current Baseline

- Test suite: 48 passed
- Coverage: 71% total
- Test command: `uv run pytest -q --cov=src --cov-report=term-missing`

## What Was Added

- Auth serializer tests for registration, duplicate email handling, forgot password validation, reset password success and failure, and OAuth provider validation.
- Auth view tests for register, activate, resend activation, forgot password, reset password, and logout blacklist behavior.
- Cart view tests for create, list, retrieve ownership behavior, update, and delete.
- Order view tests for order history, order creation from cart, and payment intent validation.
- A fix in the reset password view so the POST endpoint uses the real reset-password serializer instead of the forgot-password email serializer.

## Remaining Coverage Gaps

The biggest uncovered areas are still:

- `src/products/interfaces/views.py`
- `src/products/interfaces/serializers.py`
- `src/products/service.py`
- Remaining branches in `src/users/interfaces/views.py`
- Remaining model validation branches in `cart`, `orders`, `categories`, and `products`

## Next Test Slice

1. Add product service tests for search, filtering, and recommendation helpers.
2. Add serializer validation tests for product create/update payloads.
3. Add product view tests for the most used list/detail endpoints and error branches.
4. Add any missing order/cart edge-case tests only after the product slice is in place.

## Critical Functionality Priority

The order of importance is:

1. Authentication and password reset
2. Cart ownership and cart mutation
3. Order creation and payment intent creation
4. Product search, filtering, and detail flows

This sequence gives the best return on test effort because it protects the most user-facing paths first.
