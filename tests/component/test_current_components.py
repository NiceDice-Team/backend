from decimal import Decimal

import pytest
from django.db import IntegrityError

from cart.infrastructure.models import CartItem
from cart.interfaces.serializers import CartItemDetailSerializer, CartItemSerializer
from products.interfaces.serializers import ProductSerializer
from users.interfaces.serializers import RegisterSerializer


pytestmark = [pytest.mark.component, pytest.mark.django_db]


def test_register_serializer_hashes_password_and_preserves_identity():
    serializer = RegisterSerializer(
        data={
            "email": "new@example.com",
            "password": "strongpassword123",
            "first_name": "New",
            "last_name": "User",
        }
    )

    assert serializer.is_valid(), serializer.errors
    user = serializer.save()

    assert user.email == "new@example.com"
    assert user.username == "new@example.com"
    assert user.password != "strongpassword123"
    assert user.check_password("strongpassword123")


def test_register_serializer_rejects_duplicate_email(user_factory):
    user_factory(email="duplicate@example.com")
    serializer = RegisterSerializer(
        data={
            "email": "duplicate@example.com",
            "password": "strongpassword123",
            "first_name": "Duplicate",
            "last_name": "User",
        }
    )

    assert not serializer.is_valid()
    assert serializer.errors["email"] == ["User with this email already exists"]


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("-0.01")])
def test_product_serializer_rejects_non_positive_price(price, product_factory):
    product = product_factory()
    serializer = ProductSerializer(product, data={"price": price}, partial=True)

    assert not serializer.is_valid()
    assert serializer.errors["price"] == ["Ціна повинна бути більшою за 0."]


def test_product_serializer_exposes_relationships_and_money(product_factory):
    product = product_factory(price=Decimal("29.99"), discount=Decimal("15.50"), stock=4)

    data = ProductSerializer(product).data

    assert data["price"] == "29.99"
    assert data["discount"] == "15.50"
    assert data["stock"] == 4
    assert data["brand"] == product.brand_id
    assert data["categories"] == [product.categories.get().id]


def test_cart_serializer_rejects_missing_required_quantity(user_factory, product_factory):
    serializer = CartItemSerializer(data={"user": user_factory().id, "product": product_factory().id})

    assert not serializer.is_valid()
    assert "quantity" in serializer.errors


def test_cart_serializer_and_detail_preserve_quantity(user_factory, product_factory):
    item = CartItem.objects.create(user=user_factory(), product=product_factory(), quantity=3)

    write_data = CartItemSerializer(item).data
    detail_data = CartItemDetailSerializer(item).data

    assert write_data["quantity"] == 3
    assert detail_data["quantity"] == 3
    assert detail_data["product"] == {
        "id": item.product.id,
        "name": item.product.name,
        "price": item.product.price,
    }


def test_cart_database_rejects_duplicate_user_product(user_factory, product_factory):
    user = user_factory()
    product = product_factory()
    CartItem.objects.create(user=user, product=product, quantity=1)

    with pytest.raises(IntegrityError):
        CartItem.objects.create(user=user, product=product, quantity=2)


def test_cart_currently_accepts_zero_quantity(user_factory, product_factory):
    item = CartItem.objects.create(user=user_factory(), product=product_factory(), quantity=0)

    assert item.quantity == 0

