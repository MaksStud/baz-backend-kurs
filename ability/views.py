import logging

import requests
import json
import boto3
import os
from urllib.parse import urlparse

from rest_framework import viewsets, permissions, mixins
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import Serializer
from rest_framework.request import Request
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.serializers import ValidationError

from django.core.cache import cache
from django.db.models.query import QuerySet
from django.db.models import Q, Count
from django_filters.rest_framework import DjangoFilterBackend
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
from django.db.models import Case, When, Value, IntegerField

from .models import Wish, Reservation, CandidatesForReservation, AccessToViewWish

from .serializers import (WishSerializer,
                          ReservationSerializer,
                          VideoTrimSerializer,
                          CombinedSearchSerializer,
                          QuerySerializer,
                          AccessToViewWishUser,
                          AccessToViewWishSerializer,
                          ParserSerializer)

from .filters import WishFilter, ReservationFilter, AccessToWishFilter
from .services import PopularRequestService, MediaConvertService
from .choices import access_type_choices

from subscription.models import Subscription
from user.models import BazhayUser
from brand.models import Brand
from permission.permissions import IsRegisteredUserOrReadOnly, IsRegisteredUser, IsPremium, IsOwner

SECONDS_IN_A_DAY = 86400

logger = logging.getLogger(__name__)


def can_view_ability(user, wish):
    """Checks access to the wish"""
    if wish.access_type == access_type_choices[0][0]:
        return True
    elif wish.access_type == access_type_choices[2][0] and wish.author == user:
        return True
    elif wish.access_type == access_type_choices[1][0]:
        return Subscription.objects.filter(user=user, subscribed_to=wish.author).exists() or wish.author == user
    elif wish.access_type == access_type_choices[3][0]:
        access_to_view_wish = getattr(wish, 'access_to_view_wish', None)
        if access_to_view_wish:
            return AccessToViewWishUser.objects.filter(user=user, access_to_view_wish=access_to_view_wish).exists() or wish.author == user
    return False


class WishViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing wishes.

    Provides actions to list, retrieve, create, update, and delete wishes. The view only shows wishes authored by
    the requesting user. It also includes permission checks for creating, updating, and retrieving wishes.

    Attributes:
        queryset (QuerySet): The queryset of `Wish` objects.
        serializer_class (Type[serializers.ModelSerializer]): The serializer used for wish data.
        permission_classes (List[Type[permissions.BasePermission]]): List of permission classes to enforce user authentication.
        filter_backends (Tuple[Type[DjangoFilterBackend]]): Backend filters to apply to the queryset.
        filterset_class (Type[filters.FilterSet]): The filter class to use for filtering the queryset.
        pagination_class (Type[pagination.PageNumberPagination]): The pagination class to use for paginating results.
    """
    queryset = Wish.objects.all()
    serializer_class = WishSerializer
    permission_classes = [IsRegisteredUserOrReadOnly]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = WishFilter
    pagination_class = PageNumberPagination

    def get_queryset(self) -> QuerySet[Wish]:
        """
        Forms a queryset to display user records in a specific order:
        1. First, "not executed".
        2. Then "reserved".
        3. At the end, "completed".
        Within each category, the sorting goes from new to old by date of creation.

        :return: queryset: Queryset[Wish]
        """
        user = self.request.user

        queryset = self.queryset.filter(author=user)

        queryset = queryset.annotate(
            is_reserved=Case(
                When(reservation__selected_user__isnull=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )

        queryset = queryset.order_by('is_fulfilled', '-is_reserved', '-created_at')

        return queryset

    def perform_create(self, serializer: Serializer):
        """
        Creates a new wish with the requesting user set as the author.

        Args:
            serializer (Serializer): The serializer instance used to validate and save the wish data.
        """
        serializer.save(author=self.request.user)

    def perform_update(self, serializer: Serializer):
        """
        Updates an existing wish. Checks if the user has permission to edit the wish.

        Args:
            serializer (Serializer): The serializer instance used to validate and save the updated wish data.

        Raises:
            PermissionDenied: If the user does not have permission to edit the wish.
        """
        ability = self.get_object()
        if not can_view_ability(self.request.user, ability):
            raise PermissionDenied("You do not have permission to edit this wish.")
        serializer.save()

    def create(self, request: Request, *args, **kwargs) -> Response:
        self._replace_photo(request)
        return super().create(request, *args, **kwargs)

    def update(self, request: Request, *args, **kwargs) -> Response:
        self._replace_photo(request)
        return super().update(request, *args, **kwargs)

    def _replace_photo(self, request: Request) -> None:
        """
        Replaces the link to the file that was downloaded in request.data.
        :param request: Request.
        """
        file_photo = request.FILES.get('photo')
        str_photo = request.data.get('photo')
        if file_photo is None and isinstance(str_photo, str):
            try:
                request.data._mutable = True
                request.data['photo'] = self._download_photo(str_photo)
                request.data._mutable = False
            except Exception as e:
                logger.warning(f"Failed to download photo from URL: {str_photo}. Error: {e}")
                request.data._mutable = True
                if 'photo' in request.data:
                    del request.data['photo']
                request.data._mutable = False

    def _download_photo(self, photo_url: str) -> ContentFile | None:
        """
        Returns the photo that was uploaded via the link.

        :param photo_url: Link to the photo.
        :return: ContentFile.
        """
        response = requests.get(photo_url, timeout=settings.DOWNLOAD_PHOTO_TIMEOUT)
        logger.info('Start download photo.')
        if response.status_code == 200:
            parsed_url = urlparse(photo_url)
            filename = os.path.basename(parsed_url.path)
            logger.info(f'Download successful. File name: {filename}.')
            return ContentFile(response.content, filename + timezone.now().strftime('%Y%m%d%H%M%S') + '.png')
        else:
            error_message = f'Failed to download image, status code: {response.status_code}.'
            logger.error(error_message)
            raise ValidationError(error_message)

    def retrieve(self, request: Request, *args, **kwargs):
        """
        Retrieves a wish by its ID. Checks if the requesting user has permission to view the wish.

        :param request: The HTTP request instance.

        :returns: The HTTP response containing the wish data.
        """
        instance = self.get_object()

        user = request.user
        if not can_view_ability(user, instance):
            return Response({'detail': 'You do not have permission to view this wish.'},
                            status=status.HTTP_403_FORBIDDEN)

        return super().retrieve(request, *args, **kwargs)


class AllWishViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving wishes with filtering and pagination.

    Provides read-only operations to list and retrieve wishes. The queryset is filtered based on access type and
    the user's subscription status. The view also supports pagination and filtering.

    """
    queryset = Wish.objects.all()
    serializer_class = WishSerializer
    permission_classes = [IsRegisteredUserOrReadOnly]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = WishFilter
    pagination_class = PageNumberPagination

    def get_queryset(self) -> QuerySet:
        """
        Returns the filtered and paginated QuerySet of wishes.
        :returns (QuerySet): A filtered and paginated QuerySet of `Wish` objects.
        """
        user = self.request.user

        queryset = self.queryset.filter(
            Q(author=user) |
            Q(access_type='everyone') |
            Q(access_type='only_me', author=user) |
            Q(access_type='subscribers',
              author__in=Subscription.objects.filter(user=user).values_list('subscribed_to', flat=True)) |
            Q(access_to_view_wish__access_users__user=user)
        ).distinct()
        return queryset

    def list(self, request, *args, **kwargs):
        user = self.request.user
        is_new_system = request.query_params.get('is_new_recommendation_system', False)

        queryset = self.get_filtered_queryset(user)

        subscribed_authors = Subscription.objects.filter(user=user).values_list('subscribed_to', flat=True)

        queryset = queryset.annotate(
            is_followed_author=Case(
                When(author__in=subscribed_authors, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).order_by(
            '-is_followed_author',
            '-created_at',
            '-views_number'
        )

        if not is_new_system:
            self.queryset = queryset
            return super().list(request, *args, **kwargs)

        cache_key = f"user_{user.id}_viewed_wishes"
        viewed_wish_ids = cache.get(cache_key, [])

        new_wishes, viewed_wishes = self.split_wishes(queryset, viewed_wish_ids)
        full_queryset = list(new_wishes) + list(viewed_wishes)

        page = self.paginate_queryset(full_queryset)

        new_viewed_ids = self.get_new_viewed_ids(page, new_wishes)
        updated_viewed_wish_ids = list(set(viewed_wish_ids + new_viewed_ids))
        cache.set(cache_key, updated_viewed_wish_ids, timeout=60 * 60 * 24 * 7)

        self.clear_cache_if_needed(cache_key, queryset)

        return self.get_response(page, full_queryset)

    def get_filtered_queryset(self, user):
        """
        Removes unnecessary items from the queryset for the list method.

        :param user: User.

        :return: Queryset.
        """
        return self.get_queryset().exclude(
            Q(author=user) | Q(is_validation=False) | Q(is_fully_created=False)
        )

    def split_wishes(self, queryset, viewed_wish_ids):
        """
        Splits the queryset into two parts: new wishes (not yet viewed) and viewed wishes.
        This method separates wishes into two categories:
        1. Wishes that the user has not viewed (new wishes).
        2. Wishes that the user has already viewed (viewed wishes).

        :param queryset: The full list of wishes to be filtered.
        :param viewed_wish_ids: A list of wish IDs that the user has already viewed.

        :return: A tuple containing two querysets:
            - `new_wishes`: Wishes that the user has not viewed.
            - `viewed_wishes`: Wishes that the user has already viewed.
        """
        new_wishes = queryset.exclude(id__in=viewed_wish_ids)
        viewed_wishes = queryset.filter(id__in=viewed_wish_ids)
        return new_wishes, viewed_wishes

    def get_new_viewed_ids(self, page, new_wishes):
        """
        Extracts the IDs of the wishes from the current page or the new wishes.
        If the request is paginated, it returns the IDs of the wishes on the current page;
        otherwise, it returns the IDs of all the new wishes.

        :param page: The paginated page of wishes.
        :param new_wishes: The queryset of new wishes (not yet viewed).

        :return: A list of IDs of the wishes to update in the cache.
        """
        if page is not None:
            return [wish.id for wish in page]
        return [wish.id for wish in new_wishes]

    def clear_cache_if_needed(self, cache_key, queryset):
        """
        Clears the cache if all wishes in the queryset have been viewed.
        If the number of viewed wishes in the cache is equal to or greater than the total
        number of wishes in the queryset, the cache is deleted to prevent unnecessary data storage.

        :param cache_key: The key used to identify the cached data.
        :param queryset: The full queryset of wishes.
        """
        if len(cache.get(cache_key)) >= queryset.count():
            cache.delete(cache_key)

    def get_response(self, page, full_queryset):
        """
        Returns a response with the serialized data of the wishes.

        If the request is paginated, it returns the paginated response; otherwise, it returns
        a response with the full list of wishes.

        :param page: The paginated page of wishes.
        :param full_queryset: The full list of wishes (with new and viewed wishes combined).

        :return: A paginated or full response with the serialized data.
        """
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(full_queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.author == request.user:
            return super().retrieve(request, *args, **kwargs)

        if not instance.is_validation:
            raise PermissionDenied(detail="This wish is not available.")

        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def view(self, request, pk=None):
        wish = self.get_object()

        if wish.author == request.user:
            return Response({'message': 'You cannot view your own wish.'}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"user:{request.user.id}:viewed_wish:{wish.id}"

        if cache.get(cache_key):
            return Response(status=status.HTTP_200_OK)

        cache.set(cache_key, True, timeout=7 * SECONDS_IN_A_DAY)

        wish.views_number += 1
        wish.save()

        return Response(status=status.HTTP_200_OK)

      
class VideoViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):

    queryset = Wish.objects.all()
    serializer_class = VideoTrimSerializer
    permission_classes = [permissions.IsAuthenticated]


class SearchView(viewsets.GenericViewSet, mixins.ListModelMixin):
    """
    View for searching across BazhayUser, Wish, and Brand models.
    """
    serializer_class = CombinedSearchSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = PageNumberPagination
    service = PopularRequestService()

    def list(self, request: Request, *args, **kwargs) -> Response:
        """
        Handle GET requests to search across users and wishes

        :param request: DRF request object containing search query.
        :return: Response with serialized search results or an error message if no query is provided.
        """
        query = request.query_params.get('query', None)

        if query:
            querysets = self.get_queryset(query)
            self.service.set(query)

            self.__delete_not_using_fields(request, querysets)

            active_fields = len(querysets)

            if active_fields == 3:
                self.__querysets_trim(querysets, 5)
            elif active_fields == 2:
                self.__querysets_trim(querysets, 8)
            elif active_fields == 1:
                return self.__pagination_one_field(request, querysets)

            serializer = self.get_serializer(querysets, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response({"detail": "No query provided."}, status=status.HTTP_400_BAD_REQUEST)

    def get_queryset(self, query: str) -> dict:
        """
        Retrieve querysets based on the search query from the BazhayUser, Wish and Brand models.

        :param query: The search term.

        :return: A dictionary containing querysets for both users and wishes filtered by the search term.
        """
        return {
            'users': self.__get_bazhay_user_results(query),
            'wishes': self.__get_wish_results(query),
            'brands': self.__get_brand_results(query),
        }

    def __querysets_trim(self, queryset: dict, size: int) -> None:
        """
        Trims the query to the required length in each key-value pair.

        :param queryset (dict): Dictionary where the key is a string and the value is a list.
        :param size (int): The size to which you want to trim.
        :return: None.
        """
        for key in queryset.keys():
            queryset[key] = queryset[key][:size]

    def __get_bazhay_user_results(self, query: str | None) -> tuple[BazhayUser]:
        """
        Returns a tuple of users.

        :param query (str): Search query.
        :return: The tuple BazhayUser.
        """
        logger.info("Search for users.")
        return BazhayUser.objects.filter(
            Q(email__icontains=query) |
            Q(username__icontains=query) |
            Q(last_name__icontains=query) |
            Q(first_name__icontains=query) |
            Q(about_user__icontains=query)
        ).exclude(Q(email=self.request.user.email) |
                  Q(is_superuser=True)
                  ).annotate(subscriber_count=Count('subscribers')).order_by('-subscriber_count')

    def __get_wish_results(self, query: str | None) -> tuple[Wish]:
        """
        Returns a tuple of wishes.

        :param query (str): Search query.
        :return: The tuple Wish.
        """
        logger.info("Search for wishes.")
        return Wish.objects.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(additional_description__icontains=query)
            | Q(author__username__icontains=query)
            | Q(brand_author__name__icontains=query)
            | Q(brand_author__nickname__icontains=query)
            | Q(news_author__title__icontains=query)
            | Q(news_author__description__icontains=query)
        ).exclude(is_fully_created=False).order_by('-views_number')

    def __get_brand_results(self, query: str | None) -> tuple[Brand]:
        """
        Returns a tuple of brands.

        :param query (str): Search query.
        :return: The tuple Brand.
        """
        logger.info("Search for brands.")
        return Brand.objects.filter(Q(name__icontains=query)
                  | Q(name__icontains=query)
                  | Q(nickname__icontains=query)
                  | Q(description__icontains=query)).order_by('-views_number')

    def __delete_not_using_fields(self, request: Request, queryset: dict) -> None:
        """
        Removes unnecessary fields from queryset. Changes the one that was transmitted.

        :param request (Request): For information about the required fields.
        :param queryset (Queryset): Queryset that will be changed in the workflow.
        :return: None.
        """
        users = request.query_params.get('users', 'true').lower() == 'false'
        wishes = request.query_params.get('wishes', 'true').lower() == 'false'
        brands = request.query_params.get('brands', 'true').lower() == 'false'

        if users:
            del queryset['users']
        if wishes:
            del queryset['wishes']
        if brands:
            del queryset['brands']

    def __pagination_one_field(self, request: Request, queryset: dict) -> Response:
        """
        Returns the paginated page.

        :param request (Request): Transferred to the serializer.
        :paraam queryset (dict): data to be paginated.

        :return: paginated Response
        """
        key = next(iter(queryset))
        paginated_queryset = self.paginate_queryset(queryset[key])

        if paginated_queryset is not None:
            serializer = self.get_serializer({key: paginated_queryset}, context={'request': request})
            return self.get_paginated_response(serializer.data)


class QueryView(viewsets.mixins.CreateModelMixin, viewsets.mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Add and return popular queries.
    """

    serializer_class = QuerySerializer
    service = PopularRequestService()

    def get_queryset(self):
        """
        Returns a list of queries matching the input parameter.

        :return: List of dictionaries containing 'query' and 'count' keys.
        """
        query = self.request.query_params.get('query', None)
        results = self.service.get(query)

        return [{'query': result['query'], 'count': result['count']} for result in results]

    def create(self, request):
        """
        Saves a new query to the service.

        :param request (Request): Request object with query data.
        :return: Response indicating the result of the operation.
        """
        query = request.data.get('query')
        if not query:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        self.service.set(query)
        return Response({'message': 'Query saved successfully'}, status=status.HTTP_201_CREATED)


class AccessToViewWishViewSet(viewsets.ModelViewSet):
    """
    A viewset for managing access to wishes.
    """
    queryset = AccessToViewWish.objects.all()
    serializer_class = AccessToViewWishSerializer
    permission_classes = [permissions.IsAuthenticated, IsPremium]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = AccessToWishFilter

    def get_queryset(self):
        return self.queryset.filter(wish__author=self.request.user)

      
class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated, IsRegisteredUser]
    filter_backends = (DjangoFilterBackend, )
    filterset_class = ReservationFilter

    def get_queryset(self):
        return self.queryset.filter(wish__author=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        if not request.user.is_premium():
            raise PermissionDenied('Access restricted to premium users only.')

        return super().retrieve(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        if not request.user.is_premium():
            raise PermissionDenied('Access restricted to premium users only.')

        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsRegisteredUser, IsPremium])
    def select_user(self, request, pk=None):
        reservation = self.get_object()

        candidate_id = request.data.get('candidate_id')
        try:
            candidate = CandidatesForReservation.objects.get(bazhay_user=candidate_id, reservation=reservation)
        except CandidatesForReservation.DoesNotExist:
            return Response({'detail': 'Candidate not found.'}, status=status.HTTP_404_NOT_FOUND)

        reservation.selected_user = candidate.bazhay_user
        reservation.save()

        return Response({'detail': 'Candidate selected successfully.'}, status=status.HTTP_200_OK)


class MediaConvertWebhookView(APIView):

    def post(self, request):
        body = json.loads(request.body.decode('utf-8'))
        message_type = body.get("Type")

        if message_type == "SubscriptionConfirmation":
            return self.subscription_confirmation(body)

        if message_type == 'Notification':
            job = json.loads(body.get('Message'))
            media_convert_service = MediaConvertService()

            if job["detail"]["status"] == 'COMPLETE':
                self.save_trime_video(job, media_convert_service)
            else:
                raise ValidationError(detail="Error processing video")
            return Response({"message": body})

    def delete_old_s3_file(self, instance):
        """Deletes an old file from s3."""
        if instance.video:
            s3 = boto3.client('s3')
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            old_file_key = instance.video.name
            s3.delete_object(Bucket=bucket_name, Key=old_file_key)

    def subscription_confirmation(self, body: dict) -> Response:
        """
        Configures the endpoint for AWS.
        :param body: Dict by aws.
        """
        subscribe_url = body.get("SubscribeURL")
        try:
            response = requests.get(subscribe_url)
            response.raise_for_status()
            return Response({"message": "Subscription confirmed"})
        except requests.RequestException as e:
            raise ValidationError(detail="Error confirming your subscription")

    def save_trime_video(self, job_data: dict, media_convert_service: MediaConvertService):
        """
        Added trim to the wish.
        :param job_data: Data about Job AWS Media Convertor.
        :param media_convert_service: MediaConvertService element.
        """
        job_id = job_data["detail"].get('jobId')
        logger.info(f'{job_id}')
        file_name, output_s3_key = media_convert_service.get_output_url(job_id)

        wish_id = cache.get(str(job_id))

        try:
            wish = Wish.objects.get(pk=wish_id)
        except Exception as e:
            ValidationError(detail=f'Error: {wish}')

        self.delete_old_s3_file(wish)

        s3 = boto3.client('s3')
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME

        file_obj = s3.get_object(Bucket=bucket_name, Key=output_s3_key)
        file_content = file_obj['Body'].read()

        wish.video.save(file_name, ContentFile(file_content))
        wish.is_validation = True
        wish.save()


class ParserViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
    """VewSet for parser service."""
    serializer_class = ParserSerializer
    permission_classes = [permissions.IsAuthenticated, IsRegisteredUser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        serializer_info = serializer.data
        parser_data = serializer_info.get('data')

        data = {
            'name': parser_data.get('name'),
            'price': parser_data.get('price'),
            'description': parser_data.get('description'),
            'photo': parser_data.get('photo_link'),
            'currency': parser_data.get('currency'),
            'link': serializer_info.get('url')
        }

        return Response(data, status=status.HTTP_200_OK, headers=headers)
