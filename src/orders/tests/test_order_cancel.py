import re
from datetime import timedelta
from unittest import mock
from urllib.parse import urlencode, urlsplit

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework import status

from orders.cancellation import is_valid_cancel_token, make_cancel_token
from orders.infrastructure.models import DeliveryOption, Order, OrderItem, OrderStatusLog

SHIPPING_ADDRESS = "Oleksandr Doroshenko, Akademika Korolova 112, Odesa, Ukraine"


@pytest.fixture
def delivery_option(db):
    option, _ = DeliveryOption.objects.update_or_create(
        name="DHL Express",
        defaults={"description": "Test delivery", "price": "15.00", "estimated_days": 7, "is_active": True},
    )
    return option


@pytest.fixture
def make_order(delivery_option, product):
    def _make_order(user=None, order_status="pending"):
        order = Order.objects.create(
            user=user,
            shipping_address=SHIPPING_ADDRESS,
            delivery_option=delivery_option,
            status=order_status,
            total_amount="74.98",
        )
        OrderItem.objects.create(order=order, product=product, quantity=2, price=product.price)
        return order

    return _make_order


def cancel_url(order_id, token):
    path = reverse("order-cancel", kwargs={"orderId": order_id})
    query = urlencode({"token": token})
    return f"{path}?{query}"


def cancelled_page_url(order_id):
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    return f"{frontend_url}/checkout-order/order-cancel?orderId={order_id}"


def extract_cancel_link(message):
    match = re.search(r"^Cancel order: (\S+)$", message.body, re.MULTILINE)
    assert match is not None
    return match.group(1)


def relative_url(url):
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}"


def assert_order_not_changed(order, expected_status):
    order.refresh_from_db()
    assert order.status == expected_status
    assert not OrderStatusLog.objects.filter(order=order).exists()


@pytest.mark.django_db
def test_cancel_link_from_confirmation_email_cancels_order(api_client, user, user_cart, delivery_option, mailoutbox):
    api_client.force_authenticate(user=user)
    response = api_client.post(reverse("order-list-create"), {
        "cart_id": user_cart.id,
        "delivery_option_id": delivery_option.id,
        "shipping_address": SHIPPING_ADDRESS,
    }, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    order_id = response.data["id"]

    cancel_link = extract_cancel_link(mailoutbox[-1])
    api_client.force_authenticate(user=None)
    response = api_client.get(relative_url(cancel_link))

    assert response.status_code == status.HTTP_302_FOUND
    assert response["Location"] == cancelled_page_url(order_id)

    api_client.force_authenticate(user=user)
    history = api_client.get(reverse("order-list-create"))
    assert history.status_code == status.HTTP_200_OK
    assert [(order["id"], order["status"]) for order in history.data] == [(order_id, "cancelled")]


@pytest.mark.django_db
def test_confirmation_email_links_to_backend_cancel_endpoint(api_client, guest_cart, delivery_option, mailoutbox):
    response = api_client.post(reverse("order-list-create"), {
        "guest_cart_token": guest_cart.token,
        "delivery_option_id": delivery_option.id,
        "shipping_address": SHIPPING_ADDRESS,
        "email": "guest@example.com",
    }, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    order = Order.objects.get(pk=response.data["id"])

    message = mailoutbox[-1]
    cancel_link = extract_cancel_link(message)
    backend_url = settings.BACKEND_URL.rstrip("/")
    assert cancel_link == f"{backend_url}{cancel_url(order.pk, make_cancel_token(order))}"

    html_content, mimetype = message.alternatives[0]
    assert mimetype == "text/html"
    assert f"href=\"{cancel_link}\"" in html_content


@pytest.mark.django_db
@pytest.mark.parametrize("initial_status", ["pending", "processing"])
def test_order_is_cancelled_and_status_change_is_logged(api_client, user, make_order, initial_status):
    order = make_order(user=user, order_status=initial_status)

    response = api_client.get(cancel_url(order.pk, make_cancel_token(order)))

    assert response.status_code == status.HTTP_302_FOUND
    assert response["Location"] == cancelled_page_url(order.pk)
    order.refresh_from_db()
    assert order.status == "cancelled"
    log = OrderStatusLog.objects.get(order=order)
    assert (log.previous_status, log.new_status, log.changed_by) == (initial_status, "cancelled", user)


@pytest.mark.django_db
def test_guest_order_is_cancelled(api_client, make_order):
    order = make_order()

    response = api_client.get(cancel_url(order.pk, make_cancel_token(order)))

    assert response.status_code == status.HTTP_302_FOUND
    order.refresh_from_db()
    assert order.status == "cancelled"
    assert OrderStatusLog.objects.get(order=order).changed_by is None


@pytest.mark.django_db
def test_repeated_click_on_cancel_link_is_idempotent(api_client, user, make_order):
    order = make_order(user=user)
    url = cancel_url(order.pk, make_cancel_token(order))

    first_response = api_client.get(url)
    second_response = api_client.get(url)

    for response in (first_response, second_response):
        assert response.status_code == status.HTTP_302_FOUND
        assert response["Location"] == cancelled_page_url(order.pk)
    assert OrderStatusLog.objects.filter(order=order).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("shipped_status", ["shipped", "delivered"])
def test_shipped_order_cannot_be_cancelled(api_client, user, make_order, shipped_status):
    order = make_order(user=user, order_status=shipped_status)

    response = api_client.get(cancel_url(order.pk, make_cancel_token(order)))

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response["Content-Type"].startswith("text/html")
    content = response.content.decode()
    assert "Order cannot be cancelled" in content
    assert "already been shipped" in content
    assert f"Order #{order.pk}" in content
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    assert f"{frontend_url}/profile" in content
    assert_order_not_changed(order, shipped_status)


@pytest.mark.django_db
def test_order_cannot_be_cancelled_after_48_hours(api_client, make_order):
    order = make_order()
    url = cancel_url(order.pk, make_cancel_token(order))

    with mock.patch("django.utils.timezone.now", return_value=order.created_at + timedelta(hours=48, seconds=1)):
        response = api_client.get(url)

    assert response.status_code == status.HTTP_409_CONFLICT
    content = response.content.decode()
    assert "within 48 hours" in content
    assert "/profile" not in content
    assert_order_not_changed(order, "pending")


@pytest.mark.django_db
def test_order_can_be_cancelled_until_48_hours_pass(api_client, make_order):
    order = make_order()
    url = cancel_url(order.pk, make_cancel_token(order))

    with mock.patch("django.utils.timezone.now", return_value=order.created_at + timedelta(hours=47, minutes=59)):
        response = api_client.get(url)

    assert response.status_code == status.HTTP_302_FOUND
    order.refresh_from_db()
    assert order.status == "cancelled"


@pytest.mark.django_db
@pytest.mark.parametrize("token_kind", ["missing", "empty", "forged", "other_order"])
def test_invalid_token_does_not_cancel_order(api_client, make_order, token_kind):
    order = make_order()
    other_order = make_order()
    path = reverse("order-cancel", kwargs={"orderId": order.pk})
    urls = {
        "missing": path,
        "empty": cancel_url(order.pk, ""),
        "forged": cancel_url(order.pk, "x" * 43),
        "other_order": cancel_url(order.pk, make_cancel_token(other_order)),
    }

    response = api_client.get(urls[token_kind])

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response["Content-Type"].startswith("text/html")
    content = response.content.decode()
    assert "Invalid cancellation link" in content
    assert "Order #" not in content
    assert_order_not_changed(order, "pending")
    assert_order_not_changed(other_order, "pending")


@pytest.mark.django_db
def test_unknown_order_returns_invalid_link_page(api_client, make_order):
    order = make_order()

    response = api_client.get(cancel_url(order.pk + 1000, make_cancel_token(order)))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Invalid cancellation link" in response.content.decode()
    assert_order_not_changed(order, "pending")


@pytest.mark.django_db
def test_cancel_link_ignores_stale_authorization_header(api_client, make_order):
    order = make_order()

    response = api_client.get(
        cancel_url(order.pk, make_cancel_token(order)),
        HTTP_AUTHORIZATION="Bearer invalid-token",
    )

    assert response.status_code == status.HTTP_302_FOUND
    order.refresh_from_db()
    assert order.status == "cancelled"


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["head", "post", "put", "patch", "delete"])
def test_only_get_request_cancels_order(api_client, make_order, method):
    order = make_order()

    response = getattr(api_client, method)(cancel_url(order.pk, make_cancel_token(order)))

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert_order_not_changed(order, "pending")


@pytest.mark.django_db
def test_cancel_token_is_bound_to_specific_order(make_order):
    order = make_order()
    other_order = make_order()
    token = make_cancel_token(order)

    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
    assert is_valid_cancel_token(order, token)
    assert not is_valid_cancel_token(other_order, token)
    assert not is_valid_cancel_token(order, "")
    assert not is_valid_cancel_token(order, f"{token}:extra")
    assert make_cancel_token(Order.objects.get(pk=order.pk)) == token

    Order.objects.filter(pk=order.pk).update(created_at=order.created_at - timedelta(days=1))
    assert not is_valid_cancel_token(Order.objects.get(pk=order.pk), token)
