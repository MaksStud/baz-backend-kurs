from django.urls import path
from .views import app_redirect_view

urlpatterns = [
    path('redirect/<path:path>/', app_redirect_view, name='app_redirect'),
]