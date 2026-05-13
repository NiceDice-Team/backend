import pytest
from orders.interfaces.serializers import OrderSerializer
from orders.infrastructure.models import Order
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestOrderSerializer:
    """Test suite for Order serializers"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    def test_order_serializer_read(self):
        """Test serializing existing order"""
        order = Order.objects.create(
            user=self.user,
            total_amount=99.99
        )
        serializer = OrderSerializer(order)
        assert 'id' in serializer.data
        assert serializer.data['user'] == self.user.id
        assert 'products' in serializer.data
        assert 'total_amount' in serializer.data
