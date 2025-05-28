import requests as req

from django.core.cache import cache

from rest_framework import serializers
import jwt

from .models import (BazhayUser,
                     Address,
                     PostAddress,
                     AccessToAddress,
                     AccessToPostAddress,
                     UserExponentPushToken)

from subscription.models import Subscription

from google.oauth2 import id_token
from google.auth.transport import requests

from datetime import datetime


class CreateUserSerializer(serializers.Serializer):
    """
    Serializer for creating or retrieving a user based on the provided email.

    Fields:
        - email (str): The email address to create or get the user by.

    Methods:
        create(validated_data: dict) -> BazhayUser:
            Retrieves an existing user or creates a new user with the given email.
            If a new user is created, they are marked as not already registered.
    """
    email = serializers.EmailField()

    def create(self, validated_data: dict) -> BazhayUser:
        """
        Creates or retrieves a user using the provided email.

        Args:
            validated_data (dict): The validated data containing the user's email.

        Returns:
            BazhayUser: The user instance that was created or retrieved.
        """
        email = validated_data.get('email')
        user, created = BazhayUser.objects.get_or_create(email=email)

        if created:
            user.is_already_registered = False

        user.save()
        return user


class ConfirmCodeSerializer(serializers.Serializer):
    """
    Serializer for confirming a code sent to the user's email.

    This serializer checks the provided confirmation code against the one stored in the cache.

    Fields:
        - email (str): The email address of the user.
        - code (str): The confirmation code provided by the user (6 characters max).

    Methods:
        validate(data: dict) -> dict:
            Validates the email and confirmation code. Checks if the code matches the cached code
            and ensures the user exists. Adds the user to the validated data.
    """
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)

    def validate(self, data: dict) -> dict:
        """
        Validates the confirmation code and ensures the user exists.

        Args:
            data (dict): A dictionary containing 'email' and 'code'.

        Returns:
            dict: The validated data with the user object added.

        Raises:
            serializers.ValidationError: If the code is invalid or the user does not exist.
        """
        email = data.get('email')

        try:
            user = BazhayUser.objects.get(email=email)
        except BazhayUser.DoesNotExist:
            raise serializers.ValidationError({'email': 'User not found'})

        email = data.get('email')
        confirmation_code = data.get('code')

        cached_code = cache.get(f"code_{email}")

        if user.is_superuser:
            data['user'] = user
        elif cached_code != confirmation_code:
            raise serializers.ValidationError({'code': 'Invalid confirmation code'})

        data['user'] = user
        return data


class UpdateUserSerializers(serializers.ModelSerializer):
    """
    Serializer for retrieving or updating user data.

    This serializer provides a read-only view of the user's email, guest status, photo,
    subscription counts, subscriber counts, and subscription status. Additionally,
    it includes methods to determine if the user is premium or subscribed to another user.
    """
    email = serializers.EmailField(read_only=True)
    is_guest = serializers.BooleanField(read_only=True)
    photo = serializers.ImageField(read_only=True)
    subscription = serializers.SerializerMethodField()
    subscriber = serializers.SerializerMethodField()
    is_premium = serializers.SerializerMethodField()
    is_subscribed = serializers.SerializerMethodField()
    is_addresses = serializers.SerializerMethodField()
    is_post_addresses = serializers.SerializerMethodField()

    class Meta:
        model = BazhayUser
        fields = ['id', 'photo', 'email', 'first_name', 'last_name', 'username',
                  'birthday', 'view_birthday', 'about_user', 'sex', 'is_guest', 'is_premium', 'is_already_registered',
                  'is_subscribed', 'subscription', 'subscriber', 'is_addresses', 'is_post_addresses',
                  'is_unviewed_notification']

    def get_subscription(self, obj):
        """
        Returns the count of subscriptions (the number of users the given user is subscribed to).
        """
        return obj.subscriptions.count()

    def get_subscriber(self, obj):
        """
        Returns the count of subscribers (the number of users subscribed to the given user).
        """
        return obj.subscribers.count()

    def get_is_premium(self, obj):
        """
        Returns whether the user has an active premium subscription.

        If no premium subscription exists, returns False.
        """
        try:
            return obj.premium.is_active
        except:
            return False

    def get_is_subscribed(self, obj):
        """
        Returns whether the requesting user (from the context) is subscribed to the given user.
        :args obj (BazhayUser): The user object to check the subscription status for.
        """
        request_user = self.context['request'].user
        return Subscription.is_subscribed(request_user, obj)

    def get_is_addresses(self, obj: BazhayUser) -> int | None:
        """
        Returns the ID of the address associated with the given user.
        :args obj (BazhayUser): The user object to check access to addresses.
        """
        address = Address.objects.filter(user=obj).first()
        return address.id if address else None

    def get_is_post_addresses(self, obj: BazhayUser) -> int | None:
        """
        Returns the ID of the post address associated with the given user.
        :args obj (BazhayUser): The user object to check access to post addresses.
        """
        post_address = PostAddress.objects.filter(user=obj).first()
        return post_address.id if post_address else None

    def update(self, instance, validated_data):
        cache_key = f'profile_{instance.id}'
        cache.delete(cache_key)
        return super().update(instance, validated_data)


class EmailUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating the user's email.

    This serializer validates the new email, ensuring that it is not already in use by another user.

    Fields:
        - email (str): The new email address to be assigned to the user.

    Methods:
        validate_email(value: str) -> str:
            Validates the email by checking if it is already used by another user.
    """

    email = serializers.EmailField()

    def validate_email(self, value: str) -> str:
        """
        Validates the provided email, ensuring it is not already in use by another user.

        Args:
            value (str): The email to be validated.

        Returns:
            str: The validated email.

        Raises:
            serializers.ValidationError: If the email is already associated with another user.
        """
        if BazhayUser.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email is already in use')
        return value


class EmailConfirmSerializer(serializers.Serializer):
    """
    Serializer for confirming the email change by validating a confirmation code.

    This serializer checks the provided confirmation code against the one stored in the cache
    and, if valid, updates the user's email to the new email stored in the cache.

    Fields:
        - code (str): The confirmation code provided by the user.

    Attributes:
        - user (BazhayUser): The user whose email is being confirmed and updated.

    Methods:
        validate_code(value: dict) -> dict:
            Validates the confirmation code against the cached value.

        save() -> None:
            Saves the new email for the user after successful confirmation and removes the cache.
    """
    code = serializers.CharField()

    def __init__(self, *args, **kwargs) -> None:
        """
        Initializes the serializer and extracts the user instance from the arguments.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments. The 'user' argument must be provided.
        """
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)

    def validate_code(self, value: str) -> str:
        """
        Validates the provided confirmation code by checking it against the cached code.

        Args:
            value (str): The confirmation code to be validated.

        Returns:
            str: The validated confirmation code.

        Raises:
            serializers.ValidationError: If there is no pending email change or the code is invalid.
        """
        new_email = cache.get(f"pending_email_change_{self.user.id}")
        if not new_email:
            raise serializers.ValidationError('No pending email change found')

        cached_code = cache.get(f"code_{new_email}")
        if cached_code != value:
            raise serializers.ValidationError('Invalid confirmation code')

        return value

    def save(self) -> None:
        """
        Saves the new email to the user's profile after successful code validation.

        Updates the user's email and clears the cache entries related to the email change.
        """
        new_email = cache.get(f"pending_email_change_{self.user.id}")
        self.user.email = new_email
        self.user.save()

        cache.delete(f"pending_email_change_{self.user.id}")
        cache.delete(f"code_{new_email}")


class GuestUserSerializer(serializers.Serializer):
    """
    Serializer for creating or retrieving a guest user based on their IMEI.

    This serializer checks if a guest user exists with the given IMEI. If not,
    it creates a new guest user and marks them as not already registered.

    Fields:
        - imei (str): The unique identifier for the guest user (e.g., a device IMEI).
    """
    imei = serializers.CharField()

    def create(self, validated_data: dict) -> BazhayUser:
        """
        Creates or retrieves a guest user using the provided IMEI.

        Args:
            validated_data (dict): The data containing the IMEI.

        Returns:
            BazhayUser: The guest user instance.
        """
        imei = validated_data.get('imei')
        user, created = BazhayUser.objects.get_or_create(is_guest=True, imei=imei, email=None)

        if created:
            user.is_already_registered = False
            user.save()

        return user


class ConvertGuestUserSerializer(serializers.ModelSerializer):
    """
    Serializer for converting a guest user into a standard user.

    This serializer updates the guest user's email and changes their status
    from a guest to a standard user.

    Fields:
        - email (str): The email to be assigned to the guest user.
    """

    class Meta:
        model = BazhayUser
        fields = ['email']

    def update(self, instance, validated_data: dict) -> BazhayUser:
        """
        Updates the guest user's email and converts them into a standard user.

        Args:
            instance (BazhayUser): The guest user instance being updated.
            validated_data (dict): The data containing the new email.

        Returns:
            BazhayUser: The updated user instance.
        """
        instance.email = validated_data.get('email', instance.email)
        instance.is_guest = False
        instance.save()
        return instance


class UpdateUserPhotoSerializer(serializers.ModelSerializer):
    """
    Serializer for updating the user's profile photo.

    This serializer allows the user to upload a new profile photo.

    Fields:
        - photo (ImageField): The new profile photo to be uploaded.
    """

    class Meta:
        model = BazhayUser
        fields = ['photo']

    def validate_photo(self, value):
        """
        Generate a new filename based on the current timestamp down to milliseconds.
        """
        if value:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            unique_filename = f"{timestamp}-{self.instance.username}-{value.name}"
            value.name = unique_filename
        return value

    def update(self, instance, validated_data):
        if 'photo' in validated_data:
            old_photo = instance.photo
            cache_key = f'profile_{instance.id}'
            cache.delete(cache_key)

            if old_photo:
                old_photo.delete(save=False)

            if validated_data.get('photo') is None:
                instance.photo = None

        return super().update(instance, validated_data)


class GoogleAuthSerializer(serializers.ModelSerializer):
    """
    Serializer for handling Google authorization via OAuth2.

    This serializer takes a Google OAuth2 token, validates it, and either retrieves
    an existing user or creates a new user based on the token's information.
    """
    token = serializers.CharField(write_only=True)

    class Meta:
        model = BazhayUser
        fields = ['id', 'token']

    def validate(self, attrs: dict) -> dict:
        """
        Validates the Google OAuth2 token and checks the issuer.

        :param attrs: The input data containing the 'token'.

        :return ict: The decoded token information.
        """
        id_info = id_token.verify_oauth2_token(attrs.get('token'), requests.Request())

        if id_info['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise serializers.ValidationError({'error': 'Wrong issuer.'})

        return id_info

    def create(self, validated_data: dict) -> BazhayUser:
        """
        Creates or retrieves a BazhayUser based on the validated token data.

        :args validated_data (dict): The data returned by the validate method, which includes
                                   decoded information from the token.
        :returns BazhayUser: The user object that was created or retrieved.

        """
        try:
            user, created = BazhayUser.objects.get_or_create(
                email=validated_data.get('email', ''),
                defaults={
                    'username': validated_data.get('email', ''),
                    'first_name': validated_data.get('given_name', ''),
                    'last_name': validated_data.get('family_name', ''),
                }
            )
            return user
        except Exception:
            raise serializers.ValidationError(detail='Something went wrong')


class ReturnBazhayUserSerializer(serializers.ModelSerializer):
    """
    Serializer for the BazhayUser model to return user information including
    whether the requesting user is subscribed to the given user.

    """
    is_subscribed = serializers.SerializerMethodField()
    subscriber = serializers.SerializerMethodField()
    is_premium = serializers.SerializerMethodField()
    is_addresses = serializers.SerializerMethodField()
    is_post_addresses = serializers.SerializerMethodField()

    class Meta:
        model = BazhayUser
        fields = ['id', 'photo', 'username', 'first_name', 'last_name', 'email', 'is_subscribed', 'subscriber',
                  'is_premium', 'is_addresses', 'is_post_addresses']
        read_only_fields = ['id', 'photo', 'username', 'first_name', 'last_name', 'is_subscribed', 'subscriber',
                            'is_premium', 'is_addresses', 'is_post_addresses']

    def get_is_subscribed(self, obj: BazhayUser) -> bool:
        """
        Determines if the current user is subscribed to the given BazhayUser object.

        Args:
            obj (BazhayUser): The user object for which the subscription status is being checked.

        Returns:
            bool: True if the current user is subscribed to the provided user, False otherwise.
        """
        return Subscription.is_subscribed(self.context['request'].user, obj)

    def get_subscriber(self, obj: BazhayUser) -> int:
        """
        Returns the count of subscribers (the number of users subscribed to the given user).

        :param obj: BazhayUser object for which the number of subscribers is counted.

        """
        return obj.subscribers.count()

    def get_is_premium(self, obj: BazhayUser) -> bool:
        return obj.is_premium()

    def get_is_addresses(self, obj: BazhayUser) -> int | None:
        """
        Returns the ID of the address associated with the given user.
        :args obj (BazhayUser): The user object to check access to addresses.
        """
        address = Address.objects.filter(user=obj).first()
        return address.id if address else None

    def get_is_post_addresses(self, obj: BazhayUser) -> int | None:
        """
        Returns the ID of the post address associated with the given user.
        :args obj (BazhayUser): The user object to check access to post addresses.
        """
        post_address = PostAddress.objects.filter(user=obj).first()
        return post_address.id if post_address else None


class BaseAccessToAddressSerializer(serializers.ModelSerializer):
    bazhay_user = ReturnBazhayUserSerializer(read_only=True)
    asked_bazhay_user = ReturnBazhayUserSerializer(read_only=True)

    class Meta:
        model = None
        fields = ['id', 'bazhay_user', 'asked_bazhay_user', 'is_approved']
        read_only_fields = ['id', 'is_approved']

    def validate(self, data):
        bazhay_user = self.context['request'].user
        asked_bazhay_user_id = self.initial_data.get('asked_bazhay_user')

        if not asked_bazhay_user_id:
            raise serializers.ValidationError("The user ID of the accessed user is not passed.")

        try:
            asked_bazhay_user = BazhayUser.objects.get(id=asked_bazhay_user_id)
        except BazhayUser.DoesNotExist:
            raise serializers.ValidationError(f"The user with id {asked_bazhay_user_id} does not exist.")

        if bazhay_user.id == asked_bazhay_user.id:
            raise serializers.ValidationError("You cannot send an access request to yourself.")

        data['asked_bazhay_user'] = asked_bazhay_user

        return data

    def create(self, validated_data):
        bazhay_user = self.context['request'].user

        access_request = self.Meta.model.objects.create(
            bazhay_user=bazhay_user,
            asked_bazhay_user=validated_data.get('asked_bazhay_user')
        )

        return access_request


class AccessToAddressSerializer(BaseAccessToAddressSerializer):
    class Meta(BaseAccessToAddressSerializer.Meta):
        model = AccessToAddress


class AccessToPostAddressSerializer(BaseAccessToAddressSerializer):
    class Meta(BaseAccessToAddressSerializer.Meta):
        model = AccessToPostAddress


class AddressSerializer(serializers.ModelSerializer):
    """Serializer for the Address model."""
    user = ReturnBazhayUserSerializer(read_only=True)

    class Meta:
        model = Address
        fields = ['id', 'country', 'region', 'city', 'street', 'post_index', 'full_name', 'phone_number', 'user']
        read_only_fields = ['id']

    def validate(self, data):
        request = self.context['request']

        if self.instance is None:
            if Address.objects.filter(user=request.user).exists():
                raise serializers.ValidationError(detail="A address for this user already exists.")

        return data


class PostAddressSerializer(serializers.ModelSerializer):
    """Serializer for the PostAddress model."""
    user = ReturnBazhayUserSerializer(read_only=True)

    class Meta:
        model = PostAddress
        fields = ['id', 'country', 'post_service', 'city', 'nearest_branch', 'full_name', 'phone_number', 'user']
        read_only_fields = ['id']

    def validate(self, data):
        request = self.context['request']

        if self.instance is None:
            if PostAddress.objects.filter(user=request.user).exists():
                raise serializers.ValidationError(detail="A post address for this user already exists.")

        return data


class AppleAuthSerializer(serializers.Serializer):
    """Serializer to auth with apple"""

    id_token = serializers.CharField()
    authorization_code = serializers.CharField(required=False)

    def validate(self, data):
        """
        Validate id token
        """
        id_token = data.get('id_token')

        apple_keys_url = 'https://appleid.apple.com/auth/keys'
        apple_keys = req.get(apple_keys_url).json()

        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.DecodeError:
            raise serializers.ValidationError(detail="Invalid token format")

        key = next((k for k in apple_keys['keys'] if k['kid'] == header['kid']), None)
        if key is None:
            raise serializers.ValidationError(detail="Invalid signature key")

        try:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
            decoded_token = jwt.decode(id_token, public_key, algorithms=['RS256'], audience="com.ivanfranco.BAZHAYRN")
        except jwt.ExpiredSignatureError:
            raise serializers.ValidationError(detail="The token has expired")
        except jwt.InvalidTokenError:
            raise serializers.ValidationError(detail="Invalid token")

        email = decoded_token.get('email', None)
        first_name = decoded_token.get('given_name', '')
        last_name = decoded_token.get('family_name', '')

        user = BazhayUser.objects.filter(email=email).first()

        if user is None:
            data['email'] = email
            data['first_name'] = first_name
            data['last_name'] = last_name
            data['username'] = email

        data['user'] = user
        return data

    def create(self, validated_data):
        user, created = BazhayUser.objects.get_or_create(
            email=validated_data.get('email', ''),
            defaults={
                'username': validated_data.get('email', ''),
                'first_name': validated_data.get('first_name', ''),
                'last_name': validated_data.get('last_name', ''),
            }
        )
        return user


class UserExponentPushTokenSerializer(serializers.ModelSerializer):
    """Exponent Push Token Serializer."""

    class Meta:
        model = UserExponentPushToken
        fields = ['token', 'language', 'imei']

    def create(self, validated_data: dict) -> UserExponentPushToken:
        """Create or update User Exponent Push Token."""
        imei = validated_data.get('imei')
        token = validated_data.get('token')
        language = validated_data.get('language')

        user = self.context.get('request').user

        instance, created = UserExponentPushToken.objects.update_or_create(
            imei=imei,
            defaults={'token': token, 'language': language, 'bazhay_user': user}
        )
        return instance
