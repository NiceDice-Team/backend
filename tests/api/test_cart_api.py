import pytest
from django.urls import reverse
from rest_framework import status

from cart.infrastructure.models import CartItem


pytestmark = [pytest.mark.api, pytest.mark.django_db]


def test_cart_create_list_update_delete_flow(api_client, user_factory, product_factory):
    user = user_factory()
    product = product_factory(stock=2)

    created = api_client.post(
        reverse("cart-list"), {"user": user.id, "product": product.id, "quantity": 1}, format="json"
    )
    item = CartItem.objects.get()
    listed = api_client.get(reverse("cart-list"), {"user_id": user.id})
    updated = api_client.patch(
        reverse("cart-detail", kwargs={"pk": item.pk}) + f"?user_id={user.id}",
        {"quantity": 2},
        format="json",
    )
    deleted = api_client.delete(reverse("cart-detail", kwargs={"pk": item.pk}) + f"?user_id={user.id}")

    assert created.status_code == status.HTTP_201_CREATED
    assert listed.status_code == status.HTTP_200_OK
    assert listed.json()["results"][0]["product"]["id"] == product.id
    assert updated.status_code == status.HTTP_200_OK
    assert updated.json()["quantity"] == 2
    assert deleted.status_code == status.HTTP_204_NO_CONTENT
    assert not CartItem.objects.exists()


def test_cart_detail_requires_valid_user_id(api_client, user_factory, product_factory):
    item = CartItem.objects.create(user=user_factory(), product=product_factory(), quantity=1)
    url = reverse("cart-detail", kwargs={"pk": item.pk})

    missing = api_client.get(url)
    malformed = api_client.get(url, {"user_id": "invalid"})

    assert missing.status_code == status.HTTP_400_BAD_REQUEST
    assert malformed.status_code == status.HTTP_400_BAD_REQUEST


def test_cart_cross_user_lookup_is_hidden_as_not_found(api_client, user_factory, product_factory):
    owner = user_factory()
    other = user_factory()
    item = CartItem.objects.create(user=owner, product=product_factory(), quantity=1)

    response = api_client.get(reverse("cart-detail", kwargs={"pk": item.pk}), {"user_id": other.id})

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_cart_duplicate_returns_validation_error(api_client, user_factory, product_factory):
    user = user_factory()
    product = product_factory()
    payload = {"user": user.id, "product": product.id, "quantity": 1}
    assert api_client.post(reverse("cart-list"), payload, format="json").status_code == status.HTTP_201_CREATED

    duplicate = api_client.post(reverse("cart-list"), payload, format="json")

    assert duplicate.status_code == status.HTTP_400_BAD_REQUEST
    assert CartItem.objects.count() == 1


def test_cart_currently_allows_zero_and_over_stock_quantities(api_client, user_factory, product_factory):
    user = user_factory()
    product = product_factory(stock=1)

    zero = api_client.post(
        reverse("cart-list"), {"user": user.id, "product": product.id, "quantity": 0}, format="json"
    )
    item = CartItem.objects.get(user=user, product=product)
    over_stock = api_client.patch(
        reverse("cart-detail", kwargs={"pk": item.pk}) + f"?user_id={user.id}",
        {"quantity": 999},
        format="json",
    )

    assert zero.status_code == status.HTTP_201_CREATED
    assert over_stock.status_code == status.HTTP_200_OK
    assert over_stock.json()["quantity"] == 999
