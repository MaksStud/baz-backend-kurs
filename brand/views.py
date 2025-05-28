import logging

from django.core.cache import cache
from django.conf import settings

from typing import Optional
from rest_framework.request import Request
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework import status

from ability.serializers import WishSerializerForNotUser
from ability.views import SECONDS_IN_A_DAY

from .serializers import BrandSerializer, Brand

logger = logging.getLogger(__name__)


class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Brand.objects.all().order_by('priority')
    serializer_class = BrandSerializer
    lookup_field = 'slug'
    pagination_class = PageNumberPagination

    def list(self, request, *args, **kwargs):
        cache_brands_key = 'cache_brands'
        brands = cache.get(cache_brands_key)
        if brands:
            logger.info("Return cache brands.")
            return Response(brands)

        brands = super().list(request).data
        logger.info("Save brands to cache.")
        cache.set(cache_brands_key, brands, settings.CACHES_TIME)
        return Response(brands)

    @action(detail=True, methods=['get'], url_path='wish')
    def wishes(self, request: Request, slug: Optional[str] = None) -> Response:
        """Returns the paginated wish list of the original brand"""
        cache_key = f'wishes_to_{slug}_{request.query_params}'
        cached_page = cache.get(cache_key)

        if cached_page:
            return Response(cached_page, status=status.HTTP_200_OK)

        brand = self.get_object()
        wish = brand.wishes.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(wish, request)

        serializer = WishSerializerForNotUser(result_page, many=True)
        page = paginator.get_paginated_response(serializer.data)

        cache.set(cache_key, page.data, settings.CACHES_TIME)
        return page

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def view(self, request, slug=None):
        brand = self.get_object()

        cache_key = f"user:{request.user.id}:viewed_brand:{brand.slug}"

        if cache.get(cache_key):
            return Response(status=status.HTTP_200_OK)

        cache.set(cache_key, True, timeout=7 * SECONDS_IN_A_DAY)

        brand.views_number += 1
        brand.save()

        return Response(status=status.HTTP_200_OK)
