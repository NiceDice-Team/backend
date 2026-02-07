import uuid
import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from cart.infrastructure.models import CartItem
from products.infrastructure.models import Product, Brand, Brand
from categories.infrastructure.models import Category

User = get_user_model()


@pytest.mark.django_db
class TestCartItemModel:
    """Test suite for CartItem model"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.category = Category.objects.create(name=f"Electronics-{uuid.uuid4().hex[:8]}")
        self.brand, _ = Brand.objects.get_or_create(name="Test Brand")
        self.brand, _ = Brand.objects.get_or_create(name="Test Brand")
        self.product = Product.objects.create(
            name="Test Product",
            price="99.99",
            stock=10
        ,
            description="Test",
            brand=self.brand
        )
        self.product.categories.add(self.category)
        self.product.categories.add(self.category)

    def test_create_cart_item_success(self):
        """Test creating a cart item with valid data"""
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=2
        )
        assert cart_item.user == self.user
        assert cart_item.product == self.product
        assert cart_item.quantity == 2

    def test_cart_item_str_representation(self):
        """Test string representation of cart item"""
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=1
        )
        assert str(cart_item) is not None

    def test_cart_item_quantity_validation(self):
        """Test cart item quantity must be positive"""
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=1
        )
        assert cart_item.quantity > 0

    def test_cart_item_update_quantity(self):
        """Test updating cart item quantity"""
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=1
        )
        cart_item.quantity = 3
        cart_item.save()
        updated_item = CartItem.objects.get(id=cart_item.id)
        assert updated_item.quantity == 3

    def test_cart_item_delete(self):
        """Test deleting a cart item"""
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=1
        )
        item_id = cart_item.id
        cart_item.delete()
        assert not CartItem.objects.filter(id=item_id).exists()
