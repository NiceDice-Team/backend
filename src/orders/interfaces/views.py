from rest_framework import generics
from orders.infrastructure.models import Order
from orders.interfaces.serializers import OrderSerializer
from drf_spectacular.utils import extend_schema, OpenApiExample


@extend_schema(tags=['orders'])
class OrderCreateView(generics.CreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    @extend_schema(
        tags=['Orders'],
        request=OrderSerializer,
        responses={201: OrderSerializer},
        examples=[
            OpenApiExample(
                name='Створити замовлення',
                summary='POST /api/orders/',
                value={'products': [1, 2, 3]},
                request_only=True
            ),
            OpenApiExample(
                name='Відповідь сервера',
                summary='201 Created',
                value={'id': 1, 'products': [1, 2, 3], 'created_at': '2025-07-05T11:00:00Z'},
                response_only=True
            )
        ]
    )
    def post(self, *args, **kwargs):
        return super().post(*args, **kwargs)
