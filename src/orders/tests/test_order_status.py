import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from cart.infrastructure.models import Cart
from orders.infrastructure.models import Order, OrderStatusLog, DeliveryOption

User = get_user_model()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username='admin',
        email='admin@example.com',
        password='adminpass',
        is_staff=True
    )


@pytest.fixture
def delivery_option(db):
    option, _ = DeliveryOption.objects.update_or_create(
        name='DHL Express',
        defaults={'description': 'Test delivery', 'price': '15.00', 'estimated_days': 7, 'is_active': True},
    )
    return option


@pytest.fixture
def test_order(user, delivery_option):
    cart = Cart.objects.create(user=user, is_active=True)
    return Order.objects.create(
        user=user,
        cart=cart,
        shipping_address='123 Test St',
        delivery_option=delivery_option,
        status='pending'
    )


@pytest.mark.django_db
def test_update_order_status_success(api_client, admin_user, test_order):
    api_client.force_authenticate(user=admin_user)
    url = reverse('order-status-update', kwargs={'orderId': test_order.id})
    response = api_client.patch(url, {'status': 'processing'}, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert response.data['status'] == 'processing'
    log = OrderStatusLog.objects.filter(order=test_order).first()
    assert log is not None
    assert log.previous_status == 'pending'
    assert log.new_status == 'processing'
    assert log.changed_by == admin_user


@pytest.mark.django_db
def test_update_order_status_no_log_if_same_status(api_client, admin_user, test_order):
    api_client.force_authenticate(user=admin_user)
    url = reverse('order-status-update', kwargs={'orderId': test_order.id})
    response = api_client.patch(url, {'status': 'pending'}, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert OrderStatusLog.objects.filter(order=test_order).count() == 0


@pytest.mark.django_db
def test_update_order_status_invalid_status(api_client, admin_user, test_order):
    api_client.force_authenticate(user=admin_user)
    url = reverse('order-status-update', kwargs={'orderId': test_order.id})
    response = api_client.patch(url, {'status': 'invalid_status'}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_update_order_status_not_found(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    url = reverse('order-status-update', kwargs={'orderId': 99999})
    response = api_client.patch(url, {'status': 'processing'}, format='json')
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_unrestricted_status_transitions(api_client, admin_user, test_order):
    api_client.force_authenticate(user=admin_user)
    url = reverse('order-status-update', kwargs={'orderId': test_order.id})
    test_order.status = 'delivered'
    test_order.save()
    response = api_client.patch(url, {'status': 'pending'}, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert response.data['status'] == 'pending'


@pytest.mark.django_db
def test_get_order_history(api_client, admin_user, test_order):
    api_client.force_authenticate(user=admin_user)

    OrderStatusLog.objects.create(order=test_order, previous_status='pending', new_status='processing',
                                  changed_by=admin_user)
    OrderStatusLog.objects.create(order=test_order, previous_status='processing', new_status='shipped',
                                  changed_by=admin_user)

    url = reverse('order-history', kwargs={'orderId': test_order.id})
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK

    results = response.data.get('results', response.data)

    assert len(results) == 2
    assert results[0]['new_status'] == 'shipped'
    assert results[1]['new_status'] == 'processing'
