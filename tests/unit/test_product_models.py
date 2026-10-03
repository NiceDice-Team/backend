from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from products.infrastructure.models import Product


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("-0.01")])
def test_product_clean_rejects_non_positive_price(price):
    product = Product(price=price)

    with pytest.raises(ValidationError) as exc_info:
        product.clean()

    assert exc_info.value.message_dict == {
        "price": ["Ціна повинна бути більшою за 0."],
    }


def test_product_clean_accepts_positive_price():
    product = Product(price=Decimal("0.01"))

    assert product.clean() is None

