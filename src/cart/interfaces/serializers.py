from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from cart.infrastructure.models import Cart, CartItem, GuestCart, GuestCartItem, GuestCheckoutSession
from common.fields import NonNullJSONField
from common.serializers import FullBodySerializerMixin
from common.validation import INT64_MAX
from products.infrastructure.models import Product
from products.interfaces.serializers import ProductSerializer

QUANTITY_MAX = 2147483647
QUANTITY_MIN = -2147483648


class CartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True, min_value=1, max_value=INT64_MAX)
    attrs = NonNullJSONField(required=False)
    metadata = NonNullJSONField(required=False)

    class Meta:
        model = CartItem
        fields = ['id', 'product_id', 'quantity', 'attrs', 'metadata']
        read_only_fields = ('id', 'sku', 'title', 'added_at', 'updated_at')
        extra_kwargs = {'quantity': {'min_value': 1, 'max_value': QUANTITY_MAX, 'default': 1}}

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Кількість має бути більшою за 0.")
        return value

    def validate_product_id(self, value):
        if not Product.objects.filter(id=value).exists():
            raise serializers.ValidationError("Товар із вказаним product_id не існує.")
        return value

    def create(self, validated_data):
        product_id = validated_data.pop('product_id')
        product = Product.objects.get(id=product_id)
        validated_data['product'] = product
        validated_data['sku'] = getattr(product, 'sku', '')
        validated_data['title'] = product.name
        return super().create(validated_data)

    def update(self, instance, validated_data):
        product_id = validated_data.get('product_id')
        if product_id:
            product = Product.objects.get(id=product_id)
            validated_data['product'] = product
            validated_data['sku'] = getattr(product, 'sku', '')
            validated_data['title'] = product.name
        return super().update(instance, validated_data)


class CartItemForCartSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    product_id = serializers.IntegerField(source='product.id', read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'cart_id', 'product_id', 'sku', 'title', 'quantity', 'attrs', 'metadata', 'added_at',
                  'updated_at', 'product_details']


@extend_schema_serializer(many=False)
class CartSerializer(serializers.ModelSerializer):
    items = CartItemForCartSerializer(many=True, read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'user_id', 'is_active', 'created_at', 'updated_at', 'items']
        read_only_fields = ('id', 'created_at', 'updated_at', 'user_id')


class GuestCartItemSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)
    product_id = serializers.IntegerField(write_only=True, min_value=1, max_value=INT64_MAX)
    attrs = NonNullJSONField(required=False)
    metadata = NonNullJSONField(required=False)

    class Meta:
        model = GuestCartItem
        fields = [
            'id', 'guest_cart_id', 'product_id', 'sku', 'title', 'quantity',
            'attrs', 'metadata', 'added_at', 'updated_at', 'product_details'
        ]
        read_only_fields = ('id', 'guest_cart_id', 'added_at', 'updated_at', 'product_details', 'sku', 'title')
        extra_kwargs = {'quantity': {'min_value': 1, 'max_value': QUANTITY_MAX, 'default': 1}}

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Кількість має бути більшою за 0.")
        return value

    def validate_product_id(self, value):
        if not Product.objects.filter(id=value).exists():
            raise serializers.ValidationError("Товар із вказаним product_id не існує.")
        return value

    def create(self, validated_data):
        product_id = validated_data.pop('product_id')
        product = Product.objects.get(id=product_id)
        validated_data['product'] = product
        validated_data['sku'] = getattr(product, 'sku', '')
        validated_data['title'] = product.name
        return super().create(validated_data)


class GuestCartSerializer(serializers.ModelSerializer):
    items = GuestCartItemSerializer(many=True, read_only=True)
    expiresAt = serializers.DateTimeField(source='expires_at', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = GuestCart
        fields = ['id', 'token', 'is_active', 'expiresAt', 'createdAt', 'items']
        read_only_fields = ('token', 'expiresAt', 'createdAt', 'is_active')

    def create(self, validated_data):
        return GuestCart.create_guest_cart()


class GuestCheckoutSessionSerializer(serializers.ModelSerializer):
    guestCheckoutToken = serializers.CharField(source='session_token', read_only=True)
    guestCartToken = serializers.CharField(source='guest_cart.token', read_only=True)
    expiresAt = serializers.DateTimeField(source='expires_at', read_only=True)

    class Meta:
        model = GuestCheckoutSession
        fields = ['guestCheckoutToken', 'guestCartToken', 'email', 'phone', 'expiresAt']
        read_only_fields = ['guestCheckoutToken', 'guestCartToken', 'expiresAt']


class CartItemUpdateSerializer(FullBodySerializerMixin, serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1, max_value=INT64_MAX)
    quantity = serializers.IntegerField(min_value=QUANTITY_MIN, max_value=QUANTITY_MAX,
                                        help_text='Нова кількість. Значення 0 і менше видаляє позицію.')
    attrs = NonNullJSONField(required=False)
    metadata = NonNullJSONField(required=False)


class CartItemRemoveSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1, max_value=INT64_MAX)


class GuestCheckoutStartSerializer(serializers.Serializer):
    guestCartToken = serializers.CharField(max_length=64)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=20)
