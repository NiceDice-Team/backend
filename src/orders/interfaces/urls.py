from django.urls import path

from src.orders.interfaces.views import OrderListViewCreateView, CreatePaymentIntentView

urlpatterns = [
    path('', OrderListViewCreateView.as_view(), name='order-list-create'),
    path('create-payment-intent/', CreatePaymentIntentView.as_view(), name='create-payment-intent'),
]
