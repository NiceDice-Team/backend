import logging
from smtplib import SMTPException
from unittest import mock

import pytest
from django.urls import reverse
from rest_framework import status

from orders.emails import build_order_context, get_address_contact, split_address, split_address_contact
from orders.infrastructure.models import DeliveryOption, Order, OrderItem

STOREFRONT_ADDRESS = 'Ukraine, John, Smith, Main Street 12, 5, 01001, Kyiv, John.Smith@Example.com, +380 50 111 22 33'
STOREFRONT_EMAIL = 'john.smith@example.com'
STOREFRONT_PHONE = '+380 50 111 22 33'
LEGACY_ADDRESS = 'Oleksandr Doroshenko, Akademika Korolova 112, Odesa, Ukraine'
LEGACY_PARTS = {
    'name': 'Oleksandr Doroshenko',
    'line_1': 'Akademika Korolova 112',
    'line_2': 'Odesa',
    'line_3': '',
    'country': 'Ukraine',
}
EMPTY_PARTS = {'name': '', 'line_1': '', 'line_2': '', 'line_3': '', 'country': ''}


@pytest.fixture
def delivery_option(db):
    return DeliveryOption.objects.create(
        name='DHL Express', description='Test delivery', price='15.00', estimated_days=7, is_active=True,
    )


def create_order(client, **payload):
    return client.post(reverse('order-list-create'), payload, format='json')


def guest_order(client, guest_cart, delivery_option, **extra):
    payload = {
        'guest_cart_token': guest_cart.token,
        'delivery_option_id': delivery_option.id,
        'shipping_address': STOREFRONT_ADDRESS,
    }
    payload.update(extra)
    return create_order(client, **payload)


def recipients(mailoutbox):
    return [message.to for message in mailoutbox]


@pytest.mark.django_db
def test_guest_gets_the_confirmation_at_the_email_from_the_storefront_address(
        api_client, guest_cart, delivery_option, mailoutbox):
    response = guest_order(api_client, guest_cart, delivery_option)

    assert response.status_code == status.HTTP_201_CREATED
    assert recipients(mailoutbox) == [[STOREFRONT_EMAIL]]
    assert mailoutbox[0].subject == f"Order Confirmation #{response.data['id']}"


@pytest.mark.django_db
def test_guest_confirmation_has_order_number_items_totals_delivery_and_payment(
        api_client, guest_cart, delivery_option, mailoutbox):
    response = guest_order(api_client, guest_cart, delivery_option)

    message = mailoutbox[0]
    html_content, mimetype = message.alternatives[0]
    assert mimetype == 'text/html'
    for expected in (
            'Thank you for your order!',
            f"Order number: {response.data['id']}",
            'Payment method: Credit Card',
            'Shipping method: DHL Express',
            '1. Test Game \u2014 2 \u00d7 $29.99 = $59.98',
            'Subtotal: $59.98',
            'Shipping: $15.00',
            'Total: $74.98',
    ):
        assert expected in message.body
    for expected in ('Test Game', '$59.98', '$74.98', 'DHL Express'):
        assert expected in html_content


@pytest.mark.django_db
def test_guest_confirmation_shows_the_contacts_and_a_readable_address(
        api_client, guest_cart, delivery_option, mailoutbox):
    response = guest_order(api_client, guest_cart, delivery_option)

    context = build_order_context(Order.objects.get(pk=response.data['id']))
    html_content, _ = mailoutbox[0].alternatives[0]
    assert context['customer_email'] == STOREFRONT_EMAIL
    assert context['customer_phone'] == STOREFRONT_PHONE
    for kind in ('shipping', 'billing'):
        assert context[f'{kind}_name'] == 'John Smith'
        assert context[f'{kind}_line_1'] == 'Main Street 12, 5'
        assert context[f'{kind}_line_2'] == '01001 Kyiv'
        assert context[f'{kind}_line_3'] == ''
        assert context[f'{kind}_country'] == 'Ukraine'
    assert f'mailto:{STOREFRONT_EMAIL}' in html_content
    assert f'tel:{STOREFRONT_PHONE}' in html_content


@pytest.mark.django_db
def test_explicit_email_field_wins_over_the_checkout_session_and_the_address(
        api_client, guest_cart, guest_session, delivery_option, mailoutbox):
    response = guest_order(api_client, guest_cart, delivery_option, email='Explicit@Example.com',
                           phone='+380991112233')

    assert response.status_code == status.HTTP_201_CREATED
    assert recipients(mailoutbox) == [['explicit@example.com']]
    html_content, _ = mailoutbox[0].alternatives[0]
    assert 'tel:+380991112233' in html_content


@pytest.mark.django_db
def test_checkout_session_email_wins_over_the_address(
        api_client, guest_cart, guest_session, delivery_option, mailoutbox):
    response = guest_order(api_client, guest_cart, delivery_option)

    assert response.status_code == status.HTTP_201_CREATED
    assert recipients(mailoutbox) == [[guest_session.email]]
    html_content, _ = mailoutbox[0].alternatives[0]
    assert f'tel:{guest_session.phone}' in html_content


@pytest.mark.django_db
def test_guest_checkout_session_created_through_the_api_is_still_used(
        api_client, guest_cart, delivery_option, mailoutbox):
    started = api_client.post(reverse('guest-checkout-start'), {
        'guestCartToken': guest_cart.token, 'email': 'Session.Buyer@Example.com',
    }, format='json')
    assert started.status_code == status.HTTP_201_CREATED

    response = guest_order(api_client, guest_cart, delivery_option, shipping_address=LEGACY_ADDRESS)

    assert response.status_code == status.HTTP_201_CREATED
    assert recipients(mailoutbox) == [['session.buyer@example.com']]


@pytest.mark.django_db
@pytest.mark.parametrize('blank', ['', None])
def test_blank_email_and_phone_fields_fall_back_to_the_address(
        api_client, guest_cart, delivery_option, mailoutbox, blank):
    response = guest_order(api_client, guest_cart, delivery_option, email=blank, phone=blank)

    assert response.status_code == status.HTTP_201_CREATED
    assert recipients(mailoutbox) == [[STOREFRONT_EMAIL]]
    html_content, _ = mailoutbox[0].alternatives[0]
    assert f'tel:{STOREFRONT_PHONE}' in html_content


@pytest.mark.django_db
def test_email_is_taken_from_the_billing_address_when_shipping_has_none(
        api_client, guest_cart, delivery_option, mailoutbox):
    response = guest_order(api_client, guest_cart, delivery_option, shipping_address=LEGACY_ADDRESS,
                           billing_address=STOREFRONT_ADDRESS)

    assert response.status_code == status.HTTP_201_CREATED
    assert recipients(mailoutbox) == [[STOREFRONT_EMAIL]]


@pytest.mark.django_db
@pytest.mark.parametrize('value', ['not-an-email', 'john@', 'a b@example.com', 12345])
def test_invalid_email_field_is_rejected_before_anything_is_created(
        api_client, guest_cart, delivery_option, mailoutbox, value):
    response = guest_order(api_client, guest_cart, delivery_option, email=value)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'email' in response.json()
    assert Order.objects.count() == 0
    assert mailoutbox == []
    guest_cart.refresh_from_db()
    assert guest_cart.is_active


@pytest.mark.django_db
def test_too_long_phone_field_is_rejected(api_client, guest_cart, delivery_option, mailoutbox):
    response = guest_order(api_client, guest_cart, delivery_option, phone='1' * 33)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'phone' in response.json()
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_email_and_phone_are_write_only_and_not_stored_on_the_order(
        api_client, guest_cart, delivery_option, mailoutbox):
    response = guest_order(api_client, guest_cart, delivery_option, email='write.only@example.com',
                           phone='+380991112233')

    assert response.status_code == status.HTTP_201_CREATED
    assert 'email' not in response.json()
    assert 'phone' not in response.json()
    assert 'write.only@example.com' not in str(response.json())


@pytest.mark.django_db
def test_guest_order_without_any_email_is_created_and_the_gap_is_logged(
        api_client, guest_cart, delivery_option, mailoutbox, caplog):
    with caplog.at_level(logging.WARNING):
        response = guest_order(api_client, guest_cart, delivery_option, shipping_address=LEGACY_ADDRESS)

    assert response.status_code == status.HTTP_201_CREATED
    assert Order.objects.count() == 1
    assert mailoutbox == []
    assert 'recipient email is empty' in caplog.text


@pytest.mark.django_db
def test_order_survives_a_mail_server_failure(api_client, guest_cart, delivery_option, caplog):
    with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=SMTPException('smtp is down')):
        with caplog.at_level(logging.ERROR):
            response = guest_order(api_client, guest_cart, delivery_option)

    assert response.status_code == status.HTTP_201_CREATED
    assert Order.objects.count() == 1
    assert 'Failed to send order confirmation email' in caplog.text


@pytest.mark.django_db
@pytest.mark.parametrize('address', [STOREFRONT_ADDRESS, LEGACY_ADDRESS])
def test_registered_user_still_gets_the_confirmation_at_the_account_email(
        auth_client, user, user_cart, delivery_option, mailoutbox, address):
    response = create_order(auth_client, cart_id=user_cart.id, delivery_option_id=delivery_option.id,
                            shipping_address=address)

    assert response.status_code == status.HTTP_201_CREATED
    assert recipients(mailoutbox) == [[user.email]]
    assert mailoutbox[0].subject == f"Order Confirmation #{response.data['id']}"


@pytest.mark.django_db
def test_registered_user_confirmation_shows_the_phone_and_a_readable_address(
        auth_client, user_cart, delivery_option, mailoutbox):
    response = create_order(auth_client, cart_id=user_cart.id, delivery_option_id=delivery_option.id,
                            shipping_address=STOREFRONT_ADDRESS)

    context = build_order_context(Order.objects.get(pk=response.data['id']))
    assert context['customer_email'] == 'user@example.com'
    assert context['customer_phone'] == STOREFRONT_PHONE
    assert context['shipping_name'] == 'John Smith'
    assert context['shipping_country'] == 'Ukraine'


@pytest.mark.django_db
def test_link_fallbacks_match_the_storefront_routes(settings, delivery_option, product):
    settings.ORDER_EMAIL_VIEW_ORDER_URL_TEMPLATE = ''
    settings.ORDER_EMAIL_PRODUCT_URL_TEMPLATE = ''
    order = Order.objects.create(shipping_address=LEGACY_ADDRESS, delivery_option=delivery_option,
                                 total_amount='74.98')
    OrderItem.objects.create(order=order, product=product, quantity=2, price=product.price)

    context = build_order_context(order)

    frontend_url = settings.FRONTEND_URL.rstrip('/')
    assert context['order_link'] == f'{frontend_url}/profile'
    assert context['items'][0]['url'] == f'{frontend_url}/product/{product.id}'


@pytest.mark.parametrize('address,expected', [
    (
            'Ukraine, John, Smith, Main Street 12, 5, 01001, Kyiv, john@example.com, +380501112233',
            {'name': 'John Smith', 'line_1': 'Main Street 12, 5', 'line_2': '01001 Kyiv', 'line_3': '',
             'country': 'Ukraine'},
    ),
    (
            'Ukraine, John, Smith, Main Street 12, 01001, Kyiv, john@example.com, +380501112233',
            {'name': 'John Smith', 'line_1': 'Main Street 12', 'line_2': '01001 Kyiv', 'line_3': '',
             'country': 'Ukraine'},
    ),
    (
            'Ukraine, John, Smith, Main Street 12, building 3, 5, 01001, Kyiv, john@example.com, +380 (50) 111-22-33',
            {'name': 'John Smith', 'line_1': 'Main Street 12, building 3, 5', 'line_2': '01001 Kyiv', 'line_3': '',
             'country': 'Ukraine'},
    ),
    (LEGACY_ADDRESS, LEGACY_PARTS),
    (LEGACY_ADDRESS + ', oleksandr@example.com', LEGACY_PARTS),
    (LEGACY_ADDRESS + ', oleksandr@example.com, +380501112233', LEGACY_PARTS),
    (
            'Oleksandr, Street 1, Flat 2, Odesa, 65000, Ukraine, oleksandr@example.com',
            {'name': 'Oleksandr', 'line_1': 'Street 1', 'line_2': 'Flat 2', 'line_3': 'Odesa, 65000',
             'country': 'Ukraine'},
    ),
    (
            'Ukraine, John, Smith, Main Street 12, Kyiv, john@example.com, +380501112233',
            {'name': 'Ukraine', 'line_1': 'John', 'line_2': 'Smith', 'line_3': 'Main Street 12', 'country': 'Kyiv'},
    ),
    ('221B Baker Street', {**EMPTY_PARTS, 'line_1': '221B Baker Street'}),
    ('john@example.com', EMPTY_PARTS),
    ('', EMPTY_PARTS),
    (None, EMPTY_PARTS),
])
def test_split_address(address, expected):
    assert split_address(address) == expected


@pytest.mark.parametrize('address,expected', [
    ('A, B, john@example.com, +380501112233', (['A', 'B'], 'john@example.com', '+380501112233')),
    ('A, B, john@example.com', (['A', 'B'], 'john@example.com', '')),
    ('A, B, john@example.com, +380 (50), 111-22-33', (['A', 'B'], 'john@example.com', '+380 (50), 111-22-33')),
    ('A\njohn@example.com;+380501112233', (['A'], 'john@example.com', '+380501112233')),
    (
        'A, first@example.com, B, last@example.com, +380501112233',
        (['A', 'first@example.com', 'B'], 'last@example.com', '+380501112233'),
    ),
    ('A, B, C', (['A', 'B', 'C'], '', '')),
    ('A, John <john@example.com>', (['A', 'John <john@example.com>'], '', '')),
    ('', ([], '', '')),
    (None, ([], '', '')),
])
def test_split_address_contact(address, expected):
    assert split_address_contact(address) == expected


def test_get_address_contact_takes_the_first_address_with_an_email():
    assert get_address_contact(LEGACY_ADDRESS, STOREFRONT_ADDRESS) == ('John.Smith@Example.com', STOREFRONT_PHONE)
    assert get_address_contact(STOREFRONT_ADDRESS, 'x, y, other@example.com') == (
        'John.Smith@Example.com', STOREFRONT_PHONE)
    assert get_address_contact(LEGACY_ADDRESS, '', None) == ('', '')
    assert get_address_contact() == ('', '')
