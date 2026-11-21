from django.urls import path
from products.interfaces.views import (
    GameTypeListCreateView, GameTypeRetrieveUpdateDestroyView,
    AudienceListCreateView, AudienceRetrieveUpdateDestroyView,
    BrandListCreateView, BrandRetrieveUpdateDestroyView,
    PhotoListView, PhotoRetrieveView,
    ReviewListCreateView, ReviewRetrieveUpdateDestroyView, FeaturedReviewListView,
)

urlpatterns = [
    path('game-types/', GameTypeListCreateView.as_view(), name='game-type-list'),
    path('game-types/<id:pk>/', GameTypeRetrieveUpdateDestroyView.as_view(), name='game-type-detail'),

    path('audiences/', AudienceListCreateView.as_view(), name='audience-list'),
    path('audiences/<id:pk>/', AudienceRetrieveUpdateDestroyView.as_view(), name='audience-detail'),

    path('brands/', BrandListCreateView.as_view(), name='brand-list'),
    path('brands/<id:pk>/', BrandRetrieveUpdateDestroyView.as_view(), name='brand-detail'),

    path('photos/', PhotoListView.as_view(), name='photo-list'),
    path('photos/<id:pk>/', PhotoRetrieveView.as_view(), name='photo-detail'),

    path('reviews/', ReviewListCreateView.as_view(), name='review-list'),
    path('reviews/featured/', FeaturedReviewListView.as_view(), name='review-featured'),
    path('reviews/<id:pk>/', ReviewRetrieveUpdateDestroyView.as_view(), name='review-detail'),
]
