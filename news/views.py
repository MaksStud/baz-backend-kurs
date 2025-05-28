from typing import Optional

from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.conf import settings

from rest_framework.request import Request
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework import status

from ability.serializers import WishSerializerForNotUser

from .serializers import NewsSerializers, News


class NewsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = News.objects.all().order_by('-priority')
    serializer_class = NewsSerializers
    lookup_field = 'slug'
    pagination_class = PageNumberPagination

    @method_decorator(cache_page(settings.CACHES_TIME))
    def list(self, request, *args, **kwargs):
        return super().list(request)

    @action(detail=True, methods=['get'], url_path='wish')
    def wishes(self, request: Request, slug: Optional[str] = None) -> Response:
        """Returns the paginated wish list of the original brand"""
        cache_key = f'wishes_to_{slug}_{request.query_params}'
        cached_page = cache.get(cache_key)

        if cached_page:
            return Response(cached_page, status=status.HTTP_200_OK)

        news = self.get_object()
        wish = news.wishes.all()
        paginator = PageNumberPagination()
        result_page = paginator.paginate_queryset(wish, request)

        serializer = WishSerializerForNotUser(result_page, many=True)
        page = paginator.get_paginated_response(serializer.data)

        cache.set(cache_key, page.data, settings.CACHES_TIME)
        return page