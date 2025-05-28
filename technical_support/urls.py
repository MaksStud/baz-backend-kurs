from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import TechnicalSupportChatViewSet, TechnicalSupportChatView

app_name = 'technical_support'

router = DefaultRouter()

router.register(r'chat', TechnicalSupportChatViewSet, basename='technical_support_chat')

urlpatterns = router.urls + [
    path('chat_in_admin/<int:pk>/', TechnicalSupportChatView.as_view(), name='technical_support_chat_in_admin'),
]
