from django.urls import path
from products.interfaces.views import (ProductListView, ProductDetailView, ProductImageUploadView,
                                       ProductImageDeleteView, ProductImageReorderView)

urlpatterns = [
    path('', ProductListView.as_view(), name='product-list'),
    path('<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
    path('<int:product_id>/images/', ProductImageUploadView.as_view(), name='product-image-upload'),
    path('<int:product_id>/images/<int:image_id>/', ProductImageDeleteView.as_view(), name='product-image-delete'),
    path('<int:product_id>/images/order/', ProductImageReorderView.as_view(), name='product-image-reorder'),
]
