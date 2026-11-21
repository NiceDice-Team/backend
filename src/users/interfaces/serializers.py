import re
from django.db import transaction
from django.utils import timezone

import requests
from cart.infrastructure.models import Cart, CartItem, GuestCart, GuestCheckoutSession
from common.fields import AcceptedBooleanField, PersonNameField, StrongPasswordField
from common.serializers import ExampleIgnoringModelSerializer
from common.validation import INT64_MAX
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email, RegexValidator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from users.services import find_user_by_email, generate_unique_username

UserModel = get_user_model()
EMAIL_PATTERN = re.compile(
    r"^(?=.{6,254}$)(?=.{1,64}@)[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$"
)

name_validator = RegexValidator(
    regex=r'^[a-zA-Z\s\'-]+$',
    message=_('Invalid name.'),
    code='invalid_name'
)


class UserSerializer(ExampleIgnoringModelSerializer):
    admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserModel
        fields = ['id', 'email', 'first_name', 'last_name', 'date_joined', 'admin']
        read_only_fields = ['date_joined', 'admin']
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': False},
            'last_name': {'required': False},
        }

    def create(self, validated_data):
        validated_data['username'] = generate_unique_username(validated_data['email'].split('@')[0])
        user = UserModel(**validated_data)
        user.set_unusable_password()
        user.save()
        return user


class PatchedUserSerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = UserModel
        fields = ['email', 'first_name', 'last_name']
        extra_kwargs = {
            'email': {'required': False},
            'first_name': {'required': False},
            'last_name': {'required': False},
        }


class RegisterSerializer(ExampleIgnoringModelSerializer):
    email = serializers.EmailField(required=True, max_length=254)
    password = StrongPasswordField(write_only=True, min_length=8, max_length=128)
    first_name = PersonNameField(required=True, max_length=150, min_length=1)
    last_name = PersonNameField(required=True, max_length=150, min_length=1)
    password_confirm = serializers.CharField(write_only=True, required=True, max_length=128)
    privacy_policy = AcceptedBooleanField(
        write_only=True,
        required=True,
        error_messages={
            'required': _('You must agree to the Privacy Policy')
        }
    )
    subscribe_news = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = UserModel
        fields = ['id', 'email', 'password', 'first_name', 'last_name', 'subscribe_news',
                  'password_confirm', 'privacy_policy']
        read_only_fields = ['id']
        extra_kwargs = {
            'first_name': {
                'required': True,
                'min_length': 1,
                'max_length': 150,
                'validators': [name_validator],
            },
            'last_name': {
                'required': True,
                'min_length': 1,
                'max_length': 150,
                'validators': [name_validator],
            },
        }

    def validate_first_name(self, value):
        # Перевірка довжини
        if not (1 <= len(value) <= 150):
            raise serializers.ValidationError("Invalid first name")

        # Перевірка на наявність цифр (заборонено)
        if any(c.isdigit() for c in value):
            raise serializers.ValidationError("Invalid first name")

        # Перевірка на допустимі символи (латиниця, ', -, пробіл)
        if not re.match(r'^[a-zA-Z\s\'\-]+$', value):
            raise serializers.ValidationError("Invalid first name")

        return value.strip()

    def validate_last_name(self, value):
        # Перевірка довжини
        if not (1 <= len(value) <= 150):
            raise serializers.ValidationError("Invalid last name")

        # Перевірка на наявність цифр (заборонено)
        if any(c.isdigit() for c in value):
            raise serializers.ValidationError("Invalid last name")

        # Перевірка на допустимі символи (латиниця, ', -, пробіл)
        if not re.match(r'^[a-zA-Z\s\'\-]+$', value):
            raise serializers.ValidationError("Invalid last name")

        return value.strip()

    def validate_email(self, value):
        # Базова валідація формату email
        try:
            validate_email(value)
        except DjangoValidationError:
            raise serializers.ValidationError("Invalid email")

        # Додаткова перевірка за патерном
        if not EMAIL_PATTERN.match(value):
            raise serializers.ValidationError("Invalid email")

        # Перевірка на унікальність
        normalized = value.lower().strip()
        if UserModel.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("User with this email already exists")
        if UserModel.objects.filter(username__iexact=normalized).exists():
            raise serializers.ValidationError("User with this email already exists")

        return normalized

    def validate_password(self, value):
        # Перевірка довжини
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters")

        if len(value) > 128:
            raise serializers.ValidationError("Password must be at most 128 characters")

        # Перевірка на наявність хоча б однієї літери
        if not any(c.isalpha() for c in value):
            raise serializers.ValidationError("Password must contain at least one letter")

        # Перевірка на наявність хоча б однієї цифри
        if not any(c.isdigit() for c in value):
            raise serializers.ValidationError("Password must contain at least one digit")

        # Заборонені символи: пробіли
        if ' ' in value:
            raise serializers.ValidationError("Password cannot contain spaces")

        # Заборонені символи: кирилиця, emoji (не-ASCII)
        try:
            value.encode('ascii')
        except UnicodeEncodeError:
            raise serializers.ValidationError("Password can only contain ASCII characters")

        return value

    def validate(self, attrs):
        # Перевірка збігу паролів
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': "Passwords do not match"
            })

        # Перевірка прапорця Privacy Policy
        if not attrs.get('privacy_policy'):
            raise serializers.ValidationError({
                'privacy_policy': "You must agree to the Privacy Policy"
            })

        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        validated_data.pop('privacy_policy')
        password = validated_data.pop('password')

        email = validated_data['email']
        username = generate_unique_username(email.split('@')[0])

        user = UserModel(username=username, **validated_data)
        user.set_password(password)
        user.is_active = False
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(email=data['email'], password=data['password'])
        if user is None:
            raise serializers.ValidationError("Invalid credentials")
        data['user'] = user
        return data


# --- Forgot Password ---
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        try:
            validate_email(value)
        except DjangoValidationError:
            raise serializers.ValidationError("Invalid email format")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField(required=True, max_length=256, help_text='Закодований у base64 ідентифікатор користувача.')
    token = serializers.CharField(required=True, max_length=256, help_text='Токен скидання пароля з посилання у листі.')
    access_token = serializers.CharField(required=False, write_only=True, max_length=256,
                                         help_text='Застаріла назва поля token, приймається для сумісності.')
    new_password = serializers.CharField(write_only=True, min_length=8, max_length=128)

    def to_internal_value(self, data):
        if hasattr(data, 'items') and not data.get('token') and data.get('access_token'):
            data = {**dict(data.items()), 'token': data['access_token']}
        return super().to_internal_value(data)

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs['uid']))
            user = UserModel.objects.get(pk=uid)
        except Exception:
            raise serializers.ValidationError("Invalid uid")
        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError("Invalid or expired token")
        attrs['user'] = user
        return attrs

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8, max_length=128)
    confirm_new_password = serializers.CharField(required=True, write_only=True, min_length=8, max_length=128)

    def validate_new_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError(['password_too_weak'])

        if len(value) > 128:
            raise serializers.ValidationError(['Password must be at most 128 characters'])

        if not any(c.isalpha() for c in value):
            raise serializers.ValidationError(['password_too_weak'])

        if not any(c.isdigit() for c in value):
            raise serializers.ValidationError(['password_too_weak'])

        if ' ' in value:
            raise serializers.ValidationError(['Password cannot contain spaces'])

        try:
            value.encode('ascii')
        except UnicodeEncodeError:
            raise serializers.ValidationError(['Password can only contain ASCII characters'])

        return value

    def validate(self, attrs):
        user = self.context.get('user')

        # Перевірка поточного пароля
        if not user.check_password(attrs['current_password']):
            raise serializers.ValidationError({
                'current_password': ['incorrect_current_password']
            })

        # Перевірка збігу нового пароля та підтвердження
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({
                'confirm_new_password': ['passwords_do_not_match']
            })

        # Перевірка, що новий пароль не збігається з поточним
        if user.check_password(attrs['new_password']):
            raise serializers.ValidationError({
                'new_password': ['New password cannot be the same as current password']
            })

        return attrs


class OAuthLoginSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=[('google', 'Google'), ('facebook', 'Facebook')], required=True)
    access_token = serializers.CharField(required=True)

    def validate(self, attrs):
        provider = attrs.get('provider')
        token = attrs.get('access_token')

        if provider == 'google':
            user_data, error_detail = self._validate_google_token(token)
        elif provider == 'facebook':
            user_data, error_detail = self._validate_facebook_token(token)
        else:
            raise serializers.ValidationError("Unsupported provider")

        if not user_data:
            if error_detail:
                raise serializers.ValidationError(error_detail)
            else:
                raise serializers.ValidationError("Unable to validate token")

        if not user_data.get('email'):
            raise serializers.ValidationError("Email not provided by OAuth provider")

        attrs['user_data'] = user_data
        return attrs

    def _validate_google_token(self, access_token):
        try:
            url = "https://www.googleapis.com/oauth2/v3/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return (
                    {
                        'email': data.get('email'),
                        'first_name': data.get('given_name', ''),
                        'last_name': data.get('family_name', ''),
                        'picture': data.get('picture', ''),
                    },
                    None
                )
            else:
                try:
                    error_data = response.json()
                    error_message = error_data.get('error', {}).get('message',
                                                                    f"Google API error (HTTP {response.status_code})")
                    return None, f"Invalid Google token: {error_message}"
                except Exception:
                    return None, f"Invalid Google token (HTTP {response.status_code})"

        except requests.Timeout:
            return None, "Request to Google API timed out"
        except requests.RequestException as e:
            return None, f"Network error while validating Google token: {str(e)}"
        except Exception as e:
            return None, f"Unexpected error during Google token validation: {str(e)}"

    def _validate_facebook_token(self, access_token):
        try:
            # Получаем данные пользователя
            user_response = requests.get(
                "https://graph.facebook.com/me",
                params={"access_token": access_token, "fields": "id,email,first_name,last_name,picture"},
                timeout=10,
            )

            if user_response.status_code != 200:
                try:
                    error_data = user_response.json()
                    error_message = error_data.get('error', {}).get('message',
                                                                    f"Facebook Graph API error (HTTP {user_response.status_code})")
                    return None, f"Invalid Facebook token: {error_message}"
                except Exception:
                    return None, f"Invalid Facebook token (HTTP {user_response.status_code})"

            user_data = user_response.json()

            # Извлекаем URL картинки
            picture_url = ''
            if 'picture' in user_data and 'data' in user_data['picture'] and 'url' in user_data['picture']['data']:
                picture_url = user_data['picture']['data']['url']

            return (
                {
                    'email': user_data.get('email'),
                    'first_name': user_data.get('first_name', ''),
                    'last_name': user_data.get('last_name', ''),
                    'picture': picture_url,
                },
                None
            )
        except requests.Timeout:
            return None, "Request to Facebook API timed out"
        except requests.RequestException as e:
            return None, f"Network error while validating Facebook token: {str(e)}"
        except Exception as e:
            return None, f"Unexpected error during Facebook token validation: {str(e)}"


class ResendActivationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, max_length=254)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    guest_cart_id = serializers.IntegerField(required=False, write_only=True, min_value=1, max_value=INT64_MAX)
    guest_checkout_token = serializers.CharField(required=False, write_only=True, max_length=64)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        guest_cart_id = attrs.get('guest_cart_id')
        guest_checkout_token = attrs.get('guest_checkout_token')

        user = find_user_by_email(email)
        if user is None:
            raise serializers.ValidationError({
                'code': 'USER_NOT_FOUND',
                'field': 'email',
                'message': 'User with this email does not exist'
            }, code='user_not_found')

        if not user.check_password(password):
            raise serializers.ValidationError({
                'code': 'INVALID_PASSWORD',
                'field': 'password',
                'message': 'Incorrect password'
            }, code='invalid_password')

        if not user.is_active:
            raise serializers.ValidationError({
                'code': 'ACCOUNT_INACTIVE',
                'field': 'email',
                'message': 'Account not activated'
            }, code='account_inactive')

        refresh = self.get_token(user)

        merged_cart_id = None
        if guest_cart_id:
            merged_cart_id = self._merge_guest_cart(guest_cart_id, user)
        elif guest_checkout_token:
            merged_cart_id = self._merge_from_guest_session(guest_checkout_token, user)

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            },
            'cart_id': merged_cart_id,
            'next_step': '/checkout' if merged_cart_id else '/products'
        }

    def _merge_guest_cart(self, guest_cart_id, user):
        guest_cart = GuestCart.objects.filter(id=guest_cart_id, is_active=True).first()
        if guest_cart is None:
            return None

        with transaction.atomic():
            user_cart = Cart.get_active_for_user(user)

            for guest_item in guest_cart.items.select_related('product'):
                existing_item = CartItem.objects.filter(cart=user_cart, product=guest_item.product).first()

                if existing_item:
                    existing_item.quantity += guest_item.quantity
                    existing_item.save(update_fields=['quantity', 'updated_at'])
                else:
                    CartItem.objects.create(
                        cart=user_cart,
                        product=guest_item.product,
                        quantity=guest_item.quantity,
                        sku=guest_item.sku,
                        title=guest_item.title,
                        attrs=guest_item.attrs,
                        metadata=guest_item.metadata,
                    )

            guest_cart.is_active = False
            guest_cart.save(update_fields=['is_active', 'updated_at'])
        return user_cart.id

    def _merge_from_guest_session(self, guest_token, user):
        session = GuestCheckoutSession.objects.filter(
            session_token=guest_token,
            expires_at__gt=timezone.now()
        ).first()
        if session is None or not session.guest_cart_id:
            return None
        return self._merge_guest_cart(session.guest_cart_id, user)


class RegistrationErrorSerializer(serializers.Serializer):
    type = serializers.CharField(required=False)
    error_code = serializers.CharField(required=False)
    errors = serializers.JSONField(required=False)
    error_message = serializers.CharField(required=False)


class TokenUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.CharField()
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)


class TokenObtainResponseSerializer(serializers.Serializer):
    refresh = serializers.CharField()
    access = serializers.CharField()
    user = TokenUserSerializer()
    cart_id = serializers.IntegerField(allow_null=True)
    next_step = serializers.CharField()


class OAuthLoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = UserSerializer()
