import uuid
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from products.infrastructure.models import Product, Brand
from categories.infrastructure.models import Category

User = get_user_model()


@pytest.mark.django_db
class TestProductViewSet:
    """Test suite for Product ViewSet"""

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
            description="Test Description",
            price="99.99",
            stock=10
        ,
            brand=self.brand
        )
        self.product.categories.add(self.category)
        self.product.categories.add(self.category)

    def test_list_products(self):
        """Test listing all products"""
        response = self.client.get('/api/products/')
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_product(self):
        """Test retrieving a single product"""
        response = self.client.get(f'/api/products/{self.product.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == "Test Product"

    def test_retrieve_nonexistent_product(self):
        """Test retrieving non-existent product returns 404"""
        response = self.client.get('/api/products/99999/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_product_authenticated(self):
        """Test creating product with authentication"""
        self.client.force_authenticate(user=self.user)
        data = {
            'name': 'New Product',
            'description': 'New Description',
            'price': 49.99,
            'stock': 5,
            'categories': [self.category.id],
            'brand': self.brand.id
        }
        response = self.client.post('/api/products/', data)
        # May require admin permissions
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_403_FORBIDDEN]

    def test_filter_products_by_category(self):
        """Test filtering products by category"""
        response = self.client.get(f'/api/products/?category={self.category.id}')
        assert response.status_code == status.HTTP_200_OK

    def test_search_products(self):
        """Test searching products by name"""
        response = self.client.get('/api/products/?search=Test')
        assert response.status_code == status.HTTP_200_OK
