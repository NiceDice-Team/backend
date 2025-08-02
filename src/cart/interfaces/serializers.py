from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from common.serializers import ExampleIgnoringModelSerializer
from cart.infrastructure.models import CartItem


class CartItemSerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity']
        extra_kwargs = {
            'id': {'read_only': False},
            'product': {'required': True},
            'quantity': {'required': True},
        }


class PatchedCartItemSerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = CartItem
        fields = ['product', 'quantity']
        extra_kwargs = {
            'product': {'required': False},
            'quantity': {'required': False},
        }


class CartItemDetailSerializer(ExampleIgnoringModelSerializer):
    product = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity']
        extra_kwargs = {
            'id': {'read_only': False},
            'quantity': {'required': True},
        }

    @extend_schema_field(serializers.IntegerField())
    def get_product(self, obj):
        return {
            'id': obj.product.id,
            'name': obj.product.name,
            'price': obj.product.price,
        }
