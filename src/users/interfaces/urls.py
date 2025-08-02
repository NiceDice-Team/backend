from django.urls import path
from users.interfaces.views import (UserListCreateView, UserRetrieveUpdateDestroyView, RegisterView, LogoutView,
                                    ForgotPasswordView, ResetPasswordView, ActivateView, TokenObtainPairWithTag,
                                    TokenRefreshWithTag, OAuthLoginView, )

from src.users.interfaces.views import GetUserIdView

urlpatterns = [
    # CRUD для користувачів
    path('', UserListCreateView.as_view(), name='user-list-create'),
    path('<int:pk>/', UserRetrieveUpdateDestroyView.as_view(), name='user-detail'),
    path('auth/user-id/', GetUserIdView.as_view(), name='get-user-id'),

    # Реєстрація / активація / логаут
    path('register/', RegisterView.as_view(), name='register'),
    path('activate/<str:uidb64>/<str:token>/', ActivateView.as_view(), name='activate'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # JWT токени
    path('token/', TokenObtainPairWithTag.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshWithTag.as_view(), name='token_refresh'),

    # Forgot & Reset Password
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),

    # OAuth
    path('oauth/', OAuthLoginView.as_view(), name='oauth_login'),

]
