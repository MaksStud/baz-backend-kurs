from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class IgnoreInvalidTokenAuthentication(TokenAuthentication):
    """
    Custom authentication class that inherits from TokenAuthentication.

    This class overrides the `authenticate` method to handle invalid token errors gracefully.
    Instead of raising an `AuthenticationFailed` exception, it returns `None` when an invalid token is encountered.
    This allows the request to continue processing without interruption.

    Methods:
        authenticate(request):
            Attempts to authenticate the user using the provided request.
            Returns a two-tuple of `(user, token)` if authentication is successful,
            or `None` if authentication fails due to an invalid token.
    """
    def authenticate(self, request):
        """
        Attempt to authenticate the user using the provided request.

        This method calls the parent class's `authenticate` method and catches
        any `AuthenticationFailed` exceptions that occur. If an exception is caught,
        it returns `None` instead of raising the exception.

        Args:
            request: The request object containing the authentication information.

        Returns:
            tuple or None: A two-tuple of `(user, token)` if authentication is successful,
            or `None` if authentication fails due to an invalid token.
        """
        try:
            return super().authenticate(request)
        except AuthenticationFailed:
            return None
