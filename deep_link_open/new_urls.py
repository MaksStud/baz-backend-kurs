from django.urls import path
from .views import AppleRedirectAPIView, PlayStoreAPIView


urlpatterns = [
    path('apple-app-site-association', AppleRedirectAPIView.as_view(), name='apple_app_redirect'),
    path('assetlinks.json', PlayStoreAPIView.as_view(), name='play_store_app_redirect')
]
