from categories.infrastructure.models import Category
from common.fields import OptionalURLField
from common.serializers import ExampleIgnoringModelSerializer
from rest_framework import serializers


class CategorySerializer(ExampleIgnoringModelSerializer):
    image = OptionalURLField(required=False, allow_blank=True, max_length=1000)

    class Meta:
        model = Category
        fields = ['id', 'name', 'image', 'creationAt', 'updatedAt']
        extra_kwargs = {
            'id': {'read_only': True},
            'name': {'required': True},
            'creationAt': {'source': 'created_at', 'read_only': True, 'format': '%Y-%m-%dT%H:%M:%S.000Z'},
            'updatedAt': {'source': 'updated_at', 'read_only': True, 'format': '%Y-%m-%dT%H:%M:%S.000Z'},
        }

    def validate_name(self, value):
        if self.instance is not None and self.instance.slug:
            return value
        slug = Category.build_slug(value)
        if not slug:
            raise serializers.ValidationError('Name must contain at least one letter or digit.')
        collisions = Category.objects.filter(slug=slug)
        if self.instance is not None:
            collisions = collisions.exclude(pk=self.instance.pk)
        if collisions.exists():
            raise serializers.ValidationError('A category with a similar name already exists.')
        return value


class PatchedCategorySerializer(ExampleIgnoringModelSerializer):
    image = OptionalURLField(required=False, allow_blank=True, max_length=1000)

    class Meta:
        model = Category
        fields = ['name', 'image']
        extra_kwargs = {
            'name': {'required': False},
        }
