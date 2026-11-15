from cart.infrastructure.models import GuestCart
from rest_framework.permissions import BasePermission

GUEST_TOKEN_HEADER = 'X-Guest-Token'


class IsAuthenticatedOrHasGuestCart(BasePermission):
    message = 'Потрібна автентифікація або токен гостьового кошика у заголовку X-Guest-Token.'

    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            return True
        return GuestCart.get_by_token(request.headers.get(GUEST_TOKEN_HEADER)) is not None
