from django.db.models import Q
from django.utils import timezone

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from permission.permissions import IsRegisteredUser

from .models import CongratulatoryNotification, Notification
from .serializers import NotificationSerializers, CongratulatoryNotificationSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsRegisteredUser]

    def get_serializer_class(self):
        """
        Returns the appropriate serializer depending on the request type.
        """
        if self.action == 'list' and self.request.query_params.get('type') == 'congratulatory':
            return CongratulatoryNotificationSerializer
        return NotificationSerializers

    def get_queryset(self):
        """
        Combines the queryset for two models but allows full CRUD only for Notification.
        """
        user = self.request.user

        notifications = Notification.objects.filter(
            Q(users=user),
            send_at__lte=timezone.now(),
            send_at__gte=user.date_joined
        )

        if self.action == 'list':
            congratulatory_notifications = CongratulatoryNotification.objects.filter(
                send_at__lte=timezone.now(),
                send_at__gte=user.date_joined
            )
            combined_queryset = list(notifications) + list(congratulatory_notifications)
            return sorted(combined_queryset, key=lambda obj: obj.send_at)

        return notifications


