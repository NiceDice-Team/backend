from rest_framework.permissions import BasePermission, IsAuthenticatedOrReadOnly, SAFE_METHODS


def is_admin_user(user):
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


ReadOnlyOrAuthenticated = IsAuthenticatedOrReadOnly


class IsAdmin(BasePermission):

    def has_permission(self, request, view):
        return is_admin_user(request.user)


class IsSelfOrAdmin(BasePermission):

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return is_admin_user(request.user) or obj.pk == request.user.pk


class OwnerOrAdminCanModify(BasePermission):
    allows_anonymous_reads = True

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return is_admin_user(request.user) or getattr(obj, 'user_id', None) == request.user.pk
