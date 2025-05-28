import logging
import json
import re
from typing import Optional

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from user.models import BazhayUser


logger = logging.getLogger(__name__)


class LogResponsesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.path.startswith('/api/'):
            content_type = response.get('Content-Type', '').lower()

            if 'application/json' in content_type:
                try:
                    response_data = json.loads(response.content.decode('utf-8'))
                    logger.info(
                        f"Response for {request.path}: {response.status_code} - {json.dumps(response_data, indent=4)}")
                except json.JSONDecodeError:
                    logger.info(
                        f"Response for {request.path}: {response.status_code} - {response.content.decode('utf-8')}")
            elif 'text/html' in content_type:
                logger.info(f"Response for {request.path}: {response.status_code} - HTML content")
            else:
                logger.info(f"Response for {request.path}: {response.status_code} - {response.content.decode('utf-8')}")

        return response


class JWTAuthMiddleware:
    """
    Custom JWT Authentication Middleware to support JWT-based auth with WebSockets.
    """
    def __init__(self, inner: callable) -> None:
        """
        Initialize the JWTAuthMiddleware with the inner WebSocket consumer.

        :param inner: The WebSocket consumer to wrap.
        """
        self.inner = inner

    async def __call__(self, scope: dict, receive: callable, send: callable) -> None:
        """
        Handle the WebSocket connection and authenticate the user using JWT.

        :param scope: The scope of the WebSocket connection.
        :param receive: A callable to receive messages from the WebSocket.
        :param send: A callable to send messages to the WebSocket.
        :return: None
        """
        logger.info(scope)
        user = await self.get_user_from_session(scope)

        if not user:
            token = self.get_token_from_scope(scope)
            user = await self.authenticate_with_jwt(token)

        scope['user'] = user
        await self.inner(scope, receive, send)

    def get_token_from_scope(self, scope: dict) -> Optional[str]:
        """
        Extract the JWT token from the WebSocket scope.

        :param scope: The scope of the WebSocket connection.
        :return: The JWT token if found, else None.
        """
        token = None
        for item in scope['query_string'].decode().split('&'):
            if item.startswith('token='):
                token = item.split('=')[1]
        return token

    async def authenticate_with_jwt(self, token: str) -> Optional[User]:
        """
        Authenticate the user using the provided JWT token.

        :param token: The JWT token to validate.
        :return: The authenticated user.
        :raises AuthenticationFailed: If the token is invalid.
        """
        if not token:
            raise AuthenticationFailed('Authorization required')

        try:
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            user = await sync_to_async(jwt_auth.get_user)(validated_token)
            return user
        except Exception as e:
            raise AuthenticationFailed('Invalid token')

    @database_sync_to_async
    def get_user_from_session(self, scope: dict) -> Optional[User]:
        """
        Attempt to retrieve the user from the session.

        :param scope: The scope of the WebSocket connection.
        :return: The user if found, else None.
        """
        sessionid = self.extract_session_id(scope['headers'])
        logger.info(sessionid)

        if not sessionid:
            return None

        try:
            session = Session.objects.get(pk=sessionid)
            user_id = session.get_decoded().get('_auth_user_id')
            logger.info(f'User if from session {user_id}')
            user = BazhayUser.objects.get(id=user_id)
            return user
        except (Session.DoesNotExist, User.DoesNotExist):
            return None

    def extract_session_id(self, headers: list) -> Optional[str]:
        """
        Extract the session ID from the WebSocket headers.

        :param headers: The headers from the WebSocket connection.
        :return: The session ID if found, else None.
        """
        for header in headers:
            if header[0] == b'cookie':
                cookie_str = header[1].decode('utf-8')
                match = re.search(r'sessionid=([a-z0-9-]+)', cookie_str)
                if match:
                    return match.group(1)
        return None
