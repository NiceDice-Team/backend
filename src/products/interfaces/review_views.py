from django.db import IntegrityError, transaction
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.exceptions import NotFound

from common.converters import ID_PATH_SCHEMA
from common.exceptions import Conflict
from common.openapi import ErrorResponse409Serializer
from common.permissions import OwnerOrAdminCanModify, ReadOnlyOrAuthenticated

from .serializers import PatchedReviewSerializer, ReviewSerializer, ReviewWriteSerializer
from ..infrastructure.models import Product, Review

PRODUCT_ID_PATH = OpenApiParameter(
    name='product_id', type=ID_PATH_SCHEMA, location=OpenApiParameter.PATH, description='ID продукту'
)
REVIEW_ID_PATH = OpenApiParameter(
    name='review_id', type=ID_PATH_SCHEMA, location=OpenApiParameter.PATH, description='ID відгуку'
)


@extend_schema(
    tags=['Reviews'],
    parameters=[PRODUCT_ID_PATH],
)
@extend_schema(methods=['GET'], responses={200: ReviewSerializer(many=True)})
@extend_schema(
    methods=['POST'],
    request=ReviewWriteSerializer,
    responses={
        201: ReviewSerializer,
        409: ErrorResponse409Serializer,
    },
)
class ProductReviewListView(generics.ListCreateAPIView):
    serializer_class = ReviewWriteSerializer
    permission_classes = [ReadOnlyOrAuthenticated]

    def get_product(self):
        try:
            return Product.objects.get(pk=self.kwargs.get('product_id'))
        except Product.DoesNotExist:
            raise NotFound('Продукт не знайдено.')

    def get_queryset(self):
        return Review.objects.filter(product_id=self.kwargs.get('product_id')).select_related('user').order_by(
            '-created_at', '-id'
        )

    def list(self, request, *args, **kwargs):
        self.get_product()
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        product = self.get_product()
        try:
            with transaction.atomic():
                serializer.save(user=self.request.user, product=product)
        except IntegrityError:
            raise Conflict('Відгук цього користувача на цей продукт уже існує.')


@extend_schema(
    tags=['Reviews'],
    parameters=[PRODUCT_ID_PATH, REVIEW_ID_PATH],
)
@extend_schema(methods=['GET'], responses={200: ReviewSerializer})
@extend_schema(methods=['PUT'], request=ReviewWriteSerializer, responses={200: ReviewSerializer})
@extend_schema(methods=['PATCH'], request=PatchedReviewSerializer, responses={200: ReviewSerializer})
@extend_schema(methods=['DELETE'], responses={204: None})
class ProductReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ReviewWriteSerializer
    permission_classes = [OwnerOrAdminCanModify]

    def get_queryset(self):
        return Review.objects.filter(
            product_id=self.kwargs.get('product_id'), id=self.kwargs.get('review_id')
        ).select_related('user')

    def get_object(self):
        obj = generics.get_object_or_404(self.get_queryset())
        self.check_object_permissions(self.request, obj)
        return obj
