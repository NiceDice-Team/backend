from django.urls import path

from src.orders.interfaces.views import OrderListViewCreateView, CreatePaymentIntentView, DeliveryOptionsView

urlpatterns = [
    path('', OrderListViewCreateView.as_view(), name='order-list-create'),
    path('create-payment-intent/', CreatePaymentIntentView.as_view(), name='create-payment-intent'),
    path('delivery-options/', DeliveryOptionsView.as_view(), name='delivery-options'),
]
