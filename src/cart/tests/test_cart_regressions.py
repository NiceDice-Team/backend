import pytest
from django.urls import reverse
from rest_framework import status

from cart.infrastructure.models import Cart, CartItem, GuestCart, GuestCartItem
from cart.interfaces.serializers import QUANTITY_MAX

ANONYMOUS_CART_REQUESTS = [
    ('get', 'cart-list-add'),
    ('post', 'cart-item'),
    ('patch', 'cart-item'),
    ('delete', 'cart-item'),
    ('delete', 'cart-clear'),
]


def send(client, method, url, payload):
    if method == 'get':
        return client.get(url)
    return getattr(client, method)(url, payload, format='json')


@pytest.mark.django_db
@pytest.mark.parametrize('method,route', ANONYMOUS_CART_REQUESTS)
def test_anonymous_caller_cannot_manage_another_users_cart(api_client, user, user_cart, product, method, route):
    url = reverse(route) + f'?user_id={user.id}&product_id={product.id}'
    payload = {'user': user.id, 'user_id': user.id, 'product_id': product.id, 'quantity': 7}

    response = send(api_client, method, url, payload)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    item = CartItem.objects.get(cart=user_cart)
    assert item.quantity == 1
    assert CartItem.objects.count() == 1


@pytest.mark.django_db
def test_cart_ignores_owner_identifiers_supplied_by_the_caller(auth_client, user, other_user, product):
    other_cart = Cart.objects.create(user=other_user, is_active=True)
    CartItem.objects.create(cart=other_cart, product=product, quantity=3, sku='X', title='X')

    created = auth_client.post(
        reverse('cart-item'),
        {'user': other_user.id, 'user_id': other_user.id, 'product_id': product.id, 'quantity': 2},
        format='json',
    )

    assert created.status_code == status.HTTP_201_CREATED
    assert CartItem.objects.get(cart__user=user, product=product).quantity == 2
    assert CartItem.objects.get(cart=other_cart).quantity == 3

    listed = auth_client.get(reverse('cart-list-add'), {'user_id': other_user.id})

    assert listed.status_code == status.HTTP_200_OK
    assert listed.data['user_id'] == user.id
    assert [item['quantity'] for item in listed.data['items']] == [2]


@pytest.mark.django_db
def test_cart_update_and_delete_never_touch_another_users_items(auth_client, other_user, product):
    other_cart = Cart.objects.create(user=other_user, is_active=True)
    CartItem.objects.create(cart=other_cart, product=product, quantity=3, sku='X', title='X')

    updated = auth_client.patch(
        reverse('cart-item'),
        {'user_id': other_user.id, 'product_id': product.id, 'quantity': 9},
        format='json',
    )
    removed = auth_client.delete(reverse('cart-item'), {'user_id': other_user.id, 'product_id': product.id},
                                 format='json')
    cleared = auth_client.delete(reverse('cart-clear') + f'?user_id={other_user.id}')

    assert updated.status_code == status.HTTP_404_NOT_FOUND
    assert removed.status_code == status.HTTP_404_NOT_FOUND
    assert cleared.status_code == status.HTTP_204_NO_CONTENT
    assert CartItem.objects.get(cart=other_cart).quantity == 3


@pytest.mark.django_db
def test_cart_add_item_without_quantity_defaults_to_one(auth_client, product):
    first = auth_client.post(reverse('cart-item'), {'product_id': product.id}, format='json')
    second = auth_client.post(reverse('cart-item'), {'product_id': product.id}, format='json')

    assert first.status_code == status.HTTP_201_CREATED
    assert first.data['quantity'] == 1
    assert second.status_code == status.HTTP_200_OK
    assert second.data['quantity'] == 2


@pytest.mark.django_db
def test_cart_add_item_rejects_quantity_beyond_integer_range(auth_client, user, product):
    cart = Cart.objects.create(user=user, is_active=True)
    CartItem.objects.create(cart=cart, product=product, quantity=QUANTITY_MAX, sku='X', title='X')

    response = auth_client.post(reverse('cart-item'), {'product_id': product.id, 'quantity': 1}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert CartItem.objects.get(cart=cart, product=product).quantity == QUANTITY_MAX


@pytest.mark.django_db
@pytest.mark.parametrize('quantity', [0, -1, QUANTITY_MAX + 1])
def test_cart_add_item_rejects_out_of_range_quantity(auth_client, product, quantity):
    response = auth_client.post(reverse('cart-item'), {'product_id': product.id, 'quantity': quantity},
                                format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not CartItem.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize('field', ['attrs', 'metadata'])
@pytest.mark.parametrize('encoding,value', [('json', None), ('multipart', 'null')])
def test_cart_add_item_rejects_null_in_json_columns(auth_client, product, field, encoding, value):
    payload = {'product_id': product.id, 'quantity': 1, field: value}

    response = auth_client.post(reverse('cart-item'), payload, format=encoding)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not CartItem.objects.exists()


@pytest.mark.django_db
def test_cart_add_item_accepts_plain_text_for_free_form_json_columns_in_forms(auth_client, product):
    response = auth_client.post(
        reverse('cart-item'),
        {'product_id': product.id, 'quantity': 1, 'metadata': 'gift wrap', 'attrs': '{"color": "red"}'},
        format='multipart',
    )

    assert response.status_code == status.HTTP_201_CREATED
    item = CartItem.objects.get(product=product)
    assert item.metadata == 'gift wrap'
    assert item.attrs == {'color': 'red'}


@pytest.mark.django_db
def test_cart_remove_and_update_report_missing_products_as_not_found(auth_client):
    removed = auth_client.delete(reverse('cart-item'), {'product_id': 999999}, format='json')
    updated = auth_client.patch(reverse('cart-item'), {'product_id': 999999, 'quantity': 2}, format='json')

    assert removed.status_code == status.HTTP_404_NOT_FOUND
    assert updated.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_cart_remove_requires_product_id(auth_client):
    blank = auth_client.delete(reverse('cart-item') + '?product_id=')
    missing = auth_client.delete(reverse('cart-item'))

    assert blank.status_code == status.HTTP_400_BAD_REQUEST
    assert missing.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_cart_patch_without_required_fields_is_a_validation_error(auth_client):
    response = auth_client.patch(reverse('cart-item'), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response['Content-Type'].startswith('application/json')


@pytest.mark.django_db
def test_guest_cart_add_item_without_quantity_defaults_to_one(api_client, product):
    cart = GuestCart.create_guest_cart()

    response = api_client.post(
        reverse('guest-cart-item'), {'product_id': product.id}, format='json', HTTP_X_GUEST_TOKEN=cart.token
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['quantity'] == 1
    assert GuestCartItem.objects.get(guest_cart=cart).quantity == 1


@pytest.mark.django_db
def test_guest_checkout_start_accepts_token_from_body_or_header_only(api_client, guest_cart):
    url = reverse('guest-checkout-start')
    payload = {'email': 'guest@example.com'}

    missing = api_client.post(url, payload, format='json')
    from_header = api_client.post(url, payload, format='json', HTTP_X_GUEST_TOKEN=guest_cart.token)
    from_body = api_client.post(url, {**payload, 'guestCartToken': guest_cart.token}, format='json')

    assert missing.status_code == status.HTTP_400_BAD_REQUEST
    assert missing.data['code'] == 'GUEST_CART_TOKEN_REQUIRED'
    assert from_header.status_code == status.HTTP_201_CREATED
    assert from_body.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_guest_checkout_start_rejects_non_object_body(api_client):
    response = api_client.generic(
        'POST', reverse('guest-checkout-start'), '[null, null]', content_type='application/json'
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response['Content-Type'].startswith('application/json')
