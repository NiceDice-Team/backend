from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status


pytestmark = [pytest.mark.api, pytest.mark.django_db]


def test_product_list_retrieve_search_and_filter(api_client, product_factory):
    target = product_factory(name="Strategy Dice", price=Decimal("29.99"))
    product_factory(name="Unrelated Cards")

    listed = api_client.get(reverse("product-list"))
    retrieved = api_client.get(reverse("product-detail", kwargs={"pk": target.pk}))
    searched = api_client.get(reverse("product-list"), {"search": "Strategy"})
    filtered = api_client.get(reverse("product-list"), {"categories": target.categories.get().id})

    assert listed.status_code == status.HTTP_200_OK
    assert retrieved.status_code == status.HTTP_200_OK
    assert retrieved.json()["name"] == "Strategy Dice"
    assert [p["id"] for p in searched.json()["results"]] == [target.id]
    assert [p["id"] for p in filtered.json()["results"]] == [target.id]


def test_product_detail_not_found(api_client):
    response = api_client.get(reverse("product-detail", kwargs={"pk": 999999}))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_product_without_images_gets_placeholder(api_client, product_factory):
    product = product_factory()

    response = api_client.get(reverse("product-detail", kwargs={"pk": product.pk}))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["images"][0]["id"] == 0
    assert response.json()["images"][0]["alt"] == "Немає зображення"


@pytest.mark.parametrize("limit", ["0", "-1", "not-a-number"])
def test_product_list_rejects_invalid_limit(api_client, limit):
    response = api_client.get(reverse("product-list"), {"limit": limit})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_product_list_caps_large_limit(api_client, product_factory):
    product_factory()
    api_client.raise_request_exception = False

    response = api_client.get(reverse("product-list"), {"limit": "101"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_anonymous_product_create_update_delete_are_forbidden(api_client, product_factory):
    product = product_factory()
    payload = {
        "name": "New",
        "description": "New product",
        "price": "10.00",
        "categories": [product.categories.get().id],
        "brand": product.brand_id,
    }

    created = api_client.post(reverse("product-list"), payload, format="json")
    updated = api_client.patch(reverse("product-detail", kwargs={"pk": product.pk}), {"stock": 2}, format="json")
    deleted = api_client.delete(reverse("product-detail", kwargs={"pk": product.pk}))

    assert created.status_code == status.HTTP_401_UNAUTHORIZED
    assert updated.status_code == status.HTTP_401_UNAUTHORIZED
    assert deleted.status_code == status.HTTP_401_UNAUTHORIZED
