import logging

from django.http import FileResponse
from django.shortcuts import render
from django.conf import settings

from rest_framework.response import Response
from rest_framework.generics import RetrieveAPIView
from .serializers import AppleRedirectSerializer, PlayStoreSerializer

logger = logging.getLogger(__name__)


class AppleRedirectAPIView(RetrieveAPIView):
    """Apple redirect APIView."""
    serializer_class = AppleRedirectSerializer

    def retrieve(self, request, *args, **kwargs):
        """Return data in json format."""
        return Response(self.serializer_class.get_data())


class PlayStoreAPIView(RetrieveAPIView):
    serializer_class = PlayStoreSerializer

    def retrieve(self, request, *args, **kwargs):
        """Return json."""
        return FileResponse(self.serializer_class().get_data(), content_type="application/json")


def app_redirect_view(request, path):
    return render(request, "deeplinks/app_redirect.html", {
        'path': path,
        'app_store_link': settings.APP_STORE_LINK,
        'play_store_link': settings.PLAY_STORE_LINK,
    })