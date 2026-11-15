from django.db import transaction
from rest_framework import serializers

from categories.infrastructure.models import Category
from common.fields import NonNullJSONField
from common.serializers import ExampleIgnoringModelSerializer, FullBodySerializerMixin
from products.infrastructure.models import (Product, ProductImage, GameType, Brand, Audience, Review)


class ProductImageDetailSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True)

    class Meta:
        model = ProductImage
        fields = ['id', 'product_id', 'url_original', 'url_lg', 'url_md', 'url_sm', 'alt', 'sort']
        read_only_fields = ['id', 'product_id', 'url_lg', 'url_md', 'url_sm', 'url_original']


class ProductImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True, help_text="Зображення для завантаження")
    alt = serializers.CharField(
        required=False, allow_blank=True, max_length=255, default="", help_text="Альтернативний текст"
    )
    sort = serializers.IntegerField(required=False, default=0, min_value=0)


class ProductImageOrderItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1, max_value=2147483647, help_text="ID зображення продукту")
    sort = serializers.IntegerField(min_value=0, max_value=2147483647, help_text="Нова позиція зображення")


class ProductImageReorderSerializer(FullBodySerializerMixin, serializers.Serializer):
    images = ProductImageOrderItemSerializer(many=True, help_text="Список об'єктів {'id': int, 'sort': int}")


class ProductSerializer(ExampleIgnoringModelSerializer):
    images = ProductImageDetailSerializer(many=True, read_only=True)

    short_description = serializers.CharField(required=False, allow_blank=True)
    game_information = NonNullJSONField(required=False, default=dict)
    delivery_and_payments = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'created_at', 'updated_at', 'categories', 'brand', 'types',
            'audiences', 'images', 'discount', 'stock', 'stars', 'reviews', 'game_information', 'short_description',
            'delivery_and_payments'
        ]
        extra_kwargs = {
            'id': {'read_only': True},
            'name': {'required': True},
            'description': {'required': True},
            'price': {'required': True},
            'created_at': {'read_only': True, 'format': '%Y-%m-%dT%H:%M:%SZ'},
            'updated_at': {'read_only': True, 'format': '%Y-%m-%dT%H:%M:%SZ'},
            'types': {
                'many': True,
                'queryset': GameType.objects.all(),
                'required': False
            },
            'categories': {
                'many': True,
                'queryset': Category.objects.all(),
                'required': True
            },
            'audiences': {
                'many': True,
                'queryset': Audience.objects.all(),
                'required': False
            },
            'brand': {
                'queryset': Brand.objects.all(),
                'required': True
            },
            'images': {
                'many': True,
                'read_only': True
            },
            'discount': {'required': False},
            'stock': {'required': False},
            'stars': {'required': False},
            'reviews': {
                'many': True,
                'read_only': True
            },
        }

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('images', None)
        types_data = validated_data.pop('types', [])
        categories_data = validated_data.pop('categories', [])
        audiences_data = validated_data.pop('audiences', [])

        product = Product.objects.create(**validated_data)
        product.types.set(types_data)
        product.categories.set(categories_data)
        product.audiences.set(audiences_data)
        return product

    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data.pop('images', None)
        types_data = validated_data.pop('types', None)
        categories_data = validated_data.pop('categories', None)
        audiences_data = validated_data.pop('audiences', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if types_data is not None:
            instance.types.set(types_data)
        if categories_data is not None:
            instance.categories.set(categories_data)
        if audiences_data is not None:
            instance.audiences.set(audiences_data)

        return instance

    def validate_price(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Ціна повинна бути більшою за 0.")
        return value

    def validate_discount(self, value):
        if value is not None:
            from decimal import Decimal, InvalidOperation
            try:
                val = Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                raise serializers.ValidationError("Невірний формат знижки.")
            if val < Decimal('0.00'):
                raise serializers.ValidationError("Знижка не може бути менше 0%.")
            if val > Decimal('100.00'):
                raise serializers.ValidationError("Знижка не може бути більше 100%.")
        return value


class PatchedProductSerializer(ExampleIgnoringModelSerializer):
    short_description = serializers.CharField(required=False, allow_blank=True)
    game_information = NonNullJSONField(required=False, default=dict)
    delivery_and_payments = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Product
        fields = [
            'name', 'description', 'price',
            'categories', 'brand', 'types', 'audiences',
            'images', 'discount', 'stock', 'stars',
            'game_information', 'short_description', 'delivery_and_payments'
        ]
        extra_kwargs = {
            'name': {},
            'description': {},
            'price': {},
            'types': {
                'many': True,
                'queryset': GameType.objects.all(),
                'required': False
            },
            'categories': {
                'many': True,
                'queryset': Category.objects.all(),
                'required': False
            },
            'audiences': {
                'many': True,
                'queryset': Audience.objects.all(),
                'required': False
            },
            'brand': {
                'queryset': Brand.objects.all(),
                'required': False
            },
            'images': {
                'many': True,
                'required': False
            },
            'discount': {'required': False},
            'stock': {'required': False},
            'stars': {'required': False},
            'game_information': {'required': False},
            'short_description': {'required': False},
            'delivery_and_payments': {'required': False},
        }

    def validate_discount(self, value):
        if value is not None:
            from decimal import Decimal, InvalidOperation
            try:
                val = Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                raise serializers.ValidationError("Невірний формат знижки.")
            if val < Decimal('0.00'):
                raise serializers.ValidationError("Знижка не може бути менше 0%.")
            if val > Decimal('100.00'):
                raise serializers.ValidationError("Знижка не може бути більше 100%.")
            return value


class ProductImageSerializer(ExampleIgnoringModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='photo-detail'
    )

    class Meta:
        model = ProductImage
        fields = ['url']
        extra_kwargs = {
            'url': {}
        }


class GameTypeSerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = GameType
        fields = ['name']
        extra_kwargs = {
            'name': {}
        }


class BrandSerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = Brand
        fields = ['name']
        extra_kwargs = {
            'name': {}
        }


class AudienceSerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = Audience
        fields = ['name']
        extra_kwargs = {
            'name': {}
        }


DEFAULT_REVIEW_AUTHOR_NAME = 'Customer'

USER_NAME_HELP_TEXT = (
    "Публічне ім'я автора - ім'я та перша літера прізвища, наприклад Daniel T. "
    f"Якщо ім'я невідоме, повертається {DEFAULT_REVIEW_AUTHOR_NAME}."
)


def build_review_author_name(user):
    if user is None:
        return DEFAULT_REVIEW_AUTHOR_NAME
    first_name = (user.first_name or '').strip()
    last_name = (user.last_name or '').strip()
    if not first_name:
        return DEFAULT_REVIEW_AUTHOR_NAME
    if not last_name:
        return first_name
    return f'{first_name} {last_name[0].upper()}.'


class ReviewSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
    )
    user_id = serializers.IntegerField(read_only=True, allow_null=True)
    user_name = serializers.SerializerMethodField(help_text=USER_NAME_HELP_TEXT)
    rating = serializers.IntegerField(min_value=1, max_value=5)

    class Meta:
        model = Review
        fields = ['id', 'product_id', 'user_id', 'user_name', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'user_id', 'created_at']
        extra_kwargs = {
            'comment': {'allow_blank': True, 'required': False},
        }

    def get_user_name(self, obj) -> str:
        return build_review_author_name(obj.user)


class ReviewWriteSerializer(ReviewSerializer):
    product_id = serializers.IntegerField(read_only=True)


class FeaturedReviewSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True, help_text='ID гри, до якої залишено відгук.')
    product_name = serializers.CharField(source='product.name', read_only=True, help_text='Назва гри.')
    user_name = serializers.SerializerMethodField(help_text=USER_NAME_HELP_TEXT)

    class Meta:
        model = Review
        fields = ['id', 'product_id', 'product_name', 'user_name', 'rating', 'comment', 'created_at']
        read_only_fields = fields

    def get_user_name(self, obj) -> str:
        return build_review_author_name(obj.user)


class PatchedReviewSerializer(serializers.ModelSerializer):
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)

    class Meta:
        model = Review
        fields = ['rating', 'comment']
        extra_kwargs = {
            'comment': {'allow_blank': True, 'required': False},
        }
