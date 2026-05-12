import uuid
import pytest
from products.interfaces.serializers import ProductSerializer
from products.infrastructure.models import Product, Brand
from categories.infrastructure.models import Category


@pytest.mark.django_db
class TestProductSerializer:
    """Test suite for Product serializers"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data"""
        self.category = Category.objects.create(name=f"Electronics-{uuid.uuid4().hex[:8]}")
        self.brand, _ = Brand.objects.get_or_create(name="Test Brand")

    def test_product_serializer_read(self):
        """Test serializing existing product"""
        product = Product.objects.create(
            name='Test Product',
            description='Test Description',
            price="99.99",
            stock=10
        ,
            brand=self.brand
        )
        product.categories.add(self.category)
        serializer = ProductSerializer(product)
        assert serializer.data['name'] == 'Test Product'
        assert 'id' in serializer.data
        assert 'price' in serializer.data
        assert 'categories' in serializer.data
