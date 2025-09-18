from rest_framework import generics
from common.permissions import ReadOnlyOrAuthenticated
from categories.infrastructure.models import Category
from categories.interfaces.serializers import CategorySerializer, PatchedCategorySerializer
from drf_spectacular.utils import extend_schema, OpenApiExample


@extend_schema(tags=['Categories'])
class CategoryListCreateView(generics.ListCreateAPIView):
    permission_classes = [ReadOnlyOrAuthenticated]
    queryset = Category.objects.all().order_by('id')
    serializer_class = CategorySerializer

    @extend_schema(
        responses={200: CategorySerializer(many=True)},
        tags=['Categories'],
        examples=[
            OpenApiExample(
                name='Список категорій',
                summary='GET /api/categories/',
                value=[{'id': 1, 'name': 'Хіти', 'image': '', 'creationAt': '2025-07-04T12:00:00.000Z',
                        'updatedAt': '2025-07-05T12:00:00.000Z'}],
                response_only=True
            ),
            OpenApiExample(
                name='Створення категорії',
                summary='POST /api/categories/',
                value={'name': 'Нові', 'image': 'https://.../new.jpg'},
                request_only=True
            )
        ]
    )
    def get(self, *args, **kwargs): return super().get(*args, **kwargs)

    def post(self, *args, **kwargs):
        return super().post(*args, **kwargs)


@extend_schema(tags=['Categories'])
@extend_schema(
    methods=['GET', 'DELETE', 'PATCH'],
    tags=['Categories'],
    request=PatchedCategorySerializer,
    responses={200: CategorySerializer},
    examples=[
        OpenApiExample(
            name='Отримати категорію',
            summary='GET /api/categories/{id}/',
            value={'id': 1, 'name': 'Хіти', 'image': '', 'creationAt': '2025-07-04T12:00:00.000Z',
                   'updatedAt': '2025-07-05T12:00:00.000Z'},
            response_only=True
        ),
        OpenApiExample(
            name='Оновити категорію',
            summary='PATCH /api/categories/{id}/',
            value={'name': 'Хіти секретні'},
            request_only=True
        )
    ]
)
class CategoryRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [ReadOnlyOrAuthenticated]
    queryset = Category.objects.all().order_by('id')
    serializer_class = CategorySerializer
