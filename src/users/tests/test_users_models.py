# src/users/tests/test_users_models.py
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
    "username,email,expected_exception",
    [
        ("", "test@example.com", ValueError),                   # Empty username
        ("testuser", "invalidemail",  ValidationError),         # Invalid email format
        ("testuser", "", ValidationError),                      # Empty email
    ]
)
def test_user_creation_validation(user_model, username, email, expected_exception):
    """Ensure that creating a user with invalid email or password raises an exception."""
    with pytest.raises(expected_exception):
        user = user_model.objects.create_user(username=username, email=email)
        user.full_clean()  # Викликає ValidationError для email/пароля
        user.save()
