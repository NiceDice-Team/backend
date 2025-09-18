from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from drf_spectacular.utils import (extend_schema_view)
from rest_framework import generics
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from users.infrastructure.models import User
from users.interfaces.serializers import (UserSerializer, PatchedUserSerializer, RegisterSerializer,
                                          ForgotPasswordSerializer, ResetPasswordSerializer, )
from users.interfaces.serializers import (UserSerializer, PatchedUserSerializer, RegisterSerializer,
                                          ForgotPasswordSerializer, ResetPasswordSerializer, OAuthLoginSerializer, )

from rest_framework import serializers


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


@extend_schema(tags=['Users'])
class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: UserSerializer(many=True),
            401: OpenApiResponse(description='Неавторизовано'),
        },
        examples=[
            OpenApiExample(
                name='Успішна відповідь',
                summary='200 OK',
                value=[{
                    'id': 1,
                    'email': 'user@example.com',
                    'first_name': 'Ivan',
                    'last_name': 'Ivanov',
                    'date_joined': '2025-07-04T00:00:00Z'
                }],
                response_only=True
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=UserSerializer,
        responses={
            201: UserSerializer,
            400: OpenApiResponse(description='Неправильний запит'),
            401: OpenApiResponse(description='Неавторизовано'),
        },
        examples=[
            OpenApiExample(
                name='Створення користувача',
                summary='POST /api/users/',
                value={
                    'email': 'newuser@example.com',
                    'first_name': 'Petr',
                    'last_name': 'Petrov'
                },
                request_only=True
            ),
            OpenApiExample(
                name='Успішна відповідь',
                summary='201 Created',
                value={
                    'id': 2,
                    'email': 'newuser@example.com',
                    'first_name': 'Petr',
                    'last_name': 'Petrov',
                    'date_joined': '2025-07-10T20:00:00Z'
                },
                response_only=True
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(tags=['Users'])
@extend_schema_view(
    get=extend_schema(
        responses={
            200: UserSerializer,
            401: OpenApiResponse(description='Неавторизовано'),
            404: OpenApiResponse(description='Не знайдено'),
        },
        examples=[
            OpenApiExample(
                name='Отримання користувача',
                summary='GET /api/users/{id}/',
                value={
                    'id': 1,
                    'email': 'u@mail.com',
                    'first_name': 'Oleg',
                    'last_name': 'Petrenko',
                    'date_joined': '2025-07-04T00:00:00Z'
                },
                response_only=True
            )
        ]
    ),
    patch=extend_schema(
        request=PatchedUserSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(description='Неправильний запит'),
            401: OpenApiResponse(description='Неавторизовано'),
            404: OpenApiResponse(description='Не знайдено'),
        },
        examples=[
            OpenApiExample(
                name='Оновлення email',
                summary='PATCH /api/users/{id}/',
                value={'email': 'updated@mail.com'},
                request_only=True
            ),
            OpenApiExample(
                name='Успішна відповідь',
                summary='200 OK',
                value={
                    'id': 1,
                    'email': 'updated@mail.com',
                    'first_name': 'Oleg',
                    'last_name': 'Petrenko',
                    'date_joined': '2025-07-04T00:00:00Z'
                },
                response_only=True
            )
        ]
    ),
    delete=extend_schema(
        responses={
            204: OpenApiResponse(description='Немає вмісту'),
            401: OpenApiResponse(description='Неавторизовано'),
            404: OpenApiResponse(description='Не знайдено'),
        },
        examples=[
            OpenApiExample(
                name='Видалення користувача',
                summary='DELETE /api/users/{id}/',
                value=None,
                response_only=True
            )
        ]
    )
)
class UserRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


@extend_schema(tags=['Users'])
class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(
                description="Будь ласка, підтвердіть вашу електронну пошту",
                response={
                    "type": "object",
                    "properties": {"message": {"type": "string"}}
                }
            ),
            400: OpenApiResponse(description='Помилка валідації')
        },
        examples=[
            OpenApiExample(
                name='Реєстрація',
                summary='POST /api/users/register/',
                value={
                    'email': 'u@mail.com',
                    'password': 'secret123',
                    'first_name': 'Oleg',
                    'last_name': 'Petrenko'
                },
                request_only=True
            ),
            OpenApiExample(
                name='Помилка реєстрації',
                summary='400 Bad Request',
                value={'error_code': 'REGISTRATION_FAILED',
                       'error_message': {'email': ['Користувач з таким email вже існує']}},
                response_only=True
            ),
        ],
        auth=[]
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as exc:
            return Response({
                'error_code': 'REGISTRATION_FAILED',
                'error_message': exc.detail if hasattr(exc, 'detail') else str(exc)
            }, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        user.is_active = False
        user.save()

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        activation_path = reverse('activate', kwargs={'uidb64': uid, 'token': token})
        activation_url = request.build_absolute_uri(activation_path)

        subject = 'Confirm your registration'
        message = (
            f'Hello {user.first_name},\n\n'
            'Please click the link below to activate your account:\n'
            f'{activation_url}\n\n'
            'If you did not register, please ignore this email.'
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)

        return Response(
            {"message": "A confirmation email has been sent to your email address."},
            status=status.HTTP_201_CREATED
        )


@extend_schema(tags=['Users'])
class ActivateView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses={
            200: OpenApiResponse(description='Активація успішна'),
            400: OpenApiResponse(description='Недійсний або прострочений токен'),
        },
        examples=[
            OpenApiExample(
                name='Успішна активація',
                summary='200 OK',
                value={'message': 'Акаунт успішно активовано'},
                response_only=True
            ),
            OpenApiExample(
                name='Невдала активація',
                summary='400 Bad Request',
                value={'error_code': 'TOKEN_INVALID', 'error_message': 'Недійсний або прострочений токен'},
                response_only=True
            ),
        ]
    )
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except Exception:
            user = None

        if user is not None:
            if user.is_active:
                return Response({
                    'error_code': 'TOKEN_INVALID',
                    'error_message': 'Link already used'
                }, status=status.HTTP_400_BAD_REQUEST)

            if default_token_generator.check_token(user, token):
                user.is_active = True
                user.save()
                return Response({
                    'message': 'Account successfully activated'
                }, status=status.HTTP_200_OK)

        return Response({
            'error_code': 'TOKEN_INVALID',
            'error_message': 'Invalid or expired token'
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['Users'])
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    @extend_schema(
        tags=['Users'],
        request=LogoutSerializer,
        responses={
            205: OpenApiResponse(description='Вихід виконано'),
            400: OpenApiResponse(description='Неправильний запит'),
            401: OpenApiResponse(description='Неавторизовано'),
        },
        examples=[
            OpenApiExample(
                name='Вихід (logout)',
                summary='POST /api/users/logout/',
                value={'refresh': '<jwt>'},
                request_only=True
            ),
            OpenApiExample(
                name='Успішний вихід',
                summary='205 Reset Content',
                value=None,
                response_only=True
            ),
            OpenApiExample(
                name='Помилка токена',
                summary='400 Bad Request',
                value={'detail': 'Недійсний токен або вже внесений до чорного списку'},
                response_only=True
            )
        ]
    )
    def post(self, request):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(refresh_token).blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response({"detail": "Invalid token or already blacklisted"}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['Users'])
class ForgotPasswordView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'forgot-password'
    permission_classes = [AllowAny]

    @extend_schema(
        request=ForgotPasswordSerializer,
        responses={
            200: OpenApiResponse(
                description="Якщо e-mail існує, посилання для скидання буде надіслано",
                response={'type': 'object', 'properties': {'message': {'type': 'string'}}}
            ),
            400: OpenApiResponse(description='Помилка валідації')
        },
        examples=[
            OpenApiExample(
                name='Запит скидання',
                summary='POST /api/users/forgot-password/',
                value={'email': 'user@example.com'},
                request_only=True
            ),
            OpenApiExample(
                name='Успішна відповідь',
                summary='200 OK',
                value={'message': 'Якщо e-mail існує, посилання для скидання буде надіслано'},
                response_only=True
            ),
            OpenApiExample(
                name='Невірний email',
                summary='400 Bad Request',
                value={'email': ['Неправильний формат електронної адреси']},
                response_only=True
            )
        ]
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(email=serializer.validated_data['email'])
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_path = f"/reset-password?uid={uid}&token={token}"
            reset_url = request.build_absolute_uri(reset_path)
            subject = 'Скидання пароля'
            message = (
                f"Добрий день {user.first_name},\n\n"
                f"Для скидання пароля перейдіть за посиланням:\n{reset_url}\n\n"
                "Посилання дійсне 1 годину."
            )
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
        except User.DoesNotExist:
            pass
        return Response(
            {'message': 'Якщо email існує, посилання для скидання буде надіслано'},
            status=status.HTTP_200_OK
        )


@extend_schema(tags=['Users'])
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer

    @extend_schema(
        tags=['Users'],
        request=ResetPasswordSerializer,
        responses={
            200: OpenApiResponse(description="Пароль успішно змінено"),
            400: OpenApiResponse(description='Помилка валідації або невірний/сплив токен')
        },
        examples=[
            OpenApiExample(
                name='Скидання пароля',
                summary='POST /api/users/reset-password/',
                value={'uid': '<uid>', 'token': '<token>', 'new_password': 'newsecret123'},
                request_only=True
            ),
            OpenApiExample(
                name='Успішне скидання',
                summary='200 OK',
                value={'message': 'Пароль успішно змінено'},
                response_only=True
            ),
            OpenApiExample(
                name='Невірний токен',
                summary='400 Bad Request',
                value={'non_field_errors': ['Invalid or expired token']},
                response_only=True
            )
        ]
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Пароль успішно змінено'}, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Users'],
    summary='Отримання JWT‑токенів',
    description='POST /api/users/token/ — отримання пари access і refresh токенів',
    request=TokenObtainPairSerializer,
    responses={
        200: TokenObtainPairSerializer,
        400: OpenApiResponse(description='Помилка валідації'),
        401: OpenApiResponse(description='Невірні облікові дані'),
    },
    examples=[
        OpenApiExample(
            name='Отримання токенів',
            summary='POST /api/users/token/',
            value={'email': 'u@mail.com', 'password': 'secret123'},
            request_only=True
        ),
        OpenApiExample(
            name='Успішна відповідь',
            summary='200 OK',
            value={'access': '<access_token>', 'refresh': '<refresh_token>'},
            response_only=True
        ),
        OpenApiExample(
            name='Невірні дані',
            summary='401 Unauthorized',
            value={'detail': 'No active account found with the given credentials'},
            response_only=True
        )
    ]
)
class TokenObtainPairWithTag(TokenObtainPairView):
    serializer_class = TokenObtainPairSerializer


@extend_schema(
    tags=['Users'],
    summary='Оновлення access‑токена',
    description='POST /api/users/token/refresh/ — обмін refresh на новий access',
    request=TokenRefreshSerializer,
    responses={
        200: TokenRefreshSerializer,
        400: OpenApiResponse(description='Помилка валідації'),
    },
    examples=[
        OpenApiExample(
            name='Оновлення токена',
            summary='POST /api/users/token/refresh/',
            value={'refresh': '<refresh_token>'},
            request_only=True
        ),
        OpenApiExample(
            name='Успішна відповідь',
            summary='200 OK',
            value={'access': '<new_access_token>'},
            response_only=True
        ),
        OpenApiExample(
            name='Невірний refresh',
            summary='400 Bad Request',
            value={'detail': 'Token is invalid or expired'},
            response_only=True
        )
    ],
    auth=[]
)
class TokenRefreshWithTag(TokenRefreshView):
    serializer_class = TokenRefreshSerializer


@extend_schema(tags=['Users'])
class OAuthLoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Users'],
        request=OAuthLoginSerializer,
        responses={
            200: OpenApiResponse(
                description="Успішна OAuth авторизація",
                response={
                    "type": "object",
                    "properties": {
                        "access": {"type": "string"},
                        "refresh": {"type": "string"},
                        "user": UserSerializer.Meta.fields
                    }
                }
            ),
            400: OpenApiResponse(description='Помилка валідації або невалідний токен'),
        },
        examples=[
            OpenApiExample(
                name='OAuth логін (Google)',
                summary='POST /api/users/oauth/',
                value={
                    'provider': 'google',
                    'token': '<google_oauth2_token>'
                },
                request_only=True
            ),
            OpenApiExample(
                name='OAuth логін (Facebook)',
                summary='POST /api/users/oauth/',
                value={
                    'provider': 'facebook',
                    'token': '<facebook_access_token>'
                },
                request_only=True
            ),
            OpenApiExample(
                name='Успішна відповідь OAuth',
                summary='200 OK',
                value={
                    'access_token': '<access_token>',
                    'refresh_token': '<refresh_token>',
                    'user': {
                        'id': 1,
                        'email': 'oauthuser@example.com',
                        'first_name': 'OAuth',
                        'last_name': 'User',
                        'date_joined': '2025-07-04T00:00:00Z'
                    }
                },
                response_only=True
            ),
            OpenApiExample(
                name='Невалідний токен',
                summary='400 Bad Request',
                value={'detail': 'Unable to validate token'},
                response_only=True
            )
        ],
        auth=[]
    )
    def post(self, request):
        serializer = OAuthLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_data = serializer.validated_data['user_data']
        email = user_data['email']

        if not email:
            return Response({'detail': 'Email not provided by OAuth provider'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                return Response({'detail': 'User account is disabled.'}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            user = User.objects.create_user(
                email=email,
                username=email,
                first_name=user_data.get('first_name', ''),
                last_name=user_data.get('last_name', ''),
            )

        refresh = RefreshToken.for_user(user)
        user_serializer = UserSerializer(user)

        return Response({
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'user': user_serializer.data
        }, status=status.HTTP_200_OK)


@extend_schema(tags=['Users'])
class GetUserIdView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Users'],
        responses={
            200: OpenApiResponse(
                response={'type': 'object', 'properties': {'user_id': {'type': 'integer'}}},
                description='Успішне отримання ID користувача'
            ),
            401: OpenApiResponse(description='Токен не надано або недійсний'),
        },
        examples=[
            OpenApiExample(
                name='Успішна відповідь',
                summary='200 OK',
                value={'user_id': 123},
                response_only=True
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        return Response({'user_id': request.user.id}, status=status.HTTP_200_OK)
