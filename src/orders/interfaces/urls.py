from django.urls import path

from orders.interfaces.views import (OrderListViewCreateView, CreatePaymentIntentView, DeliveryOptionListView,
                                     CheckoutStartView, OrderStatusUpdateView, OrderHistoryView, OrderCancelView)
from . import views
from .views import AnonymOrderListView

urlpatterns = [
    path('', OrderListViewCreateView.as_view(), name='order-list-create'),
    path('create-payment-intent/', CreatePaymentIntentView.as_view(), name='create-payment-intent'),
    path('delivery-options/', DeliveryOptionListView.as_view(), name='delivery-options'),
    path('payment-methods/', views.PaymentMethodListView.as_view(), name='payment-methods'),
    path('start/', CheckoutStartView.as_view(), name='checkout-start'),
    path('anonim/', AnonymOrderListView.as_view(), name='order-anonim-list'),
    path('<id:orderId>/status/', OrderStatusUpdateView.as_view(), name='order-status-update'),
    path('<id:orderId>/history/', OrderHistoryView.as_view(), name='order-history'),
    path("<id:orderId>/cancel/", OrderCancelView.as_view(), name="order-cancel"),
]
