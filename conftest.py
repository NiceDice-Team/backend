# backend/conftest.py

import django
import os
import sys
import pytest
from pathlib import Path

# Check that the settings module is set correctly
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.test_settings")
SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.append(str(SRC_DIR))

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient
from cart.infrastructure.models import Cart, CartItem, GuestCart, GuestCartItem, GuestCheckoutSession
from src.categories.models import Category
from products.infrastructure.models import Brand, Product


@pytest.fixture(scope="session", autouse=True)
def django_setup():
    # Ensure Django is set up before running tests
    django.setup()

@pytest.fixture
def user_model():
    # User model fixture to be used in tests
    return get_user_model()


@pytest.fixture
def category_model():
    # Category model fixture to be used in tests
    return Category


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(user_model):
    user = user_model.objects.create_user(
        username="user",
        email="user@example.com",
        password="testpass123",
        first_name="Test",
        last_name="User",
    )
    user.is_active = True
    user.save(update_fields=["is_active"])
    return user


@pytest.fixture
def product(category_model):
    category = category_model.objects.create(name="Board Games", slug="board-games")
    brand = Brand.objects.create(name="Test Brand")
    product = Product.objects.create(
        name="Test Game",
        description="Test game description",
        price="29.99",
        stock=10,
        brand=brand,
    )
    product.categories.add(category)
    return product


@pytest.fixture
def guest_cart(product):
    cart = GuestCart.create_guest_cart()
    GuestCartItem.objects.create(
        guest_cart=cart,
        product=product,
        quantity=2,
        sku="TEST-GAME",
        title=product.name,
    )
    return cart


@pytest.fixture
def user_cart(user, product):
    cart = Cart.objects.create(user=user, is_active=True)
    CartItem.objects.create(
        cart=cart,
        product=product,
        quantity=1,
        sku="TEST-GAME",
        title=product.name,
    )
    return cart


@pytest.fixture
def guest_session(guest_cart):
    return GuestCheckoutSession.objects.create(
        guest_cart=guest_cart,
        email="guest@example.com",
        phone="+380123456789",
    )


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


def build_active_user(user_model, username, email, **extra):
    account = user_model.objects.create_user(
        username=username,
        email=email,
        password="testpass123",
        first_name="Test",
        last_name="User",
        **extra,
    )
    account.is_active = True
    account.save(update_fields=["is_active"])
    return account


@pytest.fixture
def other_user(user_model):
    return build_active_user(user_model, "other", "other@example.com")


@pytest.fixture
def staff_user(user_model):
    return build_active_user(user_model, "staff", "staff@example.com", is_staff=True)


def build_authenticated_client(account):
    client = APIClient()
    client.force_authenticate(user=account)
    return client


@pytest.fixture
def auth_client(user):
    return build_authenticated_client(user)


@pytest.fixture
def other_client(other_user):
    return build_authenticated_client(other_user)


@pytest.fixture
def staff_client(staff_user):
    return build_authenticated_client(staff_user)
