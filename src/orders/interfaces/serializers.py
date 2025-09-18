from common.serializers import ExampleIgnoringModelSerializer
from orders.infrastructure.models import Order
from products.interfaces.serializers import ProductSerializer
from rest_framework import serializers


class SimpleProductSerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = ProductSerializer.Meta.model
        fields = ['id', 'name', 'price']


class OrderSerializer(ExampleIgnoringModelSerializer):
    products = SimpleProductSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'products', 'total_amount', 'created_at', 'updated_at', 'status']
        extra_kwargs = {
            'id': {'read_only': True},
            'user': {'read_only': True},
            'products': {'read_only': True},
            'total_amount': {'read_only': True},
            'created_at': {'read_only': True, 'format': '%Y-%m-%dT%H:%M:%SZ'},
            'updated_at': {'read_only': True, 'format': '%Y-%m-%dT%H:%M:%SZ'},
            'status': {'read_only': True},
        }


class SimpleProductInListSerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = ProductSerializer.Meta.model
        fields = ['id', 'name', 'price']


class OrderListSerializer(ExampleIgnoringModelSerializer):
    products = SimpleProductInListSerializer(many=True, read_only=True)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'products', 'product_count', 'total_amount', 'created_at', 'status']
        extra_kwargs = {
            'id': {'read_only': True},
            'total_amount': {'read_only': True},
            'created_at': {'read_only': True, 'format': '%Y-%m-%dT%H:%M:%SZ'},
            'status': {'read_only': True},
        }

    def get_product_count(self, obj):
        return obj.products.count()
