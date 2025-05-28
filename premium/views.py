from django.conf import settings
from django.core.cache import cache

from rest_framework import viewsets, mixins, status
from rest_framework.response import Response

from .serializers import GoogleValidateSerializer, AppleValidateSerializer
from .models import Premium

from permission.permissions import IsRegisteredUser


class BaseValidationViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """A basic viewset for creating and retrieving premium data."""
    permission_classes = [IsRegisteredUser]

    def get_queryset(self):
        return Premium.objects.filter(bazhay_user=self.request.user)

    def list(self, request, *args, **kwargs):
        key = f'premium_to_{request.user.id}'
        value = cache.get(key)
        if value:
            return Response(value, status=status.HTTP_200_OK)

        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        cache.set(key, serializer.data, settings.CACHES_TIME)
        return Response(serializer.data)


class AppleValidationViewSet(BaseValidationViewSet):
    """Viewset for creating and retrieving premium data with Apple."""
    serializer_class = AppleValidateSerializer


class GoogleValidationViewSet(BaseValidationViewSet):
    """Viewset for creating and retrieving premium data with Google."""
    serializer_class = GoogleValidateSerializer



