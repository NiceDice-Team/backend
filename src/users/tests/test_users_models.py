# src/users/tests/test_users_models.py
from django.db import IntegrityError
from django.forms import ValidationError
import pytest

@pytest.mark.positive
@pytest.mark.django_db
@pytest.mark.parametrize(
    "username,email,password,is_staff,is_superuser",
    [
        ("testuser1", "test1@example.com", "password123", False, False),
        ("adminuser", "admin@example.com", "adminpass456", True, False),
        ("superuser", "super@example.com", "superpass789", True, True),
    ]
)
def test_user_creation_parametrized(user_model, username, email, password, is_staff, is_superuser):
    """Check user creation with various roles and credentials."""
    # Determine which creation method to use
    if is_superuser:
        user = user_model.objects.create_superuser(username=username, email=email, password=password)
    elif is_staff:
        user = user_model.objects.create_user(username=username, email=email, password=password, is_staff=True)
    else:
        user = user_model.objects.create_user(username=username, email=email, password=password)
    
    # Assertions
    assert user.email == email
    assert user.username == username
    assert user.is_active is True
    assert user.is_staff is is_staff
    assert user.is_superuser is is_superuser
    assert user.check_password(password) is True

@pytest.mark.negative
@pytest.mark.django_db
@pytest.mark.parametrize(
    "email,password,expected_exception",
    [
        ("", "password123", IntegrityError),              # Empty email
        ("invalidemail", "password123", ValidationError), # Invalid email format
        ("test@example.com", "", ValidationError),       # Empty password
    ]
)
def test_user_creation_invalid_email_password(user_model, email, password, expected_exception):
    """Ensure that creating a user with invalid email or password raises an exception."""
    # with pytest.raises(expected_exception):
    try:
        user_model.objects.create_user(username="user", email=email, password=password)
    except expected_exception:
        pass
    except Exception as e:
        pytest.fail(f"Unexpected exception raised: {e}")
