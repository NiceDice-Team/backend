from categories.infrastructure.models import Category
from common.serializers import ExampleIgnoringModelSerializer


class CategorySerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'image', 'creationAt', 'updatedAt']
        extra_kwargs = {
            'id': {'read_only': False},
            'name': {'required': True},
            'image': {'required': False, 'allow_blank': True},
            'creationAt': {'source': 'created_at', 'read_only': False, 'format': '%Y-%m-%dT%H:%M:%S.000Z'},
            'updatedAt': {'source': 'updated_at', 'read_only': False, 'format': '%Y-%m-%dT%H:%M:%S.000Z'},
        }


class PatchedCategorySerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = Category
        fields = ['name', 'image']
        extra_kwargs = {
            'name': {'required': False},
            'image': {'required': False, 'allow_blank': True},
        }
