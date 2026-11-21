import pytest
from django.urls import reverse
from rest_framework import status

from orders.infrastructure.models import DeliveryOption, Order


@pytest.fixture
def delivery_option():
    option, _ = DeliveryOption.objects.update_or_create(
        name='DHL Express',
        defaults={
            'description': 'International delivery',
            'price': '15.00',
            'estimated_days': 7,
            'is_active': True,
        },
    )
    return option


@pytest.mark.django_db
def test_delivery_options_return_only_active_methods(api_client, delivery_option):
    DeliveryOption.objects.update_or_create(
        name='Mest Express',
        defaults={
            'description': 'Active test delivery',
            'price': '15.00',
            'estimated_days': 2,
            'is_active': True,
        },
    )

    DeliveryOption.objects.update_or_create(
        name='Нова пошта',
        defaults={
            'description': 'Прихований спосіб доставки',
            'price': '15.00',
            'estimated_days': 3,
            'is_active': False,
        },
    )

    response = api_client.get(reverse('delivery-options'))

    assert response.status_code == status.HTTP_200_OK
    names = {item['name'] for item in response.data}
    assert names == {'DHL Express', 'Mest Express'}
    assert {item['price'] for item in response.data} == {'15.00'}


@pytest.mark.django_db
def test_guest_order_can_be_created_from_guest_cart(api_client, guest_cart, delivery_option):
    response = api_client.post(reverse('order-list-create'), {
        'guest_cart_token': guest_cart.token,
        'delivery_option_id': delivery_option.id,
        'shipping_address': '221B Baker Street, London',
    }, format='json')

    assert response.status_code == status.HTTP_201_CREATED
    assert Order.objects.filter(user__isnull=True).exists()
    guest_cart.refresh_from_db()
    assert guest_cart.is_active is False


@pytest.mark.django_db
def test_authenticated_order_history_requires_valid_token(api_client):
    response = api_client.get(
        reverse('order-list-create'),
        HTTP_AUTHORIZATION='Bearer invalid-token',
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data['code'] == 'TOKEN_NOT_VALID'
