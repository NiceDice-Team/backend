import logging

from django.db import IntegrityError, transaction
from django.db.models.functions import Length, Trim

from categories.infrastructure.models import Category
from common.permissions import IsAdmin, OwnerOrAdminCanModify, ReadOnlyOrAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample, OpenApiParameter, OpenApiResponse
from products.infrastructure.models import (Product, GameType, Audience, Brand, ProductImage, Review)
from products.interfaces.pagination import ProductLimitPagination
from products.interfaces.serializers import (ProductSerializer, PatchedProductSerializer, GameTypeSerializer,
                                             AudienceSerializer, BrandSerializer, ProductImageSerializer,
                                             ReviewSerializer, ReviewWriteSerializer, PatchedReviewSerializer,
                                             ProductImageUploadSerializer, ProductImageDetailSerializer,
                                             ProductImageReorderSerializer, FeaturedReviewSerializer)
from common.exceptions import Conflict
from common.openapi import ErrorResponse409Serializer
from common.serializers import ErrorMessageSerializer
from common.validation import filter_by_int_param
from products.service import process_and_upload_product_image, delete_product_image_files
from rest_framework import generics, filters, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class GenericListCreateView(generics.ListCreateAPIView):
    permission_classes = [ReadOnlyOrAuthenticated]


class GenericRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [ReadOnlyOrAuthenticated]

    def get_object(self):
        try:
            return super().get_object()
        except self.queryset.model.DoesNotExist:
            raise NotFound()


def get_detail_placeholder_image_data(product_id):
    return {
        "id": 0,
        "product_id": product_id,
        "url_original": "https://placehold.co/1200x1200?text=No+Image",
        "url_lg": "https://placehold.co/1200x1200?text=No+Image",
        "url_md": "https://placehold.co/600x600?text=No+Image",
        "url_sm": "https://placehold.co/300x300?text=No+Image",
        "alt": "Немає зображення",
        "sort": 0
    }


PRODUCT_LIST_PARAMETERS = [
    OpenApiParameter(
        name='search',
        description='Пошук по назві та опису продукту',
        required=False,
        type=str,
        location=OpenApiParameter.QUERY
    ),
    OpenApiParameter(
        name='ordering',
        description='Сортування, наприклад "price", "-created_at"',
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
]


@extend_schema(tags=['Products'])
@extend_schema_view(
    get=extend_schema(
        tags=['Products'],
        parameters=PRODUCT_LIST_PARAMETERS,
        examples=[
            OpenApiExample(
                name='Приклад фільтрації та сортування',
                summary='GET /api/products/?search=шахи&brand=Hasbro&ordering=-price',
                value={
                    "count": 1,
                    "total_count": 1,
                    "next": None,
                    "previous": None,
                    "results": [{
                        "id": 1,
                        "name": "Шахи",
                        "description": "Класична стратегічна настільна гра.",
                        "price": "29.99",
                        "created_at": "2025-07-04T12:00:00Z",
                        "updated_at": "2025-07-05T12:00:00Z",
                        "categories": [1, 2],
                        "brand": 1,
                        "types": [1],
                        "audiences": [1],
                        "images": [{"id": 1, "product_id": 1,
                                    "url_original": "https://cdn.example.com/media/products/original/chess.jpg",
                                    "url_lg": "https://cdn.example.com/media/products/lg/chess.jpg",
                                    "url_md": "https://cdn.example.com/media/products/md/chess.jpg",
                                    "url_sm": "https://cdn.example.com/media/products/sm/chess.jpg",
                                    "alt": "Шахова дошка", "sort": 0}],
                        "discount": "10.00",
                        "stock": 100,
                        "stars": "4.50",
                        "reviews": [1]
                    }]
                },
                response_only=True,
            ),
        ],
    ),
    post=extend_schema(
        tags=['Products'],
        request=ProductSerializer,
        responses={201: ProductSerializer},
    ),
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
    ordering = ['id']

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related(
            'images',
            'categories',
            'types',
            'audiences',
            'brand',
        )
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
    methods=['GET'],
    tags=['Products'],
    responses={200: ProductSerializer},
    examples=[
        OpenApiExample(
            name='Деталі продукту з зображеннями',
            summary='GET /api/products/{id}/',
            description='Отримання інформації про продукт з наявними зображеннями.',
            value={
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
                "images": [{"url_lg": "https://cdn.bgshop.work.gd/media/products/lg/chess.jpg",
                            "url_md": "https://cdn.bgshop.work.gd/media/products/md/chess.jpg",
                            "url_sm": "https://cdn.bgshop.work.gd/media/products/sm/chess.jpg", "alt": "Шахова дошка",
                            "sort": 0}],
                "discount": "10.00",
                "stock": 100,
                "stars": "4.50",
                "reviews": [{"rating": "4.50", "comment": "Кльова гра!"}]
            },
            response_only=True,
        ),
        OpenApiExample(
            name='Деталі продукту без зображень (з плейсхолдером)',
            summary='GET /api/products/{id}/',
            description='Отримання інформації про продукт без зображень. Плейсхолдер додається автоматично.',
            value={
                "id": 2,
                "name": "Destinies",
                "description": "Destinies is a competitive, story-driven board game...",
                "price": "666.00",
                "created_at": "2025-05-19T13:50:48Z",
                "updated_at": "2025-06-19T11:31:45Z",
                "categories": [],
                "brand": 2,
                "types": [],
                "audiences": [],
                "images": [
                    {
                        "id": 0,
                        "url_lg": "https://placehold.co/600x400?text=No+Image",
                        "url_md": "https://placehold.co/600x400?text=No+Image",
                        "url_sm": "https://placehold.co/600x400?text=No+Image",
                        "alt": "Placeholder Image",
                        "sort": 0
                    }
                ],
                "discount": "160.00",
                "stock": 0,
                "stars": "7.00",
                "reviews": []
            },
            response_only=True,
        ),
    ],
)
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
                "images": [{"url_lg": "https://cdn.bgshop.work.gd/media/products/lg/chess.jpg",
                            "url_md": "https://cdn.bgshop.work.gd/media/products/md/chess.jpg",
                            "url_sm": "https://cdn.bgshop.work.gd/media/products/sm/chess.jpg", "alt": "Шахова дошка",
                            "sort": 0}],
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

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        if not data.get('images'):
            data['images'] = [get_detail_placeholder_image_data(instance.pk)]
        return Response(data)


@extend_schema(tags=['Game Types'])
class GameTypeListCreateView(GenericListCreateView):
    queryset = GameType.objects.all()
    serializer_class = GameTypeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']


@extend_schema(tags=['Game Types'])
class GameTypeRetrieveUpdateDestroyView(GenericRetrieveUpdateDestroyView):
    queryset = GameType.objects.all()
    serializer_class = GameTypeSerializer


@extend_schema(tags=['Audiences'])
class AudienceListCreateView(GenericListCreateView):
    queryset = Audience.objects.all()
    serializer_class = AudienceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']


@extend_schema(tags=['Audiences'])
class AudienceRetrieveUpdateDestroyView(GenericRetrieveUpdateDestroyView):
    queryset = Audience.objects.all()
    serializer_class = AudienceSerializer


@extend_schema(tags=['Brands'])
class BrandListCreateView(GenericListCreateView):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']


@extend_schema(tags=['Brands'])
class BrandRetrieveUpdateDestroyView(GenericRetrieveUpdateDestroyView):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer


@extend_schema(
    tags=['Photos'],
    description='Список зображень лише для читання. Для змін використовуйте /api/products/{product_id}/images/.',
)
class PhotoListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    queryset = ProductImage.objects.all().order_by('id')
    serializer_class = ProductImageSerializer


@extend_schema(
    tags=['Photos'],
    description='Зображення лише для читання. Для змін використовуйте /api/products/{product_id}/images/.',
)
class PhotoRetrieveView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    queryset = ProductImage.objects.all().order_by('id')
    serializer_class = ProductImageSerializer


@extend_schema(
    tags=['Reviews'],
    parameters=[
        OpenApiParameter(
            name='product_id',
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description='Filter reviews by product ID',
        ),
    ],
    request=ReviewSerializer,
    responses={
        200: ReviewSerializer(many=True),
        201: ReviewSerializer,
        409: ErrorResponse409Serializer,
    },
    examples=[
        OpenApiExample(
            name='Create review',
            summary='POST /api/reviews/',
            value={'product_id': 10, 'rating': 5, 'comment': 'Nice!'},
            request_only=True,
        ),
        OpenApiExample(
            name='Review response',
            summary='201 Created',
            value={
                'id': 1,
                'product_id': 10,
                'user_id': 3,
                'user_name': 'Daniel T.',
                'rating': 5,
                'comment': 'Nice!',
                'created_at': '2025-07-10T12:00:00Z',
            },
            response_only=True,
        ),
    ],
)
class ReviewListCreateView(GenericListCreateView):
    serializer_class = ReviewSerializer
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Review.objects.select_related('user').order_by('-created_at', '-id')
        return filter_by_int_param(queryset, 'product_id', self.request.query_params.get('product_id'), 'product_id')

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(user=self.request.user)
        except IntegrityError:
            raise Conflict('Review for this product by current user already exists.')


FEATURED_REVIEWS_COUNT = 4
FEATURED_REVIEWS_POOL_SIZE = 50
FEATURED_REVIEW_MIN_RATING = 4
FEATURED_REVIEW_MIN_COMMENT_LENGTH = 30


@extend_schema(
    tags=['Reviews'],
    summary='Відгуки для головної сторінки',
    description=(
        f"Повертає до {FEATURED_REVIEWS_COUNT} випадкових відгуків для блоку відгуків на головній сторінці. "
        f"У вибірку потрапляють відгуки з оцінкою від {FEATURED_REVIEW_MIN_RATING}, "
        f"текстом від {FEATURED_REVIEW_MIN_COMMENT_LENGTH} символів і автором, у якого вказано ім'я. "
        "З однієї гри береться не більше 1 відгуку. "
        "Токен не потрібен. Якщо підходящих відгуків немає, повертається порожній список. "
        "Для посилання на гру використовуйте product_id, для імені автора - user_name."
    ),
    responses={200: FeaturedReviewSerializer(many=True)},
    examples=[
        OpenApiExample(
            name='Відгуки для головної сторінки',
            summary='GET /api/reviews/featured/',
            value={
                'id': 56,
                'product_id': 7,
                'product_name': 'Catan',
                'user_name': 'Daniel T.',
                'rating': 5,
                'comment': 'Catan is a fun and engaging board game that combines strategy, trading, '
                           'and friendly competition.',
                'created_at': '2026-10-25T16:14:00Z',
            },
            response_only=True,
        ),
    ],
)
class FeaturedReviewListView(generics.ListAPIView):
    serializer_class = FeaturedReviewSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    filter_backends = []

    def get_queryset(self):
        return (
            Review.objects
            .filter(rating__gte=FEATURED_REVIEW_MIN_RATING, user__isnull=False)
            .exclude(user__first_name='')
            .annotate(comment_length=Length(Trim('comment')))
            .filter(comment_length__gte=FEATURED_REVIEW_MIN_COMMENT_LENGTH)
            .select_related('user', 'product')
            .order_by('?')
        )

    def list(self, request, *args, **kwargs):
        selected = []
        seen_products = set()
        for review in self.get_queryset()[:FEATURED_REVIEWS_POOL_SIZE]:
            if review.product_id in seen_products:
                continue
            seen_products.add(review.product_id)
            selected.append(review)
            if len(selected) == FEATURED_REVIEWS_COUNT:
                break
        return Response(self.get_serializer(selected, many=True).data)


@extend_schema(tags=['Reviews'])
@extend_schema(methods=['GET'], responses={200: ReviewSerializer})
@extend_schema(methods=['PUT'], request=ReviewWriteSerializer, responses={200: ReviewSerializer})
@extend_schema(methods=['PATCH'], request=PatchedReviewSerializer, responses={200: ReviewSerializer})
@extend_schema(methods=['DELETE'], responses={204: None})
class ReviewRetrieveUpdateDestroyView(GenericRetrieveUpdateDestroyView):
    permission_classes = [OwnerOrAdminCanModify]
    queryset = Review.objects.all()
    serializer_class = ReviewWriteSerializer


PLACEHOLDER_IMAGE_URL = "https://placehold.co/600x400?text=No+Image"


def get_placeholder_image_data():
    return {
        "id": 0,
        "url_lg": PLACEHOLDER_IMAGE_URL,
        "url_md": PLACEHOLDER_IMAGE_URL,
        "url_sm": PLACEHOLDER_IMAGE_URL,
        "alt": "Placeholder Image",
        "sort": 0
    }


@extend_schema(tags=['Products Images'])
class ProductImageUploadView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        operation_id='upload_product_image',
        description="Завантажити нове зображення для продукту",
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'image': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Файл зображення'
                    },
                    'alt': {
                        'type': 'string',
                        'description': 'Альтернативний текст для зображення'
                    }
                },
                'required': ['image']
            }
        },
        responses={
            201: ProductImageDetailSerializer,
            400: OpenApiResponse(description='Помилка валідації'),
            404: OpenApiResponse(description='Продукт не знайдено'),
        }
    )
    def post(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            logger.warning(f"Product with id {product_id} not found for image upload.")
            return Response({'error': 'Продукт не знайдено.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductImageUploadSerializer(data=request.data)
        if not serializer.is_valid():
            logger.info(f"Invalid data for ProductImageUploadSerializer: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        image_file = serializer.validated_data['image']
        alt_text = serializer.validated_data.get('alt', '').strip()

        try:
            product_image = process_and_upload_product_image(product, image_file, alt_text)
        except Exception as e:
            logger.error(f"Error processing image for product {product_id}: {e}")
            return Response(
                {'error': f'Не вдалося обробити зображення: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        response_serializer = ProductImageDetailSerializer(product_image)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Products Images'])
class ProductImageDeleteView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        operation_id='delete_product_image',
        description="Видалити зображення продукту",
        responses={
            204: OpenApiResponse(description='Зображення успішно видалено'),
            404: OpenApiResponse(description='Продукт або зображення не знайдено'),
        }
    )
    def delete(self, request, product_id, image_id):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            logger.warning(f"Product with id {product_id} not found for image deletion.")
            raise NotFound("Продукт не знайдено.")

        try:
            image = ProductImage.objects.get(pk=image_id, product=product)
        except ProductImage.DoesNotExist:
            logger.warning(f"ProductImage with id {image_id} not found for product {product_id}.")
            raise NotFound("Зображення не знайдено.")

        try:
            delete_product_image_files(image)
        except Exception as e:
            logger.error(f"Error deleting files for ProductImage {image_id}: {e}")

        image.delete()
        logger.info(f"ProductImage {image_id} deleted successfully.")
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=['Products Images'])
class ProductImageReorderView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        operation_id='reorder_product_images',
        description="Змінити порядок зображень продукту",
        request=ProductImageReorderSerializer,
        responses={
            200: OpenApiResponse(description='Порядок успішно змінено'),
            400: OpenApiResponse(description='Помилка валідації'),
            404: OpenApiResponse(description='Продукт не знайдено'),
        }
    )
    def patch(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            logger.warning(f"Product with id {product_id} not found for image reordering.")
            raise NotFound("Продукт не знайдено.")

        serializer = ProductImageReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_updates = serializer.validated_data['images']
        new_sort_values = {item['id']: item['sort'] for item in image_updates}

        with transaction.atomic():
            images = {
                image.pk: image
                for image in ProductImage.objects.select_for_update().filter(
                    product=product, pk__in=list(new_sort_values)
                )
            }
            for item in image_updates:
                if item['id'] not in images:
                    logger.warning(
                        f"ProductImage {item['id']} does not belong to product {product_id} during reorder."
                    )
                    raise ValidationError(f"Зображення з ID {item['id']} не належить цьому продукту.")

            for image_id, image in images.items():
                image.sort = new_sort_values[image_id]
                image.save(update_fields=['sort'])

        logger.info(f"Successfully reordered images for product {product_id}.")
        return Response({'message': 'Порядок зображень успішно оновлено.'}, status=status.HTTP_200_OK)


class ProductCountView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='api_product_count_get',
        tags=['Products'],
        description="Повертає кількість товарів. Без параметрів - загальна кількість. З category_id - кількість у певній категорії.",
        parameters=[
            OpenApiParameter(
                name='category_id',
                type={'type': 'integer', 'minimum': 1},
                location=OpenApiParameter.QUERY,
                required=False,
                description='ID категорії для фільтрації'
            ),
        ],
        responses={
            200: {'type': 'object', 'properties': {'count': {'type': 'integer'}}, 'required': ['count']},
            400: OpenApiResponse(response=ErrorMessageSerializer, description='Невалідний category_id'),
            404: OpenApiResponse(response=ErrorMessageSerializer, description='Категорію не знайдено'),
        },
    )
    def get(self, request):
        category_id_str = request.query_params.get('category_id', None)

        if category_id_str is not None:
            try:
                category_id = int(category_id_str)
            except (ValueError, TypeError):
                return Response({'error': 'category_id must be an integer'}, status=400)

            if category_id <= 0:
                return Response({'error': 'category_id must be a positive integer'}, status=400)

            if not Category.objects.filter(id=category_id).exists():
                return Response({'error': 'Category not found'}, status=404)

            queryset = Product.objects.filter(categories__id=category_id)
        else:
            queryset = Product.objects.all()

        count = queryset.count()
        return Response({'count': count})
