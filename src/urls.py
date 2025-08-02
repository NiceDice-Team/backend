from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from drf_spectacular.renderers import OpenApiJsonRenderer

from src.views import api_root

urlpatterns = [
    path('', api_root, name='api-root'),
    path('admin/', admin.site.urls),

    path('api/products/', include('products.interfaces.urls')),
    path('api/orders/', include('orders.interfaces.urls')),
    path('api/categories/', include('categories.interfaces.urls')),
    path('api/users/', include('users.interfaces.urls')),
    path('api/carts/', include('cart.interfaces.urls')),
    path('api/', include('products.interfaces.additional_urls')),

    path(
        'api/schema/',
        SpectacularAPIView.as_view(renderer_classes=[OpenApiJsonRenderer]),
        name='schema'
    ),
    path('api/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
