from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from cart.infrastructure.models import CartItem
from cart.interfaces.serializers import CartItemDetailSerializer, CartItemSerializer
from products.infrastructure.models import Audience, GameType
from products.interfaces.serializers import ProductSerializer
from users.interfaces.serializers import LoginSerializer, RegisterSerializer, ResetPasswordSerializer


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


def test_product_serializer_create_persists_relationships(product_factory):
    reference = product_factory()
    category = reference.categories.get()
    game_type = GameType.objects.create(name="Strategy")
    audience = Audience.objects.create(name="Family")
    serializer = ProductSerializer(
        data={
            "name": "Created Product",
            "description": "Created through serializer",
            "price": "24.50",
            "discount": "10.00",
            "stock": 7,
            "brand": reference.brand_id,
            "categories": [category.id],
            "types": [game_type.id],
            "audiences": [audience.id],
        }
    )

    assert serializer.is_valid(), serializer.errors
    product = serializer.save()

    assert product.price == Decimal("24.50")
    assert product.discount == Decimal("10.00")
    assert list(product.categories.values_list("id", flat=True)) == [category.id]
    assert list(product.types.values_list("name", flat=True)) == ["Strategy"]
    assert list(product.audiences.values_list("name", flat=True)) == ["Family"]


def test_product_serializer_update_replaces_relationships(product_factory):
    product = product_factory()
    replacement = product_factory()
    new_category = replacement.categories.get()
    new_type = GameType.objects.create(name="Party")
    serializer = ProductSerializer(
        product,
        data={
            "price": "19.99",
            "categories": [new_category.id],
            "types": [new_type.id],
        },
        partial=True,
    )

    assert serializer.is_valid(), serializer.errors
    updated = serializer.save()

    assert updated.price == Decimal("19.99")
    assert list(updated.categories.values_list("id", flat=True)) == [new_category.id]
    assert list(updated.types.values_list("name", flat=True)) == ["Party"]


@pytest.mark.parametrize("discount", [Decimal("-1.00"), Decimal("100.01")])
def test_product_serializer_currently_accepts_out_of_range_discount(discount, product_factory):
    product = product_factory()
    serializer = ProductSerializer(product, data={"discount": discount}, partial=True)

    assert serializer.is_valid(), serializer.errors
    updated = serializer.save()

    assert updated.discount == discount
    updated.refresh_from_db()
    assert updated.discount == discount


def test_product_serializer_rejects_negative_stock(product_factory):
    serializer = ProductSerializer(product_factory(), data={"stock": -1}, partial=True)

    assert not serializer.is_valid()
    assert "stock" in serializer.errors


def test_login_serializer_authenticates_valid_credentials(user_factory):
    user = user_factory(email="serializer-login@example.com", password="correct-password")
    serializer = LoginSerializer(data={"email": user.email, "password": "correct-password"})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["user"] == user


def test_login_serializer_rejects_invalid_credentials(user_factory):
    user = user_factory(email="serializer-login-fail@example.com", password="correct-password")
    serializer = LoginSerializer(data={"email": user.email, "password": "wrong-password"})

    assert not serializer.is_valid()
    assert serializer.errors["non_field_errors"] == ["Invalid credentials"]


@pytest.mark.bug
def test_current_reset_serializer_defect_reads_undeclared_token_field(user_factory):
    user = user_factory()
    serializer = ResetPasswordSerializer(
        data={
            "uid": urlsafe_base64_encode(force_bytes(user.pk)),
            "access_token": "value",
            "new_password": "newpassword123",
        }
    )

    with pytest.raises(KeyError, match="token"):
        serializer.is_valid()
