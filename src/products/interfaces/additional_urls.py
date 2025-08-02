from django.urls import path
from products.interfaces.views import (
    GameTypeListCreateView, GameTypeRetrieveUpdateDestroyView,
    AudienceListCreateView, AudienceRetrieveUpdateDestroyView,
    BrandListCreateView, BrandRetrieveUpdateDestroyView,
    PhotoListCreateView, PhotoRetrieveUpdateDestroyView,
    ReviewListCreateView, ReviewRetrieveUpdateDestroyView,
)

urlpatterns = [
    path('game-types/', GameTypeListCreateView.as_view(), name='game-type-list'),
    path('game-types/<int:pk>/', GameTypeRetrieveUpdateDestroyView.as_view(), name='game-type-detail'),

    path('audiences/', AudienceListCreateView.as_view(), name='audience-list'),
    path('audiences/<int:pk>/', AudienceRetrieveUpdateDestroyView.as_view(), name='audience-detail'),

    path('brands/', BrandListCreateView.as_view(), name='brand-list'),
    path('brands/<int:pk>/', BrandRetrieveUpdateDestroyView.as_view(), name='brand-detail'),

    path('photos/', PhotoListCreateView.as_view(), name='photo-list'),
    path('photos/<int:pk>/', PhotoRetrieveUpdateDestroyView.as_view(), name='photo-detail'),

    path('reviews/', ReviewListCreateView.as_view(), name='review-list'),
    path('reviews/<int:pk>/', ReviewRetrieveUpdateDestroyView.as_view(), name='review-detail'),
]
