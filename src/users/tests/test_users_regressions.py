from smtplib import SMTPException
from unittest.mock import patch

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status

REGISTER_PAYLOAD = {
    'email': 'mail-failure@example.com',
    'password': 'strongpassword123',
    'password_confirm': 'strongpassword123',
    'first_name': 'Mail',
    'last_name': 'Failure',
    'privacy_policy': True,
}


def reset_payload(account, **overrides):
    payload = {
        'uid': urlsafe_base64_encode(force_bytes(account.pk)),
        'token': default_token_generator.make_token(account),
        'new_password': 'newpassword123',
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_reset_password_accepts_the_documented_token_payload(api_client, user):
    response = api_client.post(reverse('reset-password'), reset_payload(user), format='json',
                               HTTP_ACCEPT='application/json')

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.check_password('newpassword123')


@pytest.mark.django_db
def test_reset_password_still_accepts_the_legacy_access_token_name(api_client, user):
    payload = reset_payload(user)
    payload['access_token'] = payload.pop('token')

    response = api_client.post(reverse('reset-password'), payload, format='json')

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.check_password('newpassword123')


@pytest.mark.django_db
def test_reset_password_token_cannot_be_reused(api_client, user):
    payload = reset_payload(user)

    first = api_client.post(reverse('reset-password'), payload, format='json')
    second = api_client.post(reverse('reset-password'), {**payload, 'new_password': 'anotherpass456'}, format='json')

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_400_BAD_REQUEST
    user.refresh_from_db()
    assert user.check_password('newpassword123')


@pytest.mark.django_db
@pytest.mark.parametrize('override', [
    {'token': 'not-a-real-token'},
    {'uid': 'not-a-uid'},
    {'uid': urlsafe_base64_encode(b'999999')},
    {'new_password': 'short'},
])
def test_reset_password_rejects_invalid_input_with_controlled_errors(api_client, user, override):
    response = api_client.post(reverse('reset-password'), reset_payload(user, **override), format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response['Content-Type'].startswith('application/json')
    user.refresh_from_db()
    assert user.check_password('testpass123')


@pytest.mark.django_db
@pytest.mark.parametrize('body', ['[null, null]', '"text"', 'null', '1'])
def test_reset_password_rejects_non_object_bodies(api_client, body):
    response = api_client.generic('POST', reverse('reset-password'), body, content_type='application/json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_reset_password_redirect_without_query_goes_to_the_configured_frontend(api_client, settings):
    settings.FRONTEND_URL = 'https://frontend.example.test'

    response = api_client.get(reverse('reset-password'))

    assert response.status_code == status.HTTP_302_FOUND
    assert response['Location'].startswith('https://frontend.example.test/forgot-password?')


@pytest.mark.django_db
def test_registration_is_rolled_back_when_the_activation_email_fails(api_client, user_model):
    with patch('users.emails.send_mail', side_effect=SMTPException('provider down')):
        failed = api_client.post(reverse('register'), REGISTER_PAYLOAD, format='json')

    assert failed.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert failed.data['error_code'] == 'EMAIL_DELIVERY_FAILED'
    assert not user_model.objects.filter(email=REGISTER_PAYLOAD['email']).exists()
    assert len(mail.outbox) == 0

    retried = api_client.post(reverse('register'), REGISTER_PAYLOAD, format='json')

    assert retried.status_code == status.HTTP_201_CREATED
    assert user_model.objects.filter(email=REGISTER_PAYLOAD['email'], is_active=False).count() == 1
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_registration_is_rolled_back_when_the_backend_accepts_nothing(api_client, user_model):
    with patch('users.emails.send_mail', return_value=0):
        response = api_client.post(reverse('register'), REGISTER_PAYLOAD, format='json')

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert not user_model.objects.filter(email=REGISTER_PAYLOAD['email']).exists()


@pytest.mark.django_db
def test_registration_rejects_an_email_that_is_already_a_username(api_client, user_model):
    user_model.objects.create_user(
        username='identity-collision@example.com', email='someone-else@example.com', password='testpass123'
    )
    payload = {**REGISTER_PAYLOAD, 'email': 'identity-collision@example.com'}

    response = api_client.post(reverse('register'), payload, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not user_model.objects.filter(email='identity-collision@example.com').exists()
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_registration_rejects_an_email_that_differs_only_by_case(api_client, user):
    payload = {**REGISTER_PAYLOAD, 'email': user.email.upper()}

    response = api_client.post(reverse('register'), payload, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_registration_generates_a_unique_username_for_equal_local_parts(api_client, user_model):
    user_model.objects.create_user(username='shared', email='shared@one.example', password='testpass123')
    payload = {**REGISTER_PAYLOAD, 'email': 'shared@two.example'}

    response = api_client.post(reverse('register'), payload, format='json')

    assert response.status_code == status.HTTP_201_CREATED
    assert user_model.objects.get(email='shared@two.example').username != 'shared'


@pytest.mark.django_db
@pytest.mark.parametrize('field', ['first_name', 'last_name'])
@pytest.mark.parametrize('value', ['', '   ', 'John3', 'Jo<script>', 'x' * 151])
def test_registration_rejects_invalid_names(api_client, user_model, field, value):
    response = api_client.post(reverse('register'), {**REGISTER_PAYLOAD, field: value}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not user_model.objects.filter(email=REGISTER_PAYLOAD['email']).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('body', ['[null, null]', '"text"', 'null', '1'])
def test_register_rejects_non_object_bodies(api_client, user_model, body):
    response = api_client.generic('POST', reverse('register'), body, content_type='application/json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert user_model.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize('body', ['[null, null]', '"text"', 'null', '1', '[]'])
def test_resend_activation_rejects_non_object_bodies(api_client, user_model, body):
    response = api_client.generic('POST', reverse('resend-activation'), body, content_type='application/json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response['Content-Type'].startswith('application/json')
    assert user_model.objects.count() == 0
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_resend_activation_rejects_non_string_email(api_client):
    response = api_client.post(reverse('resend-activation'), {'email': ['a@example.com']}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_token_endpoint_reports_missing_credentials_as_validation_errors(api_client):
    empty = api_client.post(reverse('token_obtain_pair'), {}, format='json')
    blank = api_client.post(reverse('token_obtain_pair'), {'email': '', 'password': ''}, format='json')

    assert empty.status_code == status.HTTP_400_BAD_REQUEST
    assert blank.status_code == status.HTTP_400_BAD_REQUEST
    assert response_fields(empty) >= {'email', 'password'}


def response_fields(response):
    return {error['attr'] for error in response.data['errors']}


@pytest.mark.django_db
def test_refresh_endpoint_reports_invalid_tokens_as_unauthorized(api_client):
    response = api_client.post(reverse('token_refresh'), {'refresh': 'garbage'}, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response['Content-Type'].startswith('application/json')


@pytest.mark.django_db
def test_user_admin_endpoints_stay_closed_to_regular_users(auth_client, api_client):
    assert api_client.get(reverse('user-list-create')).status_code == status.HTTP_401_UNAUTHORIZED
    assert auth_client.get(reverse('user-list-create')).status_code == status.HTTP_403_FORBIDDEN
