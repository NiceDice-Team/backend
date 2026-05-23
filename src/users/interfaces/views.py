import logging
from urllib.parse import urlencode, urljoin, urlparse

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from drf_spectacular.utils import (extend_schema_view)
from rest_framework import generics
from rest_framework import serializers
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
                                          ForgotPasswordSerializer, ResetPasswordSerializer as ResetPasswordInputSerializer,
                                          OAuthLoginSerializer, ResendActivationSerializer)

logger = logging.getLogger(__name__)


def get_frontend_url() -> str:
    frontend_url = getattr(settings, 'FRONTEND_BASE_URL', '').strip()
    return frontend_url or "https://team-challange-front.vercel.app"


FRONTEND_URL = get_frontend_url()


def build_public_url(request, path: str) -> str:
    base = getattr(settings, 'SITE_BASE_URL', '').strip()
    if base:
        if path.startswith('http://') or path.startswith('https://'):
            return path

        parsed_base = urlparse(base.rstrip('/'))
        base_path = parsed_base.path or ''
        relative_path = path
        if base_path and relative_path.startswith(base_path):
            relative_path = relative_path[len(base_path):]

        normalized_base = parsed_base._replace(path=base_path).geturl()
        if not normalized_base.endswith('/'):
            normalized_base = f"{normalized_base}/"

        return urljoin(normalized_base, relative_path.lstrip('/'))
    if request is None:
        return path
    return request.build_absolute_uri(path)


def wants_json_response(request) -> bool:
    accepted_format = getattr(getattr(request, 'accepted_renderer', None), 'format', None)
    if accepted_format == 'json':
        return True
    accept_header = request.headers.get('Accept', '')
    return 'application/json' in accept_header


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


@extend_schema(tags=['Users'])
class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: UserSerializer(many=True),
            401: OpenApiResponse(description='Unauthorized'),
        },
        examples=[
            OpenApiExample(
                name='Successful response',
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
            400: OpenApiResponse(description='Bad request'),
            401: OpenApiResponse(description='Unauthorized'),
        },
        examples=[
            OpenApiExample(
                name='Create user',
                summary='POST /api/users/',
                value={
                    'email': 'newuser@example.com',
                    'first_name': 'Petr',
                    'last_name': 'Petrov'
                },
                request_only=True
            ),
            OpenApiExample(
                name='Successful response',
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
            401: OpenApiResponse(description='Unauthorized'),
            404: OpenApiResponse(description='Not found'),
        },
        examples=[
            OpenApiExample(
                name='Get user',
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
            400: OpenApiResponse(description='Bad request'),
            401: OpenApiResponse(description='Unauthorized'),
            404: OpenApiResponse(description='Not found'),
        },
        examples=[
            OpenApiExample(
                name='Update email',
                summary='PATCH /api/users/{id}/',
                value={'email': 'updated@mail.com'},
                request_only=True
            ),
            OpenApiExample(
                name='Successful response',
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
            204: OpenApiResponse(description='No content'),
            401: OpenApiResponse(description='Unauthorized'),
            404: OpenApiResponse(description='Not found'),
        },
        examples=[
            OpenApiExample(
                name='Delete user',
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
                description="Please confirm your email address",
                response={
                    "type": "object",
                    "properties": {"message": {"type": "string"}}
                }
            ),
            400: OpenApiResponse(description='Validation error')
        },
        examples=[
            OpenApiExample(
                name='Registration',
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
                name='Registration error',
                summary='400 Bad Request',
                value={'error_code': 'REGISTRATION_FAILED',
                       'error_message': {'email': ['A user with this email already exists']}},
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
        activation_url = build_public_url(request, activation_path)

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
            200: OpenApiResponse(description='Activation successful'),
            400: OpenApiResponse(description='Invalid or expired token'),
        },
        examples=[
            OpenApiExample(
                name='Successful activation',
                summary='200 OK',
                value={'message': 'Account successfully activated'},
                response_only=True
            ),
            OpenApiExample(
                name='Failed activation',
                summary='400 Bad Request',
                value={'error_code': 'TOKEN_INVALID', 'error_message': 'Invalid or expired token'},
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
            205: OpenApiResponse(description='Logout completed'),
            400: OpenApiResponse(description='Bad request'),
            401: OpenApiResponse(description='Unauthorized'),
        },
        examples=[
            OpenApiExample(
                name='Logout',
                summary='POST /api/users/logout/',
                value={'refresh': '<jwt>'},
                request_only=True
            ),
            OpenApiExample(
                name='Successful logout',
                summary='205 Reset Content',
                value=None,
                response_only=True
            ),
            OpenApiExample(
                name='Token error',
                summary='400 Bad Request',
                value={'detail': 'Invalid token or already blacklisted'},
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
                description="If the email exists, a reset link will be sent",
                response={'type': 'object', 'properties': {'message': {'type': 'string'}}}
            ),
            400: OpenApiResponse(description='Validation error')
        },
        examples=[
            OpenApiExample(
                name='Reset request',
                summary='POST /api/users/forgot-password/',
                value={'email': 'user@example.com'},
                request_only=True
            ),
            OpenApiExample(
                name='Successful response',
                summary='200 OK',
                value={'message': 'If the email exists, a reset link will be sent'},
                response_only=True
            ),
            OpenApiExample(
                name='Invalid email',
                summary='400 Bad Request',
                value={'email': ['Invalid email format']},
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

            frontend_reset_url = f"{FRONTEND_URL}/reset-password?uid={uid}&token={token}"

            subject = 'Password reset'
            message = (
                f"Hello {user.first_name},\n\n"
                f"Use the following link to reset your password: {frontend_reset_url}\n\n"
                f"The link is valid for 1 hour."
            )
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
        except User.DoesNotExist:
            pass
        return Response(
            {'message': 'If the email exists, a reset link will be sent'},
            status=status.HTTP_200_OK
        )


@extend_schema(tags=['Users'])
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordInputSerializer

    def get(self, request):
        uid = request.GET.get('uid')
        token = request.GET.get('token')

        if not uid or not token:
            params = urlencode(
                {'reset_status': 'error', 'error': 'The password reset link is invalid or corrupted.'})
            redirect_url = f"{FRONTEND_URL}/forgot-password?{params}"
            return redirect(redirect_url)

        try:
            uid_int = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=uid_int)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            params = urlencode(
                {'reset_status': 'error', 'error': 'The password reset link is invalid or corrupted.'})
            redirect_url = f"{FRONTEND_URL}/forgot-password?{params}"
            return redirect(redirect_url)

        if not default_token_generator.check_token(user, token):
            params = urlencode(
                {'reset_status': 'error', 'error': 'The password reset link is invalid or expired.'})
            redirect_url = f"{FRONTEND_URL}/forgot-password?{params}"
            return redirect(redirect_url)

        redirect_url = f"{FRONTEND_URL}/forgot-password?uid={uid}&token={token}"
        return redirect(redirect_url)

    @extend_schema(
        tags=['Users'],
        request=ResetPasswordInputSerializer,
        responses={
            200: OpenApiResponse(description="Password changed successfully"),
            400: OpenApiResponse(description='Validation error or invalid/expired token')
        },
        examples=[
            OpenApiExample(
                name='Reset password',
                summary='POST /api/users/reset-password/',
                value={'uid': '<uid>', 'token': '<token>', 'new_password': 'newsecret123'},
                request_only=True
            ),
            OpenApiExample(
                name='Successful reset',
                summary='200 OK',
                value={'message': 'Password changed successfully'},
                response_only=True
            ),
            OpenApiExample(
                name='Invalid token',
                summary='400 Bad Request',
                value={'non_field_errors': ['Invalid or expired token']},
                response_only=True
            )
        ]
    )
    def post(self, request):
        serializer = ResetPasswordInputSerializer(data=request.data)
        expect_json = wants_json_response(request)

        if serializer.is_valid():
            try:
                serializer.save()
                if expect_json:
                    return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)

                params = urlencode({'reset_status': 'success', 'message': 'Password changed successfully'})
                redirect_url = f"{FRONTEND_URL}/forgot-password?{params}"
                return redirect(redirect_url)

            except Exception as e:
                error_message = "Error while resetting the password."
                if hasattr(e, 'detail'):
                    if isinstance(e.detail, dict):
                        error_message = str(e.detail)
                    elif isinstance(e.detail, list):
                        error_message = str(e.detail[0]) if e.detail else error_message
                    else:
                        error_message = str(e.detail)

                if expect_json:
                    return Response({'error': error_message}, status=status.HTTP_400_BAD_REQUEST)

                params = urlencode({'reset_status': 'error', 'error': error_message})
                redirect_url = f"{FRONTEND_URL}/forgot-password?{params}"
                return redirect(redirect_url)

        else:
            first_field_errors = next(iter(serializer.errors.values()), [])
            error_message = str(first_field_errors[0]) if first_field_errors else "Validation error"

            if expect_json:
                return Response({'error': error_message}, status=status.HTTP_400_BAD_REQUEST)

            params = urlencode({'reset_status': 'error', 'error': error_message})
            redirect_url = f"{FRONTEND_URL}/forgot-password?{params}"
            return redirect(redirect_url)


@extend_schema(
    tags=['Users'],
    summary='Obtain JWT tokens',
    description='POST /api/users/token/ — obtain an access and refresh token pair',
    request=TokenObtainPairSerializer,
    responses={
        200: TokenObtainPairSerializer,
        400: OpenApiResponse(description='Validation error'),
        401: OpenApiResponse(description='Invalid credentials'),
    },
    examples=[
        OpenApiExample(
            name='Obtain tokens',
            summary='POST /api/users/token/',
            value={'email': 'u@mail.com', 'password': 'secret123'},
            request_only=True
        ),
        OpenApiExample(
            name='Successful response',
            summary='200 OK',
            value={'access': '<access_token>', 'refresh': '<refresh_token>'},
            response_only=True
        ),
        OpenApiExample(
            name='Invalid credentials',
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
    summary='Refresh access token',
    description='POST /api/users/token/refresh/ — exchange refresh for a new access token',
    request=TokenRefreshSerializer,
    responses={
        200: TokenRefreshSerializer,
        400: OpenApiResponse(description='Validation error'),
    },
    examples=[
        OpenApiExample(
            name='Refresh token',
            summary='POST /api/users/token/refresh/',
            value={'refresh': '<refresh_token>'},
            request_only=True
        ),
        OpenApiExample(
            name='Successful response',
            summary='200 OK',
            value={'access': '<new_access_token>'},
            response_only=True
        ),
        OpenApiExample(
            name='Invalid refresh token',
            summary='400 Bad Request',
            value={'detail': 'Token is invalid or expired'},
            response_only=True
        )
    ],
    auth=[]
)
class TokenRefreshWithTag(TokenRefreshView):
    serializer_class = TokenRefreshSerializer


@extend_schema(
    tags=['Users'],
    description="Authorization through OAuth providers (Google, Facebook)",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'provider': {
                    'type': 'string',
                    'enum': ['google', 'facebook'],
                    'description': 'OAuth provider name'
                },
                'access_token': {
                    'type': 'string',
                    'description': 'Access token received from the OAuth provider'
                }
            },
            'required': ['provider', 'access_token']
        }
    },
    responses={
        200: OpenApiResponse(
            description="Successful OAuth authorization",
            response={
                "type": "object",
                "properties": {
                    "access": {"type": "string", "description": "JWT access token"},
                    "refresh": {"type": "string", "description": "JWT refresh token"},
                    "user": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "email": {"type": "string", "format": "email"},
                            "first_name": {"type": "string"},
                            "last_name": {"type": "string"},
                            "date_joined": {"type": "string", "format": "date-time"}
                        }
                    }
                }
            }
        ),
        400: OpenApiResponse(description='Validation error or invalid token'),
    },
    examples=[
        OpenApiExample(
            name='OAuth login (Google)',
            summary='POST /api/users/oauth/',
            value={'provider': 'google', 'access_token': '<google_oauth2_token>'},
            request_only=True
        ),
        OpenApiExample(
            name='OAuth login (Facebook)',
            summary='POST /api/users/oauth/',
            value={'provider': 'facebook', 'access_token': '<facebook_access_token>'},
            request_only=True
        ),
        OpenApiExample(
            name='Successful OAuth response',
            summary='200 OK',
            value={
                'access': '<access_token>',
                'refresh': '<refresh_token>',
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
            name='Invalid token',
            summary='400 Bad Request',
            value={'detail': 'Unable to validate token'},
            response_only=True
        )
    ],
    auth=[]
)
class OAuthLoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Users'],
        request=OAuthLoginSerializer,
        responses={
            200: OpenApiResponse(
                description="Successful OAuth authorization",
                response={
                    "type": "object",
                    "properties": {
                        "access": {"type": "string"},
                        "refresh": {"type": "string"},
                        "user": UserSerializer.Meta.fields
                    }
                }
            ),
            400: OpenApiResponse(description='Validation error or invalid token'),
        },
        examples=[
            OpenApiExample(
                name='OAuth login (Google)',
                summary='POST /api/users/oauth/',
                value={
                    'provider': 'google',
                    'access_token': '<google_oauth2_token>'
                },
                request_only=True
            ),
            OpenApiExample(
                name='OAuth login (Facebook)',
                summary='POST /api/users/oauth/',
                value={
                    'provider': 'facebook',
                    'access_token': '<facebook_access_token>'
                },
                request_only=True
            ),
            OpenApiExample(
                name='Successful OAuth response',
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
                name='Invalid token',
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
                description='User ID retrieved successfully'
            ),
            401: OpenApiResponse(description='Token not provided or invalid'),
        },
        examples=[
            OpenApiExample(
                name='Successful response',
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

    @extend_schema(
        request=ResendActivationSerializer,
        responses={
            200: OpenApiResponse(description="A confirmation email has been sent to your email address."),
            400: OpenApiResponse(description='A user with this email was not found or is already activated.'),
        },
        examples=[
            OpenApiExample(
                name='Resend request',
                summary='POST /api/users/resend-activation/',
                value={'email': 'user@example.com'},
                request_only=True
            ),
            OpenApiExample(
                name='Successful resend',
                summary='200 OK',
                value={'message': 'A confirmation email has been sent to your email address.'},
                response_only=True
            ),
            OpenApiExample(
                name='User not found',
                summary='400 Bad Request',
                value={'detail': 'A user with this email was not found.'},
                response_only=True
            ),
            OpenApiExample(
                name='User already activated',
                summary='400 Bad Request',
                value={'detail': 'This account is already activated.'},
                response_only=True
            ),
        ],
        auth=[]
    )
    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response({'detail': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'detail': 'A user with this email was not found.'}, status=status.HTTP_400_BAD_REQUEST)

        if user.is_active:
            return Response({'detail': 'This account is already activated.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            activation_path = reverse('activate', kwargs={'uidb64': uid, 'token': token})
            activation_url = build_public_url(request, activation_path)

            subject = 'Resend registration confirmation'
            message = (
                f'Hello {user.first_name},\n\n'
                f'You requested that the registration confirmation email be sent again.\n'
                f'Please click the link below to activate your account:\n'
                f'{activation_url}\n\n'
                f'If you did not make this request, simply ignore this email.'
            )

            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False
            )
            logger.info(f"Resent activation email to {user.email} (ID: {user.id})")

            return Response({"message": "A confirmation email has been sent to your email address."},
                            status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error while resending activation email for {email}: {e}")
            return Response({'detail': 'An error occurred while sending the email. Please try again later.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
