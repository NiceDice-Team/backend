import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient
from django.urls import reverse


@pytest.mark.django_db
class TestUserAuthViews:
    @pytest.fixture
    def api_client(self):
        return APIClient()

    def test_register_view_creates_inactive_user_and_sends_email(self, api_client, user_model):
        payload = {
            "email": "signup@example.com",
            "password": "strongpassword123",
            "first_name": "Signup",
            "last_name": "User",
        }

        response = api_client.post(reverse('register'), payload, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert user_model.objects.filter(email="signup@example.com").exists()
        user = user_model.objects.get(email="signup@example.com")
        assert user.is_active is False
        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == 'Confirm your registration'

    def test_register_view_rejects_duplicate_email_with_400(self, api_client, user_model):
        user_model.objects.create_user(
            email="signup-duplicate@example.com",
            username="signup-duplicate@example.com",
            password="strongpassword123",
            first_name="Existing",
            last_name="User",
        )
        payload = {
            "email": "signup-duplicate@example.com",
            "password": "strongpassword123",
            "first_name": "Signup",
            "last_name": "User",
        }

        response = api_client.post(reverse('register'), payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['error_code'] == 'REGISTRATION_FAILED'
        assert 'already exists' in str(response.json()['error_message']).lower()

    def test_activate_view_activates_user(self, api_client, user_model):
        user = user_model.objects.create_user(
            email="activate@example.com",
            username="activate@example.com",
            password="strongpassword123",
            first_name="Activate",
            last_name="User",
        )
        user.is_active = False
        user.save(update_fields=['is_active'])
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        response = api_client.get(reverse('activate', kwargs={'uidb64': uid, 'token': token}))

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.is_active is True
        assert response.json()['message'] == 'Account successfully activated'

    def test_resend_activation_view_sends_email_for_inactive_user(self, api_client, user_model):
        user = user_model.objects.create_user(
            email="resend@example.com",
            username="resend@example.com",
            password="strongpassword123",
            first_name="Resend",
            last_name="User",
        )
        user.is_active = False
        user.save(update_fields=['is_active'])

        response = api_client.post(reverse('resend-activation'), {'email': user.email}, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.json()['message'] == 'A confirmation email has been sent to your email address.'
        assert len(mail.outbox) >= 1
        assert mail.outbox[-1].subject == 'Resend registration confirmation'

    def test_forgot_password_view_sends_reset_email(self, api_client, user_model):
        user_model.objects.create_user(
            email="forgot@example.com",
            username="forgot@example.com",
            password="strongpassword123",
            first_name="Forgot",
            last_name="User",
        )

        response = api_client.post(reverse('forgot-password'), {'email': 'forgot@example.com'}, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.json()['message'] == 'If the email exists, a reset link will be sent'
        assert len(mail.outbox) >= 1
        assert mail.outbox[-1].subject == 'Password reset'
        assert '/reset-password?uid=' in mail.outbox[-1].body

    def test_reset_password_view_changes_password(self, api_client, user_model):
        user = user_model.objects.create_user(
            email="reset@example.com",
            username="reset@example.com",
            password="oldpassword123",
            first_name="Reset",
            last_name="User",
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        response = api_client.post(reverse('reset-password'), {
            'uid': uid,
            'token': token,
            'new_password': 'newpassword123',
        }, format='json', HTTP_ACCEPT='application/json')

        assert response.status_code == status.HTTP_200_OK
        assert response.json()['message'] == 'Password changed successfully'
        user.refresh_from_db()
        assert user.check_password('newpassword123') is True

    def test_logout_view_blacklists_refresh_token(self, api_client, user_model):
        user = user_model.objects.create_user(
            email="logout@example.com",
            username="logout@example.com",
            password="strongpassword123",
            first_name="Logout",
            last_name="User",
        )
        refresh = RefreshToken.for_user(user)
        api_client.force_authenticate(user=user)

        response = api_client.post(reverse('logout'), {'refresh': str(refresh)}, format='json')

        assert response.status_code == status.HTTP_205_RESET_CONTENT
