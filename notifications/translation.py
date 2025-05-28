from modeltranslation.translator import translator, TranslationOptions
from .models import Notification, CongratulatoryNotification


class NotificationTranslationOptions(TranslationOptions):
    """Notification Translation"""
    fields = ('message',)


class CongratulatoryNotificationTranslationOptions(TranslationOptions):
    """Congratulatory Notification Translation"""
    fields = ('message',)


translator.register(Notification, NotificationTranslationOptions)
translator.register(CongratulatoryNotification, CongratulatoryNotificationTranslationOptions)

