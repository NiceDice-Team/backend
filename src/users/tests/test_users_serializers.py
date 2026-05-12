import pytest
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.interfaces.serializers import (
    ForgotPasswordSerializer,
    OAuthLoginSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
)


@pytest.mark.django_db
def test_register_serializer_creates_user(user_model):
    serializer = RegisterSerializer(data={
        "email": "newuser@example.com",
        "password": "strongpassword123",
        "first_name": "New",
        "last_name": "User",
    })

    assert serializer.is_valid(), serializer.errors

    user = serializer.save()

    assert user.email == "newuser@example.com"
    assert user.check_password("strongpassword123") is True


@pytest.mark.django_db
def test_register_serializer_rejects_duplicate_email(user_model):
    user_model.objects.create_user(
        email="existing@example.com",
        username="existing@example.com",
        password="strongpassword123",
        first_name="Existing",
        last_name="User",
    )

    serializer = RegisterSerializer(data={
        "email": "existing@example.com",
        "password": "strongpassword123",
        "first_name": "New",
        "last_name": "User",
    })

    assert serializer.is_valid() is False
    assert "already exists" in str(serializer.errors["email"][0])


@pytest.mark.django_db
def test_forgot_password_serializer_validates_email():
    serializer = ForgotPasswordSerializer(data={"email": "invalid-email"})

    assert serializer.is_valid() is False
    assert "Enter a valid email address." in str(serializer.errors["email"][0])


@pytest.mark.django_db
def test_reset_password_serializer_updates_password(user_model):
    user = user_model.objects.create_user(
        email="reset@example.com",
        username="reset@example.com",
        password="oldpassword123",
        first_name="Reset",
        last_name="User",
    )
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    serializer = ResetPasswordSerializer(data={
        "uid": uid,
        "token": token,
        "new_password": "newpassword123",
    })

    assert serializer.is_valid(), serializer.errors
    updated_user = serializer.save()

    user.refresh_from_db()
    assert updated_user.pk == user.pk
    assert user.check_password("newpassword123") is True


@pytest.mark.django_db
def test_reset_password_serializer_rejects_invalid_token(user_model):
    user = user_model.objects.create_user(
        email="reset-invalid@example.com",
        username="reset-invalid@example.com",
        password="oldpassword123",
        first_name="Reset",
        last_name="User",
    )
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    serializer = ResetPasswordSerializer(data={
        "uid": uid,
        "token": "invalid-token",
        "new_password": "newpassword123",
    })

    assert serializer.is_valid() is False
    assert "Invalid or expired token" in str(serializer.errors["non_field_errors"][0])


@pytest.mark.django_db
def test_oauth_login_serializer_rejects_unsupported_provider():
    serializer = OAuthLoginSerializer(data={
        "provider": "github",
        "access_token": "token",
    })

    assert serializer.is_valid() is False
    assert "is not a valid choice" in str(serializer.errors["provider"][0])
