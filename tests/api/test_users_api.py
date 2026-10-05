import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from users.interfaces.serializers import OAuthLoginSerializer


pytestmark = [pytest.mark.api, pytest.mark.django_db]


def registration_payload(email="signup@example.com"):
    return {
        "email": email,
        "password": "strongpassword123",
        "first_name": "Signup",
        "last_name": "User",
    }


def test_registration_creates_inactive_user_and_sends_activation_email(api_client, user_model):
    response = api_client.post(reverse("register"), registration_payload(), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    user = user_model.objects.get(email="signup@example.com")
    assert not user.is_active
    assert user.check_password("strongpassword123")
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [user.email]
    assert message.from_email == "Dice&Decks Tests <tests@nicedice.invalid>"
    assert message.subject == "Підтвердіть вашу реєстрацію"
    assert f"/api/users/activate/{urlsafe_base64_encode(force_bytes(user.pk))}/" in message.body


def test_registration_rejects_duplicate_email(api_client, user_factory):
    user_factory(email="duplicate@example.com")

    response = api_client.post(
        reverse("register"), registration_payload("duplicate@example.com"), format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error_code"] == "REGISTRATION_FAILED"
    assert "already exists" in str(response.json()["error_message"])
    assert len(mail.outbox) == 0


@pytest.mark.bug
@pytest.mark.django_db(transaction=True)
def test_current_registration_identity_collision_defect_returns_500_without_new_user(
    api_client, user_factory, user_model
):
    user_factory(username="identity-collision@example.com", email="original@example.com")
    api_client.raise_request_exception = False

    response = api_client.post(
        reverse("register"), registration_payload("identity-collision@example.com"), format="json"
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert not user_model.objects.filter(email="identity-collision@example.com").exists()
    assert len(mail.outbox) == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [("email", "not-an-email"), ("password", "short"), ("first_name", "")],
)
def test_registration_rejects_one_malformed_field_without_persistence(
    api_client, user_model, field, value
):
    payload = registration_payload(f"malformed-{field}@example.com")
    payload[field] = value

    response = api_client.post(reverse("register"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error_code"] == "REGISTRATION_FAILED"
    assert field in response.json()["error_message"]
    assert not user_model.objects.filter(email=payload.get("email", "")).exists()
    assert len(mail.outbox) == 0


def test_activation_changes_user_state(api_client, user_factory):
    user = user_factory(is_active=False)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    response = api_client.get(reverse("activate", kwargs={"uidb64": uid, "token": token}))

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.is_active


def test_activation_rejects_invalid_token_without_state_change(api_client, user_factory):
    user = user_factory(is_active=False)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    response = api_client.get(reverse("activate", kwargs={"uidb64": uid, "token": "invalid"}))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    user.refresh_from_db()
    assert not user.is_active


def test_activation_rejects_reused_token_without_changing_active_user(api_client, user_factory):
    user = user_factory(is_active=False)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    url = reverse("activate", kwargs={"uidb64": uid, "token": token})
    assert api_client.get(url).status_code == status.HTTP_200_OK

    repeated = api_client.get(url)

    assert repeated.status_code == status.HTTP_400_BAD_REQUEST
    assert repeated.json() == {"error_code": "TOKEN_INVALID", "error_message": "Link already used"}
    user.refresh_from_db()
    assert user.is_active


def test_resend_activation_sends_one_message(api_client, user_factory):
    user = user_factory(email="inactive@example.com", is_active=False)

    response = api_client.post(reverse("resend-activation"), {"email": user.email}, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [user.email]
    assert mail.outbox[0].subject == "Повторне підтвердження реєстрації"


def test_resend_activation_rejects_active_user(api_client, user_factory):
    user = user_factory(is_active=True)

    response = api_client.post(reverse("resend-activation"), {"email": user.email}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert len(mail.outbox) == 0


def test_forgot_password_sends_message_only_for_existing_user(api_client, user_factory):
    user = user_factory(email="forgot@example.com")

    existing = api_client.post(reverse("forgot-password"), {"email": user.email}, format="json")
    missing = api_client.post(reverse("forgot-password"), {"email": "missing@example.com"}, format="json")

    assert existing.status_code == missing.status_code == status.HTTP_200_OK
    assert existing.json() == missing.json()
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [user.email]
    assert mail.outbox[0].subject == "Скидання пароля"
    assert "/reset-password?uid=" in mail.outbox[0].body


def test_forgot_password_rejects_malformed_email_without_sending(api_client):
    response = api_client.post(reverse("forgot-password"), {"email": "invalid"}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["errors"][0]["attr"] == "email"
    assert len(mail.outbox) == 0


def test_token_login_success_and_failure(api_client, user_factory):
    user = user_factory(email="login@example.com", password="correct-password")

    success = api_client.post(
        reverse("token_obtain_pair"), {"email": user.email, "password": "correct-password"}, format="json"
    )
    failure = api_client.post(
        reverse("token_obtain_pair"), {"email": user.email, "password": "wrong-password"}, format="json"
    )

    assert success.status_code == status.HTTP_200_OK
    assert set(success.json()) >= {"access", "refresh"}
    assert failure.status_code == status.HTTP_401_UNAUTHORIZED


def test_logout_blacklists_valid_refresh_token(api_client, user_factory):
    user = user_factory()
    refresh = RefreshToken.for_user(user)
    api_client.force_authenticate(user=user)

    response = api_client.post(reverse("logout"), {"refresh": str(refresh)}, format="json")

    assert response.status_code == status.HTTP_205_RESET_CONTENT


@pytest.mark.parametrize("payload", [{}, {"refresh": "not-a-token"}])
def test_logout_rejects_missing_or_invalid_refresh_token(api_client, user_factory, payload):
    api_client.force_authenticate(user=user_factory())

    response = api_client.post(reverse("logout"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.bug
def test_current_reset_password_defect_rejects_documented_token_payload(api_client, user_factory):
    user = user_factory()
    payload = {
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
        "new_password": "newpassword123",
    }

    response = api_client.post(
        reverse("reset-password"), payload, format="json", HTTP_ACCEPT="application/json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "This field is required."
    user.refresh_from_db()
    assert not user.check_password("newpassword123")


def test_oauth_google_success_isolated_from_provider(api_client, monkeypatch, user_model):
    monkeypatch.setattr(
        OAuthLoginSerializer,
        "_validate_google_token",
        lambda self, token: (
            {"email": "oauth@example.com", "first_name": "OAuth", "last_name": "User", "picture": ""},
            None,
        ),
    )

    response = api_client.post(
        reverse("oauth_login"), {"provider": "google", "access_token": "fake-token"}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert set(response.json()) == {"access_token", "refresh_token", "user"}
    assert user_model.objects.filter(email="oauth@example.com").exists()


def test_protected_user_list_rejects_anonymous_request(api_client):
    response = api_client.get(reverse("user-list-create"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.bug
def test_current_registration_defect_persists_inactive_user_after_email_failure(
    api_client, monkeypatch, user_model
):
    monkeypatch.setattr(
        "users.interfaces.views.send_mail",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("mail unavailable")),
    )
    api_client.raise_request_exception = False

    response = api_client.post(
        reverse("register"), registration_payload("mail-failure@example.com"), format="json"
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    user = user_model.objects.get(email="mail-failure@example.com")
    assert not user.is_active


def test_resend_activation_maps_email_failure_to_500(api_client, user_factory, monkeypatch):
    user = user_factory(email="resend-failure@example.com", is_active=False)
    monkeypatch.setattr(
        "src.users.interfaces.views.send_mail",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("mail unavailable")),
    )

    response = api_client.post(reverse("resend-activation"), {"email": user.email}, format="json")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == {
        "detail": "Сталася помилка при надсиланні листа. Будь ласка, спробуйте пізніше."
    }


@pytest.mark.parametrize("payload", [{}, {"email": "unknown@example.com"}])
def test_resend_activation_rejects_missing_or_unknown_email(api_client, payload):
    response = api_client.post(reverse("resend-activation"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert len(mail.outbox) == 0


def test_oauth_rejects_unsupported_provider_without_network(api_client):
    response = api_client.post(
        reverse("oauth_login"), {"provider": "github", "access_token": "fake"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["errors"][0]["attr"] == "provider"


def test_oauth_rejects_provider_error(api_client, monkeypatch):
    monkeypatch.setattr(
        OAuthLoginSerializer,
        "_validate_google_token",
        lambda self, token: (None, "Invalid Google token: expired"),
    )

    response = api_client.post(
        reverse("oauth_login"), {"provider": "google", "access_token": "fake"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "type": "validation_error",
        "errors": [{"code": "invalid", "detail": "Invalid Google token: expired", "attr": "non_field_errors"}],
    }


def test_oauth_rejects_inactive_existing_user(api_client, user_factory, monkeypatch):
    user_factory(email="disabled-oauth@example.com", is_active=False)
    monkeypatch.setattr(
        OAuthLoginSerializer,
        "_validate_google_token",
        lambda self, token: (
            {"email": "disabled-oauth@example.com", "first_name": "", "last_name": "", "picture": ""},
            None,
        ),
    )

    response = api_client.post(
        reverse("oauth_login"), {"provider": "google", "access_token": "fake"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "User account is disabled."


def test_oauth_rejects_provider_profile_without_email_without_creating_user(
    api_client, user_model, monkeypatch
):
    monkeypatch.setattr(
        OAuthLoginSerializer,
        "_validate_google_token",
        lambda self, token: ({"email": None, "first_name": "No", "last_name": "Email"}, None),
    )

    response = api_client.post(
        reverse("oauth_login"), {"provider": "google", "access_token": "fake"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["errors"][0]["detail"] == "Email not provided by OAuth provider"
    assert not user_model.objects.exists()


@pytest.mark.bug
def test_current_resend_activation_validation_defect_returns_500_for_non_object_json(
    api_client, user_model
):
    api_client.raise_request_exception = False

    response = api_client.post(reverse("resend-activation"), [None, None], format="json")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert not user_model.objects.exists()
