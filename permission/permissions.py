from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsGuestUser(BasePermission):
    """Provides a toast to a guest user """
    def has_permission(self, request, view) -> bool:
        return request.user.is_authenticated and request.user.is_guest


class IsRegisteredUser(BasePermission):
    """Grant access to a regular user, deny access to a guest """
    def has_permission(self, request, view) -> bool:
        return request.user.is_authenticated and not request.user.is_guest


class IsRegisteredUserOrReadOnly(BasePermission):
    """Give full access to a regular user, if a guest user, then only for reading """
    def has_permission(self, request, view) -> bool:
        if not request.user.is_authenticated:
            return False

        if request.user.is_guest and request.method in SAFE_METHODS:
            return True

        if not request.user.is_guest:
            return True

        return False


class IsOwner(BasePermission):
    """
    Allows access only to the author (owner) of the record.
    """
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsPremium(BasePermission):
    """
    Access only for premium users.
    """
    def has_object_permission(self, request, view, obj):
        return request.user.is_premium()


class IsAuthorOrReadOnly(BasePermission):
    """
    Custom permission to allow only the author of an object to modify it,
    while others can only read it (if they have access).
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.user == request.user