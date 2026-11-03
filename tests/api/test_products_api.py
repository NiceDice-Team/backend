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


@pytest.mark.bug
def test_current_pagination_defect_returns_500_when_limit_exceeds_cap(api_client, product_factory):
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


def test_authenticated_product_create_update_delete_flow(
    api_client, user_factory, product_factory
):
    reference = product_factory()
    category = reference.categories.get()
    user = user_factory()
    api_client.force_authenticate(user=user)

    created = api_client.post(
        reverse("product-list"),
        {
            "name": "Managed Product",
            "description": "Created by authenticated API flow",
            "price": "12.50",
            "brand": reference.brand_id,
            "categories": [category.id],
            "stock": 3,
        },
        format="json",
    )

    assert created.status_code == status.HTTP_201_CREATED, created.json()
    product_id = created.json()["id"]

    updated = api_client.patch(
        reverse("product-detail", kwargs={"pk": product_id}),
        {"price": "15.75", "stock": 8},
        format="json",
    )

    assert updated.status_code == status.HTTP_200_OK, updated.json()
    assert updated.json()["price"] == "15.75"
    assert updated.json()["stock"] == 8

    deleted = api_client.delete(reverse("product-detail", kwargs={"pk": product_id}))
    retrieved = api_client.get(reverse("product-detail", kwargs={"pk": product_id}))

    assert deleted.status_code == status.HTTP_204_NO_CONTENT
    assert retrieved.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    ("invalid_field", "invalid_value"),
    [
        ("name", None),
        ("description", None),
        ("price", "not-a-number"),
        ("brand", 999999),
        ("categories", [999999]),
    ],
)
def test_authenticated_product_create_isolates_invalid_field_without_new_persistence(
    api_client, user_factory, product_factory, invalid_field, invalid_value
):
    from products.infrastructure.models import Product

    api_client.force_authenticate(user=user_factory())
    reference = product_factory()
    initial_count = Product.objects.count()
    payload = {
        "name": "Valid Product",
        "description": "Valid description",
        "price": "10.00",
        "brand": reference.brand_id,
        "categories": [reference.categories.get().id],
    }
    if invalid_value is None:
        payload.pop(invalid_field)
    else:
        payload[invalid_field] = invalid_value

    response = api_client.post(reverse("product-list"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert {error["attr"] for error in response.json()["errors"]} == {invalid_field}
    assert Product.objects.count() == initial_count


def test_authenticated_product_patch_rejects_invalid_values_without_state_change(
    api_client, user_factory, product_factory
):
    product = product_factory(price=Decimal("25.00"), stock=4)
    api_client.force_authenticate(user=user_factory())

    response = api_client.patch(
        reverse("product-detail", kwargs={"pk": product.pk}),
        {"price": "0.00", "stock": -1},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    product.refresh_from_db()
    assert product.price == Decimal("25.00")
    assert product.stock == 4


def test_authenticated_product_patch_rejects_unknown_product_without_creating_one(
    api_client, user_factory
):
    from products.infrastructure.models import Product

    api_client.force_authenticate(user=user_factory())

    response = api_client.patch(
        reverse("product-detail", kwargs={"pk": 999999}),
        {"stock": 1},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert not Product.objects.exists()
