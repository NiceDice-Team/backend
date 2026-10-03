from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from cart.infrastructure.models import CartItem
from orders.infrastructure.models import Order
from orders.interfaces import views as order_views


pytestmark = [pytest.mark.api, pytest.mark.django_db]


def test_order_from_multiple_cart_items_persists_total_and_consumes_only_user_cart(
    api_client, user_factory, product_factory
):
    user = user_factory()
    other = user_factory()
    first = product_factory(price=Decimal("15.50"))
    second = product_factory(price=Decimal("7.25"))
    CartItem.objects.create(user=user, product=first, quantity=2)
    CartItem.objects.create(user=user, product=second, quantity=1)
    CartItem.objects.create(user=other, product=second, quantity=3)

    response = api_client.post(reverse("order-list-create"), {"user_id": user.id}, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    order = Order.objects.get()
    assert order.total_amount == Decimal("38.25")
    assert order.status == "pending"
    assert set(order.products.values_list("id", flat=True)) == {first.id, second.id}
    assert not CartItem.objects.filter(user=user).exists()
    assert CartItem.objects.filter(user=other, quantity=3).exists()


@pytest.mark.parametrize(
    ("payload", "detail"),
    [
        ({}, "Поле 'user_id' є обов'язковим в тілі запиту."),
        ({"user_id": "invalid"}, "Параметр 'user_id' має бути цілим числом."),
        ({"user_id": 999999}, "Користувач з ID 999999 не знайдений."),
    ],
)
def test_order_rejects_missing_malformed_and_unknown_user(api_client, payload, detail):
    response = api_client.post(reverse("order-list-create"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == detail
    assert not Order.objects.exists()


def test_order_rejects_empty_cart(api_client, user_factory):
    user = user_factory()

    response = api_client.post(reverse("order-list-create"), {"user_id": user.id}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not Order.objects.exists()


def test_payment_intent_uses_exact_provider_request(api_client, monkeypatch):
    calls = []

    class Intent(dict):
        id = "pi_test"

    monkeypatch.setattr(
        order_views.stripe.PaymentIntent,
        "create",
        lambda **kwargs: calls.append(kwargs) or Intent(client_secret="secret-1"),
    )

    response = api_client.post(reverse("create-payment-intent"), {"amount": 2500}, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"clientSecret": "secret-1"}
    assert calls == [{"amount": 2500, "currency": "uah"}]


@pytest.mark.parametrize("amount", [None, 0, -1, "not-an-integer"])
def test_payment_intent_rejects_invalid_amount_without_provider_call(api_client, monkeypatch, amount):
    monkeypatch.setattr(
        order_views.stripe.PaymentIntent,
        "create",
        lambda **kwargs: pytest.fail("Stripe must not be called"),
    )

    response = api_client.post(reverse("create-payment-intent"), {"amount": amount}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_payment_intent_maps_provider_error_to_400(api_client, monkeypatch):
    class FakeStripeError(Exception):
        def __init__(self, message):
            self.user_message = message

    monkeypatch.setattr(order_views.stripe.error, "StripeError", FakeStripeError)
    monkeypatch.setattr(
        order_views.stripe.PaymentIntent,
        "create",
        lambda **kwargs: (_ for _ in ()).throw(FakeStripeError("Payment failed")),
    )

    response = api_client.post(reverse("create-payment-intent"), {"amount": 2500}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"error": "Payment failed"}

