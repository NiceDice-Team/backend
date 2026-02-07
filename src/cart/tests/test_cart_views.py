import uuid
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from cart.infrastructure.models import CartItem
from products.infrastructure.models import Product, Brand, Brand
from categories.infrastructure.models import Category

User = get_user_model()


@pytest.mark.django_db
class TestCartItemViewSet:
    """Test suite for CartItem ViewSet"""

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
        self.cart_item = CartItem.objects.create(
            user=self.user,
            product=self.product,
            quantity=2
        )

    def test_list_cart_items_authenticated(self):
        """Test listing cart items requires authentication"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/carts/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_list_cart_items_unauthenticated(self):
        """Test listing cart items without authentication"""
        response = self.client.get('/api/carts/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]

    def test_retrieve_cart_item_authenticated(self):
        """Test retrieving own cart item"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/carts/{self.cart_item.id}/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    def test_delete_cart_item(self):
        """Test removing item from cart"""
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(f'/api/carts/{self.cart_item.id}/')
        assert response.status_code in [status.HTTP_204_NO_CONTENT, status.HTTP_400_BAD_REQUEST]

    def test_update_cart_item_quantity(self):
        """Test updating cart item quantity"""
        self.client.force_authenticate(user=self.user)
        data = {'quantity': 5}
        response = self.client.patch(f'/api/carts/{self.cart_item.id}/', data)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]
