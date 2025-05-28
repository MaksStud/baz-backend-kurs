import logging
import re
import datetime
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache

from rest_framework import serializers
from rest_framework.serializers import ValidationError

from .models import Wish, Reservation, CandidatesForReservation, AccessToViewWish, AccessToViewWishUser
from .tasks import validate_photo_task, validate_video_task
from .services import MediaConvertService
from .parser.services import OpenAiSiteParser, AbstractSiteParser, parsers
from .choices import access_type_choices

from user.serializers import ReturnBazhayUserSerializer, BazhayUser
from brand.serializers import BrandSerializer
from news.serializers import NewsSerializers

logger = logging.getLogger(__name__)


class WishSerializer(serializers.ModelSerializer):
    """
    Serializer for Wish model.

    Handles the serialization and validation of Wish instances, including
    fields for various attributes, user-related fields, and custom validation
    based on the user's subscription status.
    """
    photo = serializers.ImageField(required=False)
    video = serializers.FileField(required=False, allow_null=True)
    author = ReturnBazhayUserSerializer(read_only=True)
    brand_author = BrandSerializer(read_only=True)
    news_author = NewsSerializers(read_only=True)
    is_reservation = serializers.SerializerMethodField()
    is_user_create = serializers.SerializerMethodField()
    is_your_wish = serializers.SerializerMethodField()
    is_reserved_by_me = serializers.SerializerMethodField()
    is_me_candidates_to_reservation = serializers.SerializerMethodField()

    class Meta:
        model = Wish
        fields = ['id', 'name', 'name_en', 'name_uk', 'photo', 'video', 'price', 'link', 'description',
                  'description_en', 'description_uk',
                  'additional_description', 'additional_description_en', 'additional_description_uk', 'access_type',
                  'currency', 'created_at', 'is_fully_created', 'is_reservation', 'is_user_create', 'is_your_wish',
                  'is_reserved_by_me', 'is_fulfilled',
                  'is_me_candidates_to_reservation', 'image_size', 'author', 'brand_author',
                  'news_author', 'is_validation', 'is_copied_from_brand']
        read_only_fields = ['id', 'author', 'created_at', 'brand_author', 'news_author']

    def validate(self, data: dict) -> dict:
        """
        Validate wish data.

        Ensures users adhere to limits on the number of fully created wishes,
        and restricts certain actions based on subscription status.
        """
        user = self.context['request'].user
        is_premium = hasattr(user, 'premium') and user.premium.is_active
        max_wishes = settings.WISH_WITHOUT_PREMIUM

        if not is_premium:
            # Check when creating a new wish
            if self.instance is None and Wish.objects.filter(author=user, is_fully_created=True).count() >= max_wishes:
                raise ValidationError(
                    f"You cannot create more than {max_wishes} fully created wishes without a premium subscription.")

            # Check for change is_fully_created
            self.check_for_change_fully_created(data, max_wishes, user)

            # Restrictions on changing the access type
            if 'access_type' in data and data.get('access_type') in [access_type_choices[0][0],
                                                                     access_type_choices[3][0]]:
                raise ValidationError(
                    "You cannot change the access type to a non-default value without a premium subscription.")

        return data

    def check_for_change_fully_created(self, data: dict, max_wishes: int, user: BazhayUser):
        """Checks whether the limit is exceeded when changing the is_fully_created field."""
        if self.instance and 'is_fully_created' in data:
            if data['is_fully_created'] and not self.instance.is_fully_created:
                current_fully_created_count = Wish.objects.filter(author=user, is_fully_created=True).count()
                if current_fully_created_count >= max_wishes:
                    raise ValidationError(
                        f"You cannot mark more than {max_wishes} wishes as fully created without a premium subscription.")

    def check_valid(self, wish: Wish, validated_data: dict):
        """If the file is present, starts validation in the background."""
        if 'video' in validated_data and validated_data.get('video') is not None:
            validate_video_task.delay(wish.id)
            wish.is_validation = False
        else:
            wish.is_validation = True

        if 'photo' in validated_data and validated_data.get('photo') is not None:
            validate_photo_task.delay(wish.id)
            wish.is_validation = False
        else:
            wish.is_validation = True

        wish.save()
        return wish

    def create(self, validated_data):
        """Creating an object."""
        wish = super().create(validated_data)
        return self.check_valid(wish, validated_data)

    def update(self, instance, validated_data: dict):
        """Updating an object."""
        video = validated_data.get('video', None)

        if video is None and 'video' in validated_data:
            instance.video = None
            instance.save()

        instance = super().update(instance, validated_data)
        return self.check_valid(instance, validated_data)

    def get_is_reservation(self, obj: Wish) -> bool:
        """
        Determine if the wish is reserved.

        :args obj (Wish): The wish instance.
        :returns (bool): True if the wish is reserved, otherwise False.
        """
        reservation = Reservation.objects.filter(wish=obj).first()
        if reservation and reservation.selected_user:
            return True
        return False

    def get_is_reserved_by_me(self, obj):
        """
        Check if the current user has reserved the wish.

        :args obj (Wish): The wish instance.
        :returns bool: True if the current user has reserved the wish, otherwise False.
        """
        reservation = Reservation.objects.filter(wish=obj).first()
        if reservation is None:
            return False

        return reservation.selected_user == self.context['request'].user

    def get_is_me_candidates_to_reservation(self, obj):
        reservation = Reservation.objects.filter(wish=obj).first()
        if reservation is None:
            return False

        candidate = CandidatesForReservation.objects.filter(reservation=reservation,
                                                            bazhay_user=self.context['request'].user).first()

        return True if candidate is not None else False

    def get_is_user_create(self, obj: Wish) -> bool:
        """
        Determine if the wish was created by the user.

        Args:
            obj (Wish): The wish instance.

        Returns:
            bool: True if the wish was created by the user, otherwise False.
        """
        return True if obj.author else False

    def get_is_your_wish(self, obj: Wish) -> bool:
        """
        Determine if the wish belongs to the requesting user.

        Args:
            obj (Wish): The wish instance.

        Returns:
            bool: True if the wish belongs to the requesting user, otherwise False.
        """
        return obj.author == self.context['request'].user


class VideoTrimSerializer(serializers.ModelSerializer):
    wish = WishSerializer(read_only=True)
    video = serializers.FileField(write_only=True)
    start = serializers.IntegerField(write_only=True, required=True)
    end = serializers.IntegerField(write_only=True, required=True)

    class Meta:
        model = Wish
        fields = ['id', 'video', 'start', 'end', 'wish']

    def validate(self, attrs):
        end = attrs.get('end', None)
        start = attrs.get('start', None)
        video = attrs.get('video', None)

        if video is None:
            raise serializers.ValidationError("Video is required.")

        if end is None or start is None or end <= start:
            raise serializers.ValidationError("The time frame is not correct.")

        user = self.context['request'].user

        if self.instance and self.instance.author != user:
            raise serializers.ValidationError("You do not have permission to modify this wish.")

        return attrs

    def update(self, instance, validated_data: dict) -> Wish:
        """Update video in wish."""
        video = validated_data.get('video')
        start = validated_data.get('start')
        end = validated_data.get('end')

        video_url = f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/ability_media/{video.name}"
        instance.video.save(video.name, video)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file_name = f"video_{timestamp}_{instance.author.username}_trim"

        media_convert_service = MediaConvertService()
        job_id = media_convert_service.create_job(video_url, start, end, output_file_name)
        instance.is_validation = False
        instance.save()

        cache.set(str(job_id), instance.id)
        return instance


class WishSerializerForNotUser(serializers.ModelSerializer):
    """
    Serializer for the Wish model to handle serialization and deserialization of wish objects.

    This serializer is used to convert Wish model instances into JSON format and vice versa.
    It includes the fields that are relevant for views where the user is not authenticated or does not
    need to see or modify all the fields.
    """
    class Meta:
        model = Wish
        fields = ['id', 'name', 'name_en', 'name_uk', 'photo', 'video', 'price', 'link', 'description', 'description_en', 'description_uk',
                  'additional_description', 'additional_description_en', 'additional_description_uk', 'currency',
                  'created_at', 'image_size']


class CombinedSearchSerializer(serializers.Serializer):
    """
    Serializer to combine results from Wish, BazhayUser and Brand models.
    """
    wishes = WishSerializer(many=True, read_only=True)
    users = ReturnBazhayUserSerializer(many=True, read_only=True)
    brands = BrandSerializer(many=True, read_only=True)

    class Meta:
        fields = ['wishes', 'users', 'brands']


class QuerySerializer(serializers.Serializer):
    """Serializer to query."""
    query = serializers.CharField(max_length=255, required=False)
    count = serializers.IntegerField(read_only=True)


class AccessToViewWishUserSerializer(serializers.ModelSerializer):
    user = ReturnBazhayUserSerializer(read_only=True)

    class Meta:
        model = AccessToViewWishUser
        fields = ['id', 'user']


class AccessToViewWishSerializer(serializers.ModelSerializer):
    users = AccessToViewWishUserSerializer(many=True, read_only=True, source='access_users')
    user_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True
    )
    wish_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = AccessToViewWish
        fields = ['id', 'wish', 'users', 'user_ids', 'wish_id']
        read_only_fields = ['wish']

    def validate(self, attrs):
        """Custom validation for the user_ids and wish_id."""
        if self.instance is None:
            wish_id = attrs.get('wish_id')
            if wish_id is not None:
                try:
                    Wish.objects.get(id=wish_id)
                except Wish.DoesNotExist:
                    raise serializers.ValidationError(detail=f"The wish with id {wish_id} does not exist.")

        user_ids = attrs.get('user_ids', [])
        users = BazhayUser.objects.filter(id__in=user_ids)
        if users.count() != len(user_ids):
            raise serializers.ValidationError(detail="Some of the users do not exist.")

        return attrs

    def create(self, validated_data: dict) -> AccessToViewWish:
        users_ids = validated_data.pop('user_ids')
        wish_id = validated_data.pop('wish_id')

        wish = Wish.objects.get(id=wish_id)

        access_to_view_wish = AccessToViewWish.objects.create(wish=wish)

        for user_id in users_ids:
            user = BazhayUser.objects.get(id=user_id)
            AccessToViewWishUser.objects.create(user=user, access_to_view_wish=access_to_view_wish)

        AccessToViewWishUser.objects.create(user=self.context['request'].user, access_to_view_wish=access_to_view_wish)

        return access_to_view_wish

    def update(self, instance, validated_data):
        user_ids = validated_data.pop('user_ids', [])

        instance.access_users.all().delete()

        for user_id in user_ids:
            user = BazhayUser.objects.get(id=user_id)
            AccessToViewWishUser.objects.create(user=user, access_to_view_wish=instance)

        AccessToViewWishUser.objects.create(user=self.context['request'].user, access_to_view_wish=instance)

        instance.save()
        return instance

    def to_representation(self, instance):
        """Remove the current user from the users list in the response."""
        representation = super().to_representation(instance)
        current_user_id = instance.wish.author.id
        return_user_list = []

        for value in representation['users']:
            if value['user']['id'] != current_user_id:
                return_user_list.append(value)

        representation['users'] = return_user_list
        return representation

    
class CandidatesForReservationSerializer(serializers.ModelSerializer):
    bazhay_user = ReturnBazhayUserSerializer(read_only=True)

    class Meta:
        model = CandidatesForReservation
        fields = ['bazhay_user']


class ReservationSerializer(serializers.ModelSerializer):
    candidates = CandidatesForReservationSerializer(many=True, read_only=True)
    selected_user = ReturnBazhayUserSerializer(read_only=True)

    class Meta:
        model = Reservation
        fields = ['id', 'wish', 'selected_user', 'candidates']
        read_only_fields = ['selected_user']

    def validate(self, data):
        wish = data.get('wish')
        user = self.context['request'].user

        if Reservation.objects.filter(wish=wish).exists():
            reservation = Reservation.objects.get(wish=wish)
            if not reservation.is_active:
                raise serializers.ValidationError(detail="It's already reserved for someone.")
            if CandidatesForReservation.objects.filter(reservation=reservation, bazhay_user=user).exists():
                raise serializers.ValidationError(detail="The user is already a candidate for this reservation.")

        if wish.author == user:
            raise serializers.ValidationError(detail="You cannot reserve your own wish.")

        return data

    def create(self, validated_data):
        wish = validated_data.get('wish')
        user = self.context['request'].user

        reservation, created = Reservation.objects.get_or_create(wish=wish)

        if wish.author.is_premium():
            CandidatesForReservation.objects.create(
                reservation=reservation,
                bazhay_user=user
            )
        else:
            if created:
                reservation.selected_user = user

        reservation.save()
        return reservation


class ParserSerializer(serializers.Serializer):
    """Serializer for parsers service"""
    url = serializers.URLField(max_length=100_000)
    data = serializers.DictField(read_only=True)

    def create(self, validated_data):
        url = validated_data.get('url')
        parser = self.__get_parser(url)
        result = parser.get_product(url)
        return {'url': validated_data.get('url'), 'data': result}

    def __get_parser(self, url: str) -> AbstractSiteParser:
        """
        Return parser service.
        :param url: URL of the page to be parsered.
        :return: Parser service.
        """
        domain_name = self.get_domain_name(url)
        logger.info(f'Domain name {domain_name}')
        return parsers.get(domain_name, OpenAiSiteParser)()

    def get_domain_name(self, url):
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lstrip('www.')

        match = re.match(r'^([a-zA-Z0-9-]+)\.', domain)
        if match:
            return match.group(1)
        return None
