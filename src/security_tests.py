import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
def test_sitemap_has_strict_csp_and_nosniff(client):
    response = client.get(reverse('sitemap-xml'))

    assert response.status_code == status.HTTP_200_OK
    assert response['Content-Security-Policy'] == "default-src 'none';"
    assert response['X-Content-Type-Options'] == 'nosniff'
    assert b'<urlset' in response.content


@pytest.mark.django_db
def test_api_cors_allows_configured_frontend_origin(client):
    response = client.options(
        reverse('guest-cart'),
        HTTP_ORIGIN='http://localhost:3000',
        HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
    )

    assert response['Access-Control-Allow-Origin'] == 'http://localhost:3000'


@pytest.mark.django_db
def test_api_cors_rejects_unknown_origin(client):
    response = client.options(
        reverse('guest-cart'),
        HTTP_ORIGIN='https://attacker.example',
        HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
    )

    assert 'Access-Control-Allow-Origin' not in response


@pytest.mark.django_db
def test_guest_cart_admin_endpoint_requires_admin(api_client, user):
    api_client.force_authenticate(user=user)
    response = api_client.get(reverse('guest-cart-list-all'))

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_guest_cart_admin_endpoint_allows_staff(api_client, user, guest_cart):
    user.is_staff = True
    user.save(update_fields=['is_staff'])
    api_client.force_authenticate(user=user)
    response = api_client.get(reverse('guest-cart-list-all'))

    assert response.status_code == status.HTTP_200_OK
    assert response.data['results'][0]['token'] == guest_cart.token
