from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from .views import (AuthViewSet,
                    UpdateUserViewSet,
                    UpdateUserEmailViewSet,
                    GuestUserViewSet,
                    UpdateUserPhotoViewSet,
                    GoogleLoginView,
                    ListUserViewSet,
                    AddressViewSet,
                    PostAddressViewSet,
                    CreateAccessRequestViewSet,
                    GetAccessRequestViewSet,
                    CreatePostAddressAccessRequestViewSet,
                    GetPostAddressAccessRequestViewSet,
                    AppleLoginView,
                    UserExponentPushTokenViewSet)

router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'auth/guest', GuestUserViewSet, basename='auth_guest')
router.register(r'user/update-email', UpdateUserEmailViewSet, basename='update_email')
router.register(r'users', ListUserViewSet, basename='users_list')
router.register(r'user/address', AddressViewSet, basename='users_address')
router.register(r'user/post-address', PostAddressViewSet, basename='users_post_address')
router.register(r'create-access-address', CreateAccessRequestViewSet, basename='create-access-request')
router.register(r'get-access-address', GetAccessRequestViewSet, basename='get-access-request')
router.register(r'create-access-post-address', CreatePostAddressAccessRequestViewSet, basename='create-access-post-address')
router.register(r'get-access-post-address', GetPostAddressAccessRequestViewSet, basename='get-access-post-address')
router.register(r'push-token', UserExponentPushTokenViewSet, basename='push-token')

urlpatterns = router.urls + [
    path('user/', UpdateUserViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', TokenBlacklistView.as_view(), name='logout'),
    path('user/photo/', UpdateUserPhotoViewSet.as_view({'put': 'update'})),
    path('auth/google/', GoogleLoginView.as_view({"post": "create"}), name='google_auth'),
    path('auth/apple/', AppleLoginView.as_view(), name='apple-login'),
]
