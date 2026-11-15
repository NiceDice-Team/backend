import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestAuthWithGuestCart:
    def test_login_with_guest_cart_merge(self, api_client, user, guest_cart):
        """Test login merges guest cart to user cart"""
        url = reverse('token_obtain_pair')
        data = {
            'email': user.email,
            'password': 'testpass123',
            'guest_cart_id': guest_cart.id
        }
        response = api_client.post(url, data)
        assert response.status_code == 200
        assert 'cart_id' in response.data
        assert response.data['cart_id'] is not None

    def test_login_user_not_found(self, api_client):
        """Test login returns USER_NOT_FOUND code"""
        url = reverse('token_obtain_pair')
        data = {'email': 'nonexistent@example.com', 'password': 'testpass123'}
        response = api_client.post(url, data)
        assert response.status_code == 400
        assert response.data.get('code') == 'USER_NOT_FOUND'

    def test_login_invalid_password(self, api_client, user):
        """Test login returns INVALID_PASSWORD code"""
        url = reverse('token_obtain_pair')
        data = {'email': user.email, 'password': 'wrongpassword'}
        response = api_client.post(url, data)
        assert response.status_code == 400
        assert response.data.get('code') == 'INVALID_PASSWORD'

    def test_guest_checkout_start(self, api_client, guest_cart):
        """Test guest checkout session creation"""
        url = reverse('guest-checkout-start')
        data = {
            'guestCartToken': guest_cart.token,
            'email': 'guest@example.com',
            'phone': '+380123456789'
        }
        response = api_client.post(url, data)
        assert response.status_code == 201
        assert 'guestCheckoutToken' in response.data
        assert 'expiresAt' in response.data

    def test_unified_checkout_auth_user(self, api_client, user, user_cart):
        """Test checkout start for authenticated user"""
        api_client.force_authenticate(user=user)
        url = reverse('checkout-start')
        data = {'cartId': user_cart.id}
        response = api_client.post(url, data)
        assert response.status_code == 200
        assert response.data['userType'] == 'authenticated'

    def test_unified_checkout_guest(self, api_client, guest_session):
        """Test checkout start for guest user"""
        url = reverse('checkout-start')
        data = {'guestCheckoutToken': guest_session.session_token}
        response = api_client.post(url, data)
        assert response.status_code == 200
        assert response.data['userType'] == 'guest'
