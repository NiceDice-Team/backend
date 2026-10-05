"""Create deterministic local-only records for runtime contract testing."""

import os
import sys
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.contract_settings")

import django  # noqa: E402
from django.db import transaction  # noqa: E402

django.setup()

from categories.infrastructure.models import Category  # noqa: E402
from products.infrastructure.models import Brand, Product  # noqa: E402
from rest_framework_simplejwt.tokens import RefreshToken  # noqa: E402
from users.infrastructure.models import User  # noqa: E402


def main() -> None:
    with transaction.atomic():
        user, _ = User.objects.update_or_create(
            email="contract-user@nicedice.invalid",
            defaults={
                "username": "contract-user@nicedice.invalid",
                "first_name": "Contract",
                "last_name": "User",
                "is_active": True,
                "is_staff": False,
                "is_superuser": False,
            },
        )
        user.set_password("contract-password-not-a-secret")
        user.save()

        category, _ = Category.objects.update_or_create(
            slug="contract-category",
            defaults={"name": "Contract Category", "description": "Local contract seed"},
        )
        brand, _ = Brand.objects.update_or_create(name="Contract Brand", defaults={})
        product, _ = Product.objects.update_or_create(
            slug="contract-product",
            defaults={
                "name": "Contract Product",
                "description": "Local contract seed",
                "price": Decimal("10.00"),
                "stock": 10,
                "brand": brand,
            },
        )
        product.categories.set([category])

        assert User.objects.filter(email=user.email, username=user.email).count() == 1
        assert user.is_active and user.check_password("contract-password-not-a-secret")
        assert Category.objects.filter(pk=category.pk, name="Contract Category").count() == 1
        assert Brand.objects.filter(pk=brand.pk, name="Contract Brand").count() == 1
        assert Product.objects.filter(
            pk=product.pk,
            name="Contract Product",
            price=Decimal("10.00"),
            stock=10,
            brand=brand,
            categories=category,
        ).count() == 1

        token = str(RefreshToken.for_user(user).access_token)
        if not token:
            raise RuntimeError("Contract seed failed to generate a JWT")

    print(token)


if __name__ == "__main__":
    main()
