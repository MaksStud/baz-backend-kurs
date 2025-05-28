from rest_framework.routers import DefaultRouter

from .views import AppleValidationViewSet, GoogleValidationViewSet

router = DefaultRouter()
router.register('apple-validation', AppleValidationViewSet, basename='apple_validation')
router.register('google-validation', GoogleValidationViewSet, basename='google_validation')

urlpatterns = router.urls
