import logging

from drf_spectacular.utils import (extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter)
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from cart.infrastructure.models import Cart, CartItem, GuestCart, GuestCartItem
from common.serializers import CodedErrorSerializer
from common.validation import INT64_MAX
from products.infrastructure.models import Product
from .serializers import (CartSerializer, CartItemSerializer, CartItemUpdateSerializer, CartItemRemoveSerializer,
                          GuestCartSerializer, GuestCartItemSerializer, GuestCheckoutSessionSerializer,
                          GuestCheckoutStartSerializer, QUANTITY_MAX)
from ..infrastructure.models import GuestCheckoutSession

logger = logging.getLogger(__name__)

PRODUCT_ID_QUERY_PARAMETER = OpenApiParameter(
    name='product_id',
    type={'type': 'integer', 'format': 'int64', 'minimum': 1, 'maximum': INT64_MAX},
    location=OpenApiParameter.QUERY,
    required=True,
    description='ID товару для видалення'
)

CART_ERROR_RESPONSE = OpenApiResponse(
    response=CodedErrorSerializer,
    description='Помилка запиту. Тіло - стандартний конверт помилок (type, errors) або словник '
                'поле - список повідомлень, або об\'єкт з ключами code, field, message, error.'
)


def coded_error(description):
    return OpenApiResponse(response=CodedErrorSerializer, description=description)


def build_remove_payload(request):
    data = dict(request.data.items()) if hasattr(request.data, 'items') else {}
    if not data.get('product_id') and request.query_params.get('product_id'):
        data['product_id'] = request.query_params.get('product_id')
    return data


@extend_schema_view(
    list=extend_schema(
        operation_id='api_cart_get',
        responses={200: CartSerializer},
    ),
    add_item=extend_schema(
        operation_id='api_cart_add_item',
        request=CartItemSerializer,
        responses={201: CartItemSerializer, 200: CartItemSerializer, 400: CART_ERROR_RESPONSE},
    ),
    update_item=extend_schema(
        operation_id='api_cart_update_item',
        request=CartItemUpdateSerializer,
        responses={200: CartItemSerializer, 204: None, 400: CART_ERROR_RESPONSE, 404: CART_ERROR_RESPONSE},
    ),
    remove_item=extend_schema(
        operation_id='api_cart_remove_item',
        parameters=[PRODUCT_ID_QUERY_PARAMETER],
        request=None,
        responses={204: None, 400: CART_ERROR_RESPONSE, 404: CART_ERROR_RESPONSE},
    ),
    clear=extend_schema(
        operation_id='api_cart_clear',
        responses={204: None},
    ),
)
@extend_schema(tags=['Cart - Authenticated'])
class CartViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CartSerializer
    pagination_class = None
    filter_backends = []

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    def get_active_cart(self):
        return Cart.get_active_for_user(self.request.user)

    def list(self, request, *args, **kwargs):
        cart = self.get_active_cart()
        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='add-item')
    def add_item(self, request):
        cart = self.get_active_cart()
        serializer = CartItemSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            product_id = serializer.validated_data['product_id']

            existing_item = CartItem.objects.filter(cart=cart, product_id=product_id).first()

            if existing_item:
                total_quantity = existing_item.quantity + serializer.validated_data['quantity']
                if total_quantity > QUANTITY_MAX:
                    return Response(
                        {'quantity': ['Загальна кількість товару в кошику перевищує допустимий максимум.']},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                existing_item.quantity = total_quantity
                existing_item.attrs = serializer.validated_data.get('attrs', existing_item.attrs)
                existing_item.metadata = serializer.validated_data.get('metadata', existing_item.metadata)
                existing_item.save()

                response_serializer = CartItemSerializer(existing_item, context={'request': request})
                return Response(response_serializer.data, status=status.HTTP_200_OK)

            serializer.validated_data['cart'] = cart
            cart_item = serializer.save()

            response_serializer = CartItemSerializer(cart_item, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['patch'], url_path='update-item')
    def update_item(self, request):
        cart = self.get_active_cart()
        serializer = CartItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data['product_id']
        new_quantity = serializer.validated_data['quantity']

        try:
            cart_item = CartItem.objects.get(cart=cart, product_id=product_id)
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Товар не знайдено в кошику."},
                status=status.HTTP_404_NOT_FOUND
            )

        if new_quantity <= 0:
            cart_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        cart_item.quantity = new_quantity

        if 'attrs' in serializer.validated_data:
            cart_item.attrs = serializer.validated_data['attrs']

        if 'metadata' in serializer.validated_data:
            cart_item.metadata = serializer.validated_data['metadata']

        cart_item.save()

        response_serializer = CartItemSerializer(cart_item, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], url_path='remove-item')
    def remove_item(self, request):
        cart = self.get_active_cart()
        payload = build_remove_payload(request)

        if not payload.get('product_id'):
            return Response(
                {"error": "Потрібно вказати 'product_id'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CartItemRemoveSerializer(data=payload)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            cart_item = CartItem.objects.get(cart=cart, product_id=serializer.validated_data['product_id'])
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Товар не знайдено в кошику."},
                status=status.HTTP_404_NOT_FOUND
            )

        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['delete'], url_path='clear')
    def clear(self, request):
        cart = self.get_active_cart()
        cart.items.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    create=extend_schema(
        operation_id='api_guest_cart_create',
        summary='Створити гостеву корзину',
        description='Створює нову пусту гостеву корзину та повертає токен для доступу',
        request=None,
        responses={
            201: OpenApiResponse(
                description='Гостева корзина створена',
                response=GuestCartSerializer
            )
        },
    ),
    retrieve=extend_schema(
        operation_id='api_guest_cart_get',
        summary='Отримати гостеву корзину',
        responses={
            200: GuestCartSerializer,
            404: coded_error('Корзина не знайдена'),
            401: coded_error('Токен не переданий або прострочений'),
        },
    ),
)
@extend_schema(tags=['Cart - Guest'])
class GuestCartViewSet(viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    serializer_class = GuestCartSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'guest-checkout'

    GUEST_TOKEN_HEADER = OpenApiParameter(
        name='X-Guest-Token',
        type=str,
        location=OpenApiParameter.HEADER,
        required=True,
        description='Токен гостевої корзини'
    )

    def get_queryset(self):
        return GuestCart.objects.filter(is_active=True)

    def get_guest_cart_or_error(self, request):
        token = request.headers.get('X-Guest-Token')

        if not token:
            return None, Response(
                {
                    'code': 'GUEST_TOKEN_MISSING',
                    'field': 'X-Guest-Token',
                    'message': 'Токен гостьового кошика не передано.',
                    'error': 'Токен гостьового кошика не передано.',
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        guest_cart = GuestCart.get_by_token(token, allow_expired=True)

        if guest_cart is None:
            return None, Response(
                {
                    'code': 'GUEST_CART_NOT_FOUND',
                    'field': 'X-Guest-Token',
                    'message': 'Гостьовий кошик не знайдено.',
                    'error': 'Гостьовий кошик не знайдено, токен недійсний або строк дії токена минув.',
                },
                status=status.HTTP_404_NOT_FOUND
            )

        if not guest_cart.refresh_if_needed(grace_hours=24, ttl_hours=24):
            return None, Response(
                {
                    'code': 'GUEST_TOKEN_EXPIRED',
                    'field': 'X-Guest-Token',
                    'message': 'Токен гостьового кошика прострочено.',
                    'error': 'Токен гостьового кошика прострочено.',
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        return guest_cart, None

    @extend_schema(
        operation_id='api_guest_cart_create',
        summary='Створити гостеву корзину',
        description='Створює нову пусту гостеву корзину та повертає токен для доступу',
        request=None,
        responses={
            201: OpenApiResponse(
                description='Гостева корзина створена',
                response=GuestCartSerializer
            )
        },
    )
    def create(self, request, *args, **kwargs):
        guest_cart = GuestCart.create_guest_cart()
        serializer = GuestCartSerializer(guest_cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        operation_id='api_guest_cart_get',
        summary='Отримати гостеву корзину',
        parameters=[GUEST_TOKEN_HEADER],
        responses={
            200: GuestCartSerializer,
            404: coded_error('Корзина не знайдена'),
            401: coded_error('Токен не переданий або прострочений'),
        }
    )
    def retrieve(self, request, *args, **kwargs):
        guest_cart, error_response = self.get_guest_cart_or_error(request)

        if error_response is not None:
            return error_response

        serializer = GuestCartSerializer(guest_cart, context={'request': request})
        return Response(serializer.data)

    @extend_schema(
        operation_id='api_guest_cart_add_item',
        summary='Додати товар до гостевої корзини',
        request=GuestCartItemSerializer,
        parameters=[GUEST_TOKEN_HEADER],
        responses={
            201: GuestCartItemSerializer,
            200: GuestCartItemSerializer,
            400: coded_error('Перевищено доступний залишок товару'),
            404: coded_error('Корзина або товар не знайдені'),
            401: coded_error('Токен не переданий або прострочений'),
        }
    )
    def add_item(self, request, *args, **kwargs):
        guest_cart, error_response = self.get_guest_cart_or_error(request)
        if error_response is not None:
            return error_response

        serializer = GuestCartItemSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            product_id = serializer.validated_data['product_id']
            new_quantity = serializer.validated_data['quantity']

            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return Response(
                    {"error": "Товар не знайдено."},
                    status=status.HTTP_404_NOT_FOUND
                )

            if new_quantity > product.stock:
                return Response(
                    {"error": f"Запитана кількість перевищує доступний залишок. Доступно: {product.stock}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            existing_item = GuestCartItem.objects.filter(
                guest_cart=guest_cart,
                product_id=product_id
            ).first()

            if existing_item:
                total_quantity = existing_item.quantity + new_quantity

                if total_quantity > product.stock:
                    return Response(
                        {
                            "error": f"Загальна кількість перевищує доступний залишок. Доступно: {product.stock}, вже в кошику: {existing_item.quantity}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                existing_item.quantity = total_quantity
                if 'attrs' in serializer.validated_data:
                    existing_item.attrs = serializer.validated_data['attrs']
                if 'metadata' in serializer.validated_data:
                    existing_item.metadata = serializer.validated_data['metadata']
                existing_item.save()
                return Response(
                    GuestCartItemSerializer(existing_item, context={'request': request}).data,
                    status=status.HTTP_200_OK
                )

            serializer.validated_data['guest_cart'] = guest_cart
            new_item = serializer.save()
            return Response(
                GuestCartItemSerializer(new_item, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        operation_id='api_guest_cart_update_item',
        summary='Оновити кількість товару',
        request=CartItemUpdateSerializer,
        parameters=[GUEST_TOKEN_HEADER],
        responses={
            200: GuestCartItemSerializer,
            204: OpenApiResponse(description='Товар видалено'),
            400: coded_error('Перевищено доступний залишок товару'),
            404: coded_error('Не знайдено'),
            401: coded_error('Токен не переданий або прострочений'),
        }
    )
    def update_item(self, request, *args, **kwargs):
        guest_cart, error_response = self.get_guest_cart_or_error(request)
        if error_response is not None:
            return error_response

        serializer = CartItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product_id = serializer.validated_data['product_id']
        new_quantity = serializer.validated_data['quantity']

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {"error": "Товар не знайдено."},
                status=status.HTTP_404_NOT_FOUND
            )

        if new_quantity > product.stock:
            return Response(
                {"error": f"Запитана кількість перевищує доступний залишок. Доступно: {product.stock}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            cart_item = GuestCartItem.objects.get(
                guest_cart=guest_cart,
                product_id=product_id
            )
        except GuestCartItem.DoesNotExist:
            return Response(
                {"error": "Товар не знайдено в кошику."},
                status=status.HTTP_404_NOT_FOUND
            )

        if new_quantity <= 0:
            cart_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        cart_item.quantity = new_quantity
        if 'attrs' in serializer.validated_data:
            cart_item.attrs = serializer.validated_data['attrs']
        if 'metadata' in serializer.validated_data:
            cart_item.metadata = serializer.validated_data['metadata']
        cart_item.save()

        return Response(
            GuestCartItemSerializer(cart_item, context={'request': request}).data,
            status=status.HTTP_200_OK
        )

    @extend_schema(
        operation_id='api_guest_cart_remove_item',
        summary='Видалити товар з корзини',
        parameters=[
            GUEST_TOKEN_HEADER,
            PRODUCT_ID_QUERY_PARAMETER,
        ],
        request=None,
        responses={
            204: OpenApiResponse(description='Товар видалено'),
            400: CART_ERROR_RESPONSE,
            404: coded_error('Не знайдено'),
            401: coded_error('Токен не переданий або прострочений'),
        }
    )
    def remove_item(self, request, *args, **kwargs):
        guest_cart, error_response = self.get_guest_cart_or_error(request)

        if error_response is not None:
            return error_response

        serializer = CartItemRemoveSerializer(data=build_remove_payload(request))
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data['product_id']

        try:
            cart_item = GuestCartItem.objects.get(
                guest_cart=guest_cart,
                product_id=product_id
            )
        except GuestCartItem.DoesNotExist:
            return Response(
                {
                    'code': 'CART_ITEM_NOT_FOUND',
                    'message': 'Товар не знайдено в кошику.',
                    'error': 'Товар не знайдено в кошику.',
                },
                status=status.HTTP_404_NOT_FOUND
            )

        cart_item.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        operation_id='api_guest_cart_clear',
        summary='Очистити корзину',
        parameters=[GUEST_TOKEN_HEADER],
        responses={
            204: OpenApiResponse(description='Кошик очищено'),
            401: coded_error('Токен не переданий або прострочений'),
            404: coded_error('Корзина не знайдена'),
        }
    )
    def clear(self, request, *args, **kwargs):
        guest_cart, error_response = self.get_guest_cart_or_error(request)

        if error_response is not None:
            return error_response

        guest_cart.items.all().delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        operation_id='api_guest_cart_delete',
        summary='Видалити корзину',
        parameters=[GUEST_TOKEN_HEADER],
        responses={
            204: OpenApiResponse(description='Кошик видалено'),
            401: coded_error('Токен не переданий або прострочений'),
            404: coded_error('Корзина не знайдена'),
        }
    )
    def delete_guest_cart(self, request, *args, **kwargs):
        guest_cart, error_response = self.get_guest_cart_or_error(request)

        if error_response is not None:
            return error_response

        guest_cart.delete_with_items()

        return Response(status=status.HTTP_204_NO_CONTENT)


def guest_checkout_error(http_status, code, field, message, extra=None):
    body = {'code': code, 'field': field, 'message': message, 'error': message}
    if extra:
        body.update(extra)
    return Response(body, status=http_status)


@extend_schema(
    tags=['Cart - Guest'],
    summary='Створити checkout-сесію для гостьового кошика',
    description='Створює короткострокову сесію checkout для активного гостьового кошика. Потрібен токен '
                'гостьового кошика - у полі guestCartToken або у заголовку X-Guest-Token.',
    request=GuestCheckoutStartSerializer,
    responses={
        201: GuestCheckoutSessionSerializer,
        400: OpenApiResponse(response=CodedErrorSerializer, description='Помилка валідації'),
        404: OpenApiResponse(response=CodedErrorSerializer, description='Гостьовий кошик не знайдено'),
        401: OpenApiResponse(response=CodedErrorSerializer, description='Токен гостьового кошика прострочено'),
    },
)
class GuestCheckoutStartView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'guest-checkout'

    def post(self, request):
        payload = dict(request.data.items()) if hasattr(request.data, 'items') else {}
        token = payload.get('guestCartToken') or request.headers.get('X-Guest-Token')

        if not token:
            return guest_checkout_error(
                status.HTTP_400_BAD_REQUEST, 'GUEST_CART_TOKEN_REQUIRED', 'guestCartToken',
                'Потрібно вказати токен гостьового кошика.',
                {'guestCartToken': ['Потрібно вказати токен гостьового кошика.']},
            )

        if not payload.get('email'):
            return guest_checkout_error(
                status.HTTP_400_BAD_REQUEST, 'EMAIL_REQUIRED', 'email',
                "Email є обов'язковим для гостьового checkout.",
                {'email': ["Email є обов'язковим для гостьового checkout."]},
            )

        payload['guestCartToken'] = token
        serializer = GuestCheckoutStartSerializer(data=payload)
        if not serializer.is_valid():
            field, messages = next(iter(serializer.errors.items()))
            message = str(messages[0]) if isinstance(messages, (list, tuple)) and messages else str(messages)
            return guest_checkout_error(status.HTTP_400_BAD_REQUEST, 'VALIDATION_ERROR', field, message,
                                        {field: [message]})

        token = serializer.validated_data['guestCartToken']
        email = serializer.validated_data['email']
        phone = serializer.validated_data.get('phone') or ''

        guest_cart = GuestCart.get_by_token(token, allow_expired=True)
        token_expired = False

        if guest_cart is not None and not guest_cart.refresh_if_needed(grace_hours=24, ttl_hours=24):
            guest_cart = None
            token_expired = True

        if not guest_cart:
            if token_expired:
                return guest_checkout_error(
                    status.HTTP_401_UNAUTHORIZED, 'GUEST_TOKEN_EXPIRED', 'guestCartToken',
                    'Токен гостьового кошика прострочено.',
                )

            return guest_checkout_error(
                status.HTTP_404_NOT_FOUND, 'GUEST_CART_NOT_FOUND', 'guestCartToken',
                'Гостьовий кошик не знайдено, токен недійсний або строк дії токена минув.',
            )

        if not guest_cart.items.exists():
            return Response(
                {
                    'code': 'GUEST_CART_EMPTY',
                    'message': 'Неможливо почати checkout: гостьовий кошик порожній.',
                    'error': 'Неможливо почати checkout: гостьовий кошик порожній.',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = GuestCheckoutSession.objects.create(
            guest_cart=guest_cart,
            email=email,
            phone=phone,
        )

        logger.info("Guest checkout session created for guest cart %s", guest_cart.id)

        response_serializer = GuestCheckoutSessionSerializer(session, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Cart - Admin'],
    summary="Отримати всі гостеві корзини",
    description="Повертає список всіх гостевих корзин з пагінацією. Доступно тільки адміністраторам.",
    responses={200: GuestCartSerializer(many=True)},
)
class GuestCartListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = GuestCartSerializer

    def get_queryset(self):
        return GuestCart.objects.all().order_by('id').prefetch_related('items')
