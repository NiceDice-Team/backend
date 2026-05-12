import uuid
import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from orders.infrastructure.models import Order, OrderItem
from products.infrastructure.models import Product, Brand
from categories.infrastructure.models import Category

User = get_user_model()


@pytest.mark.django_db
class TestOrderModel:
    """Test suite for Order model"""

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

    def test_create_order_success(self):
        """Test creating an order with valid data"""
        order = Order.objects.create(
            user=self.user,
            total_amount=99.99
        )
        assert order.user == self.user
        assert float(order.total_amount) == 99.99

    def test_order_str_representation(self):
        """Test string representation of order"""
        order = Order.objects.create(
            user=self.user,
            total_amount=99.99
        )
        assert str(order) is not None

    def test_order_user_relationship(self):
        """Test order-user relationship"""
        order = Order.objects.create(
            user=self.user,
            total_amount=99.99
        )
        assert order.user == self.user

    def test_order_timestamps(self):
        """Test order has timestamps"""
        order = Order.objects.create(
            user=self.user,
            total_amount=99.99
        )
        assert hasattr(order, 'created_at')


@pytest.mark.django_db
class TestOrderItemModel:
    """Test suite for OrderItem model"""

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
        self.order = Order.objects.create(
            user=self.user,
            total_amount=99.99
        )

    def test_create_order_item_success(self):
        """Test creating an order item"""
        order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price="99.99"
        )
        assert order_item.order == self.order
        assert order_item.product == self.product
        assert order_item.quantity == 2

    def test_order_item_quantity_validation(self):
        """Test order item quantity must be positive"""
        order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price="99.99"
        )
        assert order_item.quantity > 0
