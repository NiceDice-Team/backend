import logging

from common.permissions import ReadOnlyOrAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter, OpenApiResponse
from products.infrastructure.models import (Product, GameType, Audience, Brand, ProductImage, Review)
from products.interfaces.pagination import ProductLimitPagination
from products.interfaces.serializers import (ProductSerializer, PatchedProductSerializer, GameTypeSerializer,
                                             AudienceSerializer, BrandSerializer, ProductImageSerializer,
                                             ReviewSerializer, PatchedReviewSerializer,
                                             ProductImageUploadSerializer, ProductImageDetailSerializer,
                                             ProductImageReorderSerializer)
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


@extend_schema(tags=['Products'])
@extend_schema(
    responses={200: ProductSerializer(many=True)},
    tags=['Products'],
    parameters=[
        OpenApiParameter(
            name='search',
            description='Search by product name and description',
            required=False,
            type=str,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='ordering',
            description='Sorting, for example `price`, `-created_at`',
            required=False,
            type=str,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='brand',
            description='Filter by brand name',
            required=False,
            type=str,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='categories',
            description='Filter by category IDs (comma-separated)',
            required=False,
            type=str,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='types',
            description='Filter by game type names (comma-separated)',
            required=False,
            type=str,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='audiences',
            description='Filter by audience names (comma-separated)',
            required=False,
            type=str,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='limit',
            description='Number of products per page (maximum 100)',
            required=False,
            type=int,
            location=OpenApiParameter.QUERY
        ),
        OpenApiParameter(
            name='offset',
            description='Pagination offset',
            required=False,
            type=int,
            location=OpenApiParameter.QUERY
        ),
    ],
    examples=[
        OpenApiExample(
            name='Filtering and sorting example',
            summary='GET /api/products/?search=chess&brand=Hasbro&ordering=-price',
            value=[{
                "id": 1,
                "name": "Chess",
                "description": "A classic strategy board game.",
                "price": "29.99",
                "created_at": "2025-07-04T12:00:00Z",
                "updated_at": "2025-07-05T12:00:00Z",
                "categories": [1, 2],
                "brand": "Hasbro",
                "types": ["Strategy"],
                "audiences": ["Adults"],
                "images": [{"url_lg": "https://cdn.example.com/media/products/lg/chess.jpg    ",
                            "url_md": "https://cdn.example.com/media/products/md/chess.jpg    ",
                            "url_sm": "https://cdn.example.com/media/products/sm/chess.jpg    ", "alt": "Chess board",
                            "sort": 0}],
                "discount": "10.00",
                "stock": 100,
                "stars": "4.50",
                "reviews": [{"rating": "4.50", "comment": "Great game!"}]
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
    ordering = ['id']

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

    def list(self, request, *args, **kwargs):
        limit_param = request.query_params.get('limit')
        if limit_param is not None:
            try:
                limit_value = int(limit_param)
                if limit_value <= 0:
                    raise ValidationError("Limit must be a positive integer.")
                if limit_value > 100:
                    request.query_params = request.query_params.copy()
                    request.query_params['limit'] = '100'
            except ValueError:
                raise ValidationError("Limit must be an integer.")
        return super().list(request, *args, **kwargs)


@extend_schema(tags=['Products'])
@extend_schema(
    methods=['GET'],
    tags=['Products'],
    responses={200: ProductSerializer},
    examples=[
        OpenApiExample(
            name='Product details with images',
            summary='GET /api/products/{id}/',
            description='Retrieve information about a product with existing images.',
            value={
                "id": 1,
                "name": "Chess",
                "description": "A classic strategy board game.",
                "price": "29.99",
                "created_at": "2025-07-04T12:00:00Z",
                "updated_at": "2025-07-05T12:00:00Z",
                "categories": [1, 2],
                "brand": "Hasbro",
                "types": ["Strategy"],
                "audiences": ["Adults"],
                "images": [{"url_lg": "https://cdn.bgshop.work.gd/media/products/lg/chess.jpg",
                            "url_md": "https://cdn.bgshop.work.gd/media/products/md/chess.jpg",
                            "url_sm": "https://cdn.bgshop.work.gd/media/products/sm/chess.jpg", "alt": "Chess board",
                            "sort": 0}],
                "discount": "10.00",
                "stock": 100,
                "stars": "4.50",
                "reviews": [{"rating": "4.50", "comment": "Great game!"}]
            },
            response_only=True,
        ),
        OpenApiExample(
            name='Product details without images (with placeholder)',
            summary='GET /api/products/{id}/',
            description='Retrieve information about a product without images. A placeholder is added automatically.',
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
            name='Product update example',
            summary='Update price and stock quantity',
            description='PATCH request to modify the price and stock fields',
            value={"price": 19.99, "stock": 50},
            request_only=True,
        ),
        OpenApiExample(
            name='Example response after update',
            summary='Response with updated product data',
            description='Full Product object after a successful PATCH',
            value={
                "id": 1,
                "name": "Chess",
                "description": "A classic strategy board game.",
                "price": "19.99",
                "created_at": "2025-07-04T12:00:00Z",
                "updated_at": "2025-07-06T14:30:00Z",
                "categories": [1, 2],
                "brand": "Hasbro",
                "types": ["Strategy"],
                "audiences": ["Adults"],
                "images": [{"url_lg": "https://cdn.bgshop.work.gd/media/products/lg/chess.jpg",
                            "url_md": "https://cdn.bgshop.work.gd/media/products/md/chess.jpg",
                            "url_sm": "https://cdn.bgshop.work.gd/media/products/sm/chess.jpg", "alt": "Chess board",
                            "sort": 0}],
                "discount": "10.00",
                "stock": 50,
                "stars": "4.50",
                "reviews": [{"rating": "4.50", "comment": "Great game!"}]
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
            placeholder_data = {
                "id": 0,
                "url_original": "https://placehold.co/1200x1200?text=No+Image",
                "url_lg": "https://placehold.co/1200x1200?text=No+Image",
                "url_md": "https://placehold.co/600x600?text=No+Image",
                "url_sm": "https://placehold.co/300x300?text=No+Image",
                "alt": "No image available",
                "sort": 0
            }
            data['images'] = [placeholder_data]
        return Response(data)


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
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='upload_product_image',
        description="Upload a new image for a product",
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'image': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Image file'
                    },
                    'alt': {
                        'type': 'string',
                        'description': 'Alternative text for the image'
                    }
                },
                'required': ['image']
            }
        },
        responses={
            201: ProductImageDetailSerializer,
            400: OpenApiResponse(description='Validation error'),
            404: OpenApiResponse(description='Product not found'),
        }
    )
    def post(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            logger.warning(f"Product with id {product_id} not found for image upload.")
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

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
                {'error': f'Failed to process image: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        response_serializer = ProductImageDetailSerializer(product_image)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Products Images'])
class ProductImageDeleteView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='delete_product_image',
        description="Delete a product image",
        responses={
            204: OpenApiResponse(description='Image deleted successfully'),
            404: OpenApiResponse(description='Product or image not found'),
        }
    )
    def delete(self, request, product_id, image_id):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            logger.warning(f"Product with id {product_id} not found for image deletion.")
            raise NotFound("Product not found.")

        try:
            image = ProductImage.objects.get(pk=image_id, product=product)
        except ProductImage.DoesNotExist:
            logger.warning(f"ProductImage with id {image_id} not found for product {product_id}.")
            raise NotFound("Image not found.")

        try:
            delete_product_image_files(image)
        except Exception as e:
            logger.error(f"Error deleting files for ProductImage {image_id}: {e}")

        image.delete()
        logger.info(f"ProductImage {image_id} deleted successfully.")
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=['Products Images'])
class ProductImageReorderView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id='reorder_product_images',
        description="Change the order of product images",
        request=ProductImageReorderSerializer,
        responses={
            200: OpenApiResponse(description='Order updated successfully'),
            400: OpenApiResponse(description='Validation error'),
            404: OpenApiResponse(description='Product not found'),
        }
    )
    def patch(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            logger.warning(f"Product with id {product_id} not found for image reordering.")
            raise NotFound("Product not found.")

        serializer = ProductImageReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image_updates = serializer.validated_data['images']

        for item in image_updates:
            image_id = item['id']
            new_sort_value = item['sort']
            try:
                image = ProductImage.objects.get(pk=image_id, product=product)
                image.sort = new_sort_value
                image.save(update_fields=['sort'])
                logger.debug(f"Updated sort order for ProductImage {image_id} to {new_sort_value}.")
            except ProductImage.DoesNotExist:
                logger.warning(f"ProductImage {image_id} does not belong to product {product_id} during reorder.")
                raise ValidationError(f"Image with ID {image_id} does not belong to this product.")

        logger.info(f"Successfully reordered images for product {product_id}.")
        return Response({'message': 'Image order updated successfully.'}, status=status.HTTP_200_OK)
