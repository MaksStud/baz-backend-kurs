from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (WishViewSet,
                    AllWishViewSet,
                    ReservationViewSet,
                    VideoViewSet,
                    SearchView,
                    QueryView,
                    AccessToViewWishViewSet,
                    MediaConvertWebhookView,
                    ParserViewSet)

router = DefaultRouter()
router.register(r'wishes', WishViewSet, basename='wish')
router.register(r'all-wishes', AllWishViewSet, basename='all_wish')
router.register(r'reservation', ReservationViewSet, basename='reservation')
router.register(r'video', VideoViewSet, basename='video')
router.register(r'search', SearchView, basename='search')
router.register(r'query', QueryView, basename='query')
router.register('access-to-wish', AccessToViewWishViewSet, basename='access-to-wish')
router.register('parser', ParserViewSet, basename='parser')

urlpatterns = router.urls + [
    path('media-convert-webhook/', MediaConvertWebhookView.as_view(), name='media_convert_webhook'),
]
