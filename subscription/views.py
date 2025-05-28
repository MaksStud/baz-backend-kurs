from rest_framework import generics
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework import filters

from .serializers import CreateOrDeleteSubscriptionSerializer, Subscription, SubscribersSerializer, SubscriptionsSerializer

from permission.permissions import IsRegisteredUser
from .pagination import SubscriptionPagination


class SubscribeView(generics.CreateAPIView):
    serializer_class = CreateOrDeleteSubscriptionSerializer
    permission_classes = [IsRegisteredUser]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SubscriptionListView(ReadOnlyModelViewSet):
    serializer_class = SubscriptionsSerializer
    permission_classes = [IsRegisteredUser]
    pagination_class = SubscriptionPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ['subscribed_to__username', 'subscribed_to__first_name', 'subscribed_to__last_name',
                     'subscribed_to__email']

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user)


class SubscribersListView(ReadOnlyModelViewSet):
    serializer_class = SubscribersSerializer
    permission_classes = [IsRegisteredUser]
    pagination_class = SubscriptionPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'user__email']

    def get_queryset(self):
        return Subscription.objects.filter(subscribed_to=self.request.user)


class UnsubscribeView(generics.GenericAPIView):
    serializer_class = CreateOrDeleteSubscriptionSerializer
    permission_classes = [IsRegisteredUser]

    def delete(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
