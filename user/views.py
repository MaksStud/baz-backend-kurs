from django.core.cache import cache
from django.conf import settings

from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView

from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import BazhayUser, Address, PostAddress, AccessToAddress, AccessToPostAddress, UserExponentPushToken
from .authentication import IgnoreInvalidTokenAuthentication
from .serializers import (CreateUserSerializer,
                          ConfirmCodeSerializer,
                          UpdateUserSerializers,
                          EmailUpdateSerializer,
                          EmailConfirmSerializer,
                          GuestUserSerializer,
                          ConvertGuestUserSerializer,
                          UpdateUserPhotoSerializer,
                          GoogleAuthSerializer,
                          ReturnBazhayUserSerializer,
                          AddressSerializer,
                          PostAddressSerializer,
                          AccessToAddressSerializer,
                          AccessToPostAddressSerializer,
                          AppleAuthSerializer,
                          UserExponentPushTokenSerializer)

from .utils import save_and_send_confirmation_code
from .filters import BazhayUserFilter

from permission.permissions import (IsRegisteredUser,
                                    IsRegisteredUserOrReadOnly,
                                    IsAuthorOrReadOnly)


def is_valid(serializer: serializers.Serializer) -> Response:
    """
    Validates and processes data using the provided serializer.

    If the serializer data is valid, the method saves the data and sends a confirmation code.
    Returns an HTTP response indicating the result of the validation.

    Args:
        serializer (serializers.Serializer): The serializer instance containing the data to be validated.

    Returns:
        Response: HTTP response with status 200 OK if valid, or 400 Bad Request with errors if invalid.
    """
    if serializer.is_valid():
        user = serializer.save()
        save_and_send_confirmation_code(user.email)
        return Response(status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AuthViewSet(viewsets.ViewSet):
    """
    ViewSet for handling user authentication tasks such as registration, login,
    and transforming guest users into standard users.

    Provides endpoints for user registration, logging in, and converting guest users.
    Additionally, it includes a confirmation endpoint to verify codes and complete user registration or conversion.

    Methods:
        create(request: Request) -> Response:
            Handles user registration, login, or conversion of a guest user to a standard user.

        confirm_code(request: Request) -> Response:
            Validates the confirmation code, completes the user registration or conversion,
            and returns JWT tokens along with the registration status.
    """
    authentication_classes = [IgnoreInvalidTokenAuthentication]
    permission_classes = [AllowAny]

    def create(self, request: Request) -> Response:
        """
        Handles registration, login, or transformation of a guest user into a standard user.

        If the user is authenticated and is a guest, converts them to a standard user.
        Otherwise, processes registration or login for a new user.

        Args:
            request (Request): The incoming request containing user data.

        Returns:
            Response: HTTP response with status 200 OK if successful, or 400 Bad Request with errors if validation fails.
        """
        if request.user.is_authenticated and request.user.is_guest:
            serializer = ConvertGuestUserSerializer(data=request.data, instance=request.user)
            return is_valid(serializer)
        else:
            serializer = CreateUserSerializer(data=request.data)
            return is_valid(serializer)

    @action(detail=False, methods=['post'], url_path='confirm')
    def confirm_code(self, request: Request) -> Response:
        """
        Validates the confirmation code and completes the user registration or conversion process.

        If the user is a guest, it converts them to a standard user. Deletes the confirmation code from cache,
        generates JWT tokens, and returns user registration status along with the tokens.

        Args:
            request (Request): The incoming request containing the confirmation code.

        Returns:
            Response: HTTP response with status 200 OK if the confirmation is successful and user is registered,
                      or 201 Created if the user is newly registered, or 400 Bad Request with errors if validation fails.
        """
        serializer = ConfirmCodeSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            if user.is_guest:
                serializer = ConvertGuestUserSerializer(instance=user, data={'email': user.email})
                if serializer.is_valid():
                    serializer.save()

            cache.delete(f"code_{user.email}")

            refresh = RefreshToken.for_user(user)
            is_already_registered = user.is_already_registered
            data = {
                'is_already_registered': is_already_registered,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
            status_code = status.HTTP_200_OK if is_already_registered else status.HTTP_201_CREATED
            return Response(data, status=status_code)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateUserViewSet(viewsets.GenericViewSet,
                        mixins.UpdateModelMixin,
                        mixins.RetrieveModelMixin,
                        mixins.DestroyModelMixin):
    """
    ViewSet for retrieving, updating, and deleting the currently authenticated user.

    Provides functionality to update or retrieve user details, and delete the user.
    Access is controlled to ensure only the authenticated user can update or delete their own data.

    Methods:
        get_object():
            Returns the user object that matches the current authenticated user's ID.
    """
    queryset = BazhayUser.objects.all()
    serializer_class = UpdateUserSerializers
    permission_classes = [IsRegisteredUser]

    def get_object(self):
        """
        Returns the user object that corresponds to the current authenticated user's ID.

        Returns:
            BazhayUser: The user instance associated with the authenticated user.
        """
        return self.queryset.filter(id=self.request.user.id).first()

    def retrieve(self, request, *args, **kwargs):
        cache_key = f'profile_{request.user.id}'
        value = cache.get(cache_key)
        if value:
            return Response(value)
        response = super().retrieve(request)
        data = response.data
        cache.set(cache_key, data, settings.CACHES_TIME)
        return response


class UpdateUserEmailViewSet(viewsets.ViewSet):
    """
    ViewSet for updating the user's email address and confirming the email change.

    Provides actions for requesting an email change and confirming the change via a confirmation code.

    Methods:
        create(request: Request) -> Response:
            Initiates an email change request by validating the new email and sending a confirmation code.

        confirm_code(request: Request) -> Response:
            Confirms the email change by validating the confirmation code and updating the user's email.
    """
    permission_classes = [IsRegisteredUser]

    def create(self, request: Request) -> Response:
        """
        Requests an email change by validating the new email and sending a confirmation code.

        Args:
            request (Request): The incoming request containing the new email address.

        Returns:
            Response: A response with status 200 if the email change request is successful,
                      or status 400 with validation errors if the request fails.
        """
        serializer = EmailUpdateSerializer(data=request.data)
        user = request.user

        if serializer.is_valid():
            new_email = serializer.validated_data['email']
            cache.set(f"pending_email_change_{user.id}", new_email, timeout=3600)
            save_and_send_confirmation_code(new_email)
            return Response(status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='confirm')
    def confirm_code(self, request: Request) -> Response:
        """
        Confirms the email change by validating the confirmation code and updating the user's email.

        Args:
            request (Request): The incoming request containing the confirmation code.

        Returns:
            Response: A response with status 200 if the confirmation is successful,
                      or status 400 with validation errors if the confirmation fails.
        """
        user = request.user
        serializer = EmailConfirmSerializer(data=request.data, user=user)

        if serializer.is_valid():
            serializer.save()
            return Response(status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GuestUserViewSet(viewsets.ViewSet):
    """
    ViewSet for creating and logging in guest users.

    This viewset handles the creation of guest users and provides JWT tokens for authentication.
    It uses custom authentication and permission classes to allow access without standard token validation.

    Methods:
        create(request: Request) -> Response:
            Handles the creation of a guest user and returns JWT tokens if successful.
            Returns a 201 status code on successful creation, or a 400 status code with errors if validation fails.
    """
    authentication_classes = [IgnoreInvalidTokenAuthentication]
    permission_classes = [AllowAny]

    def create(self, request: Request) -> Response:
        """
        Creates a guest user and returns JWT tokens for authentication.

        Args:
            request (Request): The incoming request containing the guest user data.

        Returns:
            Response: A response containing refresh and access tokens if the user is successfully created,
                      or validation errors if the creation fails.
        """
        serializer = GuestUserSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)

            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateUserPhotoViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for updating the user's profile photo.

    Provides endpoints for updating the photo of the currently authenticated user.
    The viewset ensures that only the authenticated user can update their own photo.

    Methods:
        get_object():
            Returns the object (user) that matches the current authenticated user's ID.
    """
    queryset = BazhayUser.objects.all()
    serializer_class = UpdateUserPhotoSerializer
    permission_classes = [IsRegisteredUserOrReadOnly]

    def get_object(self):
        """
        Returns the user object that corresponds to the current authenticated user's ID.
        :returns BazhayUser: The user instance associated with the authenticated user.
        """
        return self.request.user


class GoogleLoginView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for handling Google authorization and user login.

    This viewset processes Google OAuth2 tokens, creates or retrieves a user based on the token,
    and returns JWT tokens for authenticated access.

    Methods:
        create(request: Request, *args, **kwargs) -> Response:
            Validates the Google authentication token, creates or retrieves a user,
            and returns access and refresh tokens for the user.
    """
    serializer_class = GoogleAuthSerializer

    def create(self, request: Request, *args, **kwargs) -> Response:
        """
        Handles the creation of a user based on the Google OAuth2 token and returns JWT tokens.

        Args:
            request (Request): The incoming request containing the Google token.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Response: A response containing access and refresh tokens if the token is valid.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        data = {
            'is_already_registered': user.is_already_registered,
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }
        return Response(data, status=status.HTTP_200_OK)


class ListUserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving user details.

    Provides read-only operations for listing all users and retrieving individual user details.
    Applies authentication, pagination, and filtering to the user list.

    Methods:
        get_serializer_class():
            Returns the appropriate serializer class based on the action being performed.

        get_queryset():
            Excludes the current authenticated user from the queryset.
    """
    serializer_class = ReturnBazhayUserSerializer
    queryset = BazhayUser.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = BazhayUserFilter

    def get_serializer_class(self):
        """
        Returns the appropriate serializer class based on the action being performed.

        For 'list' action, returns ReturnBazhayUserSerializer.
        For 'retrieve' action, returns UpdateUserSerializers.

        Returns:
            Serializer: The serializer class for the current action.
        """
        serializers = {
            'list': ReturnBazhayUserSerializer,
            'retrieve': UpdateUserSerializers
        }

        return serializers.get(self.action, ReturnBazhayUserSerializer)

    def get_queryset(self):
        """
        Returns the queryset of users excluding the current authenticated user.

        Returns:
            QuerySet: The filtered queryset of users.
        """
        return self.queryset.exclude(id=self.request.user.id)


class BaseAddressViewSet(viewsets.ModelViewSet):
    """Base viewset for handling address-related operations for authenticated users."""
    permission_classes = [IsAuthenticated, IsAuthorOrReadOnly]
    http_method_names = ['get', 'put', 'patch', 'delete']

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs.get('pk'))

    def create_default_address(self):
        """This should be overridden in subclasses for a particular model."""
        raise NotImplementedError('create_default_address method should be implemented in subclasses.')

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(self.get_object())
        return Response(serializer.data, status=status.HTTP_200_OK)

    def list(self, request: Request, *args, **kwargs) -> Response:
        """
        Lists all addresses associated with the authenticated user. If no addresses exist, it
        creates a default address and returns it.

        :returns: A Response object containing serialized address data.
        """
        queryset = self.get_queryset()
        my_address = self.get_queryset().filter(user=request.user)

        if not my_address.exists():
            self.create_default_address()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        """
        Updates an address only if the authenticated user is the owner of the address.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        if instance.user != request.user:
            raise PermissionDenied("You do not have permission to edit this address.")

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data, status=status.HTTP_200_OK)


class AddressViewSet(BaseAddressViewSet):
    """Viewset for handling CRUD operations related to the Address model."""
    queryset = Address.objects.all()
    serializer_class = AddressSerializer

    def get_queryset(self):
        user = self.request.user

        allowed_users = AccessToAddress.objects.filter(
            bazhay_user=user,
            is_approved=True
        ).values_list('asked_bazhay_user', flat=True)

        return self.queryset.filter(
            Q(user=user) |
            Q(user__in=allowed_users)
        )


    def create_default_address(self) -> Address:
        """Creates a default Address instance for the current authenticated user.

        :returns: A newly created Address instance."""
        return Address.objects.create(user=self.request.user)


class PostAddressViewSet(BaseAddressViewSet):
    """Viewset for handling CRUD operations related to the PostAddress model."""
    queryset = PostAddress.objects.all()
    serializer_class = PostAddressSerializer

    def get_queryset(self):
        user = self.request.user

        allowed_users = AccessToPostAddress.objects.filter(
            bazhay_user=user,
            is_approved=True
        ).values_list('asked_bazhay_user', flat=True)

        return self.queryset.filter(
            Q(user=user) |
            Q(user__in=allowed_users)
        )

    def create_default_address(self) -> PostAddress:
        """
        Creates a default PostAddress instance for the current authenticated user.
        :returns: A newly created PostAddress instance.
        """
        return PostAddress.objects.create(user=self.request.user)


class BaseAccessRequestViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = None
    model = None

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


class BaseGetAccessRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = None
    model = None

    def get_queryset(self):
        return self.queryset.filter(asked_bazhay_user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def approved(self, request, pk=None):
        try:
            access_request = self.get_object()

            if access_request.asked_bazhay_user != request.user:
                return Response({"detail": "You cannot confirm this request."}, status=status.HTTP_403_FORBIDDEN)

            access_request.is_approved = True
            access_request.save()

            return Response(status=status.HTTP_200_OK)

        except self.model.DoesNotExist:
            return Response({"detail": "The requests are unknown."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def not_approved(self, request, pk=None):
        try:
            access_request = self.get_object()

            if access_request.asked_bazhay_user != request.user:
                return Response({"detail": "You cannot confirm this request."}, status=status.HTTP_403_FORBIDDEN)

            access_request.is_not_approved = True
            access_request.save()

            return Response(status=status.HTTP_200_OK)

        except self.model.DoesNotExist:
            return Response({"detail": "The requests are unknown."}, status=status.HTTP_404_NOT_FOUND)


class CreateAccessRequestViewSet(BaseAccessRequestViewSet):
    queryset = AccessToAddress.objects.all()
    serializer_class = AccessToAddressSerializer
    model = AccessToAddress


class GetAccessRequestViewSet(BaseGetAccessRequestViewSet):
    queryset = AccessToAddress.objects.all()
    serializer_class = AccessToAddressSerializer
    model = AccessToAddress


class CreatePostAddressAccessRequestViewSet(BaseAccessRequestViewSet):
    queryset = AccessToPostAddress.objects.all()
    serializer_class = AccessToPostAddressSerializer
    model = AccessToPostAddress


class GetPostAddressAccessRequestViewSet(BaseGetAccessRequestViewSet):
    queryset = AccessToPostAddress.objects.all()
    serializer_class = AccessToPostAddressSerializer
    model = AccessToPostAddress


class AppleLoginView(APIView):
    """View to auth with Apple"""
    def post(self, request):
        serializer = AppleAuthSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data.get('user')
            if user is None:
                user = serializer.save()

            refresh = RefreshToken.for_user(user)
            return Response({
                'is_already_registered': user.is_already_registered,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserExponentPushTokenViewSet(viewsets.ModelViewSet):
    """Exponent Push Token View Set."""
    serializer_class = UserExponentPushTokenSerializer
    queryset = UserExponentPushToken.objects.all()
    permission_classes = [IsAuthenticated, IsRegisteredUser]
    lookup_field = 'token'

    def get_queryset(self):
        return self.queryset.filter(bazhay_user=self.request.user)
