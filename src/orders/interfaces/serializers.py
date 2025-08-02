from common.serializers import ExampleIgnoringModelSerializer
from orders.infrastructure.models import Order


class OrderSerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = Order
        fields = ['id', 'products', 'created_at']
        extra_kwargs = {
            'id': {'read_only': False},
            'products': {'required': True},
            'created_at': {'read_only': False, 'format': '%Y-%m-%dT%H:%M:%SZ'},
        }
