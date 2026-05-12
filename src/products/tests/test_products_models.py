import uuid
import pytest
from django.db import IntegrityError
from products.infrastructure.models import Product, Brand
from categories.infrastructure.models import Category


@pytest.mark.django_db
class TestProductModel:
    """Test suite for Product model"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data"""
        self.brand, _ = Brand.objects.get_or_create(name="Test Brand")
        self.category = Category.objects.create(name=f"Electronics-{uuid.uuid4().hex[:8]}")

    def test_create_product_success(self):
        """Test creating a product with valid data"""
        category = self.category
        product = Product.objects.create(
            name="Test Product",
            description="Test Description",
            price="99.99",
            stock=10
        ,
            brand=self.brand
        )
        product.categories.add(self.category)
        product.categories.add(self.category)
        assert product.name == "Test Product"
        assert float(product.price) == 99.99
        assert product.stock == 10

    def test_product_str_representation(self):
        """Test string representation of product"""
        category = self.category
        product = Product.objects.create(
            name="Django Book",
            price="29.99"
        ,
            description="Test",
            brand=self.brand
        )
        product.categories.add(self.category)
        product.categories.add(self.category)
        assert str(product) == "Django Book"

    def test_product_category_relationship(self):
        """Test product-category relationship"""
        category = self.category
        product = Product.objects.create(
            name="Laptop",
            price="999.99"
        ,
            description="Test",
            brand=self.brand
        )
        product.categories.add(self.category)
        product.categories.add(self.category)
        assert category in product.categories.all()

    def test_product_update(self):
        """Test updating product fields"""
        category = self.category
        product = Product.objects.create(
            name="Original",
            price="10.00"
        ,
            description="Test",
            brand=self.brand
        )
        product.categories.add(self.category)
        product.categories.add(self.category)
        product.name = "Updated"
        product.price = 15.00
        product.save()
        updated_product = Product.objects.get(id=product.id)
        assert updated_product.name == "Updated"
        assert float(updated_product.price) == 15.00

    def test_product_delete(self):
        """Test deleting a product"""
        category = self.category
        product = Product.objects.create(
            name="To Delete",
            price="10.00"
        ,
            description="Test",
            brand=self.brand
        )
        product.categories.add(self.category)
        product.categories.add(self.category)
        product_id = product.id
        product.delete()
        assert not Product.objects.filter(id=product_id).exists()
