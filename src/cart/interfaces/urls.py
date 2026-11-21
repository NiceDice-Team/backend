from django.urls import path

from .views import CartViewSet, GuestCartViewSet, GuestCartListView, GuestCheckoutStartView

urlpatterns = [
    # --- Authenticated Cart ---
    path('', CartViewSet.as_view({'get': 'list'}), name='cart-list-add'),
    path('item/', CartViewSet.as_view({'post': 'add_item', 'patch': 'update_item', 'delete': 'remove_item'}), name='cart-item'),
    path('clear/', CartViewSet.as_view({'delete': 'clear'}), name='cart-clear'),

    # --- Guest Cart ---
    path('guest/', GuestCartViewSet.as_view({'get': 'retrieve', 'post': 'create', 'delete': 'delete_guest_cart'}), name='guest-cart'),
    path('guest/item/', GuestCartViewSet.as_view({'post': 'add_item', 'patch': 'update_item', 'delete': 'remove_item'}), name='guest-cart-item'),
    path('guest/clear/', GuestCartViewSet.as_view({'delete': 'clear'}), name='guest-cart-clear'),
    path('guest/checkout/start/', GuestCheckoutStartView.as_view(), name='guest-checkout-start'),
    path('guest/all/', GuestCartListView.as_view(), name='guest-cart-list-all'),
]
