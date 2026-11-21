from rest_framework import generics
from common.permissions import ReadOnlyOrAuthenticated
from categories.infrastructure.models import Category
from categories.interfaces.serializers import CategorySerializer
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample


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
                value={
                    'count': 1,
                    'next': None,
                    'previous': None,
                    'results': [{'id': 1, 'name': 'Хіти', 'image': '', 'creationAt': '2025-07-04T12:00:00.000Z',
                                 'updatedAt': '2025-07-05T12:00:00.000Z'}],
                },
                response_only=True
            ),
        ]
    )
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    @extend_schema(
        request=CategorySerializer,
        responses={201: CategorySerializer},
        tags=['Categories'],
        examples=[
            OpenApiExample(
                name='Створення категорії',
                summary='POST /api/categories/',
                value={'name': 'Нові', 'image': 'https://example.com/new.jpg'},
                request_only=True
            ),
        ]
    )
    def post(self, *args, **kwargs):
        return super().post(*args, **kwargs)


@extend_schema(tags=['Categories'])
@extend_schema_view(
    get=extend_schema(
        responses={200: CategorySerializer},
        examples=[
            OpenApiExample(
                name='Отримати категорію',
                summary='GET /api/categories/{id}/',
                value={'id': 1, 'name': 'Хіти', 'image': '', 'creationAt': '2025-07-04T12:00:00.000Z',
                       'updatedAt': '2025-07-05T12:00:00.000Z'},
                response_only=True
            ),
        ],
    ),
    put=extend_schema(request=CategorySerializer, responses={200: CategorySerializer}),
    patch=extend_schema(
        responses={200: CategorySerializer},
        examples=[
            OpenApiExample(
                name='Оновити категорію',
                summary='PATCH /api/categories/{id}/',
                value={'name': 'Хіти секретні'},
                request_only=True
            ),
        ],
    ),
    delete=extend_schema(responses={204: None}),
)
class CategoryRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [ReadOnlyOrAuthenticated]
    queryset = Category.objects.all().order_by('id')
    serializer_class = CategorySerializer
