from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from cart.infrastructure.models import Cart, CartItem, GuestCart, GuestCartItem
from orders.infrastructure.models import DeliveryOption, Order, OrderStatusLog


class FakeIntent(dict):
    id = 'pi_test_123'


@pytest.fixture
def active_delivery():
    option, _ = DeliveryOption.objects.update_or_create(
        name='Regression Express',
        defaults={'description': 'Test delivery', 'price': '5.00', 'estimated_days': 2, 'is_active': True},
    )
    return option


def order_payload(delivery, **extra):
    return {'delivery_option_id': delivery.id, 'shipping_address': '221B Baker Street, London', **extra}


@pytest.mark.django_db
def test_anonymous_caller_cannot_read_order_history(api_client, user, user_cart, active_delivery):
    Order.objects.create(user=user, cart=user_cart, delivery_option=active_delivery,
                         shipping_address='Somewhere 1', total_amount='10.00')

    plain = api_client.get(reverse('order-list-create'))
    by_user = api_client.get(reverse('order-list-create'), {'user_id': user.id})

    assert plain.status_code == status.HTTP_401_UNAUTHORIZED
    assert by_user.status_code == status.HTTP_401_UNAUTHORIZED
    assert 'Somewhere 1' not in by_user.content.decode()


@pytest.mark.django_db
def test_order_history_ignores_user_id_of_authenticated_caller(other_client, user, other_user, user_cart,
                                                               active_delivery):
    Order.objects.create(user=user, cart=user_cart, delivery_option=active_delivery,
                         shipping_address='Somewhere 1', total_amount='10.00')

    response = other_client.get(reverse('order-list-create'), {'user_id': user.id})

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []


@pytest.mark.django_db
@pytest.mark.parametrize('extra', [
    {},
    {'user_id': 'victim'},
    {'cart_id': 'victim_cart'},
    {'user': 'victim'},
])
def test_anonymous_caller_cannot_create_orders_for_a_victim(api_client, user, user_cart, active_delivery, extra):
    replacements = {'victim': user.id, 'victim_cart': user_cart.id}
    payload = order_payload(active_delivery, **{key: replacements[value] for key, value in extra.items()})

    response = api_client.post(reverse('order-list-create'), payload, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert Order.objects.count() == 0
    user_cart.refresh_from_db()
    assert user_cart.is_active is True
    assert CartItem.objects.filter(cart=user_cart).count() == 1


@pytest.mark.django_db
def test_user_cannot_order_from_someone_elses_cart(other_client, user, user_cart, active_delivery):
    response = other_client.post(
        reverse('order-list-create'), order_payload(active_delivery, cart_id=user_cart.id), format='json'
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Order.objects.count() == 0
    user_cart.refresh_from_db()
    assert user_cart.is_active is True
    assert CartItem.objects.filter(cart=user_cart).count() == 1


@pytest.mark.django_db
def test_user_orders_from_own_cart_and_cart_is_consumed(auth_client, user, user_cart, active_delivery):
    response = auth_client.post(
        reverse('order-list-create'), order_payload(active_delivery, cart_id=user_cart.id), format='json'
    )

    assert response.status_code == status.HTTP_201_CREATED
    order = Order.objects.get()
    assert order.user_id == user.id
    assert order.items.count() == 1
    user_cart.refresh_from_db()
    assert user_cart.is_active is False


@pytest.mark.django_db
def test_order_creation_rolls_back_completely_when_a_step_fails(auth_client, user_cart, active_delivery):
    with patch('orders.interfaces.serializers.OrderItem.objects.bulk_create', side_effect=RuntimeError('boom')):
        with pytest.raises(RuntimeError):
            auth_client.post(
                reverse('order-list-create'), order_payload(active_delivery, cart_id=user_cart.id), format='json'
            )

    assert Order.objects.count() == 0
    user_cart.refresh_from_db()
    assert user_cart.is_active is True
    assert CartItem.objects.filter(cart=user_cart).count() == 1


@pytest.mark.django_db
def test_guest_order_requires_a_live_guest_cart(api_client, active_delivery):
    unknown = api_client.post(
        reverse('order-list-create'), order_payload(active_delivery, guest_cart_token='x' * 64), format='json'
    )

    assert unknown.status_code == status.HTTP_400_BAD_REQUEST
    assert Order.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize('body', ['[null, null]', '"text"', '123', 'null', '[]'])
@pytest.mark.parametrize('authenticated', [False, True])
def test_order_create_rejects_non_object_json_bodies(api_client, auth_client, body, authenticated):
    client = auth_client if authenticated else api_client

    response = client.generic('POST', reverse('order-list-create'), body, content_type='application/json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response['Content-Type'].startswith('application/json')
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_checkout_start_rejects_non_object_json_bodies(auth_client):
    response = auth_client.generic('POST', reverse('checkout-start'), '[null, null]', content_type='application/json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_payment_intent_requires_authentication_or_guest_token(api_client):
    with patch('orders.interfaces.views.stripe.PaymentIntent.create', return_value=FakeIntent(client_secret='s')) as stripe_call:
        anonymous = api_client.post(reverse('create-payment-intent'), {'amount': 2500}, format='json')
        forged = api_client.post(reverse('create-payment-intent'), {'amount': 2500}, format='json',
                                 HTTP_X_GUEST_TOKEN='nope')

    assert anonymous.status_code == status.HTTP_401_UNAUTHORIZED
    assert forged.status_code == status.HTTP_401_UNAUTHORIZED
    stripe_call.assert_not_called()


@pytest.mark.django_db
def test_payment_intent_returns_client_secret_for_users_and_guests(auth_client, api_client, guest_cart):
    with patch('orders.interfaces.views.stripe.PaymentIntent.create',
               return_value=FakeIntent(client_secret='secret_1')) as stripe_call:
        by_user = auth_client.post(reverse('create-payment-intent'), {'amount': 2500}, format='json')
        by_guest = api_client.post(reverse('create-payment-intent'), {'amount': 2500}, format='json',
                                   HTTP_X_GUEST_TOKEN=guest_cart.token)

    assert by_user.status_code == status.HTTP_200_OK
    assert by_user.data == {'clientSecret': 'secret_1'}
    assert by_guest.status_code == status.HTTP_200_OK
    assert stripe_call.call_count == 2


@pytest.mark.django_db
@override_settings(STRIPE_DEMO_MODE=True)
def test_payment_intent_demo_mode_never_calls_stripe(auth_client):
    with patch('orders.interfaces.views.stripe.PaymentIntent.create') as stripe_call:
        response = auth_client.post(reverse('create-payment-intent'), {'amount': 2500}, format='json')

    assert response.status_code == status.HTTP_200_OK
    assert response.data['clientSecret'].startswith('demo_pi_')
    assert response.data['clientSecret'].endswith('_secret_no_charge')
    stripe_call.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize('payload', [{}, {'amount': 0}, {'amount': -5}, {'amount': 'abc'}, {'amount': 10 ** 12},
                                     {'amount': None}])
def test_payment_intent_validates_amount_before_calling_stripe(auth_client, payload):
    with patch('orders.interfaces.views.stripe.PaymentIntent.create',
               return_value=FakeIntent(client_secret='s')) as stripe_call:
        response = auth_client.post(reverse('create-payment-intent'), payload, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'error' in response.data
    stripe_call.assert_not_called()


@pytest.mark.django_db
def test_order_status_update_requires_status_field(staff_client, user, user_cart, active_delivery):
    order = Order.objects.create(user=user, cart=user_cart, delivery_option=active_delivery,
                                 shipping_address='Somewhere 1', total_amount='10.00')

    empty = staff_client.patch(reverse('order-status-update', args=[order.id]), {}, format='json')
    valid = staff_client.patch(reverse('order-status-update', args=[order.id]), {'status': 'shipped'}, format='json')

    assert empty.status_code == status.HTTP_400_BAD_REQUEST
    assert valid.status_code == status.HTTP_200_OK
    order.refresh_from_db()
    assert order.status == 'shipped'
    assert OrderStatusLog.objects.filter(order=order, new_status='shipped').count() == 1


@pytest.mark.django_db
def test_order_status_update_is_closed_to_regular_users(auth_client, api_client, user, user_cart, active_delivery):
    order = Order.objects.create(user=user, cart=user_cart, delivery_option=active_delivery,
                                 shipping_address='Somewhere 1', total_amount='10.00')

    anonymous = api_client.patch(reverse('order-status-update', args=[order.id]), {'status': 'shipped'}, format='json')
    regular = auth_client.patch(reverse('order-status-update', args=[order.id]), {'status': 'shipped'}, format='json')

    assert anonymous.status_code == status.HTTP_401_UNAUTHORIZED
    assert regular.status_code == status.HTTP_403_FORBIDDEN
    order.refresh_from_db()
    assert order.status == 'pending'


@pytest.mark.django_db
def test_guest_order_from_guest_cart_still_works(api_client, guest_cart, active_delivery):
    response = api_client.post(
        reverse('order-list-create'), order_payload(active_delivery, guest_cart_token=guest_cart.token), format='json'
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Order.objects.filter(user__isnull=True).count() == 1
    assert GuestCart.objects.get(pk=guest_cart.pk).is_active is False
    assert GuestCartItem.objects.filter(guest_cart=guest_cart).count() == 1
    assert Cart.objects.count() == 0
