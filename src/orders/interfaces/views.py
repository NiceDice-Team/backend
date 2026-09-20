import logging
import stripe

from cart.infrastructure.models import CartItem
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse, OpenApiParameter
from orders.infrastructure.models import Order
from orders.interfaces.serializers import OrderSerializer, OrderListSerializer
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)
User = get_user_model()


@extend_schema(tags=['Orders'])
class OrderListViewCreateView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Отримати історію замовлень",
        description="Повертає список замовлень для користувача з вказаним ID.",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=int,
                location=OpenApiParameter.QUERY,
                description='ID користувача',
                required=True
            )
        ],
        responses={
            200: OrderListSerializer(many=True),
            400: OpenApiResponse(description='Відсутній або некоректний параметр user_id'),
        },
    )
    def get(self, request, *args, **kwargs):
        user_id = request.query_params.get('user_id', None)
        if user_id is None:
            return Response(
                {"detail": "Параметр 'user_id' є обов'язковим."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            user_id = int(user_id)
        except ValueError:
            return Response(
                {"detail": "Параметр 'user_id' має бути цілим числом."},
                status=status.HTTP_400_BAD_REQUEST
            )

        orders = Order.objects.filter(user_id=user_id).order_by('-created_at')
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Створити замовлення",
        description="Створює нове замовлення для користувача на основі ID користувача та його кошика.",
        request=OrderSerializer,
        responses={
            201: OrderSerializer,
            400: OpenApiResponse(description='Помилка в запиті'),
        },
        examples=[
            OpenApiExample(
                name='Створити замовлення',
                summary='POST /api/orders/',
                value={'user_id': 1},
                request_only=True
            ),
            OpenApiExample(
                name='Відповідь сервера',
                summary='201 Created',
                value={'id': 1, 'user': 1, 'products': [1, 2, 3], 'total_amount': '65.49',
                       'created_at': '2025-07-05T11:00:00Z', 'updated_at': '2025-07-05T11:00:00Z', 'status': 'pending'},
                response_only=True
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({"detail": "Поле 'user_id' є обов'язковим в тілі запиту."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            user_id = int(user_id)
        except ValueError:
            return Response({"detail": "Параметр 'user_id' має бути цілим числом."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": f"Користувач з ID {user_id} не знайдений."}, status=status.HTTP_400_BAD_REQUEST)

        carts = CartItem.objects.filter(user=user)
        if not carts.exists():
            return Response({"detail": "Кошик користувача порожній."}, status=status.HTTP_400_BAD_REQUEST)

        products = [cart.product for cart in carts]
        total_amount = sum(cart.product.price * cart.quantity for cart in carts)

        order = Order.objects.create(user=user, total_amount=total_amount)
        order.products.set(products)

        carts.delete()

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CreatePaymentIntentView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            amount = request.data.get('amount')
            if not amount:
                return Response({'error': 'Необхідно вказати суму'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                amount = int(amount)
            except (ValueError, TypeError):
                return Response({'error': 'Сума повинна бути цілим числом в копійках'}, status=status.HTTP_400_BAD_REQUEST)

            if amount <= 0:
                return Response({'error': 'Сума повинна бути більшою за нуль'}, status=status.HTTP_400_BAD_REQUEST)

            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency='uah',
            )
            logger.info(f"PaymentIntent створено: {intent.id}")
            return Response({
                'clientSecret': intent['client_secret']
            })

        except stripe.error.StripeError as e:
            logger.error(f"Помилка API Stripe: {e.user_message}")
            return Response({'error': e.user_message}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Непередбачена помилка при створенні PaymentIntent: {e}")
            return Response({'error': 'Сталася непередбачена помилка.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
