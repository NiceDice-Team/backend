from django.urls import path
from products.interfaces.views import (ProductListView, ProductDetailView, ProductImageUploadView,
                                       ProductImageDeleteView, ProductImageReorderView, ProductCountView)

from products.interfaces.review_views import ProductReviewDetailView, ProductReviewListView

urlpatterns = [
    path('', ProductListView.as_view(), name='product-list'),
    path('<id:pk>/', ProductDetailView.as_view(), name='product-detail'),
    path('<id:product_id>/images/', ProductImageUploadView.as_view(), name='product-image-upload'),
    path('<id:product_id>/images/<id:image_id>/', ProductImageDeleteView.as_view(), name='product-image-delete'),
    path('<id:product_id>/images/order/', ProductImageReorderView.as_view(), name='product-image-reorder'),
    path('count/', ProductCountView.as_view(), name='product-count'),
    path('products/<id:product_id>/reviews/', ProductReviewListView.as_view(), name='product-reviews-list'),
    path('products/<id:product_id>/reviews/<id:review_id>/', ProductReviewDetailView.as_view(), name='product-review-detail'),
]
