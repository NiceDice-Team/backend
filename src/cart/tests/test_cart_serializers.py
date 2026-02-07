import uuid
import pytest
from cart.interfaces.serializers import CartItemSerializer, CartItemDetailSerializer
from cart.infrastructure.models import CartItem
from products.infrastructure.models import Product, Brand, Brand
from categories.infrastructure.models import Category
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestCartItemSerializer:
    """Test suite for Cart serializers"""

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

    def test_cart_item_serializer_read(self):
        """Test serializing existing cart item"""
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=2
        )
        serializer = CartItemSerializer(cart_item)
        assert serializer.data['quantity'] == 2
        assert 'product' in serializer.data

    def test_cart_item_detail_serializer(self):
        """Test CartItemDetailSerializer includes product details"""
        cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=2
        )
        serializer = CartItemDetailSerializer(cart_item)
        assert 'product' in serializer.data
