import logging
from urllib.parse import urlencode

from common.permissions import IsAdmin, IsSelfOrAdmin
from common.serializers import CodedErrorSerializer, MessageSerializer
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter, OpenApiResponse
from drf_spectacular.utils import (extend_schema_view)
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from users.infrastructure.models import User
from users.emails import (RegistrationEmailError, send_activation_email_async, send_newsletter_welcome_email_async,
                          send_registration_email)
from users.interfaces.serializers import (UserSerializer, PatchedUserSerializer, RegisterSerializer,
                                          ForgotPasswordSerializer, ResetPasswordSerializer, OAuthLoginSerializer,
                                          OAuthLoginResponseSerializer, RegistrationErrorSerializer,
                                          ResendActivationSerializer, CustomTokenObtainPairSerializer,
                                          TokenObtainResponseSerializer, ChangePasswordSerializer)
from users.services import build_activation_url, find_user_by_email, generate_unique_username

UserModel = get_user_model()

logger = logging.getLogger(__name__)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


@extend_schema(tags=['Users'])
class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]

    @extend_schema(
        responses={
            200: UserSerializer(many=True),
            401: OpenApiResponse(description='Неавторизовано'),
            403: OpenApiResponse(description='Доступно лише адміністраторам'),
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
            403: OpenApiResponse(description='Доступно лише адміністраторам'),
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
            403: OpenApiResponse(description='Доступно лише власнику облікового запису або адміністратору'),
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
            403: OpenApiResponse(description='Доступно лише власнику облікового запису або адміністратору'),
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
            403: OpenApiResponse(description='Доступно лише власнику облікового запису або адміністратору'),
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
    permission_classes = [IsSelfOrAdmin]


@extend_schema(tags=['Users'])
class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'

    @extend_schema(
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(
                description="Реєстрація успішна. Лист із підтвердженням надіслано.",
                response=MessageSerializer
            ),
            400: OpenApiResponse(response=RegistrationErrorSerializer, description='Помилка валідації'),
            503: OpenApiResponse(
                response=RegistrationErrorSerializer,
                description='Лист із підтвердженням не вдалося надіслати. Обліковий запис не створено, '
                            'запит можна безпечно повторити.'
            ),
        },
        examples=[
            OpenApiExample(
                name='Реєстрація',
                summary='POST /api/users/register/',
                value={
                    'email': 'u@mail.com',
                    'password': 'secret123',
                    'password_confirm': 'secret123',
                    'first_name': 'Oleg',
                    'last_name': 'Petrenko',
                    'privacy_policy': True,
                    'subscribe_news': True
                },
                request_only=True
            ),
        ],
        auth=[]
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error_code': 'REGISTRATION_FAILED', 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                user = serializer.save()
                send_registration_email(
                    email=user.email,
                    first_name=user.first_name,
                    activation_url=build_activation_url(request, user),
                    subscribe_news=user.subscribe_news,
                )
        except IntegrityError:
            return Response(
                {'error_code': 'REGISTRATION_FAILED', 'errors': {'email': ['User with this email already exists']}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RegistrationEmailError:
            return Response(
                {
                    'error_code': 'EMAIL_DELIVERY_FAILED',
                    'error_message': 'We could not send the confirmation email. '
                                     'The account was not created, please try again later.',
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        logger.info(
            "User %s registered. Activation email sent.",
            user.email,
        )

        return Response(
            {
                "message": (
                    "Thank you for registering!\n"
                    "A confirmation email has been sent to your inbox.\n"
                    "Please click the link in that email to activate your account.\n"
                    "Check the message for 5-10 minutes. "
                    "If you don't find the email, please check your spam folder "
                    "and resend it again."
                )
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=['Users'])
class ActivateView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        responses={
            302: OpenApiResponse(description='Перенаправлення на фронтенд зі статусом активації'),
        },
        examples=[
            OpenApiExample(
                name='Успішне перенаправлення після активації',
                summary='302 Перенаправлення на фронтенд',
                description="Перенаправлення на FRONTEND_URL з activation_status=success",
                value=None,
                response_only=True,
            ),
            OpenApiExample(
                name='Вже активовано',
                summary='302 Перенаправлення на фронтенд',
                description="Перенаправлення на FRONTEND_URL з activation_status=already_activated",
                value=None,
                response_only=True,
            ),
            OpenApiExample(
                name='Недійсний токен',
                summary='302 Перенаправлення на фронтенд',
                description="Перенаправлення на FRONTEND_URL з activation_status=error",
                value=None,
                response_only=True,
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
                params = urlencode({
                    'activation_status': 'already_activated',
                    'message': 'Ваш обліковий запис вже активовано.'
                })
                return redirect(f"{settings.FRONTEND_URL}/login/?{params}")

            if default_token_generator.check_token(user, token):
                user.is_active = True
                user.save()
                send_activation_email_async(user.email, user.subscribe_news)

                if user.subscribe_news:
                    send_newsletter_welcome_email_async(user.email)

                params = urlencode({
                    'activation_status': 'success',
                    'message': 'Your account has been successfully activated.'
                })
                return redirect(f"{settings.FRONTEND_URL}/login/?{params}")
            else:
                params = urlencode({
                    'activation_status': 'error',
                    'error_code': 'activation_link_expired',
                    'message': 'Посилання для активації недійсне або термін його дії минув.'
                })
                return redirect(f"{settings.FRONTEND_URL}/login/?{params}")

        params = urlencode({
            'activation_status': 'error',
            'error_code': 'invalid_user',
            'message': 'Недійсне посилання для активації.'
        })
        return redirect(f"{settings.FRONTEND_URL}/login/?{params}")


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
                response=MessageSerializer
            ),
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
        user = find_user_by_email(serializer.validated_data['email'])

        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            frontend_reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

            subject = 'Password Reset'
            message = (
                f"Good afternoon {user.first_name},\n"
                f"To reset your password, please follow this link: {frontend_reset_url}\n"
                f"The link is valid for 1 hour."
            )
            try:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
            except Exception:
                logger.exception("Password reset email FAILED to send to %s", user.email)
        return Response(
            {'message': 'Якщо email існує, посилання для скидання буде надіслано'},
            status=status.HTTP_200_OK
        )


@extend_schema(tags=['Users'])
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer

    @extend_schema(
        operation_id='users_reset_password_redirect',
        summary='Перейти за посиланням скидання пароля',
        description='Перевіряє uid і token з листа та перенаправляє на сторінку скидання пароля фронтенду. '
                    'Адреса призначення береться з налаштування FRONTEND_URL. Для відсутніх або недійсних '
                    'параметрів перенаправлення також виконується, але з описом помилки у query-рядку.',
        parameters=[
            OpenApiParameter(name='uid', type=str, location=OpenApiParameter.QUERY, required=False,
                             description='Закодований ідентифікатор користувача'),
            OpenApiParameter(name='token', type=str, location=OpenApiParameter.QUERY, required=False,
                             description='Токен скидання пароля'),
        ],
        request=None,
        responses={
            302: OpenApiResponse(description='Перенаправлення на FRONTEND_URL/forgot-password'),
        },
    )
    def get(self, request):
        uid = request.GET.get('uid')
        token = request.GET.get('token')

        if not uid or not token:
            params = urlencode(
                {'reset_status': 'error', 'error': 'Посилання для скидання пароля недійсне або пошкоджене.'})
            redirect_url = f"{settings.FRONTEND_URL}/forgot-password?{params}"
            return redirect(redirect_url)

        try:
            uid_int = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=uid_int)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            params = urlencode(
                {'reset_status': 'error', 'error': 'Посилання для скидання пароля недійсне або пошкоджене.'})
            redirect_url = f"{settings.FRONTEND_URL}/forgot-password?{params}"
            return redirect(redirect_url)

        if not default_token_generator.check_token(user, token):
            params = urlencode(
                {'reset_status': 'error', 'error': 'Посилання для скидання пароля недійсне або спливло.'})
            redirect_url = f"{settings.FRONTEND_URL}/forgot-password?{params}"
            return redirect(redirect_url)

        redirect_url = f"{settings.FRONTEND_URL}/forgot-password?{urlencode({'uid': uid, 'token': token})}"
        return redirect(redirect_url)

    @extend_schema(
        tags=['Users'],
        request=ResetPasswordSerializer,
        responses={
            200: OpenApiResponse(response=MessageSerializer, description="Пароль успішно змінено"),
            400: OpenApiResponse(response=CodedErrorSerializer,
                                 description='Помилка валідації або невірний/сплив токен')
        },
        examples=[
            OpenApiExample(
                name='Скидання пароля',
                summary='POST /api/users/reset-password/',
                value={'uid': '<uid>', 'token': '<token>', 'new_password': 'newPass123!'},
                request_only=True
            ),
            OpenApiExample(
                name='Успішне скидання',
                summary='200 OK',
                value={'message': 'Пароль успішно змінено'},
                response_only=True,
                status_codes=['200']
            ),
            OpenApiExample(
                name='Невірний токен',
                summary='400 Bad Request',
                value={'errors': {'non_field_errors': ['Invalid or expired token']}},
                response_only=True,
                status_codes=['400']
            )
        ]
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer.save()
        return Response(
            {'message': 'Пароль успішно змінено'},
            status=status.HTTP_200_OK
        )


@extend_schema(
    tags=['Users'],
    summary='Отримання JWT-токенів',
    description='POST /api/users/token/ - отримання пари access і refresh токенів. Помилки автентифікації '
                'повертаються зі статусом 400 і полями code, field, message.',
    request=CustomTokenObtainPairSerializer,
    responses={
        200: OpenApiResponse(
            response=TokenObtainResponseSerializer,
            description='Успішна автентифікація',
            examples=[
                OpenApiExample(
                    name='Успішна відповідь',
                    value={
                        'access': 'eyJ0eXAiOiJKV1QiLCJhbGc.',
                        'refresh': 'eyJ0eXAiOiJKV1QiLCJhbGc.',
                        'user': {'id': 1, 'email': 'user@example.com', 'first_name': 'Ivan', 'last_name': 'Ivanov'},
                        'cart_id': None,
                        'next_step': '/products',
                    },
                    response_only=True
                )
            ]
        ),
        400: OpenApiResponse(
            response=CodedErrorSerializer,
            description='Помилка валідації або невірні облікові дані',
            examples=[
                OpenApiExample(
                    name='Користувача не знайдено',
                    value={'code': 'USER_NOT_FOUND', 'field': 'email', 'message': 'User with this email does not exist'},
                    response_only=True
                ),
                OpenApiExample(
                    name='Невірний пароль',
                    value={'code': 'INVALID_PASSWORD', 'field': 'password', 'message': 'Incorrect password'},
                    response_only=True
                ),
                OpenApiExample(
                    name='Акаунт не активовано',
                    value={'code': 'ACCOUNT_INACTIVE', 'field': 'email', 'message': 'Account not activated'},
                    response_only=True
                )
            ]
        ),
    },
    examples=[
        OpenApiExample(
            name='Запит на отримання токенів',
            summary='POST /api/users/token/',
            value={'email': 'user@example.com', 'password': 'secret123'},
            request_only=True
        )
    ]
)
class TokenObtainPairWithTag(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


@extend_schema(
    tags=['Users'],
    summary='Оновлення access-токена',
    description='POST /api/users/token/refresh/ - обмін refresh на новий access. Недійсний або прострочений '
                'refresh-токен повертає 401.',
    request=TokenRefreshSerializer,
    responses={
        200: TokenRefreshSerializer,
        400: OpenApiResponse(response=CodedErrorSerializer, description='Помилка валідації'),
        401: OpenApiResponse(response=CodedErrorSerializer, description='Недійсний або прострочений refresh-токен'),
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
            response_only=True,
            status_codes=['200']
        ),
        OpenApiExample(
            name='Невірний refresh',
            summary='401 Unauthorized',
            value={'detail': 'Token is invalid or expired', 'code': 'token_not_valid'},
            response_only=True,
            status_codes=['401']
        )
    ],
    auth=[]
)
class TokenRefreshWithTag(TokenRefreshView):
    serializer_class = TokenRefreshSerializer


@extend_schema(
    tags=['Users'],
    description="Авторизація через OAuth провайдерів (Google, Facebook). Відповідь містить пари access/refresh "
                "та access_token/refresh_token з однаковими значеннями.",
    request=OAuthLoginSerializer,
    responses={
        200: OpenApiResponse(response=OAuthLoginResponseSerializer, description="Успішна OAuth авторизація"),
        400: OpenApiResponse(response=CodedErrorSerializer, description='Помилка валідації або невалідний токен'),
    },
    examples=[
        OpenApiExample(
            name='OAuth логін (Google)',
            summary='POST /api/users/oauth/',
            value={'provider': 'google', 'access_token': '<google_oauth2_token>'},
            request_only=True
        ),
        OpenApiExample(
            name='OAuth логін (Facebook)',
            summary='POST /api/users/oauth/',
            value={'provider': 'facebook', 'access_token': '<facebook_access_token>'},
            request_only=True
        ),
        OpenApiExample(
            name='Успішна відповідь OAuth',
            summary='200 OK',
            value={
                'access': '<access_token>',
                'refresh': '<refresh_token>',
                'access_token': '<access_token>',
                'refresh_token': '<refresh_token>',
                'user': {
                    'id': 1,
                    'email': 'oauthuser@example.com',
                    'first_name': 'OAuth',
                    'last_name': 'User',
                    'date_joined': '2025-07-04T00:00:00Z',
                    'admin': False
                }
            },
            response_only=True,
            status_codes=['200']
        ),
        OpenApiExample(
            name='Невалідний токен',
            summary='400 Bad Request',
            value={'detail': 'Unable to validate token'},
            response_only=True,
            status_codes=['400']
        )
    ],
    auth=[]
)
class OAuthLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OAuthLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_data = serializer.validated_data['user_data']
        email = user_data['email']

        if not email:
            return Response({'detail': 'Email not provided by OAuth provider'}, status=status.HTTP_400_BAD_REQUEST)

        user = find_user_by_email(email)
        if user is not None and not user.is_active:
            return Response({'detail': 'User account is disabled.'}, status=status.HTTP_400_BAD_REQUEST)

        if user is None:
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=email,
                        username=generate_unique_username(email),
                        first_name=user_data.get('first_name', ''),
                        last_name=user_data.get('last_name', ''),
                    )
            except IntegrityError:
                user = find_user_by_email(email)
                if user is None:
                    raise

        refresh = RefreshToken.for_user(user)
        user_serializer = UserSerializer(user)
        access = str(refresh.access_token)

        return Response({
            'access': access,
            'refresh': str(refresh),
            'access_token': access,
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


@extend_schema(tags=['Users'])
class ResendActivationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'resend-activation'

    @extend_schema(
        request=ResendActivationSerializer,
        responses={
            200: OpenApiResponse(response=MessageSerializer, description="A new verification email has been sent."),
            400: OpenApiResponse(response=CodedErrorSerializer, description="Error"),
            404: OpenApiResponse(response=CodedErrorSerializer, description="Not found"),
            503: OpenApiResponse(response=CodedErrorSerializer,
                                 description="The verification email could not be sent, try again later."),
        },
        examples=[
            OpenApiExample(
                name='Успішне надсилання',
                summary='200 OK',
                value={'message': 'A new verification email has been sent.\n\nPlease check your inbox.'},
                response_only=True,
                status_codes=['200']
            ),
        ],
        auth=[]
    )
    def post(self, request):
        if not request.data.get('email'):
            return Response({'detail': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ResendActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        user = find_user_by_email(email)
        if user is None:
            return Response({'detail': "We couldn't find an account associated with this email address."},
                            status=status.HTTP_404_NOT_FOUND)

        if user.is_active:
            return Response({'detail': "Your email has already been verified.\n\nYou can sign in to your account."},
                            status=status.HTTP_400_BAD_REQUEST)

        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        try:
            send_registration_email(
                email=user.email,
                first_name=user.first_name,
                activation_url=build_activation_url(request, user),
                subscribe_news=user.subscribe_news,
            )
        except RegistrationEmailError:
            logger.error("Error resending activation email for %s", email)
            return Response({'detail': 'An error occurred while sending the email. Please try again later.'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({
            "message": "A new verification email has been sent.\n\nPlease check your inbox."
        }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Users'],
    request=ChangePasswordSerializer,
    responses={
        200: OpenApiResponse(description="Пароль успішно змінено"),
        400: OpenApiResponse(
            description="Помилка валідації",
            response={
                "type": "object",
                "properties": {
                    "current_password": {"type": "array", "items": {"type": "string"}},
                    "new_password": {"type": "array", "items": {"type": "string"}},
                    "confirm_new_password": {"type": "array", "items": {"type": "string"}}
                },
                "example": {
                    "current_password": ["incorrect_current_password"],
                    "new_password": ["password_too_weak"],
                    "confirm_new_password": ["passwords_do_not_match"]
                }
            }
        ),
        401: OpenApiResponse(description='Неавторизовано'),
    },
    examples=[
        OpenApiExample(
            name='Зміна пароля',
            summary='POST /api/users/change-password/',
            value={
                'current_password': 'old_secret123',
                'new_password': 'new_secret456',
                'confirm_new_password': 'new_secret456'
            },
            request_only=True
        ),
        OpenApiExample(
            name='Успішна зміна',
            summary='200 OK',
            value={'message': 'Пароль успішно змінено'},
            response_only=True
        ),
        OpenApiExample(
            name='Невірний поточний пароль',
            summary='400 Bad Request',
            value={'current_password': ['incorrect_current_password']},
            response_only=True
        ),
        OpenApiExample(
            name='Паролі не співпадають',
            summary='400 Bad Request',
            value={'confirm_new_password': ['passwords_do_not_match']},
            response_only=True
        ),
        OpenApiExample(
            name='Слабкий пароль',
            summary='400 Bad Request',
            value={'new_password': ['password_too_weak']},
            response_only=True
        ),
    ]
)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'user': request.user})
        if serializer.is_valid():
            new_password = serializer.validated_data.get('new_password')
            user = request.user
            user.set_password(new_password)
            user.save()
            return Response({'message': 'Пароль успішно змінено'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
