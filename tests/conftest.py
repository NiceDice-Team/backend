from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from categories.infrastructure.models import Category
from products.infrastructure.models import Brand, Product


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_factory(user_model):
    counter = 0

    def create(**overrides):
        nonlocal counter
        counter += 1
        email = overrides.pop("email", f"user{counter}@example.com")
        password = overrides.pop("password", "strongpassword123")
        return user_model.objects.create_user(
            username=overrides.pop("username", email),
            email=email,
            password=password,
            first_name=overrides.pop("first_name", "Test"),
            last_name=overrides.pop("last_name", "User"),
            **overrides,
        )

    return create


@pytest.fixture
def product_factory():
    counter = 0

    def create(**overrides):
        nonlocal counter
        counter += 1
        category = overrides.pop("category", None) or Category.objects.create(
            name=f"Category {counter}", slug=f"category-{counter}"
        )
        brand = overrides.pop("brand", None) or Brand.objects.create(name=f"Brand {counter}")
        product = Product.objects.create(
            name=overrides.pop("name", f"Product {counter}"),
            slug=overrides.pop("slug", f"product-{counter}"),
            description=overrides.pop("description", "Test product"),
            price=overrides.pop("price", Decimal("10.00")),
            discount=overrides.pop("discount", Decimal("0.00")),
            stock=overrides.pop("stock", 10),
            brand=brand,
            **overrides,
        )
        product.categories.add(category)
        return product

    return create

