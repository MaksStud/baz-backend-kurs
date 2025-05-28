from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, (TokenError, InvalidToken)):
        return Response(
            {"detail": "Token is invalid or expired"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    return response
