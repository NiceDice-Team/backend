from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from cart.infrastructure.models import CartItem
from orders.infrastructure.models import Order
from products.infrastructure.models import Brand, Product


class FakePaymentIntent(dict):
    id = 'pi_test_123'


class FakeStripeError(Exception):
    def __init__(self, user_message):
        super().__init__(user_message)
        self.user_message = user_message


def get_error_detail(response):
    data = response.json()
    if 'detail' in data:
        return data['detail']
    return data['errors'][0]['detail']


@pytest.mark.django_db
class TestOrderViews:
    @pytest.fixture
    def api_client(self):
        return APIClient()

    @pytest.fixture
    def user(self, user_model):
        return user_model.objects.create_user(
            username='buyer',
            email='buyer@example.com',
            password='strongpassword123',
        )

    @pytest.fixture
    def other_user(self, user_model):
        return user_model.objects.create_user(
            username='other-buyer',
            email='other@example.com',
            password='strongpassword123',
        )

    @pytest.fixture
    def brand(self):
        return Brand.objects.create(name='Nice Dice Brand')

    @pytest.fixture
    def product(self, brand, category_model):
        category = category_model.objects.create(
            name='Board Games',
            slug='board-games',
            description='Board games',
            image='',
        )
        product = Product.objects.create(
            name='Dice Set',
            slug='dice-set',
            brand=brand,
            description='A nice dice set',
            price=Decimal('15.50'),
            stock=5,
        )
        product.categories.add(category)
        return product

    @pytest.fixture
    def another_product(self, brand, category_model):
        category = category_model.objects.create(
            name='Accessories',
            slug='accessories',
            description='Accessories',
            image='',
        )
        product = Product.objects.create(
            name='Dice Tray',
            slug='dice-tray',
            brand=brand,
            description='A dice tray',
            price=Decimal('7.25'),
            stock=3,
        )
        product.categories.add(category)
        return product

    @pytest.fixture
    def order_url(self):
        return reverse('order-list-create')

    @pytest.fixture
    def payment_intent_url(self):
        return reverse('create-payment-intent')

    @pytest.mark.positive
    def test_create_order_returns_201_and_persists_order_with_items(
        self, api_client, user, product, another_product, order_url
    ):
        api_client.force_authenticate(user=user)
        CartItem.objects.create(user=user, product=product, quantity=2)
        CartItem.objects.create(user=user, product=another_product, quantity=1)

        response = api_client.post(order_url, {'user_id': user.id}, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        order = Order.objects.get()
        assert response.json()['id'] == order.id
        assert response.json()['status'] == 'pending'
        assert order.user == user
        assert order.total_amount == Decimal('38.25')
        assert order.products.count() == 2
        assert set(order.products.values_list('id', flat=True)) == {product.id, another_product.id}
        assert order.items.count() == 2
        assert set(order.items.values_list('product_id', 'quantity', 'price')) == {
            (product.id, 2, Decimal('15.50')),
            (another_product.id, 1, Decimal('7.25')),
        }
        assert not CartItem.objects.filter(user=user).exists()

    @pytest.mark.negative
    def test_create_order_requires_authenticated_user(self, api_client, user, product, order_url):
        CartItem.objects.create(user=user, product=product, quantity=1)

        response = api_client.post(order_url, {'user_id': user.id}, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert get_error_detail(response) == 'Authentication credentials were not provided.'
        assert Order.objects.count() == 0

    @pytest.mark.negative
    def test_create_order_requires_user_id(self, api_client, user, product, order_url):
        api_client.force_authenticate(user=user)
        CartItem.objects.create(user=user, product=product, quantity=1)

        response = api_client.post(order_url, {}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'user_id' in response.json()['detail']
        assert Order.objects.count() == 0

    @pytest.mark.negative
    def test_create_order_rejects_empty_cart(self, api_client, user, order_url):
        api_client.force_authenticate(user=user)

        response = api_client.post(order_url, {'user_id': user.id}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['detail'] == 'Кошик користувача порожній.'
        assert Order.objects.count() == 0

    @pytest.mark.negative
    def test_create_order_rejects_negative_product_price(self, api_client, user, product, order_url):
        Product.objects.filter(pk=product.pk).update(price=Decimal('-10.00'))
        product.refresh_from_db()
        api_client.force_authenticate(user=user)
        CartItem.objects.create(user=user, product=product, quantity=1)

        response = api_client.post(order_url, {'user_id': user.id}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['detail'] == 'Ціна товару повинна бути більшою за 0.'
        assert Order.objects.count() == 0

    @pytest.mark.negative
    def test_create_order_for_another_user_is_forbidden(
        self, api_client, user, other_user, product, order_url
    ):
        api_client.force_authenticate(user=user)
        CartItem.objects.create(user=user, product=product, quantity=1)

        response = api_client.post(order_url, {'user_id': other_user.id}, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()['detail'] == 'Неможливо створити замовлення для іншого користувача.'
        assert Order.objects.count() == 0

    @pytest.mark.positive
    def test_create_order_uses_only_authenticated_users_cart_items(
        self, api_client, user, other_user, product, another_product, order_url
    ):
        api_client.force_authenticate(user=user)
        CartItem.objects.create(user=user, product=product, quantity=2)
        CartItem.objects.create(user=other_user, product=another_product, quantity=3)

        response = api_client.post(order_url, {'user_id': user.id}, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        order = Order.objects.get()
        assert order.total_amount == Decimal('31.00')
        assert set(order.items.values_list('product_id', flat=True)) == {product.id}
        assert not CartItem.objects.filter(user=user).exists()
        assert CartItem.objects.filter(user=other_user, product=another_product, quantity=3).exists()

    @pytest.mark.positive
    def test_create_payment_intent_returns_client_secret(self, api_client, payment_intent_url, monkeypatch):
        fake_intent = FakePaymentIntent(client_secret='secret_123')
        create_calls = []

        def fake_create(**kwargs):
            create_calls.append(kwargs)
            return fake_intent

        monkeypatch.setattr('orders.interfaces.views.stripe.PaymentIntent.create', fake_create)

        response = api_client.post(payment_intent_url, {'amount': 2500}, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {'clientSecret': 'secret_123'}
        assert create_calls == [{'amount': 2500, 'currency': 'uah'}]

    @pytest.mark.negative
    def test_create_payment_intent_returns_error_when_stripe_fails(
        self, api_client, payment_intent_url, monkeypatch
    ):
        monkeypatch.setattr('orders.interfaces.views.stripe.error.StripeError', FakeStripeError)

        def fake_create(**kwargs):
            raise FakeStripeError('Payment failed')

        monkeypatch.setattr('orders.interfaces.views.stripe.PaymentIntent.create', fake_create)

        response = api_client.post(payment_intent_url, {'amount': 2500}, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {'error': 'Payment failed'}

    @pytest.mark.positive
    def test_order_total_matches_cart_subtotal_without_shipping(self, api_client, user, product, order_url):
        api_client.force_authenticate(user=user)
        CartItem.objects.create(user=user, product=product, quantity=3)

        response = api_client.post(order_url, {'user_id': user.id}, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()['total_amount'] == '46.50'

    @pytest.mark.skip(reason='Promo-code discounts are not implemented in the checkout flow yet.')
    def test_order_total_applies_promo_code_discount(self):
        pass

    @pytest.mark.skip(reason='Order payment status transitions are not implemented by the current payment intent endpoint.')
    def test_successful_payment_marks_order_paid(self):
        pass

    @pytest.mark.skip(reason='Order payment status transitions are not implemented by the current payment intent endpoint.')
    def test_failed_payment_marks_order_payment_failed(self):
        pass
