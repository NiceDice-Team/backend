from decimal import Decimal

from cart.infrastructure.models import Cart, GuestCart
from common.serializers import FullBodySerializerMixin
from common.validation import INT64_MAX
from django.db import transaction

from orders.emails import send_order_confirmation_email
from orders.infrastructure.models import Order, OrderItem, DeliveryOption, PaymentMethod, OrderStatusLog
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import NotAuthenticated

PAYMENT_AMOUNT_MAX = 99999999


class DeliveryOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryOption
        fields = '__all__'


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = '__all__'


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'product_id', 'quantity', 'price', 'subtotal']

    @extend_schema_field(serializers.FloatField())
    def get_subtotal(self, obj):
        return obj.subtotal


class OrderListSerializer(serializers.ModelSerializer):
    delivery_option = DeliveryOptionSerializer(read_only=True, allow_null=True)
    payment_method = PaymentMethodSerializer(read_only=True, allow_null=True)
    items = OrderItemSerializer(many=True, read_only=True)
    subtotal = serializers.SerializerMethodField()
    shipping_cost = serializers.SerializerMethodField()
    user = serializers.IntegerField(source='user.id', allow_null=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'cart', 'delivery_option', 'payment_method', 'shipping_address', 'billing_address',
                  'status', 'created_at', 'updated_at', 'subtotal', 'shipping_cost', 'total_amount', 'items']

    @extend_schema_field(serializers.FloatField())
    def get_subtotal(self, obj):
        return obj.subtotal

    @extend_schema_field(serializers.FloatField())
    def get_shipping_cost(self, obj):
        return obj.shipping_cost


class PaymentIntentCreateSerializer(serializers.Serializer):
    amount = serializers.IntegerField(
        min_value=1,
        max_value=PAYMENT_AMOUNT_MAX,
        help_text='Сума платежу в центах USD.',
        error_messages={
            'required': 'Необхідно вказати суму',
            'null': 'Необхідно вказати суму',
            'invalid': 'Сума повинна бути цілим числом у центах USD.',
            'min_value': 'Сума повинна бути більшою за нуль',
            'max_value': 'Сума перевищує допустиму межу платежу.',
            'max_string_length': 'Сума повинна бути цілим числом у центах USD.',
        },
    )


class PaymentIntentResponseSerializer(serializers.Serializer):
    clientSecret = serializers.CharField()


class CheckoutStartSerializer(serializers.Serializer):
    guestCartToken = serializers.CharField(required=False, max_length=64,
                                           help_text="Токен гостевої корзини (обов'язково для гостей)")
    guestCheckoutToken = serializers.CharField(required=False, max_length=64,
                                               help_text='Токен гостьової checkout-сесії')
    cartId = serializers.IntegerField(required=False, min_value=1, max_value=INT64_MAX,
                                      help_text='ID кошика (тільки для авторизованих користувачів)')
    email = serializers.EmailField(required=False, help_text="Email для контактів (обов'язково для гостей)")
    phone = serializers.CharField(required=False, max_length=20, help_text='Телефон для контактів (опціонально)')


class CheckoutStartResponseSerializer(serializers.Serializer):
    checkoutSession = serializers.CharField()
    cart = serializers.DictField()
    userType = serializers.ChoiceField(choices=['authenticated', 'guest'])
    requiresAuthentication = serializers.BooleanField()
    guestCartToken = serializers.CharField(required=False)
    nextStep = serializers.ChoiceField(choices=['shipping', 'payment', 'confirmation'])


class OrderCreateSerializer(serializers.ModelSerializer):
    delivery_option_id = serializers.IntegerField(write_only=True, required=True, min_value=1, max_value=INT64_MAX,
                                                  help_text="ID методу доставки (обов'язково)")
    payment_method_id = serializers.IntegerField(write_only=True, required=False, min_value=1, max_value=INT64_MAX,
                                                 help_text="ID методу оплати (опціонально)")
    cart_id = serializers.IntegerField(write_only=True, required=False, min_value=1, max_value=INT64_MAX,
                                       help_text="ID кошика авторизованого користувача. Потрібен Bearer-токен, "
                                                 "кошик має належати власнику токена.")
    guest_cart_token = serializers.CharField(write_only=True, required=False, max_length=64,
                                             help_text="Токен гостьової корзини для анонімних користувачів замість cart_id.")
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True, allow_null=True, max_length=254,
                                   help_text="Email покупця для листа-підтвердження замовлення. Якщо не вказано, "
                                             "для гостя він береться з checkout-сесії гостьового кошика, а потім із "
                                             "адреси доставки чи оплати у форматі \"..., email, телефон\". "
                                             "Для авторизованого користувача береться email акаунта.")
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True, max_length=32,
                                  help_text="Телефон покупця для листа-підтвердження. Якщо не вказано, береться "
                                            "з checkout-сесії або з адреси доставки чи оплати.")
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    shipping_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'cart', 'delivery_option', 'payment_method', 'shipping_address', 'billing_address',
                  'status', 'created_at', 'updated_at', 'subtotal', 'shipping_cost', 'total_amount',
                  'delivery_option_id', 'payment_method_id', 'cart_id', 'guest_cart_token', 'email', 'phone', 'items']
        read_only_fields = ['user', 'status', 'created_at', 'updated_at', 'subtotal', 'shipping_cost', 'total_amount',
                            'cart']

    def _request_user(self):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            return user
        return None

    def _load_source(self, cart_id, guest_cart_token, lock):
        if cart_id is not None:
            user = self._request_user()
            if user is None:
                raise NotAuthenticated()
            carts = Cart.objects.select_for_update() if lock else Cart.objects.all()
            cart = carts.filter(pk=cart_id, user=user).first()
            if cart is None:
                raise serializers.ValidationError({'cart_id': 'Кошик не знайдено.'})
            if not cart.is_active:
                raise serializers.ValidationError({'cart': 'Кошик не активний.'})
            items = list(cart.items.select_related('product'))
            if not items:
                raise serializers.ValidationError({'cart': 'Обраний кошик порожній.'})
            return cart, items

        guest_cart = GuestCart.get_by_token(guest_cart_token)
        if guest_cart is not None and lock:
            guest_cart = GuestCart.objects.select_for_update().filter(pk=guest_cart.pk, is_active=True).first()
        if guest_cart is None:
            raise serializers.ValidationError({'guest_cart_token': 'Невірний або прострочений токен кошика.'})
        items = list(guest_cart.items.select_related('product'))
        if not items:
            raise serializers.ValidationError({'guest_cart': 'Обраний гостевий кошик порожній.'})
        return guest_cart, items

    @staticmethod
    def _validate_stock(items):
        stock_errors = [
            {
                'product_id': item.product.id,
                'message': f"Товар '{item.product.name}': замовлено {item.quantity}, доступно {item.product.stock}"
            }
            for item in items if item.quantity > item.product.stock
        ]
        if stock_errors:
            raise serializers.ValidationError({'stock_validation': stock_errors})

    def validate(self, attrs):
        if not attrs.get('shipping_address'):
            raise serializers.ValidationError("Адреса доставки є обов'язковою.")

        cart_id = attrs.get('cart_id')
        guest_cart_token = attrs.get('guest_cart_token')
        if cart_id is None and not guest_cart_token:
            raise serializers.ValidationError("Потрібно вказати 'cart_id' або 'guest_cart_token'.")
        if cart_id is not None and guest_cart_token:
            raise serializers.ValidationError("Потрібно вказати лише одне поле: 'cart_id' або 'guest_cart_token'.")

        _, items = self._load_source(cart_id, guest_cart_token, lock=False)
        self._validate_stock(items)

        if not DeliveryOption.objects.filter(id=attrs['delivery_option_id'], is_active=True).exists():
            raise serializers.ValidationError({"delivery_option_id": "Метод доставки не існує або наразі недоступний."})

        payment_method_id = attrs.get('payment_method_id')
        if payment_method_id is not None and not PaymentMethod.objects.filter(id=payment_method_id).exists():
            raise serializers.ValidationError({"payment_method_id": "Метод оплати не існує."})

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        guest_cart_token = validated_data.get('guest_cart_token')
        customer_email = validated_data.get('email')
        customer_phone = validated_data.get('phone')

        with transaction.atomic():
            order = self._create_order(validated_data)

        send_order_confirmation_email(
            order=order,
            request=request,
            guest_cart_token=guest_cart_token,
            customer_email=customer_email,
            customer_phone=customer_phone,
        )

        return order

    def _create_order(self, validated_data):
        delivery_option_id = validated_data.pop('delivery_option_id')
        payment_method_id = validated_data.pop('payment_method_id', None)
        cart_id = validated_data.pop('cart_id', None)
        guest_cart_token = validated_data.pop('guest_cart_token', None)
        validated_data.pop('email', None)
        validated_data.pop('phone', None)

        source, items = self._load_source(cart_id, guest_cart_token, lock=True)
        self._validate_stock(items)

        delivery_option = DeliveryOption.objects.filter(pk=delivery_option_id, is_active=True).first()
        if delivery_option is None:
            raise serializers.ValidationError({"delivery_option_id": "Метод доставки не існує або наразі недоступний."})
        validated_data['delivery_option'] = delivery_option

        if payment_method_id is not None:
            payment_method = PaymentMethod.objects.filter(pk=payment_method_id).first()
            if payment_method is None:
                raise serializers.ValidationError({"payment_method_id": "Метод оплати не існує."})
            validated_data['payment_method'] = payment_method

        validated_data['user'] = self._request_user()
        validated_data['cart'] = source if cart_id is not None else None
        subtotal = sum((item.product.price * item.quantity for item in items), Decimal('0.00'))
        validated_data['total_amount'] = subtotal + delivery_option.price

        order = Order.objects.create(**validated_data)
        OrderItem.objects.bulk_create([
            OrderItem(order=order, product=item.product, quantity=item.quantity, price=item.product.price)
            for item in items
        ])

        source.is_active = False
        source.save(update_fields=['is_active', 'updated_at'])

        return order


class OrderStatusUpdateSerializer(FullBodySerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['status']
        extra_kwargs = {'status': {'required': True}}

    def validate_status(self, value):
        valid_statuses = [choice[0] for choice in Order.ORDER_STATUS]
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Невалідний статус. Допустимі значення: {', '.join(valid_statuses)}")
        return value

    def update(self, instance, validated_data):
        new_status = validated_data.get('status')
        previous_status = instance.status

        if previous_status != new_status:
            request = self.context.get('request')
            changed_by = request.user if request and getattr(request, 'user',
                                                             None) and request.user.is_authenticated else None

            with transaction.atomic():
                instance.status = new_status
                instance.save(update_fields=['status', 'updated_at'])

                OrderStatusLog.objects.create(
                    order=instance,
                    previous_status=previous_status,
                    new_status=new_status,
                    changed_by=changed_by
                )

        return instance


class OrderStatusLogSerializer(serializers.ModelSerializer):
    changed_by = serializers.IntegerField(source='changed_by.id', allow_null=True, read_only=True)
    changed_at = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%SZ', read_only=True)

    class Meta:
        model = OrderStatusLog
        fields = ['id', 'order', 'previous_status', 'new_status', 'changed_by', 'changed_at']
        read_only_fields = fields
