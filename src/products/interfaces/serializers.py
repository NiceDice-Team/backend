from categories.infrastructure.models import Category
from common.serializers import ExampleIgnoringModelSerializer
from products.infrastructure.models import (Product, ProductImage, GameType, Brand, Audience, Review)
from rest_framework import serializers


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


class ProductImageReorderSerializer(serializers.Serializer):
    images = serializers.ListField(
        child=serializers.DictField(child=serializers.IntegerField()),
        help_text="Список об'єктів {'id': int, 'sort': int}"
    )

    def validate_images(self, value):
        for item in value:
            if 'id' not in item or 'sort' not in item:
                raise serializers.ValidationError("Кожен елемент списку повинен містити 'id' та 'sort'.")
        return value


class ProductSerializer(ExampleIgnoringModelSerializer):
    images = ProductImageDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price',
            'created_at', 'updated_at',
            'categories', 'brand', 'types', 'audiences',
            'images', 'discount', 'stock', 'stars', 'reviews'
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

    def create(self, validated_data):
        images_data = validated_data.pop('images', [])
        types_data = validated_data.pop('types', [])
        categories_data = validated_data.pop('categories', [])
        audiences_data = validated_data.pop('audiences', [])
        brand_name = validated_data.pop('brand')

        brand, _ = Brand.objects.get_or_create(name=brand_name)
        validated_data['brand'] = brand

        product = Product.objects.create(**validated_data)

        for t in types_data:
            obj, _ = GameType.objects.get_or_create(name=t)
            product.types.add(obj)

        for c in categories_data:
            product.categories.add(c)

        for a in audiences_data:
            obj, _ = Audience.objects.get_or_create(name=a)
            product.audiences.add(obj)
        return product

    def update(self, instance, validated_data):
        images_data = validated_data.pop('images', None)
        types_data = validated_data.pop('types', None)
        categories_data = validated_data.pop('categories', None)
        audiences_data = validated_data.pop('audiences', None)
        brand_name = validated_data.pop('brand', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if brand_name is not None:
            brand, _ = Brand.objects.get_or_create(name=brand_name)
            instance.brand = brand

        instance.save()

        if types_data is not None:
            instance.types.clear()
            for t in types_data:
                obj, _ = GameType.objects.get_or_create(name=t)
                instance.types.add(obj)

        if categories_data is not None:
            instance.categories.set(categories_data)

        if audiences_data is not None:
            instance.audiences.clear()
            for a in audiences_data:
                obj, _ = Audience.objects.get_or_create(name=a)
                instance.audiences.add(obj)
        return instance

    def validate_price(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Ціна повинна бути більшою за 0.")
        return value


class PatchedProductSerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = Product
        fields = [
            'name', 'description', 'price',
            'categories', 'brand', 'types', 'audiences',
            'images', 'discount', 'stock', 'stars'
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
        }


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


class ReviewSerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = Review
        fields = ['rating', 'comment', 'created_at']
        extra_kwargs = {
            'rating': {'help_text': 'Score, e.g. 4.50'},
            'comment': {'allow_blank': True},
            'created_at': {'read_only': True, 'format': '%Y-%m-%dT%H:%M:%SZ'}
        }


class PatchedReviewSerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        extra_kwargs = {
            'rating': {},
            'comment': {}
        }
