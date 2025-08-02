import re

import requests
from common.serializers import ExampleIgnoringModelSerializer
from common.serializers import ExampleIgnoringModelSerializer
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from users.infrastructure.models import User
from users.infrastructure.models import User

UserModel = get_user_model()
EMAIL_PATTERN = re.compile(
    r"^(?=.{6,254}$)(?=.{1,64}@)[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}$"
)


class UserSerializer(ExampleIgnoringModelSerializer):
    class Meta:
        model = UserModel
        fields = ['id', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['date_joined']
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': False},
            'last_name': {'required': False},
        }


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
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)

    class Meta:
        model = UserModel
        fields = ['id', 'email', 'password', 'first_name', 'last_name']
        read_only_fields = ['id']

    def validate_email(self, value):
        try:
            validate_email(value)
        except DjangoValidationError:
            raise serializers.ValidationError("Invalid email format")
        if not EMAIL_PATTERN.match(value):
            raise serializers.ValidationError("Email does not meet validation requirements")
        if UserModel.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists")
        return value

    def create(self, validated_data):
        email = validated_data['email']
        user = UserModel.objects.create_user(
            email=email,
            username=email,
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
        )
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
    uid = serializers.CharField(required=True)
    access_token = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

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
            # 1. Получаем данные пользователя
            user_info_url = f"https://graph.facebook.com/me?access_token={access_token}&fields=id,email,first_name,last_name,picture"
            user_response = requests.get(user_info_url, timeout=10)

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
