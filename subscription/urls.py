from django.urls import path
from .views import (SubscribeView,
                    UnsubscribeView,
                    SubscriptionListView,
                    SubscribersListView)

urlpatterns = [
    path('subscribe/', SubscribeView.as_view(), name='subscribe'),
    path('unsubscribe/', UnsubscribeView.as_view(), name='unsubscribe'),

    path('subscriptions/', SubscriptionListView.as_view({'get': 'list'}), name='subscriptions'),
    path('subscribers/', SubscribersListView.as_view({'get': 'list'}), name='subscribers'),
]
