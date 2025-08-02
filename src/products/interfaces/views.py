from rest_framework import generics, filters
from rest_framework.exceptions import NotFound
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter

from common.permissions import ReadOnlyOrAuthenticated
from products.infrastructure.models import (
    Product, GameType, Audience, Brand,
    ProductImage, Review
)
from products.interfaces.serializers import (
    ProductSerializer,
    PatchedProductSerializer,
    GameTypeSerializer, AudienceSerializer, BrandSerializer,
    ProductImageSerializer, ReviewSerializer,
    PatchedReviewSerializer
)
from products.interfaces.pagination import ProductLimitPagination


class GenericListCreateView(generics.ListCreateAPIView):
    permission_classes = [ReadOnlyOrAuthenticated]


class GenericRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [ReadOnlyOrAuthenticated]

    def get_object(self):
        try:
            return super().get_object()
        except self.queryset.model.DoesNotExist:
            raise NotFound()


@extend_schema(tags=['Products'])
@extend_schema(
    responses={200: ProductSerializer(many=True)},
    tags=['Products'],
    parameters=[
        OpenApiParameter(
            name='search',
            description='Пошук по назві та опису продукту',
            required=False,
            type=str,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='ordering',
            description='Сортування, наприклад `price`, `-created_at`',
            required=False,
            type=str,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='brand',
            description='Фільтр по назві бренду',
            required=False,
            type=str,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='categories',
            description='Фільтр по ID категорій (через кому)',
            required=False,
            type=str,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='types',
            description='Фільтр по назвах типів гри (через кому)',
            required=False,
            type=str,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='audiences',
            description='Фільтр по назвах аудиторій (через кому)',
            required=False,
            type=str,
            location=OpenApiParameter.QUERY
        ),
    ],
    examples=[
        OpenApiExample(
            name='Приклад фільтрації та сортування',
            summary='GET /api/products/?search=шахи&brand=Hasbro&ordering=-price',
            value=[{
                "id": 1,
                "name": "Шахи",
                "description": "Класична стратегічна настільна гра.",
                "price": "29.99",
                "created_at": "2025-07-04T12:00:00Z",
                "updated_at": "2025-07-05T12:00:00Z",
                "categories": [1, 2],
                "brand": "Hasbro",
                "types": ["Стратегія"],
                "audiences": ["Для дорослих"],
                "images": [{"url": "https://example.com/images/chess.jpg"}],
                "discount": "10.00",
                "stock": 100,
                "stars": "4.50",
                "reviews": [{"rating": "4.50", "comment": "Кльова гра!"}]
            }],
            response_only=True,
        ),
    ],
)
class ProductListView(GenericListCreateView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    pagination_class = ProductLimitPagination

    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at', 'updated_at', 'name']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        brand = params.get('brand')
        if brand:
            qs = qs.filter(brand__name__iexact=brand)

        cats = params.get('categories')
        if cats:
            ids = [int(x) for x in cats.split(',') if x.isdigit()]
            qs = qs.filter(categories__id__in=ids)

        types = params.get('types')
        if types:
            names = [x.strip() for x in types.split(',') if x.strip()]
            qs = qs.filter(types__name__in=names)

        aud = params.get('audiences')
        if aud:
            names = [x.strip() for x in aud.split(',') if x.strip()]
            qs = qs.filter(audiences__name__in=names)

        return qs.distinct()


@extend_schema(tags=['Products'])
@extend_schema(
    methods=['PATCH'],
    tags=['Products'],
    request=PatchedProductSerializer,
    responses={200: ProductSerializer},
    examples=[
        OpenApiExample(
            name='Приклад оновлення продукту',
            summary='Оновлення ціни та кількості на складі',
            description='PATCH-запит для зміни полів price та stock',
            value={"price": 19.99, "stock": 50},
            request_only=True,
        ),
        OpenApiExample(
            name='Приклад відповіді після оновлення',
            summary='Відповідь з оновленими даними продукту',
            description='Повний об’єкт Product після успішного PATCH',
            value={
                "id": 1,
                "name": "Шахи",
                "description": "Класична стратегічна настільна гра.",
                "price": "19.99",
                "created_at": "2025-07-04T12:00:00Z",
                "updated_at": "2025-07-06T14:30:00Z",
                "categories": [1, 2],
                "brand": "Hasbro",
                "types": ["Стратегія"],
                "audiences": ["Для дорослих"],
                "images": [{"url": "https://example.com/images/chess.jpg"}],
                "discount": "10.00",
                "stock": 50,
                "stars": "4.50",
                "reviews": [{"rating": "4.50", "comment": "Кльова гра!"}]
            },
            response_only=True,
        ),
    ],
)
class ProductDetailView(GenericRetrieveUpdateDestroyView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer


@extend_schema(tags=['Game Types'])
class GameTypeListCreateView(GenericListCreateView):
    queryset = GameType.objects.all()
    serializer_class = GameTypeSerializer


@extend_schema(tags=['Game Types'])
class GameTypeRetrieveUpdateDestroyView(GenericRetrieveUpdateDestroyView):
    queryset = GameType.objects.all()
    serializer_class = GameTypeSerializer


@extend_schema(tags=['Audiences'])
class AudienceListCreateView(GenericListCreateView):
    queryset = Audience.objects.all()
    serializer_class = AudienceSerializer


@extend_schema(tags=['Audiences'])
class AudienceRetrieveUpdateDestroyView(GenericRetrieveUpdateDestroyView):
    queryset = Audience.objects.all()
    serializer_class = AudienceSerializer


@extend_schema(tags=['Brands'])
class BrandListCreateView(GenericListCreateView):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer


@extend_schema(tags=['Brands'])
class BrandRetrieveUpdateDestroyView(GenericRetrieveUpdateDestroyView):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer


@extend_schema(tags=['Photos'])
class PhotoListCreateView(GenericListCreateView):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer


@extend_schema(tags=['Photos'])
@extend_schema(
    methods=['PATCH'],
    tags=['Photos'],
    request=ProductImageSerializer,
    responses={200: ProductImageSerializer},
)
class PhotoRetrieveUpdateDestroyView(GenericRetrieveUpdateDestroyView):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer


@extend_schema(tags=['Reviews'])
class ReviewListCreateView(GenericListCreateView):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer


@extend_schema(tags=['Reviews'])
@extend_schema(
    methods=['PATCH'],
    tags=['Reviews'],
    request=PatchedReviewSerializer,
    responses={200: ReviewSerializer},
)
class ReviewRetrieveUpdateDestroyView(GenericRetrieveUpdateDestroyView):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
