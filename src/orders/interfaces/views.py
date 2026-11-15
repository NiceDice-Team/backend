import logging
import uuid
from urllib.parse import urlencode

import stripe
from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.serializers import ValidationError, as_serializer_error

from cart.infrastructure.models import GuestCart
from cart.infrastructure.models import GuestCheckoutSession, Cart
from cart.interfaces.serializers import CartSerializer, GuestCartSerializer
from common.serializers import CodedErrorSerializer, ErrorMessageSerializer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter, OpenApiResponse
from orders.cancellation import CANCELLATION_WINDOW_HOURS, OrderCancellationError, cancel_order_by_token
from orders.infrastructure.models import DeliveryOption, Order, PaymentMethod, OrderStatusLog
from orders.interfaces.permissions import GUEST_TOKEN_HEADER, IsAuthenticatedOrHasGuestCart
from orders.interfaces.serializers import (CheckoutStartResponseSerializer, CheckoutStartSerializer,
                                           DeliveryOptionSerializer, OrderCreateSerializer, OrderListSerializer,
                                           PaymentIntentCreateSerializer, PaymentIntentResponseSerializer,
                                           PaymentMethodSerializer, OrderStatusLogSerializer,
                                           OrderStatusUpdateSerializer)
from rest_framework import status, generics
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)
User = get_user_model()


@extend_schema(tags=['Orders'])
class OrderListViewCreateView(APIView):
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [AllowAny()]

    @extend_schema(
        operation_id='orders_list',
        summary="Отримати історію замовлень",
        description="Повертає список замовлень для поточного користувача.",
        responses={
            200: OrderListSerializer(many=True),
            401: OpenApiResponse(description='Необхідна авторизація'),
        },
        examples=[
            OpenApiExample(
                name='Успішна відповідь',
                value=[{
                    'id': 1,
                    'user': 7,
                    'shipping_address': '221B Baker Street, London',
                    'billing_address': '221B Baker Street, London',
                    'status': 'pending',
                    'subtotal': '59.99',
                    'shipping_cost': '15.00',
                    'total_amount': '74.99',
                    'items': [{'id': 1, 'quantity': 2, 'price': '29.99', 'subtotal': '59.98'}],
                }],
                response_only=True,
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        orders = (Order.objects.filter(user=request.user)
                  .select_related('delivery_option', 'payment_method')
                  .prefetch_related('items')
                  .order_by('-created_at'))
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id='orders_create',
        summary="Створити замовлення",
        description="Створює нове замовлення на основі кошика. Для гостей - guest_cart_token, для авторизованих - "
                    "cart_id разом із Bearer-токеном, кошик має належати власнику токена. Запит без токена "
                    "авторизації і без guest_cart_token відхиляється зі статусом 401. Оформлення атомарне - "
                    "кошик блокується, повторно перевіряється і споживається разом зі створенням замовлення. "
                    "Після створення замовлення покупцеві надсилається лист-підтвердження. Для гостя він іде на "
                    "email із поля email, а якщо його немає - на email із checkout-сесії або з адреси доставки "
                    "чи оплати. Для авторизованого користувача він іде на email акаунта.",
        request=OrderCreateSerializer,
        responses={
            201: OrderListSerializer,
            400: OpenApiResponse(response=CodedErrorSerializer,
                                 description='Помилка валідації або логіки. Для помилок полів тіло - словник '
                                             '"поле - список повідомлень".'),
        },
        examples=[
            OpenApiExample(
                name='Замовлення для авторизованого користувача',
                value={
                    'cart_id': 12,
                    'delivery_option_id': 1,
                    'payment_method_id': 1,
                    'shipping_address': '221B Baker Street, London',
                },
                request_only=True,
            ),
            OpenApiExample(
                name='Замовлення для гостя',
                value={
                    'guest_cart_token': 'guest-cart-token',
                    'delivery_option_id': 1,
                    'shipping_address': '221B Baker Street, London',
                    'email': 'guest@example.com',
                    'phone': '+380501112233',
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated and not request.data.get('guest_cart_token'):
            raise NotAuthenticated()
        serializer = OrderCreateSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            order = serializer.save()
        except ValidationError as error:
            return Response(as_serializer_error(error), status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderListSerializer(order, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)


def first_error_message(errors):
    for messages in errors.values():
        if isinstance(messages, (list, tuple)) and messages:
            return str(messages[0])
        return str(messages)
    return 'Невалідний запит.'


@extend_schema(tags=['Orders'])
class CreatePaymentIntentView(APIView):
    permission_classes = [IsAuthenticatedOrHasGuestCart]

    @extend_schema(
        operation_id='orders_create_payment_intent',
        summary='Створити PaymentIntent',
        description='Створює Stripe PaymentIntent на суму в центах USD. Доступно авторизованим користувачам '
                    '(Bearer-токен) і гостям із дійсним токеном гостьового кошика у заголовку X-Guest-Token. '
                    'Під час генерації схеми Stripe не викликається.',
        parameters=[
            OpenApiParameter(
                name=GUEST_TOKEN_HEADER,
                type=str,
                location=OpenApiParameter.HEADER,
                required=False,
                description="Токен гостьового кошика. Обов'язковий, якщо запит без Bearer-токена.",
            ),
        ],
        request=PaymentIntentCreateSerializer,
        responses={
            200: PaymentIntentResponseSerializer,
            400: OpenApiResponse(response=ErrorMessageSerializer,
                                 description='Невалідна сума або помилка API Stripe'),
        },
        examples=[
            OpenApiExample(
                name='Створення PaymentIntent',
                value={'amount': 1500},
                request_only=True,
            ),
            OpenApiExample(
                name='Успішна відповідь',
                value={'clientSecret': 'pi_123_secret_456'},
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = PaymentIntentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'error': first_error_message(serializer.errors)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            intent = stripe.PaymentIntent.create(
                amount=serializer.validated_data['amount'],
                currency='usd',
            )
        except stripe.error.StripeError as e:
            logger.error(f"Помилка API Stripe: {e.user_message or e}")
            return Response({'error': e.user_message or 'Не вдалося створити платіж.'},
                            status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"PaymentIntent створено: {intent.id}")
        return Response({'clientSecret': intent['client_secret']})


@extend_schema(tags=['Orders'])
class DeliveryOptionListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Отримати список методів доставки",
        description="Повертає активні способи доставки DHL Express та Mest Express з фіксованою ціною 15 USD.",
        responses={200: DeliveryOptionSerializer(many=True)},
        examples=[
            OpenApiExample(
                name='Доступні способи доставки',
                value=[
                    {'id': 1, 'name': 'DHL Express', 'description': 'International delivery', 'price': '15.00',
                     'estimated_days': 7, 'is_active': True},
                    {'id': 2, 'name': 'Mest Express', 'description': 'Alternative delivery option', 'price': '15.00',
                     'estimated_days': 10, 'is_active': True},
                ],
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        options = DeliveryOption.objects.filter(is_active=True).order_by('name')
        serializer = DeliveryOptionSerializer(options, many=True)
        return Response(serializer.data)


@extend_schema(tags=['Orders'])
class PaymentMethodListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Отримати список методів оплати",
        description="Повертає всі доступні варіанти методів оплати.",
        responses={200: PaymentMethodSerializer(many=True)}
    )
    def get(self, request):
        methods = PaymentMethod.objects.all()
        serializer = PaymentMethodSerializer(methods, many=True)
        return Response(serializer.data)


def checkout_error(http_status, code, field, message):
    return Response({'code': code, 'field': field, 'message': message}, status=http_status)


@extend_schema(
    tags=['Orders', 'Checkout'],
    summary='Почати checkout',
    description='Ініціює checkout для авторизованих користувачів і гостей.',
    request=CheckoutStartSerializer,
    responses={
        200: CheckoutStartResponseSerializer,
        400: OpenApiResponse(response=CodedErrorSerializer, description='Помилка валідації або порожній кошик'),
        401: OpenApiResponse(response=CodedErrorSerializer, description='Необхідна авторизація'),
        404: OpenApiResponse(response=CodedErrorSerializer, description='Кошик або сесію не знайдено'),
    },
    examples=[
        OpenApiExample(
            name='Checkout для авторизованого користувача',
            value={'cartId': 12},
            request_only=True,
        ),
        OpenApiExample(
            name='Checkout для гостя',
            value={'guestCartToken': 'guest-cart-token'},
            request_only=True,
        ),
    ],
)
class CheckoutStartView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CheckoutStartSerializer(data=request.data)
        if not serializer.is_valid():
            field, messages = next(iter(serializer.errors.items()))
            message = str(messages[0]) if isinstance(messages, (list, tuple)) and messages else str(messages)
            return checkout_error(status.HTTP_400_BAD_REQUEST, 'VALIDATION_ERROR', field, message)

        is_authenticated = request.user.is_authenticated
        guest_token = serializer.validated_data.get('guestCartToken')
        guest_checkout_token = serializer.validated_data.get('guestCheckoutToken')
        cart_id = serializer.validated_data.get('cartId')

        if not is_authenticated and not guest_token and not guest_checkout_token:
            return checkout_error(status.HTTP_401_UNAUTHORIZED, 'AUTH_REQUIRED', 'guestCartToken',
                                  'Authentication required or guestCartToken must be provided')

        returned_guest_token = None

        if is_authenticated:
            if cart_id:
                cart = Cart.objects.filter(id=cart_id, user=request.user, is_active=True).first()
                if cart is None:
                    return checkout_error(status.HTTP_404_NOT_FOUND, 'CART_NOT_FOUND', 'cartId',
                                          'Cart not found or does not belong to user')
            else:
                cart = Cart.get_active_for_user(request.user)
            user_type = 'authenticated'
        else:
            if guest_checkout_token:
                session = GuestCheckoutSession.objects.select_related('guest_cart').filter(
                    session_token=guest_checkout_token,
                ).first()
                if session is None:
                    return checkout_error(status.HTTP_404_NOT_FOUND, 'GUEST_CHECKOUT_SESSION_NOT_FOUND',
                                          'guestCheckoutToken', 'Invalid or expired guest checkout token')
                if session.is_expired():
                    return checkout_error(status.HTTP_404_NOT_FOUND, 'GUEST_CHECKOUT_SESSION_EXPIRED',
                                          'guestCheckoutToken', 'Guest checkout session has expired')
                guest_cart = session.guest_cart if session.guest_cart and session.guest_cart.is_active else None
                guest_token = guest_cart.token if guest_cart else None
            else:
                guest_cart = GuestCart.get_by_token(guest_token)

            if not guest_cart:
                return checkout_error(status.HTTP_404_NOT_FOUND, 'GUEST_CART_NOT_FOUND', 'guestCartToken',
                                      'Invalid or expired guest cart token')

            cart = guest_cart
            user_type = 'guest'
            returned_guest_token = guest_token

        if not cart.items.exists():
            return checkout_error(status.HTTP_400_BAD_REQUEST, 'CART_EMPTY',
                                  'cartId' if is_authenticated else 'guestCartToken', 'Cart is empty')

        if is_authenticated:
            cart_data = CartSerializer(cart, context={'request': request}).data
        else:
            cart_data = GuestCartSerializer(cart, context={'request': request}).data

        response_data = {
            'checkoutSession': str(uuid.uuid4()),
            'cart': cart_data,
            'userType': user_type,
            'requiresAuthentication': False,
            'nextStep': 'shipping'
        }

        if not is_authenticated and returned_guest_token:
            response_data['guestCartToken'] = returned_guest_token

        return Response(response_data, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Orders'],
    summary="Отримати всі анонімні замовлення",
    description="Повертає список замовлень, створених без авторизації. Доступно тільки адміністраторам.",
    responses={200: OrderListSerializer(many=True)},
)
class AnonymOrderListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        orders = Order.objects.filter(user__isnull=True).order_by('-created_at')
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(tags=['Orders'])
class OrderStatusUpdateView(generics.UpdateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderStatusUpdateSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'pk'
    lookup_url_kwarg = 'orderId'
    http_method_names = ['patch']

    @extend_schema(
        operation_id='orders_update_status',
        summary="Змінити статус замовлення",
        description="Оновлює статус замовлення та створює запис в Audit Log.",
        request=OrderStatusUpdateSerializer,
        responses={
            200: OrderListSerializer,
            400: OpenApiResponse(description='Невалідний статус'),
            401: OpenApiResponse(description='Необхідна авторизація'),
            403: OpenApiResponse(description='Недостатньо прав'),
            404: OpenApiResponse(description='Замовлення не знайдено')
        },
    )
    def patch(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        response_serializer = OrderListSerializer(instance, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)


@extend_schema(tags=['Orders'])
class OrderHistoryView(generics.ListAPIView):
    serializer_class = OrderStatusLogSerializer
    permission_classes = [IsAdminUser]

    @extend_schema(
        operation_id='orders_get_history',
        summary="Отримати історію змін статусів замовлення",
        description="Повертає Audit Log змін статусів для конкретного замовлення.",
        responses={
            200: OrderStatusLogSerializer(many=True),
            401: OpenApiResponse(description='Необхідна авторизація'),
            403: OpenApiResponse(description='Недостатньо прав'),
            404: OpenApiResponse(description='Замовлення не знайдено')
        },
    )
    def get(self, request, *args, **kwargs):
        order_id = self.kwargs.get('orderId')
        if not Order.objects.filter(pk=order_id).exists():
            raise NotFound("Замовлення не знайдено.")
        return self.list(request, *args, **kwargs)

    def get_queryset(self):
        order_id = self.kwargs.get('orderId')
        return OrderStatusLog.objects.filter(order_id=order_id).order_by('-changed_at')


ORDER_CANCEL_ERROR_PAGES = {
    OrderCancellationError.INVALID_LINK: (
        status.HTTP_404_NOT_FOUND,
        "Invalid cancellation link",
        "This cancellation link is invalid or incomplete. "
        "Please open the link from your order confirmation email once again.",
    ),
    OrderCancellationError.ALREADY_SHIPPED: (
        status.HTTP_409_CONFLICT,
        "Order cannot be cancelled",
        "This order has already been shipped, so it can no longer be cancelled.",
    ),
    OrderCancellationError.WINDOW_EXPIRED: (
        status.HTTP_409_CONFLICT,
        "Order cannot be cancelled",
        f"An order can be cancelled only within {CANCELLATION_WINDOW_HOURS} hours of being placed, "
        "and this period has already expired.",
    ),
}


@extend_schema(tags=["Orders"])
class OrderCancelView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ["get"]

    @extend_schema(
        operation_id="orders_cancel_by_email_link",
        summary="Скасувати замовлення за посиланням з email",
        description=(
            "Посилання для скасування з листа підтвердження замовлення. Перевіряє підписаний токен, "
            "переводить замовлення у статус cancelled, пише запис в Audit Log і перенаправляє на сторінку "
            f"підтвердження на фронтенді. Скасування доступне протягом {CANCELLATION_WINDOW_HOURS} годин "
            "після оформлення, поки замовлення не відправлено. Повторний перехід для вже скасованого "
            "замовлення теж перенаправляє на сторінку підтвердження."
        ),
        parameters=[
            OpenApiParameter(
                name="token",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Підписаний токен з листа підтвердження замовлення",
            ),
        ],
        responses={
            302: OpenApiResponse(
                description=(
                    "Замовлення скасовано, перенаправлення на "
                    "FRONTEND_URL/checkout-order/order-cancel?orderId={orderId}"
                )
            ),
            404: OpenApiResponse(description="Недійсне посилання або замовлення не існує (HTML-сторінка)"),
            409: OpenApiResponse(
                description="Замовлення вже відправлено або минув термін для скасування (HTML-сторінка)"
            ),
        },
    )
    def get(self, request, *args, **kwargs):
        try:
            order = cancel_order_by_token(self.kwargs["orderId"], request.query_params.get("token", ""))
        except OrderCancellationError as error:
            return self._render_error_page(error)

        query = urlencode({"orderId": order.pk})
        return redirect(f"{self._frontend_url()}/checkout-order/order-cancel?{query}")

    def _render_error_page(self, error):
        http_status, title, message = ORDER_CANCEL_ERROR_PAGES[error.code]
        order = error.order
        frontend_url = self._frontend_url()
        context = {
            "title": title,
            "message": message,
            "order_id": order.pk if order else None,
            "orders_url": f"{frontend_url}/profile" if order and order.user_id else "",
            "shop_url": frontend_url,
            "support_email": getattr(settings, "REPLY_TO_EMAIL", ""),
        }
        return HttpResponse(render_to_string("order-cancel-error.html", context), status=http_status)

    @staticmethod
    def _frontend_url():
        return str(settings.FRONTEND_URL).rstrip("/")
