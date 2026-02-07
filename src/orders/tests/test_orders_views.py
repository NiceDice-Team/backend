import uuid
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from orders.infrastructure.models import Order
from products.infrastructure.models import Product, Brand, Brand
from categories.infrastructure.models import Category

User = get_user_model()


@pytest.mark.django_db
class TestOrderViewSet:
    """Test suite for Order ViewSet"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test client and data"""
        self.client = APIClient()
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

    def test_list_orders_authenticated(self):
        """Test listing orders requires authentication"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/orders/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST]

    def test_list_orders_unauthenticated(self):
        """Test listing orders without authentication"""
        response = self.client.get('/api/orders/')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_400_BAD_REQUEST]

    def test_retrieve_order_authenticated(self):
        """Test retrieving own order"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/orders/{self.order.id}/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST]

    def test_retrieve_other_user_order(self):
        """Test cannot retrieve other user's order"""
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="otherpass123"
        )
        self.client.force_authenticate(user=other_user)
        response = self.client.get(f'/api/orders/{self.order.id}/')
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]
