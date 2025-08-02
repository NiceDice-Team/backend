from rest_framework.routers import DefaultRouter
from cart.interfaces.views import CartItemViewSet

router = DefaultRouter()
router.register(r'', CartItemViewSet, basename='cart')

urlpatterns = router.urls
